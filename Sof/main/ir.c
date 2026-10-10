#include <stddef.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/hw_timer.h"
#include "driver/i2s.h"
#include "driver/soc.h"
#include "esp8266/gpio_struct.h"
#include "esp8266/i2s_struct.h"
#include "esp8266/timer_struct.h"
#include "esp8266/pin_mux_register.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "rom/uart.h"
#include "nvs.h"
#include "app.h"
#include "ir.h"
#include "portal.h"

#if CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ != 80 && CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ != 160
#error Software IR timing requires a configured 80 or 160 MHz CPU clock
#endif
#define CPU_CYCLES_PER_US CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ
#define CPU_CLOCK_HZ (CPU_CYCLES_PER_US * 1000000U)

#define IR_RX GPIO_NUM_5
#define IR_TX GPIO_NUM_14
#define IR_MAX 960
#define IR_VERSION 1
#define IR_GAP_UNITS 10000
#define IR_CLK_BLOCK 0x67
#define IR_CLK_HOST 4
#define IR_CLK_REG 4
#define IR_CLK_BIT 7

/* 使用 SDK 链接符号；音频时钟位对应 ESP8266 Arduino
 * cores/esp8266/esp8266_peri.h 中的 I2S_CLK_ENABLE()。
 */
extern int rom_i2c_readReg_Mask(int, int, int, int, int);
extern void rom_i2c_writeReg_Mask(int, int, int, int, int, int);
/* SDK 3.4 的 esp_sleep.c 导出这两个符号，但头文件未声明。 */
extern void esp_sleep_lock(void);
extern void esp_sleep_unlock(void);

typedef struct {
    uint16_t version;
    uint16_t count;
    uint16_t carrier_khz;
    uint16_t duration[IR_MAX]; /* 单位为 10 μs，偶数段为载波，奇数段为间隔。 */
} ir_code_t;

_Static_assert(sizeof(ir_code_t) <= 1984, "IR code exceeds SDK NVS blob limit");

static const char *TAG = "ir";
static ir_code_t codes[2];
static uint32_t capture_us[IR_MAX];
static volatile uint16_t capture_count;
static volatile uint32_t first_us;
static volatile uint32_t last_us;
static volatile bool capture_started;
static volatile bool capture_overflow;
static volatile uint32_t isr_call_count;
static volatile bool busy;
static volatile bool output_idle;
static volatile ir_state_t learn_state;
static volatile esp_err_t learn_error;
static volatile uint16_t tx_index;
static volatile esp_err_t tx_error;
static const ir_code_t *tx_code;
static SemaphoreHandle_t tx_done;
static int learn_slot;
static volatile uint16_t carrier_khz = 38;
/* 停止或恢复失败时保留原时钟值，供后续发送清理时再次恢复。 */
static bool clock_pending;
static int clock_before;
static bool tx_sleep_locked;
static bool i2s_pending;
static volatile bool tx_i2s_active;
/* 在 RAM 保存发送结果；RF 关闭期间发送时，UART 输出可能丢失。 */
typedef struct {
    unsigned seq;
    int slot;
    const char *stage;
    const char *backend;
    esp_err_t error, timer_stop, i2s_stop;
    unsigned segments, count, bck, clkm;
    int clock_saved, clock_enabled, clock_restored;
    unsigned late_cycles;
} send_report_t;
static send_report_t send_report;
static bool report_pending;

static int audio_clock_set(int enabled)
{
    portENTER_CRITICAL();
    rom_i2c_writeReg_Mask(IR_CLK_BLOCK, IR_CLK_HOST, IR_CLK_REG,
                        IR_CLK_BIT, IR_CLK_BIT, enabled);
    int value = rom_i2c_readReg_Mask(IR_CLK_BLOCK, IR_CLK_HOST, IR_CLK_REG,
                                   IR_CLK_BIT, IR_CLK_BIT);
    portEXIT_CRITICAL();
    return value;
}

static bool carrier_valid(int khz)
{
    return khz == 36 || khz == 38 || khz == 40;
}

static bool code_valid(const ir_code_t *code)
{
    if (code->version != IR_VERSION || code->count < 8 ||
        code->count > IR_MAX ||
        (code->carrier_khz != 36 && code->carrier_khz != 38 &&
         code->carrier_khz != 40)) return false;
    uint32_t total = 0;
    for (int i = 0; i < code->count; i++) {
        if (code->duration[i] < 8 || code->duration[i] > 65000) return false;
        total += code->duration[i];
    }
    return total <= 75000;
}

static uint32_t code_hash(const ir_code_t *code)
{
    const uint8_t *data = (const uint8_t *)code;
    size_t size = offsetof(ir_code_t, duration) + code->count * sizeof(uint16_t);
    uint32_t hash = 2166136261U;
    for (size_t i = 0; i < size; i++) hash = (hash ^ data[i]) * 16777619U;
    return hash;
}

static void IRAM_ATTR capture_isr(void *arg)
{
    isr_call_count++;
    /* SDK 每个 FreeRTOS tick 都重置 ccount，采集改用微秒计时器。 */
    uint32_t now = (uint32_t)esp_timer_get_time();
    if (!capture_started) {
        if ((GPIO.in & (1U << IR_RX)) == 0) {
            first_us = last_us = now;
            capture_started = true;
        }
        return;
    }
    if (capture_count >= IR_MAX) {
        capture_overflow = true;
        return;
    }
    capture_us[capture_count++] = now - last_us;
    last_us = now;
}

static inline void IRAM_ATTR carrier_off(void)
{
    GPIO.out_w1tc |= 1U << 14;
    PIN_FUNC_SELECT(PERIPHS_IO_MUX_MTMS_U, FUNC_GPIO14);
}

static inline void IRAM_ATTR carrier_on(void)
{
    GPIO.out_w1ts |= 1U << 14;
    PIN_FUNC_SELECT(PERIPHS_IO_MUX_MTMS_U, FUNC_I2SI_WS);
}

static void IRAM_ATTR tx_isr(void *arg)
{
    if (!tx_i2s_active) return;
    tx_index++;
    if (tx_index >= tx_code->count) {
        carrier_off();
        BaseType_t wake = pdFALSE;
        xSemaphoreGiveFromISR(tx_done, &wake);
        if (wake) portYIELD_FROM_ISR();
        return;
    }
    if (tx_index & 1) carrier_off();
    else carrier_on();
    if (frc1.ctrl.div != TIMER_CLKDIV_16 || frc1.ctrl.reload ||
        frc1.ctrl.intr_type != TIMER_EDGE_INT) {
        tx_error = ESP_ERR_INVALID_STATE;
        carrier_off();
        BaseType_t wake = pdFALSE;
        xSemaphoreGiveFromISR(tx_done, &wake);
        if (wake) portYIELD_FROM_ISR();
        return;
    }
    /* 首次定时器配置为 80 MHz / 16，即每 μs 5 tick；在 IRAM 内重装单次定时。 */
    frc1.load.data = tx_code->duration[tx_index] * 50U;
    frc1.ctrl.en = 1;
}

/* 全帧边沿截止时间相对同一起点，均小于 2^31 CPU 周期。
 * RTOS tick 会重置 ccount，调用方须全程保持临界区。
 * NMI 仍可打断时序，边沿迟到超过 5 μs 时返回失败。
 */
static bool IRAM_ATTR software_edge(uint32_t start, uint32_t deadline,
                                   bool high, unsigned *late_cycles)
{
    uint32_t elapsed;
    do {
        elapsed = soc_get_ccount() - start;
    } while (elapsed < deadline);
    unsigned late = elapsed - deadline;
    if (late > *late_cycles) *late_cycles = late;
    if (late > 5U * CPU_CYCLES_PER_US) return false;
    if (high) GPIO.out_w1ts = 1U << IR_TX;
    else GPIO.out_w1tc = 1U << IR_TX;
    /* GPIO 写入后再次检查，捕获截止检查与写入之间发生的 NMI 延迟。 */
    late = (uint32_t)(soc_get_ccount() - start) - deadline;
    if (late > *late_cycles) *late_cycles = late;
    return late <= 5U * CPU_CYCLES_PER_US;
}

static esp_err_t IRAM_ATTR software_send(const ir_code_t *code,
                                         uint32_t period, send_report_t *report)
{
    esp_err_t err = ESP_OK;
    portENTER_CRITICAL();
    uint32_t start = soc_get_ccount();
    uint32_t end = 0;
    for (unsigned i = 0; i < code->count; i++) {
        uint32_t begin = end;
        end += code->duration[i] * 10U * CPU_CYCLES_PER_US;
        if (!(i & 1)) {
            for (uint32_t pulse = begin; pulse < end; pulse += period) {
                uint32_t low = pulse + period / 2U;
                if (low > end) low = end;
                if (!software_edge(start, pulse, true, &report->late_cycles) ||
                    !software_edge(start, low, false, &report->late_cycles)) {
                    err = ESP_ERR_TIMEOUT;
                    goto finish;
                }
            }
        }
        if (!software_edge(start, end, false, &report->late_cycles)) {
            err = ESP_ERR_TIMEOUT;
            goto finish;
        }
        report->segments++;
    }
finish:
    GPIO.out_w1tc = 1U << IR_TX;
    portEXIT_CRITICAL();
    return err;
}

/* 等待信号最多 15 秒；采集最多 750 ms，高电平空闲 100 ms 判定帧结束。 */
static void learn_task(void *arg)
{
    ir_code_t candidate = { .version = IR_VERSION, .carrier_khz = ir_get_carrier() };
    TickType_t poll_ticks = pdMS_TO_TICKS(2);
    if (!poll_ticks) poll_ticks = 1;
    esp_err_t err = ESP_OK;
    capture_count = 0;
    capture_started = capture_overflow = false;
    isr_call_count = 0;
    GPIO.status_w1tc = 1U << IR_RX;
    err = gpio_isr_handler_add(IR_RX, capture_isr, NULL);
    if (err != ESP_OK) goto finish;
    err = gpio_set_intr_type(IR_RX, GPIO_INTR_ANYEDGE);
    if (err != ESP_OK) goto remove_isr;
    ESP_LOGI(TAG, "learn slot %d waiting for IR", learn_slot + 1);
    TickType_t start = xTaskGetTickCount();
    while (!capture_started && xTaskGetTickCount() - start < pdMS_TO_TICKS(15000)) {
        vTaskDelay(poll_ticks);
    }
    if (!capture_started) {
        ESP_LOGE(TAG, "capture wait timeout: isr_calls=%u", (unsigned)isr_call_count);
        err = ESP_ERR_TIMEOUT;
        goto remove_isr;
    }
    learn_state = IR_CAPTURING;
    while (!capture_overflow) {
        uint32_t now = (uint32_t)esp_timer_get_time();
        if ((int32_t)(now - first_us) >= 750000) {
            ESP_LOGE(TAG, "capture timeout: %u segments, isr_calls=%u",
                     (unsigned)capture_count, (unsigned)isr_call_count);
            err = ESP_ERR_INVALID_SIZE;
            break;
        }
        if (capture_count && gpio_get_level(IR_RX) == 1 &&
            (int32_t)(now - last_us) >= IR_GAP_UNITS * 10) break;
        vTaskDelay(poll_ticks);
    }
    if (capture_overflow) err = ESP_ERR_INVALID_SIZE;
remove_isr:
    {
        /* 先关闭硬件中断并清除待处理边沿，再移除回调；清理失败也不能继续触发。 */
        portENTER_CRITICAL();
        GPIO.pin[IR_RX].int_type = GPIO_INTR_DISABLE;
        GPIO.status_w1tc = 1U << IR_RX;
        portEXIT_CRITICAL();
        esp_err_t remove_err = gpio_isr_handler_remove(IR_RX);
        if (remove_err != ESP_OK)
            ESP_LOGE(TAG, "IR RX callback removal failed: %s", esp_err_to_name(remove_err));
        if (err == ESP_OK) err = remove_err;
    }
    if (err != ESP_OK) goto finish;
    if (capture_count >= IR_MAX) { err = ESP_ERR_INVALID_SIZE; goto finish; }
    /* 追加帧末空闲段，随后转换为 10 μs 单位并校验段数、单段及总时长。 */
    capture_us[capture_count++] = IR_GAP_UNITS * 10U;
    candidate.count = capture_count;
    ESP_LOGI(TAG, "capture complete: %u segments, isr_calls=%u",
             (unsigned)candidate.count, (unsigned)isr_call_count);
    if ((candidate.count & 1) || candidate.count < 8) {
        ESP_LOGE(TAG, "capture invalid segment count: %u", (unsigned)candidate.count);
        err = ESP_ERR_INVALID_RESPONSE;
        goto finish;
    }
    uint32_t total_units = 0;
    for (int i = 0; i < candidate.count; i++) {
        uint32_t units = (capture_us[i] + 5U) / 10U;
        if (units < 8 || units > 65000) {
            ESP_LOGE(TAG, "capture invalid segment %d: %u us", i, (unsigned)capture_us[i]);
            err = ESP_ERR_INVALID_RESPONSE;
            goto finish;
        }
        candidate.duration[i] = units;
        total_units += units;
    }
    if (!code_valid(&candidate)) {
        ESP_LOGE(TAG, "capture invalid total: %u us", (unsigned)(total_units * 10U));
        err = ESP_ERR_INVALID_RESPONSE;
        goto finish;
    }
    nvs_handle handle;
    err = nvs_open("ac", NVS_READWRITE, &handle);
    if (err != ESP_OK) goto finish;
    const char *key = learn_slot == 0 ? "ir0" : "ir1";
    size_t size = offsetof(ir_code_t, duration) + candidate.count * sizeof(uint16_t);
    err = nvs_set_blob(handle, key, &candidate, size);
    if (err == ESP_OK) err = nvs_commit(handle);
    if (err == ESP_OK) {
        /* 采集已结束，复用采集缓冲区回读 NVS，核对长度和完整内容。 */
        size_t read_size = sizeof(capture_us);
        err = nvs_get_blob(handle, key, capture_us, &read_size);
        if (err == ESP_OK && (read_size != size ||
            memcmp(capture_us, &candidate, size) != 0)) err = ESP_ERR_INVALID_RESPONSE;
        if (err != ESP_OK)
            ESP_LOGE(TAG, "learn slot %d NVS verification failed: %s",
                     learn_slot + 1, esp_err_to_name(err));
    }
    nvs_close(handle);
    if (err == ESP_OK) {
        codes[learn_slot] = candidate;
        app_reset_rule(learn_slot);
        learn_state = IR_SAVED;
        ESP_LOGI(TAG, "learn slot %d saved: %u pulses, %u kHz, code=%08x; NVS verified",
                 learn_slot + 1, (unsigned)candidate.count, (unsigned)candidate.carrier_khz,
                 (unsigned)code_hash(&candidate));
    }
finish:
    if (err != ESP_OK) {
        learn_error = err;
        learn_state = IR_ERROR;
        ESP_LOGE(TAG, "learn slot %d failed: %s", learn_slot + 1, esp_err_to_name(err));
    }
    busy = false;
    vTaskDelete(NULL);
}

esp_err_t ir_init(void)
{
    gpio_config_t rx = {
        .pin_bit_mask = 1ULL << IR_RX, .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config_t tx = {
        .pin_bit_mask = 1ULL << IR_TX, .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    esp_err_t err = gpio_config(&rx);
    if (err != ESP_OK) return err;
    err = gpio_config(&tx);
    if (err != ESP_OK) return err;
    err = gpio_set_level(IR_TX, 0);
    if (err != ESP_OK) return err;
    err = gpio_install_isr_service(0);
    if (err != ESP_OK) return err;
    tx_done = xSemaphoreCreateBinary();
    if (!tx_done) return ESP_ERR_NO_MEM;
    i2s_config_t icfg = {
        .mode = I2S_MODE_MASTER, .sample_rate = 38000,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
        .communication_format = I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB,
        .dma_buf_count = 2, .dma_buf_len = 8
    };
    i2s_pin_config_t pins = {
        .bck_o_en = -1, .ws_o_en = -1, .bck_i_en = -1,
        .ws_i_en = 1, .data_out_en = -1, .data_in_en = -1
    };
    err = i2s_driver_install(I2S_NUM_0, &icfg, 0, NULL);
    if (err != ESP_OK) return err;
    err = i2s_stop(I2S_NUM_0);
    if (err != ESP_OK) return err;
    err = i2s_set_pin(I2S_NUM_0, &pins);
    if (err != ESP_OK) return err;
    carrier_off();
    err = hw_timer_init(tx_isr, NULL);
    if (err != ESP_OK) return err;
    err = hw_timer_disarm();
    if (err != ESP_OK) return err;
    output_idle = true;
    nvs_handle handle;
    err = nvs_open("ac", NVS_READONLY, &handle);
    if (err == ESP_ERR_NVS_NOT_FOUND) return ESP_OK;
    if (err != ESP_OK) return err;
    uint16_t stored_carrier;
    err = nvs_get_u16(handle, "carrier", &stored_carrier);
    if (err != ESP_OK && err != ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(handle);
        return err;
    }
    if (err == ESP_OK) {
        if (!carrier_valid(stored_carrier)) {
            ESP_LOGE(TAG, "invalid stored carrier: %u kHz", (unsigned)stored_carrier);
            nvs_close(handle);
            return ESP_ERR_INVALID_STATE;
        }
        carrier_khz = stored_carrier;
    }
    for (int i = 0; i < 2; i++) {
        size_t size = sizeof(codes[i]);
        err = nvs_get_blob(handle, i == 0 ? "ir0" : "ir1", &codes[i], &size);
        if (err == ESP_ERR_NVS_NOT_FOUND) {
            ESP_LOGW(TAG, "stored IR slot %d missing", i + 1);
            continue;
        }
        if (err != ESP_OK || size != offsetof(ir_code_t, duration) +
            codes[i].count * sizeof(uint16_t) || !code_valid(&codes[i])) {
            ESP_LOGE(TAG, "stored IR slot %d invalid (read: %s, size: %u)",
                     i + 1, esp_err_to_name(err), (unsigned)size);
            codes[i].count = 0;
        } else {
            ESP_LOGI(TAG, "stored IR slot %d loaded: %u pulses, %u kHz, code=%08x",
                     i + 1, (unsigned)codes[i].count, (unsigned)codes[i].carrier_khz,
                     (unsigned)code_hash(&codes[i]));
        }
    }
    nvs_close(handle);
    return ESP_OK;
}

int ir_get_carrier(void)
{
    return carrier_khz;
}

esp_err_t ir_set_carrier(int khz)
{
    if (!carrier_valid(khz)) return ESP_ERR_INVALID_ARG;
    nvs_handle handle;
    esp_err_t err = nvs_open("ac", NVS_READWRITE, &handle);
    if (err != ESP_OK) return err;
    err = nvs_set_u16(handle, "carrier", khz);
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "carrier save failed: %s", esp_err_to_name(err));
        return err;
    }
    carrier_khz = khz;
    ESP_LOGI(TAG, "carrier saved: %d kHz", khz);
    return ESP_OK;
}

esp_err_t ir_start_learn(int slot)
{
    if (slot < 0 || slot > 1) return ESP_ERR_INVALID_ARG;
    portENTER_CRITICAL();
    if (busy) { portEXIT_CRITICAL(); return ESP_ERR_INVALID_STATE; }
    busy = true;
    portEXIT_CRITICAL();
    learn_slot = slot;
    learn_error = ESP_OK;
    learn_state = IR_WAITING;
    if (xTaskCreate(learn_task, "ir_learn", 4096, NULL, 8, NULL) != pdPASS) {
        busy = false;
        learn_state = IR_ERROR;
        learn_error = ESP_ERR_NO_MEM;
        ESP_LOGE(TAG, "learn slot %d could not start: no memory", slot + 1);
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

esp_err_t ir_send(int slot)
{
    if (slot < 0 || slot > 1) return ESP_ERR_INVALID_ARG;
    portENTER_CRITICAL();
    if (busy) { portEXIT_CRITICAL(); return ESP_ERR_INVALID_STATE; }
    busy = true;
    output_idle = false;
    portEXIT_CRITICAL();
    if (!tx_sleep_locked) {
        esp_sleep_lock();
        tx_sleep_locked = true;
    }
    /* 热点开启时用 I2S 载波配合硬件定时器；关闭时按配置的 CPU 频率软件生成波形。 */
    bool use_i2s = portal_is_on();
    send_report_t report = {
        .seq = send_report.seq + 1, .slot = slot,
        .stage = "code", .count = codes[slot].count,
        .backend = use_i2s ? "i2s" : "software",
        .clock_saved = -1, .clock_enabled = -1, .clock_restored = -1
    };
    esp_err_t err = ESP_OK;
    int send_carrier = ir_get_carrier();
    if (!code_valid(&codes[slot])) { err = ESP_ERR_NOT_FOUND; goto finish; }
    if (!use_i2s && (clock_pending || i2s_pending)) {
        report.stage = "pending-cleanup";
        err = ESP_ERR_INVALID_STATE;
        goto finish;
    }
    ESP_LOGI(TAG, "send slot %d starting: %u pulses, %d kHz, code=%08x backend=%s",
             slot + 1, (unsigned)codes[slot].count, send_carrier,
             (unsigned)code_hash(&codes[slot]), report.backend);
    /* 修改载波硬件前等待采样与规则日志发完。 */
    report.stage = "uart-before";
    uart_tx_wait_idle(CONFIG_ESP_CONSOLE_UART_NUM);
    /* 轻度休眠后恢复引脚驱动和收发主时钟。
     * SDK 仅在设置 TX/RX 模式标志时配置主模式；
     * 本项目只使用 I2S 时钟、不使用 DMA，因此显式恢复主模式。
     */
    report.stage = "gpio";
    err = gpio_set_direction(IR_TX, GPIO_MODE_OUTPUT);
    if (err != ESP_OK) goto finish;
    carrier_off();
    if (!use_i2s) {
        report.stage = "timer-stop";
        err = hw_timer_disarm();
        if (err != ESP_OK) goto finish;
        uint32_t hz = send_carrier * 1000U;
        uint32_t period = (CPU_CLOCK_HZ + hz / 2U) / hz;
        ESP_LOGI(TAG, "software carrier configured: requested=%u Hz calculated=%u Hz period=%u cycles; audio clock not used",
                 (unsigned)hz, (unsigned)(CPU_CLOCK_HZ / period), (unsigned)period);
        uart_tx_wait_idle(CONFIG_ESP_CONSOLE_UART_NUM);
        report.stage = "envelope";
        err = software_send(&codes[slot], period, &report);
        goto finish;
    }
    if (!clock_pending) {
        report.stage = "clock-read";
        portENTER_CRITICAL();
        clock_before = rom_i2c_readReg_Mask(IR_CLK_BLOCK, IR_CLK_HOST, IR_CLK_REG,
                                          IR_CLK_BIT, IR_CLK_BIT);
        portEXIT_CRITICAL();
        report.clock_saved = clock_before;
        if (clock_before != 0 && clock_before != 1) {
            ESP_LOGE(TAG, "audio clock read failed: value=%d", clock_before);
            err = ESP_ERR_INVALID_RESPONSE;
            goto finish;
        }
        clock_pending = true;
    }
    report.clock_saved = clock_before;
    report.stage = "clock-enable";
    int clock_enabled = audio_clock_set(1);
    report.clock_enabled = clock_enabled;
    ESP_LOGI(TAG, "audio clock: before=%d enabled=%d", clock_before, clock_enabled);
    if (clock_enabled != 1) {
        ESP_LOGE(TAG, "audio clock enable verification failed");
        err = ESP_ERR_INVALID_RESPONSE;
        goto finish;
    }
    portENTER_CRITICAL();
    I2S0.conf.tx_slave_mod = 0;
    I2S0.conf.rx_slave_mod = 0;
    portEXIT_CRITICAL();
    report.stage = "i2s-rate";
    i2s_pending = true; /* SDK 配置采样率时可能自动启动 I2S，失败也需要清理。 */
    err = i2s_set_sample_rates(I2S_NUM_0, send_carrier * 1000);
    if (err != ESP_OK) goto finish;
    report.stage = "i2s-start";
    err = i2s_start(I2S_NUM_0);
    if (err != ESP_OK) goto finish;
    unsigned bck_div = I2S0.conf.bck_div_num;
    unsigned clkm_div = I2S0.conf.clkm_div_num;
    report.bck = bck_div;
    report.clkm = clkm_div;
    if (!bck_div || !clkm_div) {
        ESP_LOGE(TAG, "invalid carrier dividers: bck=%u clkm=%u", bck_div, clkm_div);
        err = ESP_ERR_INVALID_STATE;
        goto finish;
    }
    /* I2S 使用独立的 160 MHz 外设时钟，不随 CPU 降频。 */
    ESP_LOGI(TAG, "carrier configured: requested=%u Hz, calculated=%u Hz, bck=%u clkm=%u",
             (unsigned)send_carrier * 1000U,
             160000000U / (32U * bck_div * clkm_div), bck_div, clkm_div);
    report.stage = "uart-carrier";
    uart_tx_wait_idle(CONFIG_ESP_CONSOLE_UART_NUM);
    tx_code = &codes[slot];
    tx_index = 0;
    tx_error = ESP_OK;
    xSemaphoreTake(tx_done, 0);
    tx_i2s_active = true;
    carrier_on();
    report.stage = "timer-start";
    err = hw_timer_alarm_us(tx_code->duration[0] * 10U, false);
    if (err != ESP_OK) goto finish;
    report.stage = "envelope";
    if (xSemaphoreTake(tx_done, pdMS_TO_TICKS(1200)) != pdTRUE) {
        err = ESP_ERR_TIMEOUT;
    } else err = tx_error;
    report.segments = tx_index;
finish:
    {
        tx_i2s_active = false;
        esp_err_t timer_err = hw_timer_disarm();
        report.timer_stop = timer_err;
        carrier_off();
        if (timer_err != ESP_OK) {
            ESP_LOGE(TAG, "send timer stop failed: %s", esp_err_to_name(timer_err));
            if (err == ESP_OK) err = timer_err;
        }
        esp_err_t stop_err = ESP_OK;
        if (use_i2s) {
            stop_err = i2s_stop(I2S_NUM_0);
            i2s_pending = stop_err != ESP_OK;
        }
        report.i2s_stop = stop_err;
        if (stop_err != ESP_OK) {
            ESP_LOGE(TAG, "send I2S stop failed: %s", esp_err_to_name(stop_err));
            if (err == ESP_OK) err = stop_err;
        }
        if (use_i2s && stop_err == ESP_OK && clock_pending) {
            int restored = audio_clock_set(clock_before);
            report.clock_restored = restored;
            if (restored == clock_before) {
                clock_pending = false;
                ESP_LOGI(TAG, "audio clock restored: value=%d", restored);
            } else {
                ESP_LOGE(TAG, "audio clock restore failed: expected=%d read=%d",
                         clock_before, restored);
                if (err == ESP_OK) err = ESP_ERR_INVALID_RESPONSE;
            }
        }
        /* 只有定时器停止且 I2S、时钟恢复完成才算空闲；否则保留休眠锁。 */
        output_idle = timer_err == ESP_OK && !i2s_pending && !clock_pending;
    }
    if (output_idle && tx_sleep_locked) {
        esp_sleep_unlock();
        tx_sleep_locked = false;
    }
    report.error = err;
    portENTER_CRITICAL();
    send_report = report;
    report_pending = true;
    busy = false;
    portEXIT_CRITICAL();
    if (err != ESP_OK) ESP_LOGE(TAG, "send slot %d failed: %s backend=%s segments=%u/%u late_cycles=%u",
                              slot + 1, esp_err_to_name(err), report.backend,
                              report.segments, report.count, report.late_cycles);
    else ESP_LOGI(TAG, "send slot %d complete: %u pulses, %d kHz, code=%08x backend=%s late_cycles=%u",
                  slot + 1, (unsigned)codes[slot].count, send_carrier,
                  (unsigned)code_hash(&codes[slot]), report.backend, report.late_cycles);
    return err;
}

void ir_report_last_send(void)
{
    portENTER_CRITICAL();
    if (busy || !report_pending) { portEXIT_CRITICAL(); return; }
    send_report_t report = send_report;
    report_pending = false;
    portEXIT_CRITICAL();
    ESP_LOGI(TAG, "previous send: seq=%u slot=%d backend=%s stage=%s result=%s segments=%u/%u late_cycles=%u",
             report.seq, report.slot + 1, report.backend, report.stage,
             esp_err_to_name(report.error), report.segments, report.count, report.late_cycles);
    if (strcmp(report.backend, "software") == 0) {
        ESP_LOGI(TAG, "previous clock: not used; timer_stop=%s pending_i2s=%d pending_clock=%d",
                 esp_err_to_name(report.timer_stop), i2s_pending, clock_pending);
    } else ESP_LOGI(TAG, "previous clock: saved=%d enabled=%d restored=%d bck=%u clkm=%u; timer_stop=%s i2s_stop=%s",
             report.clock_saved, report.clock_enabled, report.clock_restored,
             report.bck, report.clkm, esp_err_to_name(report.timer_stop),
             esp_err_to_name(report.i2s_stop));
}

bool ir_has_code(int slot)
{
    return slot >= 0 && slot < 2 && code_valid(&codes[slot]);
}

bool ir_is_busy(void) { return busy || !output_idle; }
ir_state_t ir_state(void) { return learn_state; }
esp_err_t ir_last_error(void) { return learn_error; }
