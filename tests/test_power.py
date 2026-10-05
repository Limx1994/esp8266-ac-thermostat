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
    "esp_sleep.h", "esp_log.h", "esp_attr.h", "esp_timer.h", "esp_err.h",
    "nvs.h", "nvs_flash.h", "rom/ets_sys.h",
]

SDK = r'''
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
extern unsigned test_log_seq, test_learn_wait, test_learn_end;
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
struct mock_gpio {
    uint32_t in, out_w1tc, out_w1ts, status, status_w1tc;
    struct { int int_type; bool wakeup_enable; } pin[17];
};
extern struct mock_gpio GPIO;
extern int test_pin_func;
#define CONFIG_ESP8266_DEFAULT_CPU_FREQ_160 1
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
int gpio_get_level(gpio_num_t);
esp_err_t gpio_set_intr_type(gpio_num_t, gpio_int_type_t);
esp_err_t gpio_wakeup_enable(gpio_num_t, gpio_int_type_t);
esp_err_t gpio_isr_handler_add(gpio_num_t, TaskFunction_t, void *);
esp_err_t gpio_isr_handler_remove(gpio_num_t);
esp_err_t gpio_install_isr_service(int);
esp_err_t esp_pm_configure(const void *);
esp_err_t esp_sleep_enable_gpio_wakeup(void);
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
int test_pin_func;
unsigned test_log_seq, test_learn_wait, test_learn_end;
void test_log(const char *tag, const char *fmt, ...) {
    (void)tag;
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
esp_err_t nvs_set_blob(nvs_handle handle, const char *key, const void *data, size_t size) {
    (void)handle; (void)key; (void)data; (void)size; return ESP_OK;
}
esp_err_t nvs_set_u16(nvs_handle handle, const char *key, uint16_t value) {
    (void)handle; (void)key; (void)value; return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle handle) { (void)handle; return ESP_OK; }
'''

CONTROL = r'''
#include <setjmp.h>
#include <string.h>
#include "main.c"
static jmp_buf finished;
static TickType_t start_tick;
static uint32_t now_ms, end_ms, notified, ap_start, hold_until[17];
static uint32_t sample_times[512], send_times[16];
static int sample_count, send_count, pm_calls, blocked_keys;
static int ap_starts, ap_stops;
static uint32_t stopped_at;
static bool ap, ap_used, ir_busy, fail_pm, fail_wakeup, sensor_error;
static bool led_test;
static uint16_t adc_raw = 855;
static esp_err_t adc_error = ESP_OK;
static int battery_reads;
static bool power_external = true, start_failed, conversion_pending;
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
    return ESP_OK;
}
esp_err_t sensor_init(void) { return ESP_OK; }
esp_err_t adc_init(adc_config_t *cfg) {
    assert(cfg->mode == ADC_READ_TOUT_MODE && cfg->clk_div == 8);
    return ESP_OK;
}
esp_err_t adc_read(uint16_t *raw) {
    assert(!auto_sleep);
    battery_reads++;
    *raw = adc_raw;
    return adc_error;
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
    *temp = temperatures[sample_count <= 5 ? sample_count - 1 : 4];
    return sensor_error && sample_count == 2 ? ESP_ERR_INVALID_CRC : ESP_OK;
}
esp_err_t ir_init(void) { return ESP_OK; }
bool ir_has_code(int slot) { (void)slot; return true; }
bool ir_is_busy(void) { return ir_busy; }
ir_state_t ir_state(void) { return ir_busy ? IR_WAITING : IR_IDLE; }
esp_err_t ir_send(int slot) {
    (void)slot; assert(!auto_sleep && !ir_busy && send_count < 16);
    send_times[send_count++] = now_ms; return ESP_OK;
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
static void run_control(uint32_t duration, const event_t *script, size_t count,
                        bool pm_error, bool wake_error, bool temp_error, TickType_t base) {
    memset(&GPIO, 0, sizeof(GPIO)); memset(&current, 0, sizeof(current));
    memset(states, 0, sizeof(states)); memset(hold_until, 0, sizeof(hold_until));
    s1_pending = s2_pending = led_enabled = auto_sleep = sleep_failed = false;
    ap = ap_used = ir_busy = false;
    fail_pm = pm_error; fail_wakeup = wake_error; sensor_error = temp_error;
    sample_count = send_count = pm_calls = blocked_keys = 0;
    battery_reads = 0;
    conversion_pending = false;
    conversion_sleeps = conversion_awake = 0;
    ap_starts = ap_stops = 0; stopped_at = 0;
    now_ms = notified = 0; start_tick = base; end_ms = duration;
    events = script; event_count = count; event_pos = 0;
    if (!setjmp(finished)) app_main();
    assert(battery_reads == sample_count);
}
int main(void) {
    run_control(130000, NULL, 0, false, false, false, 0);
    assert(sample_count == 5 && send_count == 2 && auto_sleep && !led_enabled);
    for (int i = 0; i < 5; i++) assert(sample_times[i] == (uint32_t)i * 30000);
    assert(send_times[0] == 30760 && send_times[1] == 120760);
    assert(conversion_sleeps == 5 && conversion_awake == 0);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    run_control(130000, NULL, 0, false, false, false, UINT32_MAX - 500);
    assert(sample_count == 5 && send_count == 2);
    run_control(130000, NULL, 0, true, false, false, 0);
    assert(sample_count == 5 && send_count == 2 && pm_calls == 2 && sleep_failed && !auto_sleep);
    run_control(130000, NULL, 0, false, true, false, 0);
    assert(sample_count == 5 && pm_calls == 0 && sleep_failed && !auto_sleep);
    run_control(130000, NULL, 0, false, false, true, 0);
    assert(sample_count == 5 && send_count == 1 && send_times[0] == 120760);
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
    const event_t keys[] = {{1000,1,300}, {1010,1,0}, {13000,2,40},
        {45000,2,0}, {50000,2,0}, {70000,1,0}};
    run_control(82000, keys, sizeof(keys)/sizeof(keys[0]), false, false, false, 0);
    assert(blocked_keys == 1 && ap && led_enabled && !auto_sleep);
    assert(sample_count == 14 && send_count == 2);
    const uint32_t expected[] = {0,2000,4000,6000,8000,10000,12000,
        45020,70020,72020,74020,76020,78020,80020};
    for (int i = 0; i < 14; i++) assert(sample_times[i] == expected[i]);
    const event_t toggle[] = {{1000,1,0}, {11000,1,300}, {11010,1,0}};
    run_control(72000, toggle, 3, false, false, false, 0);
    assert(ap_starts == 1 && ap_stops == 1 && stopped_at == 11000 && blocked_keys == 1);
    assert(!ap && !led_enabled && auto_sleep && led_level == 1);
    assert(sample_count == 8 && sample_times[6] == 40000 && sample_times[7] == 70000);
    assert(send_count == 2 && send_times[0] == 2760 && send_times[1] == 8760);
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
    assert(!current.temp_valid && current.battery_valid && current.battery_mv == 4199);
    led_enabled = false; led_test = true;
    if (!setjmp(finished)) led_task(NULL);
    puts("power control: battery, intervals, rules, tick wrap, buttons, pause, AP timeout and PM failures passed");
    return 0;
}
'''

SENSOR = r'''
#include "sensor.c"
static int inputs[80], input_count, input_pos;
static uint8_t commands[8], byte_value;
static int command_count, bit_count, mode, level;
static int direction_calls, fail_direction;

void ets_delay_us(uint32_t us) {
    assert(mode == GPIO_MODE_OUTPUT_OD);
    if (level == 0 && (us == 6 || us == 60)) {
        byte_value |= (us == 6) << bit_count++;
        if (bit_count == 8) {
            assert(command_count < 8);
            commands[command_count++] = byte_value;
            byte_value = 0; bit_count = 0;
        }
    }
}
esp_err_t gpio_set_level(int pin, uint32_t value) {
    assert(pin == 4); level = value; return ESP_OK;
}
esp_err_t gpio_set_direction(int pin, int value) {
    assert(pin == 4);
    if (++direction_calls == fail_direction) return ESP_FAIL;
    if (value == GPIO_MODE_INPUT) assert(level == 1);
    mode = value; return ESP_OK;
}
int gpio_get_level(int pin) {
    assert(pin == 4 && input_pos < input_count);
    return inputs[input_pos++];
}
static void setup_bus(bool external, bool present) {
    input_pos = 0; input_count = 3;
    inputs[0] = !present; inputs[1] = external; inputs[2] = 0;
    command_count = bit_count = byte_value = 0;
    direction_calls = fail_direction = 0;
    mode = GPIO_MODE_OUTPUT_OD; level = 1;
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
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_CRC && temp == 999);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(0x0550, true);
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_STATE);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    inputs[input_count++] = 1;
    assert(sensor_finish(&temp) == ESP_ERR_NOT_FOUND);
    puts("power sensor: supply detection, DQ release, commands, CRC, negative temperature and GPIO errors passed");
    return 0;
}
'''

IR = r'''
#include <string.h>
#include "ir.c"
static bool i2s_running, timer_running, semaphore_ready;
static esp_err_t rate_error, start_error, stop_error, alarm_error, timer_error;
static bool send_timeout;
static TaskFunction_t timer_cb;
static uint32_t sample_rate;
static int stop_calls, disarm_calls;
static TickType_t learn_tick;
static bool run_learn, task_failed;
TickType_t xTaskGetTickCount(void) { return learn_tick; }
int64_t esp_timer_get_time(void) { return 0; }
void vTaskDelay(TickType_t ticks) { learn_tick += ticks ? ticks : 1; }
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
    if (send_timeout) return pdFALSE;
    for (int i = 0; i < IR_MAX && timer_running; i++) {
        timer_running = false; timer_cb(NULL);
    }
    return semaphore_ready ? pdTRUE : pdFALSE;
}
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t sem, BaseType_t *wake) {
    (void)sem; semaphore_ready = true; *wake = pdTRUE; return pdTRUE;
}
esp_err_t gpio_set_level(int pin, uint32_t level) { (void)pin; (void)level; return ESP_OK; }
int gpio_get_level(int pin) { (void)pin; return 1; }
esp_err_t nvs_open(const char *name, int mode, nvs_handle *handle) {
    (void)name; (void)mode; (void)handle; return ESP_ERR_NVS_NOT_FOUND;
}
esp_err_t nvs_get_u16(nvs_handle handle, const char *key, uint16_t *value) {
    (void)handle; (void)key; (void)value; return ESP_ERR_NVS_NOT_FOUND;
}
esp_err_t nvs_get_blob(nvs_handle handle, const char *key, void *data, size_t *size) {
    (void)handle; (void)key; (void)data; (void)size; return ESP_ERR_NVS_NOT_FOUND;
}
void app_reset_rule(int slot) { (void)slot; }
esp_err_t i2s_driver_install(int num, const i2s_config_t *cfg, int count, void *queue) {
    (void)num; (void)cfg; (void)count; (void)queue; i2s_running = true; return ESP_OK;
}
esp_err_t i2s_set_pin(int num, const i2s_pin_config_t *pins) { (void)num; (void)pins; return ESP_OK; }
esp_err_t i2s_set_sample_rates(int num, uint32_t rate) {
    (void)num; sample_rate = rate;
    if (rate_error == ESP_OK) i2s_running = true; /* SDK set_clk auto-starts I2S. */
    return rate_error;
}
esp_err_t i2s_start(int num) { (void)num; if (!start_error) i2s_running = true; return start_error; }
esp_err_t i2s_stop(int num) { (void)num; stop_calls++; if (!stop_error) i2s_running = false; return stop_error; }
esp_err_t hw_timer_init(TaskFunction_t cb, void *arg) { (void)arg; timer_cb = cb; return ESP_OK; }
esp_err_t hw_timer_alarm_us(uint32_t us, bool reload) {
    (void)us; (void)reload; if (!alarm_error) timer_running = true; return alarm_error;
}
esp_err_t hw_timer_disarm(void) {
    disarm_calls++; if (!timer_error) timer_running = false; return timer_error;
}
static void reset_send(void) {
    rate_error = start_error = stop_error = alarm_error = timer_error = ESP_OK;
    send_timeout = i2s_running = timer_running = semaphore_ready = busy = false;
    output_idle = true; stop_calls = disarm_calls = 0;
    codes[0] = (ir_code_t){ .version=IR_VERSION, .count=8, .carrier_khz=38 };
    for (int i = 0; i < 8; i++) codes[0].duration[i] = 100;
}
static void check_cleanup(esp_err_t expected) {
    assert(ir_send(0) == expected);
    assert(stop_calls == 1 && disarm_calls == 1 && !busy);
    assert(GPIO.out_w1tc == (1U << 14) && test_pin_func == FUNC_GPIO14);
    if (stop_error == ESP_OK && timer_error == ESP_OK)
        assert(!i2s_running && !timer_running && !ir_is_busy());
    else assert(ir_is_busy());
}
int main(void) {
    assert(ir_init() == ESP_OK && !i2s_running && !timer_running && !ir_is_busy());
    const int carriers[] = {36,38,40};
    for (int i = 0; i < 3; i++) {
        reset_send(); carrier_khz = carriers[i]; check_cleanup(ESP_OK);
        assert(sample_rate == (uint32_t)carriers[i] * 1000);
    }
    reset_send(); codes[0].count = 0; check_cleanup(ESP_ERR_NOT_FOUND);
    reset_send(); rate_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); start_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); alarm_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); send_timeout = true; check_cleanup(ESP_ERR_TIMEOUT);
    reset_send(); stop_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    stop_error = ESP_OK; assert(ir_send(0) == ESP_OK && !ir_is_busy());
    reset_send(); timer_error = ESP_FAIL; check_cleanup(ESP_FAIL);
    reset_send(); alarm_error = ESP_ERR_INVALID_ARG; stop_error = ESP_FAIL;
    check_cleanup(ESP_ERR_INVALID_ARG);
    reset_send(); busy = true; assert(ir_send(0) == ESP_ERR_INVALID_STATE && stop_calls == 0);
    reset_send(); task_failed = true;
    assert(ir_start_learn(0) == ESP_ERR_NO_MEM && test_learn_wait == 0 && !busy);
    task_failed = false; run_learn = true;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR && !busy);
    assert(ir_last_error() == ESP_ERR_TIMEOUT);
    assert(test_learn_wait > 0 && test_learn_wait < test_learn_end);
    puts("power IR: init, carriers, timeout, cleanup, recovery and learning log order passed");
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
        # Common mocks are appended after the source; prototypes are in sdk_mock.h.
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
