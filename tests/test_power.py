r"""Compile the actual control/IR sources against deterministic host SDK mocks.

Run from the repository root: python tests\test_power.py
Generated headers and executables stay in the ignored build_ascii directory.
These tests verify control flow, not ESP8266 sleep current or hardware timing.
"""

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build_ascii" / "power_test"
HEADERS = [
    "freertos/FreeRTOS.h", "freertos/task.h", "freertos/semphr.h",
    "driver/gpio.h", "driver/adc.h", "driver/hw_timer.h", "driver/i2s.h", "driver/soc.h",
    "esp8266/gpio_struct.h", "esp8266/pin_mux_register.h", "esp_wifi.h",
    "esp8266/i2s_struct.h", "esp8266/timer_struct.h",
    "esp_sleep.h", "esp_log.h", "esp_attr.h", "esp_timer.h", "esp_err.h",
    "nvs.h", "nvs_flash.h", "rom/ets_sys.h", "rom/uart.h",
]

# 主机 SDK mock 定义：提供确定性时间、GPIO 和错误注入，不模拟真实芯片电气特性。
SDK = r'''
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
extern unsigned test_log_seq, test_learn_wait, test_learn_end;
extern unsigned crc_logs;
extern unsigned test_send_start;
extern unsigned test_send_reports;
extern bool drop_send_logs;
typedef int esp_err_t;
typedef int BaseType_t;
typedef uint32_t TickType_t;
typedef void *TaskHandle_t;
typedef void *SemaphoreHandle_t;
typedef void (*TaskFunction_t)(void *);
typedef int nvs_handle;
typedef int gpio_num_t;
typedef int gpio_int_type_t;
enum { ESP_OK, ESP_FAIL, ESP_ERR_INVALID_ARG, ESP_ERR_INVALID_STATE,
       ESP_ERR_NO_MEM, ESP_ERR_NOT_FOUND, ESP_ERR_TIMEOUT, ESP_ERR_INVALID_SIZE,
       ESP_ERR_INVALID_RESPONSE, ESP_ERR_INVALID_CRC, ESP_ERR_NVS_NOT_FOUND };
enum { GPIO_NUM_2=2, GPIO_NUM_4=4, GPIO_NUM_5=5, GPIO_NUM_12=12,
       GPIO_NUM_13=13, GPIO_NUM_14=14 };
enum { GPIO_INTR_DISABLE, GPIO_INTR_NEGEDGE, GPIO_INTR_LOW_LEVEL,
       GPIO_INTR_ANYEDGE, GPIO_MODE_INPUT, GPIO_MODE_OUTPUT, GPIO_MODE_OUTPUT_OD,
       GPIO_PULLUP_DISABLE, GPIO_PULLUP_ENABLE, GPIO_PULLDOWN_DISABLE };
enum { NVS_READONLY, NVS_READWRITE };
enum { I2S_NUM_0, I2S_MODE_MASTER, I2S_BITS_PER_SAMPLE_16BIT,
       I2S_CHANNEL_FMT_RIGHT_LEFT, I2S_COMM_FORMAT_I2S, I2S_COMM_FORMAT_I2S_MSB };
enum { TIMER_CLKDIV_16=4, TIMER_EDGE_INT=0 };
enum { PERIPHS_IO_MUX_MTMS_U, FUNC_GPIO14, FUNC_I2SI_WS };
typedef struct {
    uint64_t pin_bit_mask;
    int mode, pull_up_en, pull_down_en, intr_type;
} gpio_config_t;
typedef struct {
    int mode, sample_rate, bits_per_sample, channel_format;
    int communication_format, dma_buf_count, dma_buf_len;
} i2s_config_t;
typedef struct {
    int bck_o_en, ws_o_en, bck_i_en, ws_i_en, data_out_en, data_in_en;
} i2s_pin_config_t;
typedef struct { bool light_sleep_enable; } esp_pm_config_esp8266_t;
enum { ADC_READ_TOUT_MODE };
typedef struct { int mode; uint8_t clk_div; } adc_config_t;
esp_err_t adc_init(adc_config_t *);
esp_err_t adc_read(uint16_t *);
esp_err_t adc_read_fast(uint16_t *, uint16_t);
struct mock_gpio {
    uint32_t in, out_w1tc, out_w1ts, status, status_w1tc;
    struct { int int_type; bool wakeup_enable; } pin[17];
};
extern struct mock_gpio GPIO;
extern struct mock_i2s {
    struct { unsigned tx_slave_mod, rx_slave_mod, bck_div_num, clkm_div_num; } conf;
} I2S0;
extern struct mock_timer {
    struct { uint32_t data; } count, load;
    struct { unsigned div, reload, en, intr_type; } ctrl;
} frc1;
extern int test_pin_func;
#define CONFIG_ESP8266_DEFAULT_CPU_FREQ_160 1
#define CONFIG_ESP_CONSOLE_UART_NUM 0
#define IRAM_ATTR
#define pdFALSE 0
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms) / 10U)
#define portTICK_PERIOD_MS 10U
#define portENTER_CRITICAL() ((void)0)
#define portEXIT_CRITICAL() ((void)0)
#define portYIELD_FROM_ISR() ((void)0)
#define ESP_ERROR_CHECK(expr) assert((expr) == ESP_OK)
#define PIN_FUNC_SELECT(pin, fn) ((void)(pin), test_pin_func = (fn))
#define ESP_LOGI(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGD(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGE(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) test_log(tag, __VA_ARGS__)
void test_log(const char *, const char *, ...);
const char *esp_err_to_name(esp_err_t);
TickType_t xTaskGetTickCount(void);
TaskHandle_t xTaskGetCurrentTaskHandle(void);
BaseType_t xTaskCreate(TaskFunction_t, const char *, unsigned, void *, unsigned, TaskHandle_t *);
void vTaskDelete(TaskHandle_t);
void vTaskDelay(TickType_t);
void vTaskNotifyGiveFromISR(TaskHandle_t, BaseType_t *);
BaseType_t xTaskNotifyGive(TaskHandle_t);
uint32_t ulTaskNotifyTake(BaseType_t, TickType_t);
SemaphoreHandle_t xSemaphoreCreateMutex(void);
SemaphoreHandle_t xSemaphoreCreateBinary(void);
BaseType_t xSemaphoreTake(SemaphoreHandle_t, TickType_t);
BaseType_t xSemaphoreGive(SemaphoreHandle_t);
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t, BaseType_t *);
esp_err_t gpio_config(const gpio_config_t *);
esp_err_t gpio_set_level(gpio_num_t, uint32_t);
esp_err_t gpio_set_direction(gpio_num_t, int);
void ets_delay_us(uint32_t);
uint32_t soc_get_ccount(void);
void uart_tx_wait_idle(uint8_t);
int gpio_get_level(gpio_num_t);
esp_err_t gpio_set_intr_type(gpio_num_t, gpio_int_type_t);
esp_err_t gpio_wakeup_enable(gpio_num_t, gpio_int_type_t);
esp_err_t gpio_isr_handler_add(gpio_num_t, TaskFunction_t, void *);
esp_err_t gpio_isr_handler_remove(gpio_num_t);
esp_err_t gpio_install_isr_service(int);
esp_err_t esp_pm_configure(const void *);
esp_err_t esp_sleep_enable_gpio_wakeup(void);
void esp_sleep_lock(void);
void esp_sleep_unlock(void);
int64_t esp_timer_get_time(void);
esp_err_t nvs_flash_init(void);
esp_err_t nvs_open(const char *, int, nvs_handle *);
void nvs_close(nvs_handle);
esp_err_t nvs_get_blob(nvs_handle, const char *, void *, size_t *);
esp_err_t nvs_set_blob(nvs_handle, const char *, const void *, size_t);
esp_err_t nvs_get_u16(nvs_handle, const char *, uint16_t *);
esp_err_t nvs_set_u16(nvs_handle, const char *, uint16_t);
esp_err_t nvs_commit(nvs_handle);
esp_err_t i2s_driver_install(int, const i2s_config_t *, int, void *);
esp_err_t i2s_set_pin(int, const i2s_pin_config_t *);
esp_err_t i2s_set_sample_rates(int, uint32_t);
esp_err_t i2s_start(int);
esp_err_t i2s_stop(int);
esp_err_t hw_timer_init(TaskFunction_t, void *);
esp_err_t hw_timer_alarm_us(uint32_t, bool);
esp_err_t hw_timer_disarm(void);
'''

COMMON = r'''
struct mock_gpio GPIO;
struct mock_i2s I2S0;
struct mock_timer frc1;
int test_pin_func;
unsigned test_log_seq, test_learn_wait, test_learn_end;
unsigned crc_logs;
unsigned test_send_start;
unsigned test_send_reports;
bool drop_send_logs;
void test_log(const char *tag, const char *fmt, ...) {
#ifdef TEST_IR_NVS
    assert(critical_depth == 0); /* No Flash/logging calls during a frame. */
    if (drop_send_logs && busy) return;
#endif
    (void)tag;
    if (strstr(fmt, "send slot %d starting")) test_send_start++;
    if (strstr(fmt, "previous send:")) test_send_reports++;
    if (strstr(fmt, "scratchpad=")) crc_logs++;
    if (strstr(fmt, "waiting for IR")) test_learn_wait = ++test_log_seq;
    if (strstr(fmt, "learn slot %d failed") || strstr(fmt, "learn slot %d saved"))
        test_learn_end = ++test_log_seq;
}
const char *esp_err_to_name(esp_err_t err) { (void)err; return "mock error"; }
SemaphoreHandle_t xSemaphoreCreateMutex(void) { return (void *)1; }
SemaphoreHandle_t xSemaphoreCreateBinary(void) { return (void *)2; }
BaseType_t xSemaphoreGive(SemaphoreHandle_t sem) { (void)sem; return pdTRUE; }
esp_err_t gpio_config(const gpio_config_t *cfg) {
    for (int i = 0; i < 17; i++)
        if (cfg->pin_bit_mask & (1ULL << i)) GPIO.pin[i].int_type = cfg->intr_type;
    return ESP_OK;
}
esp_err_t gpio_set_intr_type(int pin, int type) { GPIO.pin[pin].int_type = type; return ESP_OK; }
esp_err_t gpio_isr_handler_add(int pin, TaskFunction_t cb, void *arg) {
    (void)pin; (void)cb; (void)arg; return ESP_OK;
}
esp_err_t gpio_isr_handler_remove(int pin) { (void)pin; return ESP_OK; }
esp_err_t gpio_install_isr_service(int flags) { (void)flags; return ESP_OK; }
void nvs_close(nvs_handle handle) { (void)handle; }
#ifndef TEST_IR_NVS
esp_err_t nvs_set_blob(nvs_handle handle, const char *key, const void *data, size_t size) {
    (void)handle; (void)key; (void)data; (void)size; return ESP_OK;
}
esp_err_t nvs_set_u16(nvs_handle handle, const char *key, uint16_t value) {
    (void)handle; (void)key; (void)value; return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle handle) { (void)handle; return ESP_OK; }
#endif
'''

CONTROL = r'''
#include <setjmp.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
static int critical_depth;
#undef portENTER_CRITICAL
#undef portEXIT_CRITICAL
#define portENTER_CRITICAL() (++critical_depth)
#define portEXIT_CRITICAL() assert(--critical_depth >= 0)
#include "main.c"
static jmp_buf finished;
static TickType_t start_tick;
static uint32_t now_ms, end_ms, notified, ap_start, hold_until[17];
static uint32_t sample_times[512], send_times[512];
static int sample_count, send_count, pm_calls, blocked_keys;
static int ap_starts, ap_stops;
static int button_wakes[2];
static uint32_t stopped_at;
static bool ap, ap_used, ir_busy, fail_pm, fail_wakeup, sensor_error;
static bool led_test;
static uint16_t adc_raw = 855;
static esp_err_t adc_error = ESP_OK;
static int battery_reads;
static int fast_reads, single_reads;
static bool power_external = true, start_failed, conversion_pending;
static const int16_t *temp_script;
static int temp_count;
static bool enable_down, fail_send_once;
static int send_slots[512];
static int conversion_sleeps, conversion_awake;
static int led_level = 1;
typedef struct { uint32_t ms; int action; uint32_t hold; } event_t;
static const event_t *events;
static size_t event_count, event_pos;
static void advance_time(uint32_t target) {
    while (event_pos < event_count && events[event_pos].ms <= target) {
        event_t ev = events[event_pos++];
        now_ms = ev.ms;
        if (ev.action == 5) { ap_used = true; ap_start = now_ms; }
        else if (ev.action == 6) { /* Status polling is not an action. */ }
        else if (ev.action == 3 || ev.action == 4) ir_busy = ev.action == 3;
        else {
            int pin = ev.action == 1 ? 12 : 13;
            if (GPIO.pin[pin].int_type == GPIO_INTR_LOW_LEVEL) {
                if (auto_sleep) {
                    assert(GPIO.pin[pin].wakeup_enable);
                    button_wakes[ev.action - 1]++;
                }
                hold_until[pin] = ev.ms + ev.hold;
                button_isr(ev.action == 1 ? NULL : (void *)1);
                assert(GPIO.pin[pin].int_type == GPIO_INTR_DISABLE);
            } else blocked_keys++;
        }
    }
    now_ms = target;
}
TickType_t xTaskGetTickCount(void) { return start_tick + pdMS_TO_TICKS(now_ms); }
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return (void *)1; }
BaseType_t xTaskCreate(TaskFunction_t fn, const char *name, unsigned stack,
                      void *arg, unsigned pri, TaskHandle_t *handle) {
    (void)fn; (void)name; (void)stack; (void)arg; (void)pri;
    if (handle) *handle = (void *)2;
    return pdPASS;
}
void vTaskDelete(TaskHandle_t handle) { (void)handle; assert(false); }
void vTaskDelay(TickType_t ticks) {
    assert(ap || !led_enabled);
    if (conversion_pending) {
        assert(ticks == pdMS_TO_TICKS(750) + 1);
        assert(auto_sleep == (power_external && !ap && !ir_busy && !sleep_failed));
        if (auto_sleep) conversion_sleeps++;
        else conversion_awake++;
    }
    advance_time(now_ms + ticks * 10U);
}
void vTaskNotifyGiveFromISR(TaskHandle_t task, BaseType_t *wake) {
    assert(task == (void *)1); notified++; *wake = pdTRUE;
}
BaseType_t xTaskNotifyGive(TaskHandle_t task) { assert(task == (void *)2); return pdPASS; }
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t ticks) {
    assert(clear == pdTRUE);
    if (led_test) {
        assert(ticks == portMAX_DELAY && led_level == 1);
        longjmp(finished, 1);
    }
    assert(ticks <= pdMS_TO_TICKS(10000));
    if (notified) { uint32_t count = notified; notified = 0; return count; }
    assert(ticks > 0);
    uint32_t target = now_ms + ticks * 10U;
    if (event_pos < event_count && events[event_pos].ms < target) target = events[event_pos].ms;
    if (target >= end_ms) { now_ms = end_ms; longjmp(finished, 1); }
    advance_time(target);
    uint32_t count = notified; notified = 0; return count;
}
BaseType_t xSemaphoreTake(SemaphoreHandle_t sem, TickType_t ticks) {
    (void)sem; (void)ticks; return pdTRUE;
}
esp_err_t gpio_set_level(int pin, uint32_t value) {
    if (pin == 2) led_level = value;
    return ESP_OK;
}
int gpio_get_level(int pin) { return now_ms >= hold_until[pin]; }
esp_err_t gpio_wakeup_enable(int pin, int type) {
    if (fail_wakeup) return ESP_FAIL;
    GPIO.pin[pin].int_type = type; GPIO.pin[pin].wakeup_enable = true; return ESP_OK;
}
esp_err_t esp_sleep_enable_gpio_wakeup(void) { return ESP_OK; }
esp_err_t esp_pm_configure(const void *cfg) {
    pm_calls++;
    bool enable = ((const esp_pm_config_esp8266_t *)cfg)->light_sleep_enable;
    if (enable && fail_pm) return ESP_FAIL;
    if (enable) assert(!ap && !ir_busy);
    return ESP_OK;
}
esp_err_t nvs_flash_init(void) { return ESP_OK; }
esp_err_t nvs_open(const char *name, int mode, nvs_handle *handle) {
    (void)name; (void)mode; *handle = 1; return ESP_OK;
}
esp_err_t nvs_get_blob(nvs_handle handle, const char *key, void *data, size_t *size) {
    (void)handle; assert(*size == sizeof(rule_cfg_t));
    *(rule_cfg_t *)data = (rule_cfg_t){ .threshold10=260, .rising=1,
        .enabled = strcmp(key, "rule0") == 0 };
    if (enable_down && strcmp(key, "rule1") == 0)
        *(rule_cfg_t *)data = (rule_cfg_t){ .threshold10=280, .rising=0, .enabled=1 };
    return ESP_OK;
}
esp_err_t sensor_init(void) { return ESP_OK; }
esp_err_t adc_init(adc_config_t *cfg) {
    assert(cfg->mode == ADC_READ_TOUT_MODE && cfg->clk_div == 8);
    return ESP_OK;
}
esp_err_t adc_read(uint16_t *raw) {
    assert(!auto_sleep && critical_depth == 0);
    battery_reads++;
    single_reads++;
    *raw = adc_raw;
    return adc_error;
}
esp_err_t adc_read_fast(uint16_t *data, uint16_t len) {
    fast_reads++;
    assert(false && "fast ADC must not run before 1-Wire transactions");
    return ESP_FAIL;
}
esp_err_t sensor_start(bool *external_power) {
    assert(!auto_sleep && sample_count < 512);
    sample_times[sample_count] = now_ms;
    sample_count++;
    *external_power = power_external;
    conversion_pending = !(start_failed && sample_count == 2);
    return conversion_pending ? ESP_OK : ESP_ERR_NOT_FOUND;
}
esp_err_t sensor_finish(int16_t *temp) {
    assert(!auto_sleep && conversion_pending);
    assert(now_ms - sample_times[sample_count - 1] >= 750);
    conversion_pending = false;
    const int16_t temperatures[] = {250, 260, 260, 255, 260};
    *temp = temp_script ? temp_script[sample_count <= temp_count ? sample_count - 1 : temp_count - 1]
                        : temperatures[sample_count <= 5 ? sample_count - 1 : 4];
    return sensor_error && sample_count == 2 ? ESP_ERR_INVALID_CRC : ESP_OK;
}
esp_err_t ir_init(void) { return ESP_OK; }
void ir_report_last_send(void) { assert(!auto_sleep); }
bool ir_has_code(int slot) { (void)slot; return true; }
bool ir_is_busy(void) { return ir_busy; }
ir_state_t ir_state(void) { return ir_busy ? IR_WAITING : IR_IDLE; }
esp_err_t ir_send(int slot) {
    assert(!auto_sleep && !ir_busy && send_count < 512);
    send_slots[send_count] = slot;
    send_times[send_count++] = now_ms;
    if (fail_send_once) { fail_send_once = false; return ESP_FAIL; }
    return ESP_OK;
}
esp_err_t portal_init(void) { return ESP_OK; }
esp_err_t portal_start(void) {
    assert(!auto_sleep); ap = true; ap_used = false;
    ap_start = now_ms; ap_starts++; return ESP_OK;
}
esp_err_t portal_stop(void) {
    assert(!auto_sleep && !ir_busy);
    if (ap) { ap_stops++; stopped_at = now_ms; }
    ap = false; return ESP_OK;
}
bool portal_is_on(void) { return ap; }
uint32_t portal_idle_ms(void) { return now_ms - ap_start; }
uint32_t portal_timeout_ms(void) { return ap_used ? 600000 : 180000; }
/* 每个场景重置状态并用事件脚本推进主循环，覆盖采样、按键、限频与休眠降级。 */
static void run_control(uint32_t duration, const event_t *script, size_t count,
                        bool pm_error, bool wake_error, bool temp_error, TickType_t base) {
    memset(&GPIO, 0, sizeof(GPIO)); memset(&current, 0, sizeof(current));
    memset(states, 0, sizeof(states)); memset(hold_until, 0, sizeof(hold_until));
    memset(last_send, 0, sizeof(last_send));
    memset(send_recorded, 0, sizeof(send_recorded));
    s1_pending = s2_pending = led_enabled = auto_sleep = sleep_failed = false;
    adc_sleep_seen = false;
    ap = ap_used = ir_busy = false;
    fail_pm = pm_error; fail_wakeup = wake_error; sensor_error = temp_error;
    sample_count = send_count = pm_calls = blocked_keys = 0;
    battery_reads = 0;
    fast_reads = single_reads = critical_depth = 0;
    conversion_pending = false;
    conversion_sleeps = conversion_awake = 0;
    ap_starts = ap_stops = 0; stopped_at = 0;
    memset(button_wakes, 0, sizeof(button_wakes));
    now_ms = notified = 0; start_tick = base; end_ms = duration;
    events = script; event_count = count; event_pos = 0;
    if (!setjmp(finished)) app_main();
    assert(battery_reads == sample_count);
    assert(critical_depth == 0 && fast_reads == 0 && single_reads == battery_reads);
}
int main(void) {
    run_control(130000, NULL, 0, false, false, false, 0);
    assert(sample_count == 5 && send_count == 1 && auto_sleep && !led_enabled);
    for (int i = 0; i < 5; i++) assert(sample_times[i] == (uint32_t)i * 30000);
    assert(send_times[0] == 30760);
    assert(conversion_sleeps == 5 && conversion_awake == 0);
    assert(fast_reads == 0 && single_reads == 5);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    run_control(130000, NULL, 0, false, false, false, UINT32_MAX - 500);
    assert(sample_count == 5 && send_count == 1);
    run_control(130000, NULL, 0, true, false, false, 0);
    assert(sample_count == 5 && send_count == 1 && pm_calls == 2 && sleep_failed && !auto_sleep);
    run_control(130000, NULL, 0, false, true, false, 0);
    assert(sample_count == 5 && pm_calls == 0 && sleep_failed && !auto_sleep);
    run_control(130000, NULL, 0, false, false, true, 0);
    assert(sample_count == 5 && send_count == 1 && send_times[0] == 60760);
    start_failed = true;
    run_control(130000, NULL, 0, false, false, false, 0);
    assert(sample_count == 5 && send_count == 1 && conversion_sleeps == 4);
    start_failed = false;
    power_external = false;
    run_control(31000, NULL, 0, false, false, false, 0);
    assert(sample_count == 2 && conversion_sleeps == 0 && conversion_awake == 2);
    assert(auto_sleep && send_count == 1);
    power_external = true;
    const event_t conversion_key[] = {{100,1,20}};
    run_control(1000, conversion_key, 1, false, false, false, 0);
    assert(ap_starts == 1 && sample_count == 1 && conversion_sleeps == 1);
    assert(now_ms >= 750 && !auto_sleep);
    assert(button_wakes[0] == 1);
    const event_t keys[] = {{1000,1,300}, {1010,1,0}, {13000,2,40},
        {45000,2,0}, {50000,2,0}, {70000,1,0}};
    run_control(82000, keys, sizeof(keys)/sizeof(keys[0]), false, false, false, 0);
    assert(blocked_keys == 1 && ap && led_enabled && !auto_sleep);
    assert(sample_count == 14 && send_count == 1);
    const uint32_t expected[] = {0,2000,4000,6000,8000,10000,12000,
        42000,70020,72020,74020,76020,78020,80020};
    for (int i = 0; i < 14; i++) assert(sample_times[i] == expected[i]);
    const event_t sleep_keys[] = {{1000,2,0}, {35000,2,0}};
    run_control(130000, sleep_keys, 2, false, false, false, 0);
    assert(sample_count == 5 && send_count == 1 && auto_sleep && !ap && !led_enabled);
    for (int i = 0; i < 5; i++) assert(sample_times[i] == (uint32_t)i * 30000);
    assert(send_times[0] == 30760);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    assert(button_wakes[1] == 2 && button_wakes[0] == 0);
    const int16_t already_hot[] = {270};
    temp_script = already_hot; temp_count = 1;
    run_control(181000, sleep_keys, 2, false, false, false, 0);
    assert(sample_count == 7 && send_count == 2 && auto_sleep && !ap);
    assert(send_times[0] == 760 && send_times[1] == 120760);
    run_control(181000, sleep_keys, 2, false, false, false, UINT32_MAX - 500);
    assert(send_count == 2 && send_times[0] == 760 && send_times[1] == 120760);
    const event_t hot_ap[] = {{1000,1,0}};
    run_control(243000, hot_ap, 1, false, false, false, 0);
    assert(fast_reads == 0 && single_reads == 93);
    assert(send_count == 3 && send_times[0] == 760 && send_times[1] == 120760 && send_times[2] == 240760);
    fail_send_once = true;
    run_control(181000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 3 && send_times[0] == 760 && send_times[1] == 30760 && send_times[2] == 150760);
    enable_down = true;
    run_control(181000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 4 && send_slots[0] == 0 && send_slots[1] == 1);
    assert(send_slots[2] == 0 && send_slots[3] == 1);
    assert(send_times[2] - send_times[0] >= 120000 && send_times[3] - send_times[1] >= 120000);
    enable_down = false;
    run_control(181000, sleep_keys, 2, false, false, true, 0);
    assert(sample_count == 7 && send_count == 2 && auto_sleep);
    assert(send_times[0] == 760 && send_times[1] == 120760);
    temp_script = NULL; temp_count = 0;
    run_control(130000, sleep_keys, 2, true, false, false, 0);
    assert(sample_count == 5 && send_count == 1 && sleep_failed && !auto_sleep);
    const event_t sleep_ap[] = {{1000,1,0}, {5000,2,0}};
    run_control(130000, sleep_ap, 2, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at == 5000 && !ap && !led_enabled && auto_sleep);
    assert(sample_count == 7 && sample_times[3] == 34000 && sample_times[6] == 124000);
    assert(button_wakes[0] == 1);
    assert(send_count == 2 && send_times[0] == 2760 && send_times[1] == 124760);
    const event_t sleep_busy[] = {{1000,1,0}, {2000,3,0}, {3000,2,0},
        {4000,2,0}, {7000,4,0}};
    run_control(40000, sleep_busy, 5, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at >= 7000 && stopped_at <= 7100);
    assert(!ap && !led_enabled && auto_sleep && sample_count == 5);
    assert(sample_times[4] - sample_times[3] == 30000);
    const event_t toggle[] = {{1000,1,0}, {11000,1,300}, {11010,1,0}};
    run_control(72000, toggle, 3, false, false, false, 0);
    assert(ap_starts == 1 && ap_stops == 1 && stopped_at == 11000 && blocked_keys == 1);
    assert(!ap && !led_enabled && auto_sleep && led_level == 1);
    assert(sample_count == 8 && sample_times[6] == 40000 && sample_times[7] == 70000);
    assert(send_count == 1 && send_times[0] == 2760);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    const event_t reopen[] = {{1000,1,0}, {2000,1,0}, {3000,1,0}};
    run_control(7000, reopen, 3, false, false, false, 0);
    assert(ap_starts == 2 && ap_stops == 1 && ap && led_enabled && !auto_sleep);
    const event_t close_busy[] = {{1000,1,0}, {2000,3,0}, {3000,1,0}, {7000,4,0}};
    run_control(8000, close_busy, 4, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at >= 7000 && stopped_at <= 7100);
    assert(!ap && !led_enabled && auto_sleep);
    const event_t cancel_close[] = {{1000,1,0}, {2000,3,0}, {3000,1,0},
        {4000,1,0}, {7000,4,0}};
    run_control(9000, cancel_close, 5, false, false, false, 0);
    assert(ap_starts == 1 && ap_stops == 0 && ap && led_enabled && !auto_sleep);
    const event_t timeout[] = {{1000,1,0}, {100000,6,0}, {180000,6,0}};
    run_control(640000, timeout, 3, false, false, false, 0);
    assert(!ap && !led_enabled && auto_sleep);
    assert(stopped_at == 181000 && sample_count == 106);
    const event_t used[] = {{1000,1,0}, {1100,5,0}, {180000,6,0}};
    run_control(640000, used, 3, false, false, false, 0);
    assert(sample_count == 302 && sample_times[301] == 630000);
    assert(stopped_at == 601100 && !ap && auto_sleep);
    const event_t unused_busy[] = {{1000,1,0}, {180000,3,0}, {190000,4,0}};
    run_control(191000, unused_busy, 3, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at >= 190000 && stopped_at <= 190100);
    const event_t learning[] = {{1000,1,0}, {1100,5,0}, {600000,3,0}, {610000,4,0}};
    run_control(620000, learning, 4, false, false, false, 0);
    assert(!ap && auto_sleep && sample_times[sample_count - 1] == 608000);
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 4199);
    adc_raw = 0;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 0);
    adc_raw = 1023;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 5024);
    adc_raw = UINT16_MAX;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    assert(current.temp_valid);
    adc_error = ESP_FAIL;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_FAIL && current.temp_valid);
    adc_error = ESP_OK; adc_raw = 855;
    run_control(31000, NULL, 0, false, false, true, 0);
    assert(!current.temp_valid && current.battery_valid && current.battery_mv == 3821);
    adc_raw = 888;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4361);
    run_control(31000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3968);
    const event_t battery_ap[] = {{1000,1,0}};
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(ap && current.battery_mv == 4361);
    run_control(31000, NULL, 0, true, false, false, 0);
    assert(current.battery_mv == 4361 && !adc_sleep_seen);
    adc_raw = 783;
    run_control(31000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3500);
    adc_raw = 782;
    run_control(31000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv < 3500);
    adc_raw = UINT16_MAX;
    run_control(31000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    adc_raw = 855;
    led_enabled = false; led_test = true;
    if (!setjmp(finished)) led_task(NULL);
    puts("power control: per-rule 120s IR interval, sleep/recovery, retries, tick wrap, battery and AP lifecycle passed");
    return 0;
}
'''

SENSOR = r'''
#include "freertos/FreeRTOS.h"
static int critical_depth;
#undef portENTER_CRITICAL
#undef portEXIT_CRITICAL
#define portENTER_CRITICAL() assert(critical_depth++ == 0)
#define portEXIT_CRITICAL() assert(--critical_depth == 0)
#include "sensor.c"
static int inputs[256], input_count, input_pos;
static uint8_t commands[16], byte_value;
static int command_count, bit_count, mode, level;
static int direction_calls, fail_direction;
static uint32_t bus_cycles, low_start;

void ets_delay_us(uint32_t us) {
    assert(mode == GPIO_MODE_OUTPUT_OD);
    assert(us == 410 && critical_depth == 0);
}
uint32_t soc_get_ccount(void) {
    assert(mode == GPIO_MODE_OUTPUT_OD && critical_depth == 1);
    bus_cycles += 160; /* One microsecond per deterministic poll. */
    if (GPIO.out_w1tc) {
        assert(GPIO.out_w1tc == (1U << 4));
        GPIO.out_w1tc = 0; level = 0; low_start = bus_cycles;
    }
    if (GPIO.out_w1ts) {
        assert(GPIO.out_w1ts == (1U << 4));
        GPIO.out_w1ts = 0; level = 1;
        uint32_t low_us = (bus_cycles - low_start) / 160;
        if (low_us >= 480 || low_us < 6) {
            assert(input_pos < input_count);
            GPIO.in = inputs[input_pos++] << 4;
        } else {
            assert(low_us == 7 || low_us == 61);
            byte_value |= (low_us == 7) << bit_count++;
            if (bit_count == 8) {
                assert(command_count < 16);
                commands[command_count++] = byte_value;
                byte_value = 0; bit_count = 0;
            }
        }
    }
    return bus_cycles;
}
esp_err_t gpio_set_level(int pin, uint32_t value) {
    assert(pin == 4 && critical_depth == 0); level = value; return ESP_OK;
}
esp_err_t gpio_set_direction(int pin, int value) {
    assert(pin == 4);
    if (++direction_calls == fail_direction) return ESP_FAIL;
    if (value == GPIO_MODE_INPUT) assert(level == 1);
    mode = value; return ESP_OK;
}
static void setup_bus(bool external, bool present) {
    assert(critical_depth == 0);
    input_pos = 0; input_count = 3;
    inputs[0] = !present; inputs[1] = external; inputs[2] = 0;
    command_count = bit_count = byte_value = 0;
    direction_calls = fail_direction = 0;
    mode = GPIO_MODE_OUTPUT_OD; level = 1;
    bus_cycles = low_start = 0;
    GPIO.out_w1tc = GPIO.out_w1ts = 0;
}
static void queue_result(int16_t raw, bool good_crc) {
    uint8_t data[9] = {(uint8_t)raw, (uint8_t)(raw >> 8), 75, 70, 0x7f, 0xff, 12, 16, 0};
    data[8] = crc8(data, 8) ^ (good_crc ? 0 : 1);
    inputs[input_count++] = 0;
    for (int i = 0; i < 9; i++)
        for (int bit = 0; bit < 8; bit++) inputs[input_count++] = (data[i] >> bit) & 1;
}
int main(void) {
    bool external;
    int16_t temp = 999;
    assert(sensor_init() == ESP_OK);
    assert(sensor_start(NULL) == ESP_ERR_INVALID_ARG);
    assert(sensor_finish(NULL) == ESP_ERR_INVALID_ARG);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK && external && mode == GPIO_MODE_INPUT);
    queue_result(400, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 250 && mode == GPIO_MODE_OUTPUT_OD);
    const uint8_t expected[] = {0xcc, 0xb4, 0xcc, 0x44, 0xcc, 0xbe};
    assert(command_count == 6 && memcmp(commands, expected, 6) == 0);
    assert(input_pos == input_count);
    setup_bus(true, true);
    bus_cycles = UINT32_MAX - 1000; /* Counter wrap during the reset pulse. */
    assert(sensor_start(&external) == ESP_OK && external);
    queue_result(432, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 270 && critical_depth == 0);
    setup_bus(false, true);
    assert(sensor_start(&external) == ESP_OK && !external && mode == GPIO_MODE_OUTPUT_OD);
    queue_result(-168, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == -105);
    setup_bus(true, false);
    external = true;
    assert(sensor_start(&external) == ESP_ERR_NOT_FOUND && !external && command_count == 0);
    setup_bus(true, true); inputs[2] = 1;
    assert(sensor_start(&external) == ESP_ERR_NOT_FOUND && !external && command_count == 2);
    setup_bus(true, true); fail_direction = 1;
    assert(sensor_start(&external) == ESP_FAIL && !external && input_pos == 0);
    setup_bus(true, true); fail_direction = 2;
    assert(sensor_start(&external) == ESP_FAIL && !external);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    fail_direction = 3;
    assert(sensor_finish(&temp) == ESP_FAIL);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(400, false); temp = 999;
    queue_result(400, false);
    queue_result(400, false);
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_CRC && temp == 999);
    assert(crc_logs == 3);
    assert(input_pos == input_count && command_count == 10);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(400, false);
    queue_result(400, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 250);
    assert(input_pos == input_count && command_count == 8);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    inputs[input_count++] = 1;
    queue_result(400, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 250);
    assert(input_pos == input_count && command_count == 6);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(0x0550, true);
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_STATE);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    inputs[input_count++] = 1;
    inputs[input_count++] = 1;
    inputs[input_count++] = 1;
    temp = 999;
    assert(sensor_finish(&temp) == ESP_ERR_NOT_FOUND);
    assert(temp == 999 && input_pos == input_count && command_count == 4);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    unsigned old_crc_logs = crc_logs;
    for (int attempt = 0; attempt < 3; attempt++) {
        inputs[input_count++] = 0;
        for (int bit = 0; bit < 72; bit++) inputs[input_count++] = 1;
    }
    temp = 999;
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_CRC && temp == 999);
    assert(crc_logs == old_crc_logs + 3 && input_pos == input_count);
    assert(critical_depth == 0);
    puts("power sensor: reset protection, bounded retries, supply detection, CRC and GPIO errors passed");
    return 0;
}
'''

IR = r'''
#define TEST_IR_NVS
#include <string.h>
#include "freertos/FreeRTOS.h"
static int critical_depth;
static void test_ir_exit(void);
#undef portENTER_CRITICAL
#undef portEXIT_CRITICAL
#define portENTER_CRITICAL() (++critical_depth)
#define portEXIT_CRITICAL() test_ir_exit()
#include "ir.c"
static ir_code_t saved_codes[2], pending_code;
static size_t saved_sizes[2], pending_size;
static int pending_slot;
static bool nvs_enabled, simulate_capture, corrupt_read;
static esp_err_t set_error, commit_error, read_error;
static bool i2s_running, timer_running, semaphore_ready;
static esp_err_t rate_error, start_error, stop_error, alarm_error, timer_error;
static bool send_timeout;
static TaskFunction_t timer_cb;
static uint32_t sample_rate;
static int stop_calls, disarm_calls;
static int alarm_calls;
static bool timer_config_bad;
static unsigned uart_drains;
static bool gpio_direction_failed;
static uint8_t audio_reg;
static unsigned clock_reads, clock_writes, fail_clock_write, bad_clock_read;
static bool invalid_divider;
static unsigned sleep_locks, sleep_lock_calls, sleep_unlock_calls;
static bool ap_on = true;
bool portal_is_on(void) { return ap_on; }
static unsigned start_calls;
static uint32_t cpu_base, cpu_elapsed;
static uint32_t edge_times[100000];
static bool edge_levels[100000], output_high, software_started;
static unsigned edge_count;
static bool nmi_after_high, nmi_injected;
static uint32_t nmi_at, nmi_delay;
static int fail_disarm_call;
static void trace_gpio(void) {
    bool level = output_high;
    if (GPIO.out_w1tc & (1U << 14)) level = false;
    if (GPIO.out_w1ts & (1U << 14)) level = true;
    GPIO.out_w1tc = GPIO.out_w1ts = 0;
    if (level != output_high) {
        assert(edge_count < 100000);
        edge_times[edge_count] = cpu_elapsed;
        edge_levels[edge_count++] = level;
        output_high = level;
    }
}
uint32_t soc_get_ccount(void) {
    assert(critical_depth == 1 && busy && sleep_locks == 1);
    assert(!ap_on && !i2s_running && !timer_running);
    assert(test_pin_func == FUNC_GPIO14 && !tx_i2s_active);
    trace_gpio();
    software_started = true;
    if (!nmi_injected && ((nmi_after_high && output_high) ||
        (nmi_at && cpu_elapsed >= nmi_at))) {
        cpu_elapsed += nmi_delay;
        nmi_injected = true;
    }
    uint32_t value = cpu_base + cpu_elapsed;
    cpu_elapsed += 16; /* Deterministic 0.1 us polling/store observation. */
    return value;
}
static void test_ir_exit(void) {
    assert(critical_depth > 0);
    if (critical_depth == 1 && software_started) trace_gpio();
    critical_depth--;
}
void esp_sleep_lock(void) { assert(sleep_locks == 0); sleep_locks++; sleep_lock_calls++; }
void esp_sleep_unlock(void) { assert(sleep_locks == 1); sleep_locks--; sleep_unlock_calls++; }
int rom_i2c_readReg_Mask(int block, int host, int reg, int msb, int lsb) {
    assert(sleep_locks == 1);
    assert(block == 0x67 && host == 4 && reg == 4 && msb == 7 && lsb == 7);
    clock_reads++;
    int value = (audio_reg >> 7) & 1;
    if (clock_reads == bad_clock_read) return clock_reads == 1 ? 2 : !value;
    return value;
}
void rom_i2c_writeReg_Mask(int block, int host, int reg, int msb, int lsb, int value) {
    assert(block == 0x67 && host == 4 && reg == 4 && msb == 7 && lsb == 7);
    assert(value == 0 || value == 1);
    assert(busy && test_pin_func == FUNC_GPIO14 && uart_drains > 0);
    if (!value) assert(!i2s_running); /* Restore only after stopping I2S. */
    if (++clock_writes != fail_clock_write)
        audio_reg = (audio_reg & 0x7f) | (value << 7);
    assert((audio_reg & 0x7f) == 0x35); /* Never modify adjacent clock/RF bits. */
}
esp_err_t gpio_set_direction(int pin, int mode) {
    assert(pin == 14 && mode == GPIO_MODE_OUTPUT && busy);
    return gpio_direction_failed ? ESP_FAIL : ESP_OK;
}
void uart_tx_wait_idle(uint8_t num) {
    assert(num == 0 && busy);
    assert(test_send_start > 0 || drop_send_logs);
    uart_drains++;
}
static TickType_t learn_tick;
static bool run_learn, task_failed;
TickType_t xTaskGetTickCount(void) { return learn_tick; }
int64_t esp_timer_get_time(void) { return simulate_capture ? 200000 : 0; }
void vTaskDelay(TickType_t ticks) {
    learn_tick += ticks ? ticks : 1;
    if (simulate_capture && !capture_started) {
        capture_started = true; capture_count = 7; first_us = last_us = 0;
        for (int i = 0; i < 7; i++) capture_us[i] = 1000;
    }
}
void vTaskDelete(TaskHandle_t task) { (void)task; }
BaseType_t xTaskCreate(TaskFunction_t fn, const char *name, unsigned stack,
                      void *arg, unsigned pri, TaskHandle_t *handle) {
    (void)name; (void)stack; (void)pri; (void)handle;
    if (task_failed) return pdFALSE;
    if (run_learn) fn(arg); /* Simulate the higher-priority task completing first. */
    return pdPASS;
}
BaseType_t xSemaphoreTake(SemaphoreHandle_t sem, TickType_t ticks) {
    (void)sem;
    if (!ticks) { semaphore_ready = false; return pdFALSE; }
    /* 等待 FRC1 完成时应持有休眠锁，禁止 Idle 任务进入轻度休眠。 */
    assert(sleep_locks == 1 && tx_sleep_locked);
    if (send_timeout) return pdFALSE;
    assert(i2s_running && (audio_reg & 0x80) && test_pin_func == FUNC_I2SI_WS);
    for (int i = 0; i < IR_MAX && timer_running; i++) {
        frc1.ctrl.en = 0;
        if (timer_config_bad) frc1.ctrl.div = 8;
        timer_cb(NULL);
        timer_running = frc1.ctrl.en != 0;
        if (timer_running) {
            assert(frc1.load.data == tx_code->duration[tx_index] * 50U);
            assert(test_pin_func == (tx_index & 1 ? FUNC_GPIO14 : FUNC_I2SI_WS));
        }
    }
    return semaphore_ready ? pdTRUE : pdFALSE;
}
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t sem, BaseType_t *wake) {
    (void)sem; semaphore_ready = true; *wake = pdTRUE; return pdTRUE;
}
esp_err_t gpio_set_level(int pin, uint32_t level) { (void)pin; (void)level; return ESP_OK; }
int gpio_get_level(int pin) { (void)pin; return 1; }
esp_err_t nvs_open(const char *name, int mode, nvs_handle *handle) {
    assert(strcmp(name, "ac") == 0);
    if (!nvs_enabled && mode == NVS_READONLY) return ESP_ERR_NVS_NOT_FOUND;
    *handle = 1; return ESP_OK;
}
esp_err_t nvs_get_u16(nvs_handle handle, const char *key, uint16_t *value) {
    (void)handle; (void)key; (void)value; return ESP_ERR_NVS_NOT_FOUND;
}
esp_err_t nvs_get_blob(nvs_handle handle, const char *key, void *data, size_t *size) {
    assert(handle == 1);
    if (read_error) return read_error;
    int slot = strcmp(key, "ir0") == 0 ? 0 : 1;
    if (!saved_sizes[slot]) return ESP_ERR_NVS_NOT_FOUND;
    if (*size < saved_sizes[slot]) return ESP_ERR_INVALID_SIZE;
    *size = saved_sizes[slot]; memcpy(data, &saved_codes[slot], *size);
    if (corrupt_read) ((uint8_t *)data)[8] ^= 1;
    return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle handle, const char *key, const void *data, size_t size) {
    assert(handle == 1 && size <= sizeof(pending_code));
    if (set_error) return set_error;
    pending_slot = strcmp(key, "ir0") == 0 ? 0 : 1;
    memset(&pending_code, 0, sizeof(pending_code));
    memcpy(&pending_code, data, size); pending_size = size;
    return ESP_OK;
}
esp_err_t nvs_set_u16(nvs_handle handle, const char *key, uint16_t value) {
    (void)handle; (void)key; (void)value; return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle handle) {
    assert(handle == 1);
    if (commit_error) return commit_error;
    saved_codes[pending_slot] = pending_code;
    saved_sizes[pending_slot] = pending_size; nvs_enabled = true;
    return ESP_OK;
}
void app_reset_rule(int slot) { (void)slot; }
esp_err_t i2s_driver_install(int num, const i2s_config_t *cfg, int count, void *queue) {
    (void)num; (void)cfg; (void)count; (void)queue; i2s_running = true; return ESP_OK;
}
esp_err_t i2s_set_pin(int num, const i2s_pin_config_t *pins) { (void)num; (void)pins; return ESP_OK; }
esp_err_t i2s_set_sample_rates(int num, uint32_t rate) {
    assert(uart_drains > 0 && (audio_reg & 0x80));
    assert(I2S0.conf.tx_slave_mod == 0 && I2S0.conf.rx_slave_mod == 0);
    (void)num; sample_rate = rate;
    I2S0.conf.bck_div_num = invalid_divider ? 0 : 3;
    I2S0.conf.clkm_div_num = 44;
    if (rate_error == ESP_OK) i2s_running = true; /* SDK set_clk auto-starts I2S. */
    return rate_error;
}
esp_err_t i2s_start(int num) { (void)num; start_calls++; if (!start_error) i2s_running = true; return start_error; }
esp_err_t i2s_stop(int num) { (void)num; stop_calls++; if (!stop_error) i2s_running = false; return stop_error; }
esp_err_t hw_timer_init(TaskFunction_t cb, void *arg) { (void)arg; timer_cb = cb; return ESP_OK; }
esp_err_t hw_timer_alarm_us(uint32_t us, bool reload) {
    alarm_calls++; frc1.count.data = frc1.load.data = us * 5;
    frc1.ctrl.div = TIMER_CLKDIV_16; frc1.ctrl.reload = reload;
    frc1.ctrl.intr_type = TIMER_EDGE_INT;
    if (!alarm_error) { timer_running = true; frc1.ctrl.en = 1; }
    return alarm_error;
}
esp_err_t hw_timer_disarm(void) {
    disarm_calls++;
    esp_err_t err = disarm_calls == fail_disarm_call ? ESP_FAIL : timer_error;
    if (!err) timer_running = false;
    return err;
}
static void reset_send(void) {
    assert(critical_depth == 0);
    ap_on = true; i2s_pending = tx_i2s_active = false;
    cpu_base = cpu_elapsed = 0; edge_count = 0;
    output_high = software_started = false;
    nmi_after_high = nmi_injected = false; nmi_at = nmi_delay = 0;
    fail_disarm_call = start_calls = sample_rate = 0;
    GPIO.out_w1tc = GPIO.out_w1ts = 0;
    alarm_calls = 0; timer_config_bad = false;
    gpio_direction_failed = false; GPIO.in = 0;
    audio_reg = 0x35; clock_reads = clock_writes = 0;
    fail_clock_write = bad_clock_read = 0; invalid_divider = false;
    clock_pending = false;
    tx_sleep_locked = false;
    sleep_locks = sleep_lock_calls = sleep_unlock_calls = 0;
    send_report = (send_report_t){0}; report_pending = false;
    test_send_reports = 0;
    drop_send_logs = false;
    I2S0.conf.tx_slave_mod = I2S0.conf.rx_slave_mod = 1;
    uart_drains = test_send_start = 0;
    rate_error = start_error = stop_error = alarm_error = timer_error = ESP_OK;
    send_timeout = i2s_running = timer_running = semaphore_ready = busy = false;
    output_idle = true; stop_calls = disarm_calls = 0;
    codes[0] = (ir_code_t){ .version=IR_VERSION, .count=8, .carrier_khz=38 };
    for (int i = 0; i < 8; i++) codes[0].duration[i] = 100;
}
static void check_software(esp_err_t expected) {
    ap_on = false;
    assert(ir_send(0) == expected);
    assert(strcmp(send_report.backend, "software") == 0);
    assert(send_report.error == expected && report_pending && !busy);
    assert(clock_reads == 0 && clock_writes == 0 && !i2s_pending && !clock_pending);
    assert(start_calls == 0 && stop_calls == 0 && sample_rate == 0 && alarm_calls == 0);
    assert(!output_high && test_pin_func == FUNC_GPIO14 && critical_depth == 0);
    uint16_t old_index = tx_index;
    uint32_t old_set = GPIO.out_w1ts, old_clear = GPIO.out_w1tc;
    timer_cb(NULL); /* A stale FRC1 callback cannot change software output. */
    assert(tx_index == old_index && GPIO.out_w1ts == old_set && GPIO.out_w1tc == old_clear);
    if (send_report.timer_stop == ESP_OK) {
        assert(!ir_is_busy() && sleep_locks == 0 && !tx_sleep_locked);
    } else assert(ir_is_busy() && sleep_locks == 1 && tx_sleep_locked);
}
static void check_waveform(unsigned period) {
    uint32_t begin = 0;
    unsigned edge = 0;
    for (int i = 0; i < codes[0].count; i++) {
        uint32_t end = begin + codes[0].duration[i] * 1600U;
        if (!(i & 1)) {
            for (uint32_t pulse = begin; pulse < end; pulse += period) {
                uint32_t low = pulse + period / 2;
                if (low > end) low = end;
                assert(edge + 1 < edge_count);
                assert(edge_levels[edge] && !edge_levels[edge + 1]);
                assert(edge_times[edge] >= pulse && edge_times[edge] - pulse <= 64);
                assert(edge_times[edge + 1] >= low && edge_times[edge + 1] - low <= 64);
                edge += 2;
            }
        }
        begin = end;
    }
    assert(edge == edge_count && cpu_elapsed >= begin && cpu_elapsed - begin <= 96);
    assert(send_report.segments == codes[0].count && send_report.late_cycles <= 64);
}
static void check_cleanup(esp_err_t expected) {
    assert(ir_send(0) == expected);
    assert(stop_calls == 1 && disarm_calls == 1 && !busy);
    assert(send_report.error == expected && send_report.slot == 0 && report_pending);
    assert(GPIO.out_w1tc == (1U << 14) && test_pin_func == FUNC_GPIO14);
    if (stop_error == ESP_OK && timer_error == ESP_OK && !clock_pending) {
        assert(!i2s_running && !timer_running && !ir_is_busy());
        assert(sleep_locks == 0 && sleep_unlock_calls == sleep_lock_calls);
    } else {
        assert(ir_is_busy() && sleep_locks == 1 && tx_sleep_locked);
        assert(sleep_lock_calls == 1 && sleep_unlock_calls == 0);
    }
}
int main(void) {
    assert(ir_init() == ESP_OK && !i2s_running && !timer_running && !ir_is_busy());
    const int carriers[] = {36,38,40};
    for (int i = 0; i < 3; i++) {
        reset_send(); carrier_khz = carriers[i]; check_cleanup(ESP_OK);
        assert(sample_rate == (uint32_t)carriers[i] * 1000);
        assert(uart_drains == 2 && test_send_start == 1);
        assert(alarm_calls == 1 && tx_index == codes[0].count);
        assert(audio_reg == 0x35 && clock_reads == 3 && clock_writes == 2);
    }
    reset_send(); audio_reg = 0xb5; check_cleanup(ESP_OK);
    assert(audio_reg == 0xb5 && clock_before == 1 && !clock_pending);
    reset_send(); codes[0].count = 0; check_cleanup(ESP_ERR_NOT_FOUND);
    assert(uart_drains == 0 && test_send_start == 0 && clock_writes == 0);
    reset_send(); gpio_direction_failed = true; check_cleanup(ESP_FAIL);
    assert(clock_writes == 0);
    reset_send(); bad_clock_read = 1; check_cleanup(ESP_ERR_INVALID_RESPONSE);
    assert(clock_writes == 0 && alarm_calls == 0);
    reset_send(); fail_clock_write = 1; check_cleanup(ESP_ERR_INVALID_RESPONSE);
    assert(audio_reg == 0x35 && !clock_pending && alarm_calls == 0);
    reset_send(); bad_clock_read = 2; check_cleanup(ESP_ERR_INVALID_RESPONSE);
    assert(audio_reg == 0x35 && !clock_pending && alarm_calls == 0);
    reset_send(); fail_clock_write = 2; check_cleanup(ESP_ERR_INVALID_RESPONSE);
    assert(audio_reg == 0xb5 && clock_pending && clock_before == 0 && ir_is_busy());
    fail_clock_write = 0;
    assert(ir_send(0) == ESP_OK && audio_reg == 0x35 && !ir_is_busy());
    assert(!clock_pending && clock_before == 0 && clock_reads == 5);
    assert(sleep_locks == 0 && sleep_lock_calls == 1 && sleep_unlock_calls == 1);
    reset_send(); bad_clock_read = 3; check_cleanup(ESP_ERR_INVALID_RESPONSE);
    assert(clock_pending && ir_is_busy());
    bad_clock_read = 0;
    assert(ir_send(0) == ESP_OK && audio_reg == 0x35 && !ir_is_busy());
    reset_send(); invalid_divider = true; check_cleanup(ESP_ERR_INVALID_STATE);
    assert(audio_reg == 0x35 && alarm_calls == 0);
    reset_send(); timer_config_bad = true; check_cleanup(ESP_ERR_INVALID_STATE);
    reset_send(); check_cleanup(ESP_OK); /* GPIO input stays low throughout TX. */
    assert(GPIO.in == 0 && tx_index == codes[0].count);
    reset_send(); GPIO.in = 1U << 14; check_cleanup(ESP_OK);
    assert(GPIO.in == (1U << 14) && tx_index == codes[0].count);
    reset_send(); codes[0].duration[0] = 8; check_cleanup(ESP_OK);
    assert(tx_index == codes[0].count);
    reset_send(); codes[0].count = 140;
    for (int i = 0; i < 140; i++) codes[0].duration[i] = i & 1 ? 50 : 160;
    check_cleanup(ESP_OK);
    assert(tx_index == 140 && alarm_calls == 1 && GPIO.in == 0);
    /* UART/休眠切换后验证延迟报告，不依赖发送当时的日志。 */
    assert(send_report.segments == 140 && send_report.count == 140);
    assert(send_report.clock_saved == 0 && send_report.clock_enabled == 1 &&
           send_report.clock_restored == 0 && send_report.bck == 3 && send_report.clkm == 44);
    assert(strcmp(send_report.stage, "envelope") == 0 && send_report.seq == 1);
    busy = true; ir_report_last_send(); assert(report_pending && test_send_reports == 0);
    busy = false; ir_report_last_send(); assert(!report_pending && test_send_reports == 1);
    ir_report_last_send(); assert(test_send_reports == 1);
    assert(ir_send(0) == ESP_OK && send_report.seq == 2 && report_pending);
    reset_send(); drop_send_logs = true;
    check_cleanup(ESP_OK);
    assert(test_send_start == 0 && test_send_reports == 0 && report_pending);
    ir_report_last_send(); assert(test_send_reports == 1 && !report_pending);
    drop_send_logs = false;
    reset_send(); rate_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); start_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); alarm_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); send_timeout = true; check_cleanup(ESP_ERR_TIMEOUT);
    assert(strcmp(send_report.stage, "envelope") == 0 && send_report.segments == 0);
    ir_report_last_send(); assert(test_send_reports == 1);
    reset_send(); stop_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    assert(audio_reg == 0xb5 && clock_pending && clock_writes == 1);
    stop_error = ESP_OK;
    assert(ir_send(0) == ESP_OK && !ir_is_busy() && audio_reg == 0x35);
    assert(sleep_locks == 0 && sleep_lock_calls == 1 && sleep_unlock_calls == 1);
    reset_send(); timer_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); alarm_error = ESP_ERR_INVALID_ARG; stop_error = ESP_FAIL;
    check_cleanup(ESP_ERR_INVALID_ARG);
    reset_send(); busy = true; assert(ir_send(0) == ESP_ERR_INVALID_STATE && stop_calls == 0);
    assert(sleep_lock_calls == 0 && !report_pending);
    const unsigned periods[] = {4444, 4211, 4000};
    for (int i = 0; i < 3; i++) {
        reset_send(); carrier_khz = carriers[i];
        check_software(ESP_OK); check_waveform(periods[i]);
        /* 根据观察到的 GPIO 边沿估算载波，而非读取 GPIO_IN。 */
        double hz = 160000000.0 * 20 / (edge_times[40] - edge_times[0]);
        assert(hz > carriers[i] * 999.0 && hz < carriers[i] * 1001.0);
        double duty = (double)(edge_times[1] - edge_times[0]) /
                      (edge_times[2] - edge_times[0]);
        assert(duty > 0.49 && duty < 0.51);
        assert(disarm_calls == 2 && uart_drains == 2);
        assert(send_report.clock_saved == -1 && send_report.clock_enabled == -1 &&
               send_report.clock_restored == -1);
        ir_report_last_send(); assert(test_send_reports == 1 && !report_pending);
    }
    reset_send(); carrier_khz = 38; codes[0].count = 140;
    for (int i = 0; i < 140; i++) codes[0].duration[i] = i & 1 ? 50 : 160;
    codes[0].duration[0] = 900; /* Typical long leading mark. */
    codes[0].duration[138] = 8; /* 80 us and a truncated carrier cycle. */
    codes[0].duration[139] = IR_GAP_UNITS;
    check_software(ESP_OK); check_waveform(4211);
    uint32_t hash_before = code_hash(&codes[0]);
    for (int round = 0; round < 2; round++) {
        /* 模拟休眠后 CPU 计数器重新开始，软件发送不得操作模拟音频时钟。 */
        software_started = output_high = false; edge_count = cpu_elapsed = 0;
        check_software(ESP_OK); check_waveform(4211);
        assert(code_hash(&codes[0]) == hash_before);
    }
    ap_on = true; assert(ir_send(0) == ESP_OK && sample_rate == 38000);
    assert(strcmp(send_report.backend, "i2s") == 0);
    reset_send(); carrier_khz = 38; cpu_base = UINT32_MAX - 1000;
    check_software(ESP_OK); check_waveform(4211);
    reset_send(); carrier_khz = 40;
    codes[0].duration[0] = 65000; codes[0].duration[1] = 9952;
    for (int i = 2; i < 8; i++) codes[0].duration[i] = 8;
    check_software(ESP_OK); check_waveform(4000); /* Exactly 750 ms. */
    reset_send(); codes[0].count = IR_MAX;
    for (int i = 0; i < IR_MAX; i++) codes[0].duration[i] = 8;
    carrier_khz = 38; check_software(ESP_OK); check_waveform(4211);
    reset_send(); codes[0].duration[0] = 65000; codes[0].duration[1] = 10000;
    check_software(ESP_ERR_NOT_FOUND); assert(!software_started);
    reset_send(); nmi_after_high = true; nmi_delay = 50 * 160;
    check_software(ESP_ERR_TIMEOUT);
    assert(nmi_injected && send_report.segments == 0 && send_report.late_cycles > 800);
    reset_send(); nmi_at = 2000 * 160 - 16; nmi_delay = 50 * 160;
    check_software(ESP_ERR_TIMEOUT);
    assert(nmi_injected && send_report.segments == 1 && send_report.late_cycles > 800);
    reset_send(); nmi_after_high = true; nmi_delay = 4 * 160;
    check_software(ESP_OK); assert(send_report.late_cycles <= 800);
    reset_send(); timer_error = ESP_FAIL; check_software(ESP_FAIL);
    assert(!software_started && send_report.segments == 0);
    timer_error = ESP_OK; check_software(ESP_OK);
    assert(sleep_lock_calls == 1 && sleep_unlock_calls == 1);
    reset_send(); fail_disarm_call = 2; check_software(ESP_FAIL);
    assert(send_report.segments == 8 && sleep_locks == 1);
    fail_disarm_call = 0; software_started = false; cpu_elapsed = edge_count = 0;
    check_software(ESP_OK); assert(sleep_lock_calls == 1 && sleep_unlock_calls == 1);
    reset_send(); gpio_direction_failed = true; check_software(ESP_FAIL);
    assert(!software_started);
    reset_send(); clock_pending = true; clock_before = 0; ap_on = false;
    assert(ir_send(0) == ESP_ERR_INVALID_STATE && clock_pending && sleep_locks == 1);
    assert(!software_started && clock_reads == 0 && stop_calls == 0);
    ap_on = true; assert(ir_send(0) == ESP_OK && !clock_pending && sleep_locks == 0);
    reset_send(); i2s_pending = true; ap_on = false;
    assert(ir_send(0) == ESP_ERR_INVALID_STATE && i2s_pending && sleep_locks == 1);
    assert(!software_started && clock_reads == 0 && stop_calls == 0);
    ap_on = true; assert(ir_send(0) == ESP_OK && !i2s_pending && sleep_locks == 0);
    reset_send(); drop_send_logs = true; check_software(ESP_OK);
    assert(test_send_start == 0 && report_pending);
    ir_report_last_send(); assert(test_send_reports == 1 && !report_pending);
    reset_send(); task_failed = true;
    assert(ir_start_learn(0) == ESP_ERR_NO_MEM && test_learn_wait == 0 && !busy);
    task_failed = false; run_learn = true;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR && !busy);
    assert(ir_last_error() == ESP_ERR_TIMEOUT);
    assert(test_learn_wait > 0 && test_learn_wait < test_learn_end);
    simulate_capture = true;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_SAVED && !busy);
    uint32_t saved_hash = code_hash(&codes[0]);
    assert(saved_sizes[0] == 22 && ir_has_code(0));
    assert(ir_start_learn(1) == ESP_OK && ir_state() == IR_SAVED && ir_has_code(1));
    assert(memcmp(&codes[0], &saved_codes[0], saved_sizes[0]) == 0);
    memset(codes, 0, sizeof(codes)); /* Lose RAM while preserving committed NVS. */
    assert(ir_init() == ESP_OK && ir_has_code(0) && ir_has_code(1));
    assert(code_hash(&codes[0]) == saved_hash);
    assert(ir_send(0) == ESP_OK && code_hash(&codes[0]) == saved_hash);
    reset_send(); codes[0] = saved_codes[0]; carrier_khz = 38;
    check_software(ESP_OK); check_waveform(4211);
    assert(code_hash(&codes[0]) == saved_hash); /* Same NVS blob, no re-learning. */
    ap_on = true;
    set_error = ESP_FAIL;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR);
    assert(ir_last_error() == ESP_FAIL && code_hash(&codes[0]) == saved_hash);
    set_error = ESP_OK; commit_error = ESP_FAIL;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR);
    assert(ir_last_error() == ESP_FAIL && code_hash(&codes[0]) == saved_hash);
    commit_error = ESP_OK; corrupt_read = true;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR);
    assert(ir_last_error() == ESP_ERR_INVALID_RESPONSE && code_hash(&codes[0]) == saved_hash);
    corrupt_read = false; read_error = ESP_FAIL;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR);
    assert(ir_last_error() == ESP_FAIL && code_hash(&codes[0]) == saved_hash);
    read_error = ESP_OK;
    saved_codes[0].version = 99;
    memset(codes, 0, sizeof(codes));
    assert(ir_init() == ESP_OK && !ir_has_code(0) && ir_has_code(1));
    puts("power IR: I2S/software edges, full frames, wrap/NMI, sleep lock/retry, deferred outcome, clock errors, cleanup and NVS passed");
    return 0;
}
'''


def main():
    gcc = shutil.which("gcc")
    if gcc is None:
        raise FileNotFoundError("找不到主机 gcc；请使用规则测试所需的现有 GCC")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sdk_mock.h").write_text(SDK, encoding="utf-8")
    for name in HEADERS:
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#include "sdk_mock.h"\n', encoding="utf-8")
    for name, source in [("control", CONTROL), ("sensor", SENSOR), ("ir", IR)]:
        path = OUT / f"{name}_test.c"
        # 公共 mock 接在场景源码后，函数原型由 sdk_mock.h 提供。
        path.write_text(source + COMMON, encoding="utf-8")
        exe = OUT / f"{name}_test.exe"
        command = [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-parameter", "-I", str(OUT), "-I", str(ROOT / "main"),
                   str(path)]
        if name == "control":
            command.append(str(ROOT / "main" / "rules.c"))
        subprocess.run(command + ["-o", str(exe)], check=True, cwd=ROOT)
        subprocess.run([str(exe)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
