#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "driver/gpio.h"
#include "driver/soc.h"
#include "esp8266/gpio_struct.h"
#include "esp_attr.h"
#include "rom/ets_sys.h"
#include "esp_log.h"
#include "sensor.h"

#define DQ GPIO_NUM_4
#if CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ != 80 && CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ != 160
#error 1-Wire slot timing requires a configured 80 or 160 MHz CPU clock
#endif
#define CPU_CYCLES_PER_US CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ
/* 独立供电的复位低脉冲要求至少 480 us；960 us 为本项目保守保护上限。 */
#define RESET_LOW_LIMIT_US 960
static esp_err_t slot_error;
static uint32_t slot_elapsed_us, slot_limit_us, slot_elapsed_cycles;
static const char *slot_stage;
static bool conversion_started;

static void IRAM_ATTR check_slot(uint32_t start, uint32_t limit, const char *stage)
{
    uint32_t elapsed = soc_get_ccount() - start;
    if (slot_error == ESP_OK && elapsed > limit * CPU_CYCLES_PER_US) {
        slot_elapsed_cycles = elapsed;
        slot_stage = stage;
        slot_elapsed_us = elapsed / CPU_CYCLES_PER_US;
        slot_limit_us = limit;
        slot_error = ESP_ERR_TIMEOUT;
    }
}

static esp_err_t release_bus(esp_err_t err)
{
#ifdef CONFIG_APP_SENSOR_IDLE_INPUT
    esp_err_t cleanup = gpio_set_direction(DQ, GPIO_MODE_INPUT);
    if (cleanup != ESP_OK) {
        ESP_LOGE("sensor", "bus release failed: %s", esp_err_to_name(cleanup));
        if (err == ESP_OK) err = cleanup;
    }
#endif
    return err;
}

/* 调用时已屏蔽 RTOS tick 中断，避免 ccount 被 tick 重置。
 * 边沿、延时和采样全程位于 IRAM，避免依赖 Flash cache。
 */
static void IRAM_ATTR slot_wait(uint32_t start, uint32_t us)
{
    while ((uint32_t)(soc_get_ccount() - start) < us * CPU_CYCLES_PER_US) { }
}

static bool IRAM_ATTR reset_bus(void)
{
    /* 在临界区内完成复位及存在脉冲采样，避免任务切换拉长时序。 */
    portENTER_CRITICAL();
    uint32_t edge = soc_get_ccount();
    GPIO.out_w1tc = 1U << DQ;
    uint32_t start = soc_get_ccount();
    slot_wait(start, 480);
    uint32_t release = soc_get_ccount();
    GPIO.out_w1ts = 1U << DQ;
    uint32_t released = soc_get_ccount();
    check_slot(release, 15, "reset-high-edge");
    check_slot(edge, RESET_LOW_LIMIT_US, "reset-release");
    /* 低电平可被中断延长，存在脉冲窗口必须相对释放边沿计时。 */
    slot_wait(release, 70);
    /* 上升沿位于两个时间戳之间：至少等到后时间戳 +60 us，
     * 同时不得晚于前时间戳 +75 us，覆盖存在脉冲的保证重叠窗口。 */
    slot_wait(released, 60);
    bool present = (GPIO.in & (1U << DQ)) == 0;
    check_slot(release, 75, "presence-sample");
    portEXIT_CRITICAL();
    ets_delay_us(410);
    return present && slot_error == ESP_OK;
}

static void IRAM_ATTR write_bit(int bit)
{
    portENTER_CRITICAL();
    uint32_t edge = soc_get_ccount();
    GPIO.out_w1tc = 1U << DQ;
    uint32_t start = soc_get_ccount();
    check_slot(edge, 2, "write-edge");
    slot_wait(start, bit ? 6 : 60);
    GPIO.out_w1ts = 1U << DQ;
    check_slot(start, bit ? 11 : 65, "write-release");
    slot_wait(start, 70);
    portEXIT_CRITICAL();
}

static int IRAM_ATTR read_bit(void)
{
    portENTER_CRITICAL();
    uint32_t edge = soc_get_ccount();
    GPIO.out_w1tc = 1U << DQ;
    uint32_t start = soc_get_ccount();
    check_slot(edge, 2, "read-edge");
    slot_wait(start, 3);
    GPIO.out_w1ts = 1U << DQ;
    check_slot(start, 8, "read-release");
    slot_wait(start, 13);
    int bit = (GPIO.in >> DQ) & 1U;
    check_slot(start, 15, "read-sample");
    slot_wait(start, 70);
    portEXIT_CRITICAL();
    return bit;
}

static void write_byte(uint8_t value)
{
    for (int i = 0; i < 8 && slot_error == ESP_OK; i++) write_bit((value >> i) & 1);
}

static uint8_t read_byte(void)
{
    uint8_t value = 0;
    for (int i = 0; i < 8 && slot_error == ESP_OK; i++) value |= read_bit() << i;
    return value;
}

/* DS18B20 scratchpad 使用低位优先 CRC8，反向多项式为 0x8c。 */
static uint8_t crc8(const uint8_t *data, int len)
{
    uint8_t crc = 0;
    for (int i = 0; i < len; i++) {
        uint8_t b = data[i];
        for (int j = 0; j < 8; j++) {
            uint8_t mix = (crc ^ b) & 1;
            crc >>= 1;
            if (mix) crc ^= 0x8c;
            b >>= 1;
        }
    }
    return crc;
}

static esp_err_t read_scratchpad(uint8_t data[9])
{
    if (!reset_bus()) return slot_error == ESP_OK ? ESP_ERR_NOT_FOUND : slot_error;
    write_byte(0xcc);
    write_byte(0xbe);
    for (int i = 0; i < 9; i++) data[i] = read_byte();
    if (slot_error != ESP_OK) return slot_error;
    uint8_t expected_crc = crc8(data, 8);
    if (expected_crc != data[8]) {
        ESP_LOGW("sensor", "scratchpad=%02x %02x %02x %02x %02x %02x %02x %02x %02x; expected CRC=%02x",
                 data[0], data[1], data[2], data[3], data[4],
                 data[5], data[6], data[7], data[8], expected_crc);
        return ESP_ERR_INVALID_CRC;
    }
    if ((data[4] & 0x9f) != 0x1f || data[5] != 0xff || data[7] != 0x10) {
        ESP_LOGE("sensor", "invalid scratchpad structure: config=%02x reserved=%02x/%02x",
                 data[4], data[5], data[7]);
        return ESP_ERR_INVALID_RESPONSE;
    }
    return ESP_OK;
}

static esp_err_t ensure_resolution(void)
{
    uint8_t data[9], verified[9];
    esp_err_t err = read_scratchpad(data);
    if (err != ESP_OK) return err;
    ESP_LOGI("sensor", "conversion precheck: raw16=%d config=%02x CRC=OK external_power=1",
             (int)(int16_t)((data[1] << 8) | data[0]), data[4]);
    if ((data[4] & 0x60) == 0x60) return ESP_OK;
    unsigned resolution = 9 + ((data[4] >> 5) & 3);
    if (!reset_bus()) return slot_error == ESP_OK ? ESP_ERR_NOT_FOUND : slot_error;
    write_byte(0xcc);
    write_byte(0x4e);
    /* 保留 TH/TL，只修改 RAM 分辨率；不执行 Copy Scratchpad 写 EEPROM。 */
    write_byte(data[2]);
    write_byte(data[3]);
    write_byte(data[4] | 0x60);
    if (slot_error != ESP_OK) return slot_error;
    /* 写暂存器后必须等待 tWR=10 ms 才允许下一次复位；提前复位会使配置写入
     * 失效，读回仍是旧值，且该错误不在 sensor_start 的重试范围内。 */
    ets_delay_us(10000);
    err = read_scratchpad(verified);
    if (err != ESP_OK) return err;
    if (verified[2] != data[2] || verified[3] != data[3] ||
        verified[4] != (uint8_t)(data[4] | 0x60)) {
        ESP_LOGE("sensor", "12-bit configuration readback failed");
        return ESP_ERR_INVALID_RESPONSE;
    }
    ESP_LOGI("sensor", "resolution corrected: %u -> 12 bits", resolution);
    return ESP_OK;
}

esp_err_t sensor_init(void)
{
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << DQ, .mode = GPIO_MODE_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    esp_err_t err = gpio_config(&cfg);
    if (err == ESP_OK) err = gpio_set_level(DQ, 1);
    return release_bus(err);
}

static esp_err_t start_conversion(bool *external_power)
{
    if (!external_power) return ESP_ERR_INVALID_ARG;
    *external_power = false;
    esp_err_t err = gpio_set_direction(DQ, GPIO_MODE_OUTPUT_OD);
    if (err != ESP_OK) return err;
    if (!reset_bus()) return slot_error == ESP_OK ? ESP_ERR_NOT_FOUND : slot_error;
    write_byte(0xcc);
    /* 本项目只允许独立供电；供电检测异常时禁止继续转换。 */
    write_byte(0xb4);
    bool powered = read_bit() != 0;
    if (slot_error != ESP_OK) return slot_error;
    if (!powered) {
        ESP_LOGE("sensor", "external power required; check VDD/DQ wiring");
        return ESP_ERR_INVALID_STATE;
    }
    err = ensure_resolution();
    if (err != ESP_OK) return err;
    if (!reset_bus()) return slot_error == ESP_OK ? ESP_ERR_NOT_FOUND : slot_error;
    write_byte(0xcc);
    write_byte(0x44);
    if (slot_error != ESP_OK) return slot_error;
    /* 独立供电使用完整固定等待，启动阶段不读取转换状态位。 */
    /* 已确认独立供电，由板上 4.7 kΩ 上拉保持 DQ 高电平。 */
    err = gpio_set_direction(DQ, GPIO_MODE_INPUT);
    if (err != ESP_OK) return err;
    *external_power = true;
    conversion_started = true;
    ESP_LOGI("sensor", "conversion command sent: external power, resolution=12 method=fixed-wait wait_ms=750");
    return ESP_OK;
}

static void report_slot_error(void)
{
    if (slot_error != ESP_OK)
        ESP_LOGW("sensor", "1-Wire slot exceeded: stage=%s elapsed_cycles=%u elapsed_us=%u limit_us=%u",
                 slot_stage, (unsigned)slot_elapsed_cycles,
                 (unsigned)slot_elapsed_us, (unsigned)slot_limit_us);
}

esp_err_t sensor_start(bool *external_power)
{
    if (!external_power) return ESP_ERR_INVALID_ARG;
    esp_err_t err;
    for (int attempt = 1; ; attempt++) {
        conversion_started = false;
        slot_error = ESP_OK;
        err = start_conversion(external_power);
        report_slot_error();
        if (err == ESP_OK) {
            if (attempt > 1) ESP_LOGI("sensor", "conversion start recovered: attempt=%d", attempt);
            return ESP_OK;
        }
        err = release_bus(err);
        if (attempt == 3 || slot_error != ESP_ERR_TIMEOUT) break;
        ESP_LOGW("sensor", "conversion start attempt %d timing failed; restarting transaction", attempt);
    }
    ESP_LOGE("sensor", "conversion start failed: %s", esp_err_to_name(err));
    return err;
}

static esp_err_t read_temp(int16_t *temp10, int16_t *raw16)
{
    uint8_t data[9];
    esp_err_t err = read_scratchpad(data);
    if (err != ESP_OK) return err;
    if ((data[4] & 0x60) != 0x60) {
        ESP_LOGE("sensor", "resolution changed during conversion: config=%02x", data[4]);
        return ESP_ERR_INVALID_STATE;
    }
    int16_t raw = (int16_t)((data[1] << 8) | data[0]);
    if (raw < -55 * 16 || raw > 125 * 16) {
        ESP_LOGE("sensor", "raw temperature out of range: raw16=%d", (int)raw);
        return ESP_ERR_INVALID_RESPONSE;
    }
    if (raw == 0x0550) {
        ESP_LOGW("sensor", "85 C rejected: power-on default or real value ambiguous in fixed-wait mode");
        return ESP_ERR_INVALID_STATE;
    }
    /* 固定等待后执行完整数据校验；85 ℃无法区分上电默认值，保守拒绝。 */
    *temp10 = sensor_temperature(raw, 0);
    if (raw16) *raw16 = raw;
    ESP_LOGI("sensor", "raw16=%d resolution=12 offset10=%d temperature10=%d",
             (int)raw, CONFIG_APP_TEMP_OFFSET10, (int)*temp10);
    return ESP_OK;
}

esp_err_t sensor_finish(int16_t *temp10, int16_t *raw16)
{
    if (!temp10) return ESP_ERR_INVALID_ARG;
    if (!conversion_started) {
        ESP_LOGE("sensor", "finish without conversion command");
        return ESP_ERR_INVALID_STATE;
    }
    conversion_started = false;
    esp_err_t err = gpio_set_direction(DQ, GPIO_MODE_OUTPUT_OD);
    if (err == ESP_OK) {
        /* 状态读取超时只重读状态位，不复位或重发转换命令。 */
        for (int attempt = 1; ; attempt++) {
            slot_error = ESP_OK;
            int ready = read_bit();
            err = slot_error != ESP_OK ? slot_error : (ready ? ESP_OK : ESP_ERR_TIMEOUT);
            report_slot_error();
            if (slot_error == ESP_OK || attempt == 3) {
                if (slot_error == ESP_OK && !ready)
                    ESP_LOGE("sensor", "conversion still busy after wait: ready=0; no scratchpad read");
                else if (err == ESP_OK && attempt > 1)
                    ESP_LOGI("sensor", "conversion status recovered: attempt=%d", attempt);
                break;
            }
            ESP_LOGW("sensor", "conversion status attempt %d timing failed; retrying status", attempt);
        }
    }
    if (err != ESP_OK) {
        ESP_LOGE("sensor", "conversion completion failed: %s", esp_err_to_name(err));
        return release_bus(err);
    }
    /* CRC、设备未找到和读取时序错误最多三次完整重读；无效数据不重试。 */
    int16_t result10, result_raw;
    for (int attempt = 1; ; attempt++) {
        slot_error = ESP_OK;
        err = read_temp(&result10, &result_raw);
        report_slot_error();
        if (err == ESP_OK || attempt == 3 ||
            (err != ESP_ERR_INVALID_CRC && err != ESP_ERR_NOT_FOUND && slot_error != ESP_ERR_TIMEOUT)) {
            if (err == ESP_OK && attempt > 1)
                ESP_LOGI("sensor", "scratchpad read recovered: attempt=%d", attempt);
            break;
        }
        ESP_LOGW("sensor", "scratchpad read attempt %d failed: %s; retrying",
                 attempt, esp_err_to_name(err));
    }
    err = release_bus(err);
    if (err != ESP_OK) ESP_LOGE("sensor", "temperature rejected: %s", esp_err_to_name(err));
    else {
        *temp10 = result10;
        if (raw16) *raw16 = result_raw;
        ESP_LOGI("sensor", "conversion complete: CRC and scratchpad verified");
    }
    return err;
}
