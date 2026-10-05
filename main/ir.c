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
#include "esp8266/pin_mux_register.h"
#include "esp_attr.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "app.h"
#include "ir.h"

#ifndef CONFIG_ESP8266_DEFAULT_CPU_FREQ_160
#error Raw IR capture requires the configured 160 MHz CPU clock
#endif

#define IR_RX GPIO_NUM_5
#define IR_TX GPIO_NUM_14
#define IR_MAX 960
#define IR_VERSION 1
#define IR_GAP_UNITS 10000

typedef struct {
    uint16_t version;
    uint16_t count;
    uint16_t carrier_khz;
    uint16_t duration[IR_MAX]; /* 10 microsecond units */
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

static void IRAM_ATTR capture_isr(void *arg)
{
    isr_call_count++;
    /* The SDK resets ccount on every FreeRTOS tick. */
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
    if (hw_timer_alarm_us(tx_code->duration[tx_index] * 10U, false) != ESP_OK) {
        tx_error = ESP_FAIL;
        carrier_off();
        BaseType_t wake = pdFALSE;
        xSemaphoreGiveFromISR(tx_done, &wake);
        if (wake) portYIELD_FROM_ISR();
    }
}

static void learn_task(void *arg)
{
    ir_code_t candidate = { .version = IR_VERSION, .carrier_khz = ir_get_carrier() };
    esp_err_t err = ESP_OK;
    capture_count = 0;
    capture_started = capture_overflow = false;
    isr_call_count = 0;
    GPIO.status_w1tc = 1U << IR_RX;
    err = gpio_isr_handler_add(IR_RX, capture_isr, NULL);
    if (err != ESP_OK) goto finish;
    ESP_LOGI(TAG, "learn slot %d waiting for IR", learn_slot + 1);
    TickType_t start = xTaskGetTickCount();
    while (!capture_started && xTaskGetTickCount() - start < pdMS_TO_TICKS(15000)) {
        vTaskDelay(pdMS_TO_TICKS(2));
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
        vTaskDelay(pdMS_TO_TICKS(2));
    }
    if (capture_overflow) err = ESP_ERR_INVALID_SIZE;
remove_isr:
    {
        esp_err_t remove_err = gpio_isr_handler_remove(IR_RX);
        if (err == ESP_OK) err = remove_err;
    }
    if (err != ESP_OK) goto finish;
    if (capture_count >= IR_MAX) { err = ESP_ERR_INVALID_SIZE; goto finish; }
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
    nvs_close(handle);
    if (err == ESP_OK) {
        codes[learn_slot] = candidate;
        app_reset_rule(learn_slot);
        learn_state = IR_SAVED;
        ESP_LOGI(TAG, "learn slot %d saved: %u pulses, %u kHz",
                 learn_slot + 1, (unsigned)candidate.count, (unsigned)candidate.carrier_khz);
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
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_ANYEDGE
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
    gpio_set_level(IR_TX, 0);
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
        if (err == ESP_ERR_NVS_NOT_FOUND) continue;
        if (err != ESP_OK || size != offsetof(ir_code_t, duration) +
            codes[i].count * sizeof(uint16_t) || !code_valid(&codes[i])) {
            ESP_LOGE(TAG, "stored IR slot %d invalid (read: %s, size: %u)",
                     i + 1, esp_err_to_name(err), (unsigned)size);
            codes[i].count = 0;
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
    esp_err_t err = ESP_OK;
    int send_carrier = ir_get_carrier();
    if (!code_valid(&codes[slot])) { err = ESP_ERR_NOT_FOUND; goto finish; }
    err = i2s_set_sample_rates(I2S_NUM_0, send_carrier * 1000);
    if (err != ESP_OK) goto finish;
    err = i2s_start(I2S_NUM_0);
    if (err != ESP_OK) goto finish;
    tx_code = &codes[slot];
    tx_index = 0;
    tx_error = ESP_OK;
    xSemaphoreTake(tx_done, 0);
    carrier_on();
    err = hw_timer_alarm_us(tx_code->duration[0] * 10U, false);
    if (err != ESP_OK) goto finish;
    if (xSemaphoreTake(tx_done, pdMS_TO_TICKS(1200)) != pdTRUE) {
        err = ESP_ERR_TIMEOUT;
    } else err = tx_error;
finish:
    {
        esp_err_t timer_err = hw_timer_disarm();
        carrier_off();
        if (timer_err != ESP_OK) {
            ESP_LOGE(TAG, "send timer stop failed: %s", esp_err_to_name(timer_err));
            if (err == ESP_OK) err = timer_err;
        }
        esp_err_t stop_err = i2s_stop(I2S_NUM_0);
        output_idle = timer_err == ESP_OK && stop_err == ESP_OK;
        if (stop_err != ESP_OK) {
            ESP_LOGE(TAG, "send I2S stop failed: %s", esp_err_to_name(stop_err));
            if (err == ESP_OK) err = stop_err;
        }
    }
    busy = false;
    if (err != ESP_OK) ESP_LOGE(TAG, "send slot %d failed: %s", slot + 1, esp_err_to_name(err));
    else ESP_LOGI(TAG, "send slot %d complete: %u pulses, %d kHz",
                  slot + 1, (unsigned)codes[slot].count, send_carrier);
    return err;
}

bool ir_has_code(int slot)
{
    return slot >= 0 && slot < 2 && code_valid(&codes[slot]);
}

bool ir_is_busy(void) { return busy || !output_idle; }
ir_state_t ir_state(void) { return learn_state; }
esp_err_t ir_last_error(void) { return learn_error; }
