r"""Compile the actual control/IR sources against deterministic host SDK mocks.

Run from the repository root: python tests\test_power.py
Generated headers and executables stay in the ignored build_ascii directory.
These tests verify control flow, not ESP8266 sleep current or hardware timing.
"""

from pathlib import Path
import os
import re
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build_ascii" / "power_test"
HEADERS = [
    "freertos/FreeRTOS.h", "freertos/task.h", "freertos/semphr.h", "freertos/queue.h",
    "driver/gpio.h", "driver/adc.h", "driver/hw_timer.h", "driver/i2s.h", "driver/soc.h",
    "driver/rtc.h", "esp_clk.h",
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
typedef void *QueueHandle_t;
typedef struct { unsigned unused; } List_t;
#define configMAX_TASK_NAME_LEN 16
typedef void *SemaphoreHandle_t;
typedef void (*TaskFunction_t)(void *);
typedef int nvs_handle;
typedef int gpio_num_t;
typedef int gpio_int_type_t;
enum { ESP_OK, ESP_FAIL, ESP_ERR_INVALID_ARG, ESP_ERR_INVALID_STATE,
       ESP_ERR_NO_MEM, ESP_ERR_NOT_FOUND, ESP_ERR_TIMEOUT, ESP_ERR_INVALID_SIZE,
       ESP_ERR_INVALID_RESPONSE, ESP_ERR_INVALID_CRC, ESP_ERR_NVS_NOT_FOUND };
enum { GPIO_NUM_0=0, GPIO_NUM_1=1, GPIO_NUM_2=2, GPIO_NUM_4=4, GPIO_NUM_5=5, GPIO_NUM_12=12,
       GPIO_NUM_13=13, GPIO_NUM_14=14, GPIO_NUM_15=15 };
enum { ESP_LOG_NONE };
typedef int (*putchar_like_t)(int);
void esp_log_level_set(const char *, int);
putchar_like_t esp_log_set_putchar(putchar_like_t);
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
#define CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ TEST_CPU_MHZ
typedef enum { RTC_CPU_FREQ_80M, RTC_CPU_FREQ_160M } rtc_cpu_freq_t;
rtc_cpu_freq_t rtc_clk_cpu_freq_get(void);
int esp_clk_cpu_freq(void);
typedef uint32_t esp_irqflag_t;
esp_irqflag_t soc_save_local_irq(void);
void soc_restore_local_irq(esp_irqflag_t);
extern volatile uint32_t test_rtc_counter;
#define RTC_SLP_CNT_VAL 0
uint32_t test_read_reg(uint32_t);
#define REG_READ(reg) test_read_reg(reg)
extern uint32_t g_esp_ticks_per_us;
uint32_t soc_get_ccompare(void);
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
char *pcTaskGetName(TaskHandle_t);
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
#ifdef TEST_SLEEP_TRACE
    assert(irq_state == 0); /* 入口不打印，汇总在恢复中断后输出。 */
    assert(strcmp(tag, "sleep_trace") == 0);
    assert(strstr(fmt, "%ll") == NULL); /* 设备启用 nano printf，不能依赖主机的 ll 支持。 */
    va_list args;
    va_start(args, fmt);
    vsnprintf(trace_output[trace_lines % 64], sizeof(trace_output[0]), fmt, args);
    va_end(args);
    trace_lines++;
#endif
#ifdef TEST_IR_NVS
    assert(critical_depth == 0); /* No Flash/logging calls during a frame. */
    if (strstr(fmt, "waiting for IR"))
        assert(GPIO.pin[5].int_type == GPIO_INTR_ANYEDGE && rx_handler == capture_isr);
    if (strstr(fmt, "learn slot %d failed") || strstr(fmt, "learn slot %d saved"))
        assert(GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    if (strstr(fmt, "IR RX callback removal failed")) rx_cleanup_logs++;
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
#ifdef TEST_IDLE_PINS
    if (cfg->pin_bit_mask & ((1U << 0) | (1U << 1) | (1U << 15))) {
        assert(cfg->mode == GPIO_MODE_INPUT && cfg->pull_up_en == GPIO_PULLUP_DISABLE);
        assert(cfg->pull_down_en == GPIO_PULLDOWN_DISABLE && cfg->intr_type == GPIO_INTR_DISABLE);
        if (cfg->pin_bit_mask == (1U << 1)) assert(quiet_installed && uart_drained);
        idle_pin_mask |= cfg->pin_bit_mask;
        if (fail_idle_config) return ESP_FAIL;
    }
#endif
#ifdef TEST_IR_NVS
    if (cfg->pin_bit_mask & (1U << 5)) {
        assert(cfg->mode == GPIO_MODE_INPUT && cfg->pull_up_en == GPIO_PULLUP_ENABLE);
        assert(cfg->pull_down_en == GPIO_PULLDOWN_DISABLE && cfg->intr_type == GPIO_INTR_DISABLE);
        rx_pullup = true;
    }
#endif
    for (int i = 0; i < 17; i++)
        if (cfg->pin_bit_mask & (1ULL << i)) GPIO.pin[i].int_type = cfg->intr_type;
    return ESP_OK;
}
esp_err_t gpio_set_intr_type(int pin, int type) {
#ifdef TEST_IR_NVS
    assert(pin == 5 && type == GPIO_INTR_ANYEDGE && rx_handler == capture_isr);
    assert(GPIO.pin[5].int_type == GPIO_INTR_DISABLE && GPIO.status_w1tc == (1U << 5));
    rx_enable_calls++;
    if (rx_enable_error) return rx_enable_error;
#endif
    GPIO.pin[pin].int_type = type; return ESP_OK;
}
esp_err_t gpio_isr_handler_add(int pin, TaskFunction_t cb, void *arg) {
#ifdef TEST_IR_NVS
    assert(pin == 5 && rx_pullup && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    assert(cb == capture_isr && arg == NULL);
    rx_add_calls++;
    if (rx_add_error) return rx_add_error;
    rx_handler = cb;
#endif
    (void)pin; (void)cb; (void)arg; return ESP_OK;
}
esp_err_t gpio_isr_handler_remove(int pin) {
#ifdef TEST_IR_NVS
    assert(pin == 5 && critical_depth == 0 && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    assert(GPIO.status_w1tc == (1U << 5));
    rx_remove_calls++;
    if (rx_remove_error) return rx_remove_error;
    rx_handler = NULL;
#endif
    (void)pin; return ESP_OK;
}
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
#define TEST_IDLE_PINS
#include <setjmp.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
static int critical_depth;
static bool quiet_installed, uart_drained, fail_idle_config;
static uint64_t idle_pin_mask;
#undef portENTER_CRITICAL
#undef portEXIT_CRITICAL
#define portENTER_CRITICAL() (++critical_depth)
#define portEXIT_CRITICAL() assert(--critical_depth >= 0)
#include "main.c"
void esp_log_level_set(const char *tag, int level) {
    assert(strcmp(tag, "*") == 0 && level == ESP_LOG_NONE);
}
putchar_like_t esp_log_set_putchar(putchar_like_t fn) {
    assert(fn('x') == 'x'); quiet_installed = true; return NULL;
}
void uart_tx_wait_idle(uint8_t uart) {
    assert(uart == 0 && quiet_installed); uart_drained = true;
}
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
static unsigned trace_report_calls;
static TickType_t max_notify_wait;
void sleep_trace_report(void) {
    assert(!auto_sleep);
    trace_report_calls++;
}
static unsigned cpu_mhz = TEST_CPU_MHZ;
static unsigned cpu_hz = TEST_CPU_MHZ * 1000000U;
int esp_clk_cpu_freq(void) { return cpu_hz; }
rtc_cpu_freq_t rtc_clk_cpu_freq_get(void) {
    return cpu_mhz == 80 ? RTC_CPU_FREQ_80M : RTC_CPU_FREQ_160M;
}
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
    assert(ticks <= pdMS_TO_TICKS(SLEEP_WAIT_MS));
    if (ticks > max_notify_wait) max_notify_wait = ticks;
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
    trace_report_calls = 0;
    max_notify_wait = 0;
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
    fail_idle_config = true;
#if defined(CONFIG_APP_IDLE_BOOT_PINS) || defined(CONFIG_APP_QUIET_UART)
    assert(init_idle_pins() == ESP_FAIL);
#else
    assert(init_idle_pins() == ESP_OK);
#endif
    fail_idle_config = false;
    idle_pin_mask = 0;
    assert(init_idle_pins() == ESP_OK);
#ifdef CONFIG_APP_IDLE_BOOT_PINS
    assert((idle_pin_mask & ((1U << 0) | (1U << 15))) == ((1U << 0) | (1U << 15)));
#endif
#ifdef CONFIG_APP_QUIET_UART
    assert(quiet_installed && uart_drained && (idle_pin_mask & (1U << 1)));
#endif
    assert(check_cpu_freq() == ESP_OK);
    cpu_mhz = TEST_CPU_MHZ == 80 ? 160 : 80;
    assert(check_cpu_freq() == ESP_ERR_INVALID_STATE);
    cpu_mhz = TEST_CPU_MHZ;
    cpu_hz = (TEST_CPU_MHZ == 80 ? 160 : 80) * 1000000U;
    assert(check_cpu_freq() == ESP_ERR_INVALID_STATE);
    cpu_hz = TEST_CPU_MHZ * 1000000U;
    const int16_t reported[] = {259, 260, 261};
    for (unsigned i = 0; i < sizeof(reported) / sizeof(reported[0]); i++) {
        temp_script = &reported[i]; temp_count = 1;
        run_control(1000, NULL, 0, false, false, false, 0);
        app_status_t snapshot;
        app_get_status(&snapshot);
        assert(snapshot.temp_valid && snapshot.temp10 == reported[i]);
        assert(send_count == (reported[i] >= 260));
    }
    temp_script = NULL; temp_count = 0;
    run_control(130000, NULL, 0, false, false, false, 0);
    assert(trace_report_calls == 3);
    assert(sample_count == 3 && send_count == 1 && auto_sleep && !led_enabled);
    for (int i = 0; i < 3; i++) assert(sample_times[i] == (uint32_t)i * 60000);
    assert(send_times[0] == 60760);
    assert(conversion_sleeps == 3 && conversion_awake == 0);
    assert(max_notify_wait == pdMS_TO_TICKS(SLEEP_WAIT_MS));
    assert(fast_reads == 0 && single_reads == 3);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    run_control(130000, NULL, 0, false, false, false, UINT32_MAX - 500);
    assert(sample_count == 3 && send_count == 1);
    run_control(130000, NULL, 0, true, false, false, 0);
    assert(sample_count == 3 && send_count == 1 && pm_calls == 2 && sleep_failed && !auto_sleep);
    run_control(130000, NULL, 0, false, true, false, 0);
    assert(sample_count == 3 && pm_calls == 0 && sleep_failed && !auto_sleep);
    run_control(130000, NULL, 0, false, false, true, 0);
    assert(sample_count == 3 && send_count == 1 && send_times[0] == 120760);
    start_failed = true;
    run_control(130000, NULL, 0, false, false, false, 0);
    assert(sample_count == 3 && send_count == 1 && conversion_sleeps == 2);
    start_failed = false;
    power_external = false;
    run_control(61000, NULL, 0, false, false, false, 0);
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
    assert(sample_count == 13 && send_count == 0 && trend.count == 0);
    const uint32_t expected[] = {0,2000,4000,6000,8000,10000,12000,
        70020,72020,74020,76020,78020,80020};
    for (int i = 0; i < 13; i++) assert(sample_times[i] == expected[i]);
    const event_t sleep_keys[] = {{1000,2,0}, {35000,2,0}};
    run_control(130000, sleep_keys, 2, false, false, false, 0);
    assert(sample_count == 3 && send_count == 1 && auto_sleep && !ap && !led_enabled);
    for (int i = 0; i < 3; i++) assert(sample_times[i] == (uint32_t)i * 60000);
    assert(send_times[0] == 60760);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    assert(button_wakes[1] == 2 && button_wakes[0] == 0);
    const int16_t already_hot[] = {270};
    temp_script = already_hot; temp_count = 1;
    run_control(180000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 1 && send_times[0] == 760);
    run_control(181000, sleep_keys, 2, false, false, false, 0);
    assert(sample_count == 4 && send_count == 1 && auto_sleep && !ap);
    assert(trend.interval_ms == 600000);
    run_control(601000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 2 && send_times[0] == 760 && send_times[1] == 600760);
    run_control(601000, sleep_keys, 2, false, false, false, UINT32_MAX - 500);
    assert(send_count == 2 && send_times[0] == 760 && send_times[1] == 600760);
    const event_t hot_ap[] = {{1000,1,0}};
    run_control(243000, hot_ap, 1, false, false, false, 0);
    assert(fast_reads == 0 && single_reads == 92);
    assert(send_count == 1 && send_times[0] == 760);
    assert(trend.count == 1 && trend.interval_ms == 600000);
    fail_send_once = true;
    run_control(661000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 3 && send_times[0] == 760 && send_times[1] == 60760 && send_times[2] == 660760);
    enable_down = true;
    run_control(661000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 4 && send_slots[0] == 0 && send_slots[1] == 1);
    assert(send_slots[2] == 0 && send_slots[3] == 1);
    assert(send_times[2] - send_times[0] == 600000);
    /* 第二组首发晚 500 ms，十分钟边界尚未满足，延后到下一次采样。 */
    assert(send_times[3] - send_times[1] == 659500);
    enable_down = false;
    run_control(181000, sleep_keys, 2, false, false, true, 0);
    assert(sample_count == 4 && send_count == 1 && auto_sleep);
    assert(trend.count == 2 && trend.interval_ms == 600000);
    run_control(61000, sleep_keys, 2, false, false, true, 0);
    assert(trend.count == 0 && trend.interval_ms == 600000);
    assert(send_recorded[0] && last_send[0] == pdMS_TO_TICKS(760));
    const int16_t rapid[] = {270, 275, 280, 285, 290, 295, 300};
    temp_script = rapid; temp_count = 7;
    run_control(301000, sleep_keys, 2, false, false, false, 0);
    assert(send_count == 3 && send_times[0] == 760 && send_times[1] == 120760 && send_times[2] == 240760);
    assert(trend.interval_ms == 120000 && trend.fast_milli == 500);
    TickType_t saved_send = last_send[0];
    assert(app_save_rule(0, &current.rules[0]) == ESP_OK);
    app_reset_rule(0);
    assert(last_send[0] == saved_send && send_recorded[0] && trend.count == 5);
    const event_t pause_control[] = {{150000,1,0}, {170000,2,0}};
    run_control(229000, pause_control, 2, false, false, false, 0);
    assert(send_count == 2 && last_send[0] == pdMS_TO_TICKS(120760));
    assert(trend.count == 1 && trend.interval_ms == 600000);
    run_control(169000, pause_control, 2, false, false, false, 0);
    assert(ap && trend.count == 0 && trend.interval_ms == 600000 && send_count == 2);
    assert(ir_send(0) == ESP_OK && send_count == 3); /* AP 网页手动测试不受自动门槛限制。 */
    const int16_t slowing[] = {270, 275, 280, 280, 280};
    temp_script = slowing; temp_count = 5;
    run_control(721000, NULL, 0, false, false, false, 0);
    assert(send_count == 3 && send_times[1] == 120760 && send_times[2] == 720760);
    assert(trend.interval_ms == 600000);
    temp_script = NULL; temp_count = 0;
    run_control(130000, sleep_keys, 2, true, false, false, 0);
    assert(sample_count == 3 && send_count == 1 && sleep_failed && !auto_sleep);
    const event_t sleep_ap[] = {{1000,1,0}, {5000,2,0}};
    run_control(130000, sleep_ap, 2, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at == 5000 && !ap && !led_enabled && auto_sleep);
    assert(sample_count == 5 && sample_times[3] == 64000 && sample_times[4] == 124000);
    assert(button_wakes[0] == 1);
    assert(send_count == 1 && send_times[0] == 124760);
    const event_t sleep_busy[] = {{1000,1,0}, {2000,3,0}, {3000,2,0},
        {4000,2,0}, {7000,4,0}};
    run_control(70000, sleep_busy, 5, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at >= 7000 && stopped_at <= 7100);
    assert(!ap && !led_enabled && auto_sleep && sample_count == 5);
    assert(sample_times[4] - sample_times[3] == 60000);
    const event_t toggle[] = {{1000,1,0}, {11000,1,300}, {11010,1,0}};
    run_control(72000, toggle, 3, false, false, false, 0);
    assert(ap_starts == 1 && ap_stops == 1 && stopped_at == 11000 && blocked_keys == 1);
    assert(!ap && !led_enabled && auto_sleep && led_level == 1);
    assert(sample_count == 7 && sample_times[6] == 70000);
    assert(send_count == 1 && send_times[0] == 70760);
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
    assert(stopped_at == 181000 && sample_count == 98);
    const event_t used[] = {{1000,1,0}, {1100,5,0}, {180000,6,0}};
    run_control(640000, used, 3, false, false, false, 0);
    assert(sample_count == 301 && sample_times[300] == 600000);
    assert(stopped_at == 601100 && !ap && auto_sleep);
    const event_t unused_busy[] = {{1000,1,0}, {180000,3,0}, {190000,4,0}};
    run_control(191000, unused_busy, 3, false, false, false, 0);
    assert(ap_stops == 1 && stopped_at >= 190000 && stopped_at <= 190100);
    const event_t learning[] = {{1000,1,0}, {1100,5,0}, {600000,3,0}, {610000,4,0}};
    run_control(620000, learning, 4, false, false, false, 0);
    assert(!ap && auto_sleep && sample_times[sample_count - 1] == 608000);
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 4051);
    adc_raw = 0;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 0);
    adc_raw = 1023;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 4847);
    adc_raw = UINT16_MAX;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    assert(current.temp_valid);
    adc_error = ESP_FAIL;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_FAIL && current.temp_valid);
    adc_error = ESP_OK; adc_raw = 855;
    run_control(61000, NULL, 0, false, false, true, 0);
    assert(!current.temp_valid && current.battery_valid && current.battery_mv == 3755);
    adc_raw = 888;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4207);
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3900);
    const event_t battery_ap[] = {{1000,1,0}};
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(ap && current.battery_mv == 4225);
    run_control(61000, NULL, 0, true, false, false, 0);
    assert(current.battery_mv == 4207 && !adc_sleep_seen);
    /* 重放 3994 mV 实测样本，确认按状态校准且保留原始读数波动。 */
    adc_raw = 843;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 3994);
    const uint16_t ap_adc[] = {836, 841, 841, 840, 841, 838};
    const unsigned ap_mv[] = {3977, 4001, 4001, 3996, 4001, 3987};
    for (unsigned i = 0; i < 6; i++) {
        adc_raw = ap_adc[i];
        run_control(4000, battery_ap, 1, false, false, false, 0);
        assert(ap && current.battery_mv == ap_mv[i]);
    }
    adc_raw = 910;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3996 && adc_sleep_seen);
    adc_raw = 909;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3992 && adc_sleep_seen);
    adc_raw = 797;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3500);
    adc_raw = 796;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv < 3500);
    adc_raw = UINT16_MAX;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    adc_raw = 855;
    led_enabled = false; led_test = true;
    if (!setjmp(finished)) led_task(NULL);
    puts("power control: trend 120-600s IR interval, AP pause/reset, retries, tick wrap, battery and AP lifecycle passed");
    return 0;
}
'''

SENSOR = r'''
#include "freertos/FreeRTOS.h"
#include "rules.h"
static int critical_depth;
#undef portENTER_CRITICAL
#undef portEXIT_CRITICAL
#define portENTER_CRITICAL() assert(critical_depth++ == 0)
#define portEXIT_CRITICAL() assert(--critical_depth == 0)
#include "sensor.c"
static int inputs[512], input_count, input_pos;
static uint8_t commands[32], byte_value;
static int command_count, bit_count, mode, level;
static int direction_calls, fail_direction;
static uint32_t bus_cycles, low_start;

void ets_delay_us(uint32_t us) {
    assert(mode == GPIO_MODE_OUTPUT_OD);
    assert(us == 410 && critical_depth == 0);
}
uint32_t soc_get_ccount(void) {
    assert(mode == GPIO_MODE_OUTPUT_OD && critical_depth == 1);
    bus_cycles += TEST_CPU_MHZ; /* One microsecond per deterministic poll. */
    if (GPIO.out_w1tc) {
        assert(GPIO.out_w1tc == (1U << 4));
        GPIO.out_w1tc = 0; level = 0; low_start = bus_cycles;
    }
    if (GPIO.out_w1ts) {
        assert(GPIO.out_w1ts == (1U << 4));
        GPIO.out_w1ts = 0; level = 1;
        uint32_t low_us = (bus_cycles - low_start) / TEST_CPU_MHZ;
        if (low_us >= 480 || low_us < 6) {
            assert(input_pos < input_count);
            GPIO.in = inputs[input_pos++] << 4;
        } else {
            assert(low_us == 7 || low_us == 61);
            byte_value |= (low_us == 7) << bit_count++;
            if (bit_count == 8) {
                assert(command_count < 32);
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
static void queue_result(int16_t raw, bool good_crc);
static void setup_bus(bool external, bool present) {
    assert(critical_depth == 0);
    input_pos = 0; input_count = 3;
    inputs[0] = !present; inputs[1] = external; inputs[2] = 0;
    command_count = bit_count = byte_value = 0;
    direction_calls = fail_direction = 0;
    mode = GPIO_MODE_OUTPUT_OD; level = 1;
    bus_cycles = low_start = 0;
    GPIO.out_w1tc = GPIO.out_w1ts = 0;
    input_count = 2;
    queue_result(0x0550, true); /* 上电温度仅用于核验配置。 */
    inputs[input_count++] = 0;
}
static void queue_config(int16_t raw, bool good_crc, uint8_t config) {
    uint8_t data[9] = {(uint8_t)raw, (uint8_t)(raw >> 8), 75, 70, config, 0xff, 12, 16, 0};
    data[8] = crc8(data, 8) ^ (good_crc ? 0 : 1);
    inputs[input_count++] = 0;
    for (int i = 0; i < 9; i++)
        for (int bit = 0; bit < 8; bit++) inputs[input_count++] = (data[i] >> bit) & 1;
}
static void queue_result(int16_t raw, bool good_crc) {
    queue_config(raw, good_crc, 0x7f);
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
    assert(sensor_finish(&temp) == ESP_OK && temp == 250 + CONFIG_APP_TEMP_OFFSET10);
#ifdef CONFIG_APP_SENSOR_IDLE_INPUT
    assert(mode == GPIO_MODE_INPUT);
#else
    assert(mode == GPIO_MODE_OUTPUT_OD);
#endif
    const uint8_t expected[] = {0xcc, 0xb4, 0xcc, 0xbe, 0xcc, 0x44, 0xcc, 0xbe};
    assert(command_count == 8 && memcmp(commands, expected, 8) == 0);
    assert(input_pos == input_count);
    setup_bus(true, true);
    bus_cycles = UINT32_MAX - 1000; /* Counter wrap during the reset pulse. */
    assert(sensor_start(&external) == ESP_OK && external);
    queue_result(432, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 270 + CONFIG_APP_TEMP_OFFSET10 && critical_depth == 0);
    setup_bus(false, true);
    assert(sensor_start(&external) == ESP_OK && !external && mode == GPIO_MODE_OUTPUT_OD);
    queue_result(-168, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == -105 + CONFIG_APP_TEMP_OFFSET10);
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
    fail_direction = direction_calls + 1;
    assert(sensor_finish(&temp) == ESP_FAIL);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(400, false); temp = 999;
    queue_result(400, false);
    queue_result(400, false);
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_CRC && temp == 999);
    assert(crc_logs == 3);
    assert(input_pos == input_count && command_count == 12);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(400, false);
    queue_result(400, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 250 + CONFIG_APP_TEMP_OFFSET10);
    assert(input_pos == input_count && command_count == 10);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    inputs[input_count++] = 1;
    queue_result(400, true);
    assert(sensor_finish(&temp) == ESP_OK && temp == 250 + CONFIG_APP_TEMP_OFFSET10);
    assert(input_pos == input_count && command_count == 8);
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
    assert(temp == 999 && input_pos == input_count && command_count == 6);
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
#ifdef CONFIG_APP_SENSOR_IDLE_INPUT
    assert(mode == GPIO_MODE_INPUT);
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_result(400, true);
    fail_direction = direction_calls + 2; /* Read succeeds, release fails. */
    assert(sensor_finish(&temp) == ESP_FAIL && mode == GPIO_MODE_OUTPUT_OD);
    setup_bus(true, false);
    fail_direction = 2; /* Preserve the primary error if release also fails. */
    assert(sensor_start(&external) == ESP_ERR_NOT_FOUND);
#endif
    assert(critical_depth == 0);
    const int16_t samples[] = {0, 1, -1, 4, -4, 8, -8, 399};
#if CONFIG_APP_TEMP_OFFSET10 == 3
    const int16_t calibrated[] = {3, 4, 2, 6, 1, 8, -2, 252};
#elif CONFIG_APP_TEMP_OFFSET10 == -3
    const int16_t calibrated[] = {-3, -2, -4, -1, -6, 2, -8, 246};
#else
    const int16_t calibrated[] = {0, 1, -1, 3, -3, 5, -5, 249};
#endif
    for (unsigned i = 0; i < sizeof(samples) / sizeof(samples[0]); i++) {
        setup_bus(true, true);
        assert(sensor_start(&external) == ESP_OK);
        queue_result(samples[i], true);
        assert(sensor_finish(&temp) == ESP_OK && temp == calibrated[i]);
    }
    rule_cfg_t rule = {.threshold10 = 250, .rising = 1, .enabled = 1};
    rule_state_t state = {0};
    assert(rule_step(&rule, &state, temp) == (CONFIG_APP_TEMP_OFFSET10 == 3));
    rule.rising = 0;
    assert(rule_step(&rule, &state, temp) == (CONFIG_APP_TEMP_OFFSET10 != 3));

    for (int bits = 9; bits < 12; bits++) {
        setup_bus(true, true);
        input_count = 2;
        queue_config(0x0550, true, 0x1f | ((bits - 9) << 5));
        inputs[input_count++] = 0; /* Write Scratchpad presence. */
        queue_result(0x0550, true); /* Configuration readback. */
        inputs[input_count++] = 0; /* Convert T presence. */
        assert(sensor_start(&external) == ESP_OK && external);
        const uint8_t corrected[] = {0xcc, 0xb4, 0xcc, 0xbe, 0xcc, 0x4e,
                                     75, 70, 0x7f, 0xcc, 0xbe, 0xcc, 0x44};
        assert(command_count == 13 && memcmp(commands, corrected, 13) == 0);
        queue_result(400, true);
        assert(sensor_finish(&temp) == ESP_OK && temp == 250 + CONFIG_APP_TEMP_OFFSET10);
        assert(input_pos == input_count);
    }
    for (int failure = 0; failure < 5; failure++) {
        setup_bus(true, true);
        input_count = 2;
        queue_config(400, failure != 0, 0x1f);
        if (failure != 0) {
            inputs[input_count++] = failure == 1; /* Missing before write. */
            if (failure != 1) queue_config(400, failure != 2, failure == 3 ? 0x1f : 0x7f);
        }
        if (failure == 4) {
            /* CRC-valid TH corruption must also fail the readback comparison. */
            input_count -= 73;
            uint8_t data[9] = {0x90, 1, 74, 70, 0x7f, 0xff, 12, 16, 0};
            data[8] = crc8(data, 8);
            inputs[input_count++] = 0;
            for (int i = 0; i < 9; i++)
                for (int bit = 0; bit < 8; bit++) inputs[input_count++] = (data[i] >> bit) & 1;
        }
        const esp_err_t errors[] = {ESP_ERR_INVALID_CRC, ESP_ERR_NOT_FOUND,
            ESP_ERR_INVALID_CRC, ESP_ERR_INVALID_RESPONSE, ESP_ERR_INVALID_RESPONSE};
        assert(sensor_start(&external) == errors[failure] && !external);
        assert(input_pos == input_count);
    }
    setup_bus(true, true);
    assert(sensor_start(&external) == ESP_OK);
    queue_config(400, true, 0x1f);
    temp = 999;
    assert(sensor_finish(&temp) == ESP_ERR_INVALID_STATE && temp == 999);
    assert(critical_depth == 0);
    puts("power sensor: retries, GPIO, calibration rounding/sign, rule thresholds and 12-bit repair/readback passed");
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
static bool rx_pullup;
static TaskFunction_t rx_handler;
static esp_err_t rx_add_error, rx_enable_error, rx_remove_error;
static unsigned rx_add_calls, rx_enable_calls, rx_remove_calls, rx_cleanup_logs;
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
    cpu_elapsed += TEST_CPU_MHZ / 10U; /* Deterministic 0.1 us polling/store observation. */
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
static unsigned capture_delays;
static bool run_learn, task_failed;
TickType_t xTaskGetTickCount(void) { return learn_tick; }
int64_t esp_timer_get_time(void) {
    return simulate_capture ? (capture_delays ? 200000 : 1000) : 0;
}
void vTaskDelay(TickType_t ticks) {
    assert(GPIO.pin[5].int_type == GPIO_INTR_ANYEDGE && rx_handler == capture_isr && busy);
    assert(ticks > 0); /* Yielding without blocking starves lower-priority tasks. */
    learn_tick += ticks;
    if (capture_started) capture_delays++;
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
    if (run_learn) {
        capture_delays = 0;
        fn(arg); /* Simulate the higher-priority task completing first. */
    }
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
    assert(GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
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
        uint32_t end = begin + codes[0].duration[i] * 10U * TEST_CPU_MHZ;
        if (!(i & 1)) {
            for (uint32_t pulse = begin; pulse < end; pulse += period) {
                uint32_t low = pulse + period / 2;
                if (low > end) low = end;
                assert(edge + 1 < edge_count);
                assert(edge_levels[edge] && !edge_levels[edge + 1]);
                assert(edge_times[edge] >= pulse && edge_times[edge] - pulse <= TEST_CPU_MHZ * 4U / 10U);
                assert(edge_times[edge + 1] >= low && edge_times[edge + 1] - low <= TEST_CPU_MHZ * 4U / 10U);
                edge += 2;
            }
        }
        begin = end;
    }
    assert(edge == edge_count && cpu_elapsed >= begin && cpu_elapsed - begin <= TEST_CPU_MHZ * 6U / 10U);
    assert(send_report.segments == codes[0].count && send_report.late_cycles <= TEST_CPU_MHZ * 4U / 10U);
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
    assert(rx_pullup && GPIO.pin[5].int_type == GPIO_INTR_DISABLE && rx_handler == NULL);
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
#if TEST_CPU_MHZ == 80
    const unsigned periods[] = {2222, 2105, 2000};
#else
    const unsigned periods[] = {4444, 4211, 4000};
#endif
    for (int i = 0; i < 3; i++) {
        reset_send(); carrier_khz = carriers[i];
        check_software(ESP_OK); check_waveform(periods[i]);
        /* 根据观察到的 GPIO 边沿估算载波，而非读取 GPIO_IN。 */
        double hz = TEST_CPU_MHZ * 1000000.0 * 20 / (edge_times[40] - edge_times[0]);
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
    check_software(ESP_OK); check_waveform(periods[1]);
    uint32_t hash_before = code_hash(&codes[0]);
    for (int round = 0; round < 2; round++) {
        /* 模拟休眠后 CPU 计数器重新开始，软件发送不得操作模拟音频时钟。 */
        software_started = output_high = false; edge_count = cpu_elapsed = 0;
        check_software(ESP_OK); check_waveform(periods[1]);
        assert(code_hash(&codes[0]) == hash_before);
    }
    ap_on = true; assert(ir_send(0) == ESP_OK && sample_rate == 38000);
    assert(strcmp(send_report.backend, "i2s") == 0);
    reset_send(); carrier_khz = 38; cpu_base = UINT32_MAX - 1000;
    check_software(ESP_OK); check_waveform(periods[1]);
    reset_send(); carrier_khz = 40;
    codes[0].duration[0] = 65000; codes[0].duration[1] = 9952;
    for (int i = 2; i < 8; i++) codes[0].duration[i] = 8;
    check_software(ESP_OK); check_waveform(periods[2]); /* Exactly 750 ms. */
    reset_send(); codes[0].count = IR_MAX;
    for (int i = 0; i < IR_MAX; i++) codes[0].duration[i] = 8;
    carrier_khz = 38; check_software(ESP_OK); check_waveform(periods[1]);
    reset_send(); codes[0].duration[0] = 65000; codes[0].duration[1] = 10000;
    check_software(ESP_ERR_NOT_FOUND); assert(!software_started);
    reset_send(); nmi_after_high = true; nmi_delay = 50 * TEST_CPU_MHZ;
    check_software(ESP_ERR_TIMEOUT);
    assert(nmi_injected && send_report.segments == 0 && send_report.late_cycles > 5U * TEST_CPU_MHZ);
    reset_send(); nmi_at = 2000 * TEST_CPU_MHZ - TEST_CPU_MHZ / 10U; nmi_delay = 50 * TEST_CPU_MHZ;
    check_software(ESP_ERR_TIMEOUT);
    assert(nmi_injected && send_report.segments == 1 && send_report.late_cycles > 5U * TEST_CPU_MHZ);
    reset_send(); nmi_after_high = true; nmi_delay = 4 * TEST_CPU_MHZ;
    check_software(ESP_OK); assert(send_report.late_cycles <= 5U * TEST_CPU_MHZ);
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
    assert(rx_add_calls == 0 && rx_enable_calls == 0 && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    task_failed = false; run_learn = true;
    rx_add_error = ESP_FAIL;
    assert(ir_start_learn(0) == ESP_OK && ir_last_error() == ESP_FAIL && !busy);
    assert(rx_handler == NULL && rx_remove_calls == 0 && rx_enable_calls == 0);
    rx_add_error = ESP_OK; rx_enable_error = ESP_ERR_INVALID_STATE;
    assert(ir_start_learn(0) == ESP_OK && ir_last_error() == ESP_ERR_INVALID_STATE && !busy);
    assert(rx_handler == NULL && rx_remove_calls == 1 && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    rx_enable_error = ESP_OK; rx_remove_error = ESP_FAIL;
    assert(ir_start_learn(0) == ESP_OK && ir_last_error() == ESP_ERR_TIMEOUT && !busy);
    assert(rx_cleanup_logs == 1 && rx_handler == capture_isr && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    rx_remove_error = ESP_OK;
    TickType_t wait_start = learn_tick;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR && !busy);
    assert(ir_last_error() == ESP_ERR_TIMEOUT);
    assert(learn_tick - wait_start == pdMS_TO_TICKS(15000));
    assert(rx_handler == NULL && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    assert(test_learn_wait > 0 && test_learn_wait < test_learn_end);
    simulate_capture = true;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_SAVED && !busy);
    assert(capture_delays > 0);
    assert(rx_handler == NULL && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    uint32_t saved_hash = code_hash(&codes[0]);
    assert(saved_sizes[0] == 22 && ir_has_code(0));
    rx_remove_error = ESP_FAIL;
    assert(ir_start_learn(0) == ESP_OK && ir_state() == IR_ERROR && !busy);
    assert(ir_last_error() == ESP_FAIL && code_hash(&codes[0]) == saved_hash);
    assert(rx_cleanup_logs == 2 && GPIO.pin[5].int_type == GPIO_INTR_DISABLE);
    rx_remove_error = ESP_OK;
    assert(ir_start_learn(1) == ESP_OK && ir_state() == IR_SAVED && ir_has_code(1));
    assert(memcmp(&codes[0], &saved_codes[0], saved_sizes[0]) == 0);
    memset(codes, 0, sizeof(codes)); /* Lose RAM while preserving committed NVS. */
    assert(ir_init() == ESP_OK && ir_has_code(0) && ir_has_code(1));
    assert(code_hash(&codes[0]) == saved_hash);
    assert(ir_send(0) == ESP_OK && code_hash(&codes[0]) == saved_hash);
    reset_send(); codes[0] = saved_codes[0]; carrier_khz = 38;
    check_software(ESP_OK); check_waveform(periods[1]);
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
    puts("power IR: RX IRQ lifecycle/failures, I2S/software edges, full frames, wrap/NMI, sleep lock/retry, cleanup and NVS passed");
    return 0;
}
'''


TRACE = r'''
#define TEST_SLEEP_TRACE
#include <stdarg.h>
#include "freertos/FreeRTOS.h"
static unsigned irq_state, trace_lines;
static char trace_output[64][512];
volatile uint32_t test_rtc_counter;
uint32_t g_esp_ticks_per_us = TEST_CPU_MHZ;
static uint32_t trace_ccount = 1000;
static uint32_t trace_compare = 1000 + TEST_CPU_MHZ * 10000U;
static uint32_t frc_enabled, frc_count, frc_alarm;
static TickType_t expected_idle = 50;
static unsigned real_idle_calls, real_program_calls;
static uint32_t programmed_cycles;
static uint32_t rtc_step = 10000, rtc_result, rtc_period = 8192;
static unsigned real_auto_calls, real_hw_calls, real_cal_calls;
static int os_pending = 1;
int app_os_timer_pending(void) { return os_pending; }
static int idle_mode;
static int64_t trace_now;
static TaskHandle_t wait_task = (void *)1;
static char wait_name[] = "wifi_candidate_task_long";
static TickType_t wait_now = UINT32_MAX - 20, forward_ticks;
static unsigned expect_wait_irq, forwarded[5];
static BaseType_t forward_forever;
static List_t wait_list;
static int queue_buffer;
#include "sleep_trace.c"

TaskHandle_t xTaskGetCurrentTaskHandle(void) { return wait_task; }
char *pcTaskGetName(TaskHandle_t task) { assert(task == wait_task); return wait_name; }
TickType_t xTaskGetTickCount(void) { return wait_now; }
void __real_vTaskDelay(TickType_t ticks) {
    assert(irq_state == expect_wait_irq && ticks == forward_ticks); forwarded[WAIT_DELAY]++;
}
uint32_t __real_ulTaskNotifyTake(BaseType_t clear, TickType_t ticks) {
    assert(irq_state == expect_wait_irq && ticks == forward_ticks && clear == pdTRUE);
    forwarded[WAIT_NOTIFY]++; return 17;
}
BaseType_t __real_xQueueReceive(QueueHandle_t queue, void *buffer, TickType_t ticks) {
    assert(irq_state == expect_wait_irq && ticks == forward_ticks);
    assert(queue == (void *)7 && buffer == &queue_buffer); forwarded[WAIT_QUEUE]++; return pdFALSE;
}
void __real_vTaskPlaceOnEventList(List_t *list, TickType_t ticks) {
    assert(irq_state == expect_wait_irq && ticks == forward_ticks && list == &wait_list);
    forwarded[WAIT_EVENT]++;
}
void __real_vTaskPlaceOnEventListRestricted(List_t *list, TickType_t ticks, BaseType_t forever) {
    assert(irq_state == expect_wait_irq && ticks == forward_ticks && list == &wait_list);
    assert(forever == forward_forever); forwarded[WAIT_TIMER]++;
}

uint32_t soc_get_ccount(void) { return trace_ccount; }
uint32_t soc_get_ccompare(void) { return trace_compare; }
uint32_t test_read_reg(uint32_t reg) {
    if (reg == RTC_SLP_CNT_VAL) return test_rtc_counter;
    if (reg == TRACE_FRC2_CTL) return frc_enabled ? (1U << 7) : 0;
    if (reg == TRACE_FRC2_COUNT) return frc_count;
    assert(reg == TRACE_FRC2_ALARM); return frc_alarm;
}
TickType_t __real_prvGetExpectedIdleTime(void) {
    assert(irq_state == 1); real_idle_calls++; return expected_idle;
}
void __real_pm_set_sleep_cycles(uint32_t cycles) {
    assert(irq_state == 1); real_program_calls++; programmed_cycles = cycles;
}

esp_irqflag_t soc_save_local_irq(void) {
    unsigned saved = irq_state;
    irq_state = 1;
    return saved;
}
void soc_restore_local_irq(esp_irqflag_t saved) {
    assert(saved <= 1);
    irq_state = saved;
}
int64_t esp_timer_get_time(void) { return trace_now; }
uint32_t __real_pm_rtc_clock_cali_proc(void) {
    assert(irq_state == 1);
    real_cal_calls++;
    return rtc_period;
}
uint32_t __real_rtc_light_sleep_start(uint32_t wakeup_opt, uint32_t reject_opt) {
    assert(irq_state == 1 && wakeup_opt == 3 && reject_opt == 4);
    real_hw_calls++;
    test_rtc_counter += rtc_step;
    return rtc_result;
}
void __real_esp_sleep_start(void) {
    assert(irq_state == 0);
    real_auto_calls++;
    if (!idle_mode) return;
    esp_irqflag_t saved = soc_save_local_irq();
    assert(__wrap_prvGetExpectedIdleTime() == expected_idle);
    if (idle_mode != 3)
        assert(__wrap_pm_rtc_clock_cali_proc() == rtc_period);
    if (idle_mode != 2) {
        __wrap_pm_set_sleep_cycles(1234);
        assert(programmed_cycles == 1234);
        assert(__wrap_rtc_light_sleep_start(3, 4) == rtc_result);
    }
    soc_restore_local_irq(saved);
}
static void run_idle(int mode) {
    idle_mode = mode;
    __wrap_esp_sleep_start();
    assert(irq_state == 0 && trace_lines == 0);
}
int main(void) {
    char decimal[21];
    assert(strcmp(trace_number(decimal, 0), "0") == 0);
    assert(strcmp(trace_number(decimal, UINT64_MAX), "18446744073709551615") == 0);
    sleep_trace_report(); assert(trace_lines == 0);
    run_idle(0); /* 自动入口等待中断，没有低层尝试，不算作睡眠。 */
    run_idle(1); /* 10000 RTC ticks，每 tick 2 us，应估算为 20 ms。 */
    rtc_result = 0x20;
    run_idle(1); /* 硬件拒绝仍原样返回，不能累计估算时间。 */
    rtc_result = 0;
    run_idle(2); /* 校准后跳过硬件调用，下一次不得沿用旧校准。 */
    run_idle(3); /* 缺少本次校准：上报 bad_cal，不以默认值掩盖。 */
    rtc_step = 0;
    run_idle(1); /* RTC 未推进：上报 zero_rtc。 */
    test_rtc_counter = UINT32_MAX - 99;
    rtc_step = 200;
    run_idle(1); /* RTC 回绕，200 ticks 对应 0.4 ms。 */
    rtc_period = 4096; rtc_step = 20000;
    run_idle(1); /* 校准值变化，20000 ticks 仍对应 20 ms。 */
    assert(real_auto_calls == 8 && real_hw_calls == 6 && real_cal_calls == 6);
    trace_now = 29999999; sleep_trace_report(); assert(trace_lines == 0);
    trace_now = 30000000; sleep_trace_report(); assert(trace_lines == 13);
    assert(strstr(trace_output[0], "window_ms=30000 auto=8 auto_no_hw=2 hw=6 hw_ok=5 hw_reject=1"));
    assert(strstr(trace_output[1], "rtc_call_est_ms=40 max_est_ms_total=20 bad_cal=1 zero_rtc=1"));
    assert(strstr(trace_output[1], "last_reject=0x00000020 reasons=unavailable"));
    assert(strstr(trace_output[2], "measured=3 avg_est_us=13466 min_est_us=400 max_est_us=20000"));
    assert(strstr(trace_output[3], "os=6 frc2=0 equal=0 unknown=0"));
    assert(strstr(trace_output[10], "idle_ticks=50 os_est_us=500000 frc2_enabled=0"));
    assert(strstr(trace_output[11], "requested_est_us=1234 rtc_ticks=20000 period_q12=4096 elapsed_est_us=20000"));
    assert(real_idle_calls == 7 && real_program_calls == 6);
    trace_now = 32000000; sleep_trace_report(); assert(trace_lines == 13);
    trace_now = 60000000; sleep_trace_report(); assert(trace_lines == 18);
    assert(strstr(trace_output[13], "window_ms=30000 auto=0 auto_no_hw=0 hw=0 hw_ok=0 hw_reject=0"));
    assert(strstr(trace_output[14], "rtc_call_est_ms=0 max_est_ms_total=20 bad_cal=0 zero_rtc=0"));
    assert(strstr(trace_output[15], "measured=0 avg_est_us=0 min_est_us=0 max_est_us=0"));
    /* 大计数验证 64 位累加及嵌套中断状态，不改变原始参数和返回值。 */
    irq_state = 1;
    assert(__wrap_pm_rtc_clock_cali_proc() == 4096 && irq_state == 1);
    rtc_step = 2000000;
    assert(__wrap_rtc_light_sleep_start(3, 4) == 0 && irq_state == 1);
    irq_state = 0;
    trace_now = 90000000; sleep_trace_report(); assert(trace_lines == 25);
    assert(strstr(trace_output[19], "rtc_call_est_ms=2000 max_est_ms_total=2000"));
    assert(strstr(trace_output[21], "unknown=1"));
    assert(strstr(trace_output[23], "programmed_valid=0"));
    assert(real_cal_calls == 7 && real_hw_calls == 7);
    totals.auto_calls += UINT64_C(4294967296);
    trace_now = 120000000; sleep_trace_report(); assert(trace_lines == 30);
    assert(strstr(trace_output[25], "auto=4294967296 auto_no_hw=0"));
    /* 与 CPU 频率无关的真实微秒期限，含 FRC2/ccount 回绕及零除保护。 */
    idle_mode = 1; rtc_step = 500; expected_idle = 1000;
    frc_enabled = 1; frc_count = UINT32_MAX - 99; frc_alarm = 400;
    __wrap_esp_sleep_start();
    assert(pending.frc_us == 100 && irq_state == 0);
    frc_alarm = frc_count + 50000000U;
    __wrap_esp_sleep_start(); /* RTOS 与 FRC2 均为 10 s。 */
    expected_idle = 1;
    trace_ccount = UINT32_MAX - 99;
    trace_compare = trace_ccount + TEST_CPU_MHZ * 2500U;
    __wrap_esp_sleep_start();
    assert(pending.os_us == 2500);
    g_esp_ticks_per_us = 0;
    __wrap_esp_sleep_start();
    assert(irq_state == 0);
    trace_now = 150000000; sleep_trace_report(); assert(trace_lines == 43);
    assert(strstr(trace_output[33], "os=1 frc2=1 equal=1 unknown=1"));
    assert(strstr(trace_output[34], "idle_ticks=1000 os_est_us=10000000 frc2_enabled=1 frc2_est_us=100"));
    assert(strstr(trace_output[40], "deadline_valid=0"));
    /* 等待包装器仅记录，不改参数、返回值、IRQ 状态，也不在入口打印。 */
    forward_ticks = 50;
    for (expect_wait_irq = 0; expect_wait_irq <= 1; expect_wait_irq++) {
        irq_state = expect_wait_irq;
        __wrap_vTaskDelay(forward_ticks);
        assert(__wrap_ulTaskNotifyTake(pdTRUE, forward_ticks) == 17);
        assert(__wrap_xQueueReceive((void *)7, &queue_buffer, forward_ticks) == pdFALSE);
        __wrap_vTaskPlaceOnEventList(&wait_list, forward_ticks);
        __wrap_vTaskPlaceOnEventListRestricted(&wait_list, forward_ticks, pdFALSE);
        assert(irq_state == expect_wait_irq && trace_lines == 43);
    }
    irq_state = expect_wait_irq = 0;
    for (unsigned i = 0; i < 5; i++) assert(forwarded[i] == 2);
    assert(wait_rows[0].calls == 2 && wait_rows[0].half_second == 2);
    assert(strlen((const char *)wait_rows[0].name) == 15);
    assert(wait_rows[0].last_at == UINT32_MAX - 20);
    record_wait(40, WAIT_DELAY, wait_rows[0].caller, 0, false);
    assert(wait_rows[0].calls == 3 && wait_rows[0].min_ticks == 40 && wait_rows[0].max_ticks == 50);
    forward_ticks = 0; __wrap_vTaskDelay(0);
    forward_ticks = portMAX_DELAY; __wrap_vTaskDelay(portMAX_DELAY);
    forward_ticks = 101; __wrap_vTaskDelay(101);
    forward_ticks = 0; forward_forever = pdTRUE;
    __wrap_vTaskPlaceOnEventListRestricted(&wait_list, 0, pdTRUE);
    assert(wait_zero == 1 && wait_long == 3);
    for (unsigned i = 5; i < TRACE_WAIT_SLOTS; i++) record_wait(1, WAIT_QUEUE, 100 + i, 0, false);
    record_wait(50, WAIT_QUEUE, 999, 0, false);
    assert(wait_full == 1);
    trace_now = 180000000; sleep_trace_report(); assert(trace_lines == 64);
    assert(strstr(trace_output[47], "filtered_zero=1 filtered_long_or_infinite=3 dropped_full=1 capacity=16"));
    assert(strstr(trace_output[48], "task=wifi_candidate_ api=delay calls=3 ticks_500ms=2 min_ticks=40 max_ticks=50"));
    for (unsigned i = 0; i < TRACE_WAIT_SLOTS; i++) assert(wait_rows[i].calls == 0);
    record_wait(50, WAIT_DELAY, 123, 0, false); /* 下个窗口可重新使用容量。 */
    assert(wait_rows[0].calls == 1 && wait_rows[0].min_ticks == 50 && wait_full == 0);
#ifdef CONFIG_APP_PAUSE_NOISE_TIMER
    os_pending = 0; frc_enabled = 1;
    g_esp_ticks_per_us = TEST_CPU_MHZ; expected_idle = 2924;
    trace_ccount = 1000; trace_compare = 1000 + TEST_CPU_MHZ * 10000U;
    __wrap_esp_sleep_start();
    assert(pending.frc_enabled && !pending.frc_pending && !pending.frc_us);
    assert(pending.os_us == 29240000);
    assert(totals.os_limits == 8 && totals.frc_limits == 1);
#else
    (void)os_pending;
#endif
    puts("power sleep trace: idle/RTC forwarding, rejection, calibration, wrap, 64-bit time, IRQ state and 30s delta reports passed");
    return 0;
}
'''


def check_lwip_timers(gcc):
    sdk = Path(os.environ.get("IDF_PATH", r"D:\APPS\Espressif\frameworks\ESP8266_RTOS_SDK"))
    original = (sdk / "components/lwip/lwip/src/core/timeouts.c").read_text(encoding="utf-8")
    generated = (ROOT / "build/auto/lwip_timeouts.c").read_text(encoding="utf-8")
    block = ("#if LWIP_DHCP\n"
             "  {DHCP_COARSE_TIMER_MSECS, HANDLER(dhcp_coarse_tmr)},\n"
             "  {DHCP_FINE_TIMER_MSECS, HANDLER(dhcp_fine_tmr)},\n#endif")
    assert original.count(block) == 1
    expected = original.replace(block, "/* AP-only build: DHCP client cyclic timers disabled. */")
    expected = expected.replace("static u32_t current_timeout_due_time;",
                                "static u32_t current_timeout_due_time;\nstatic int app_timers_paused;")
    expected = expected.replace("if (!tcpip_tcp_timer_active && (tcp_active_pcbs || tcp_tw_pcbs))",
                                "if (!app_timers_paused && !tcpip_tcp_timer_active && (tcp_active_pcbs || tcp_tw_pcbs))")
    expected = expected.replace("  cyclic->handler();", "  if (app_timers_paused) return;\n  cyclic->handler();")
    fragment = (ROOT / "tools/lwip_timers.inc").read_text(encoding="utf-8")
    marker = "#else /* LWIP_TIMERS && !LWIP_TIMERS_CUSTOM */"
    expected = expected.replace(marker, fragment + "\n" + marker)
    assert generated == expected
    prefix = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#define LWIP_TCP 1
#define LWIP_IPV4 1
#define IP_REASSEMBLY 1
#define LWIP_ARP 1
#define ESP_GRATUITOUS_ARP 1
#define LWIP_DHCP 1
#define ESP_DHCPS_TIMER 1
#define LWIP_AUTOIP 0
#define LWIP_IGMP 0
#define LWIP_DNS 1
#define LWIP_IPV6 0
#define TCP_TMR_INTERVAL 250
#define IP_TMR_INTERVAL 1000
#define ARP_TMR_INTERVAL 1000
#define GARP_TMR_INTERVAL 60000
#define DHCP_COARSE_TIMER_MSECS 1000
#define DHCP_FINE_TIMER_MSECS 500
#define DNS_TMR_INTERVAL 1000
#define HANDLER(x) x
#define LWIP_ARRAYSIZE(x) (sizeof(x)/sizeof((x)[0]))
#define LWIP_CONST_CAST(type, value) ((type)(value))
typedef void (*sys_timeout_handler)(void *);
struct lwip_cyclic_timer { uint32_t interval_ms; void (*handler)(void); };
static void tcp_tmr(void) {}
static void ip_reass_tmr(void) {}
static void etharp_tmr(void) {}
static void garp_tmr(void) {}
static void dhcp_coarse_tmr(void) {}
static void dhcp_fine_tmr(void) {}
static void dhcps_coarse_tmr(void) {}
static void dns_tmr(void) {}
'''
    registrar = r'''
static unsigned registered[16];
static void lwip_cyclic_timer(void *arg) { (void)arg; }
static void sys_timeout(uint32_t ms, sys_timeout_handler cb, void *arg) {
    const struct lwip_cyclic_timer *timer = arg;
    assert(cb == lwip_cyclic_timer && timer->interval_ms == ms);
    ptrdiff_t index = timer - lwip_cyclic_timers;
    assert(index > 0 && index < (ptrdiff_t)LWIP_ARRAYSIZE(lwip_cyclic_timers));
    registered[index]++;
}
'''
    checks = r'''
int main(void) {
    sys_timeouts_init();
    unsigned clients = 0, servers = 0;
    assert(registered[0] == 0); /* TCP remains on demand. */
    for (unsigned i = 1; i < LWIP_ARRAYSIZE(lwip_cyclic_timers); i++) {
        assert(registered[i] == 1);
        void (*cb)(void) = lwip_cyclic_timers[i].handler;
        if (cb == dhcp_fine_tmr || cb == dhcp_coarse_tmr) clients++;
        if (cb == dhcps_coarse_tmr) servers++;
    }
    assert(clients == (TEST_CLIENT_DISABLED ? 0U : 2U) && servers == 1);
    puts("lwIP: actual cyclic table/init, DHCP client A/B and retained server scheduling passed");
    return 0;
}
'''
    for disabled, source in [(0, original), (1, generated)]:
        table = re.search(r"const struct lwip_cyclic_timer lwip_cyclic_timers\[\] = \{.*?\n\};", source, re.S)
        init = re.search(r"void sys_timeouts_init\(void\)\n\{.*?\n\}", source, re.S)
        assert table and init
        path = OUT / f"lwip_timers_{disabled}.c"
        exe = OUT / f"lwip_timers_{disabled}.exe"
        path.write_text(prefix + table[0] + registrar + init[0] + checks, encoding="utf-8")
        subprocess.run([gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        f"-DTEST_CLIENT_DISABLED={disabled}", str(path), "-o", str(exe)], check=True, cwd=ROOT)
        subprocess.run([str(exe)], check=True, cwd=ROOT)

    check_network_pause(gcc, generated, prefix, fragment)


def check_network_pause(gcc, source, prefix, fragment):
    # Execute the generated production callbacks, init, cancellation and pause API.
    names = ["lwip_cyclic_timer", "sys_timeouts_init", "tcpip_tcp_timer",
             "tcp_timer_needed", "sys_untimeout"]
    functions = []
    for name in names:
        function = re.search(r"void\s+" + name + r"\([^\n]*\)\n\{.*?\n\}", source, re.S)
        assert function, name
        functions.append(function[0])
    table = re.search(r"const struct lwip_cyclic_timer lwip_cyclic_timers\[\] = \{.*?\n\};", source, re.S)
    prefix = prefix.replace("#include <stdio.h>", "#include <stdio.h>\n#include <stdlib.h>")
    prefix = prefix.replace("static void tcp_tmr(void) {}",
                            "static unsigned tcp_calls; static void tcp_tmr(void) { tcp_calls++; }")
    prefix = prefix.replace("static void dhcp_coarse_tmr(void) {}", "")
    prefix = prefix.replace("static void dhcp_fine_tmr(void) {}", "")
    harness = r'''
typedef uint32_t u32_t;
typedef int err_t;
#define ERR_OK 0
#define ERR_MEM -1
#define LWIP_DEBUG_TIMERNAMES 0
#define LWIP_UNUSED_ARG(x) (void)(x)
#define LWIP_ASSERT_CORE_LOCKED() assert(core_owned)
#define TIME_LESS_THAN(a,b) ((int32_t)((a)-(b)) < 0)
#define MEMP_SYS_TIMEOUT 0
struct sys_timeo { struct sys_timeo *next; sys_timeout_handler h; void *arg; };
static struct sys_timeo *next_timeout;
static u32_t current_timeout_due_time;
static int app_timers_paused, tcpip_tcp_timer_active, core_owned = 1;
static int tcp_active_pcbs, tcp_tw_pcbs, alloc_budget = -1;
static u32_t sys_now(void) { return 10000; }
static void memp_free(int pool, void *ptr) { (void)pool; free(ptr); }
static void sys_timeout(u32_t ms, sys_timeout_handler cb, void *arg) {
    (void)ms;
    if (alloc_budget == 0) return;
    if (alloc_budget > 0) alloc_budget--;
    struct sys_timeo *timer = malloc(sizeof(*timer)); assert(timer);
    *timer = (struct sys_timeo){ next_timeout, cb, arg }; next_timeout = timer;
}
static void sys_timeout_abs(u32_t ms, sys_timeout_handler cb, void *arg) {
    sys_timeout(ms, cb, arg);
}
static void one_shot(void *arg) { (void)arg; }
void sys_untimeout(sys_timeout_handler handler, void *arg);
'''
    checks = r'''
int main(void) {
    unsigned counts[3];
    const unsigned cyclic_count = LWIP_ARRAYSIZE(lwip_cyclic_timers) - 1;
    sys_timeouts_init(); tcp_active_pcbs = 1; tcp_timer_needed();
    assert(tcpip_tcp_timer_active && app_timer_queued(tcpip_tcp_timer, NULL));
    sys_timeout(1234, one_shot, (void *)1);
    assert(app_lwip_timers_set(0, counts) == ERR_OK);
    assert(counts[0] == cyclic_count && counts[1] == 1 && counts[2] == 1);
    assert(!tcpip_tcp_timer_active && app_timers_paused);
    assert(app_timer_queued(one_shot, (void *)1));
    tcp_timer_needed(); /* A late PCB registration cannot restart paused TCP. */
    lwip_cyclic_timer((void *)&lwip_cyclic_timers[1]);
    assert(!app_timer_queued(tcpip_tcp_timer, NULL) && !next_timeout->next);
    assert(app_lwip_timers_set(0, counts) == ERR_OK && !counts[0] && !counts[1]);
    for (unsigned round = 0; round < 20; round++) {
        assert(app_lwip_timers_set(1, counts) == ERR_OK);
        assert(counts[0] == cyclic_count && counts[1] == 1 && counts[2] == cyclic_count + 2);
        assert(app_lwip_timers_set(1, counts) == ERR_OK);
        assert(!counts[0] && !counts[1] && counts[2] == cyclic_count + 2); /* No duplicates. */
        sys_untimeout(lwip_cyclic_timer, (void *)&lwip_cyclic_timers[1]);
        lwip_cyclic_timer((void *)&lwip_cyclic_timers[1]);
        assert(app_timer_queued(lwip_cyclic_timer, (void *)&lwip_cyclic_timers[1]));
        sys_untimeout(tcpip_tcp_timer, NULL); tcpip_tcp_timer(NULL);
        assert(tcp_calls == round + 1 && app_timer_queued(tcpip_tcp_timer, NULL));
        assert(app_lwip_timers_set(0, counts) == ERR_OK && counts[2] == 1);
    }
    alloc_budget = 2; /* A partial restore rolls back the entire timer group. */
    assert(app_lwip_timers_set(1, counts) == ERR_MEM);
    assert(app_timers_paused && !tcpip_tcp_timer_active && counts[2] == 1);
    alloc_budget = -1; tcp_active_pcbs = 0; tcp_tw_pcbs = 1;
    assert(app_lwip_timers_set(1, counts) == ERR_OK && counts[1] == 1);
    assert(app_lwip_timers_set(0, counts) == ERR_OK);
    tcp_tw_pcbs = 0;
    assert(app_lwip_timers_set(1, counts) == ERR_OK && counts[1] == 0 && counts[2] == cyclic_count + 1);
    assert(app_lwip_timers_set(0, counts) == ERR_OK);
    sys_untimeout(one_shot, (void *)1); assert(!next_timeout);
    puts("lwIP: cyclic/TCP pause, repeated restore, late scheduling, one-shots and allocation rollback passed");
    return 0;
}
'''
    path = OUT / "network_pause.c"
    exe = OUT / "network_pause.exe"
    path.write_text(prefix + table[0] + harness + "\n".join(functions) + fragment + checks, encoding="utf-8")
    subprocess.run([gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                    str(path), "-o", str(exe)], check=True, cwd=ROOT)
    subprocess.run([str(exe)], check=True, cwd=ROOT)


def check_noise_timer(gcc):
    # Test the actual wrapper and the generated SDK deadline function together.
    source = (ROOT / "build/auto/esp_sleep.c").read_text(encoding="utf-8")
    match = re.search(r"static inline uint32_t min_sleep_us\(.*?\n}\n", source, re.S)
    if not match or "clk->frc2_enable && app_os_timer_pending()" not in match[0]:
        raise AssertionError("请先构建启用噪声定时器暂停的固件")
    header = r'''
#include <stdint.h>
#include <stdbool.h>
typedef struct os_timer_t {
    struct os_timer_t *timer_next;
    void *timer_handle;
    uint32_t timer_expire, timer_period;
    void (*timer_func)(void *);
    bool timer_repeat_flag;
    void *timer_arg;
} os_timer_t;
'''
    harness = r'''
#include "sdk_mock.h"
#include "noise_timer.c"
os_timer_t * volatile app_ets_timer_head;
os_timer_t app_noise_timer, other_timer;
uint16_t NoiseTimerInterval = 3000;
static bool fail_arm;
static unsigned irq_state, armed, last_delay;
static bool last_repeat;
esp_irqflag_t soc_save_local_irq(void) {
    unsigned saved = irq_state; irq_state = 1; return saved;
}
void soc_restore_local_irq(esp_irqflag_t saved) { irq_state = saved; }
void test_log(const char *tag, const char *fmt, ...) { (void)tag; (void)fmt; }
void pp_disable_noise_timer(void) {
    os_timer_t * volatile *link = &app_ets_timer_head;
    while (*link && *link != &app_noise_timer) link = &(*link)->timer_next;
    if (*link) *link = (*link)->timer_next;
    app_noise_timer.timer_next = NULL;
}
static void arm(os_timer_t *timer, unsigned delay, bool repeat) {
    armed++; last_delay = delay; last_repeat = repeat;
    if (fail_arm) return;
    for (os_timer_t *next = app_ets_timer_head; next; next = next->timer_next)
        if (next == timer) return;
    timer->timer_next = app_ets_timer_head; app_ets_timer_head = timer;
}
void __real_os_timer_arm(os_timer_t *timer, uint32_t ms, bool repeat) { arm(timer, ms, repeat); }
void __real_os_timer_arm_us(os_timer_t *timer, uint32_t us, bool repeat) { arm(timer, us, repeat); }
void reset_noise_timer(uint16_t interval) {
    NoiseTimerInterval = interval; pp_disable_noise_timer();
    __wrap_os_timer_arm(&app_noise_timer, interval, false);
}
void pp_noise_test(void *arg) { (void)arg; reset_noise_timer(NoiseTimerInterval); }
typedef struct { uint32_t ccount, frc2_enable, frc2_cnt, sleep_us; } pm_soc_clk_t;
#define FRC2_ALARM 0x60000630U
#define FRC2_TICKS_MAX (UINT32_MAX / 4U)
#define FRC2_TICKS_PER_US 5U
#define portTICK_RATE_MS portTICK_PERIOD_MS
#define MIN(a,b) ((a) < (b) ? (a) : (b))
static uint32_t alarm, compare, idle_ticks;
uint32_t g_esp_ticks_per_us = TEST_CPU_MHZ;
TickType_t prvGetExpectedIdleTime(void) { return idle_ticks; }
uint32_t soc_get_ccompare(void) { return compare; }
uint32_t test_read_reg(uint32_t reg) { assert(reg == FRC2_ALARM); return alarm; }
'''
    checks = r'''
int main(void) {
    assert(noise_timer_set_active(false) == ESP_ERR_INVALID_STATE);
    app_noise_timer.timer_func = pp_noise_test;
    reset_noise_timer(3000); assert(app_os_timer_pending());
    assert(noise_timer_set_active(false) == ESP_OK && !app_os_timer_pending());
    unsigned before = armed;
    pp_noise_test(NULL); reset_noise_timer(100);
    __wrap_os_timer_arm_us(&app_noise_timer, 50, true);
    assert(armed == before && blocked_arms == 3 && !app_os_timer_pending());
    irq_state = 1;
    __wrap_os_timer_arm(&other_timer, 456, true);
    assert(last_delay == 456 && last_repeat && irq_state == 1 && app_os_timer_pending());
    __wrap_os_timer_arm_us(&other_timer, 123, false);
    assert(last_delay == 123 && !last_repeat && irq_state == 1);
    irq_state = 0;
    for (unsigned i = 0; i < 20; i++) {
        assert(noise_timer_set_active(true) == ESP_OK && !noise_paused);
        before = armed;
        assert(noise_timer_set_active(true) == ESP_OK && armed == before);
        pp_noise_test(NULL);
        assert(noise_timer_set_active(false) == ESP_OK);
        assert(app_ets_timer_head == &other_timer && !other_timer.timer_next);
    }
    fail_arm = true;
    assert(noise_timer_set_active(true) == ESP_FAIL && noise_paused);
    assert(app_ets_timer_head == &other_timer);
    fail_arm = false;
    assert(noise_timer_set_active(true) == ESP_OK);
    assert(noise_timer_set_active(false) == ESP_OK);
    app_ets_timer_head = NULL;
    pm_soc_clk_t clk = { .ccount=1000, .frc2_enable=128, .frc2_cnt=100 };
    compare = 1000 + TEST_CPU_MHZ * 10000U; idle_ticks = 2924;
    alarm = 99; /* Expired enabled FRC2 alarm with no actual timer. */
    assert(min_sleep_us(&clk) == 29240000);
    alarm = 100 + 15000000; assert(min_sleep_us(&clk) == 29240000);
    app_ets_timer_head = &other_timer;
    assert(min_sleep_us(&clk) == 3000000); /* Genuine timer still limits sleep. */
    alarm = 99; assert(min_sleep_us(&clk) == 0);
    clk.frc2_cnt = UINT32_MAX - 99; alarm = 400;
    assert(min_sleep_us(&clk) == 100); /* Counter wrap. */
    clk.frc2_enable = 0; assert(min_sleep_us(&clk) == 29240000);
    idle_ticks = 1; compare = 1000; assert(min_sleep_us(&clk) == 0);
    assert(irq_state == 0);
    puts("noise timer: callback/PM rearm guard, other timers, 20 restarts, failure rollback and actual SDK deadline passed");
    return 0;
}
'''
    path = OUT / "noise_test.c"
    path.write_text(header + harness + match[0] + checks, encoding="utf-8")
    for mhz in (80, 160):
        exe = OUT / f"noise_{mhz}_test.exe"
        subprocess.run([gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                        f"-DTEST_CPU_MHZ={mhz}", "-DCONFIG_APP_PAUSE_NOISE_TIMER=1",
                        "-I", str(OUT), "-I", str(ROOT / "main"), str(path), "-o", str(exe)],
                       check=True, cwd=ROOT)
        subprocess.run([str(exe)], check=True, cwd=ROOT)


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
    for name, source in [("control", CONTROL), ("sensor", SENSOR), ("ir", IR), ("sleep_trace", TRACE)]:
        path = OUT / f"{name}_test.c"
        # 公共 mock 接在场景源码后，函数原型由 sdk_mock.h 提供。
        path.write_text(source + COMMON, encoding="utf-8")
        offsets = (0, -3, 3) if name == "sensor" else (0,)
        for mhz, profile, offset in [(mhz, profile, offset) for mhz in (80, 160)
                                     for profile in ("baseline", "measurement") for offset in offsets]:
            suffix = f"_{offset}" if offset else ""
            exe = OUT / f"{name}_{mhz}_{profile}{suffix}_test.exe"
            command = [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                       "-Wno-unused-parameter", f"-DTEST_CPU_MHZ={mhz}",
                       f"-DCONFIG_APP_TEMP_OFFSET10={offset}",
                       "-I", str(OUT), "-I", str(ROOT / "main"), str(path)]
            if name in ("control", "sensor"):
                command.append(str(ROOT / "main" / "rules.c"))
            if profile == "measurement":
                command += ["-DCONFIG_APP_QUIET_UART=1", "-DCONFIG_APP_IDLE_BOOT_PINS=1",
                            "-DCONFIG_APP_SENSOR_IDLE_INPUT=1"]
                if name == "sleep_trace":
                    command += ["-DCONFIG_APP_PAUSE_NOISE_TIMER=1"]
            print(f"power {name}: {mhz} MHz {profile} offset10={offset}", flush=True)
            subprocess.run(command + ["-o", str(exe)], check=True, cwd=ROOT)
            subprocess.run([str(exe)], check=True, cwd=ROOT)
    check_lwip_timers(gcc)
    check_noise_timer(gcc)


if __name__ == "__main__":
    main()
