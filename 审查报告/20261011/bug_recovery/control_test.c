
#define TEST_IDLE_PINS
#include <setjmp.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
static int critical_depth;
static bool drop_led_once, led_race_done;
static unsigned led_race_mode;
static void control_enter(void);
static void control_exit(void);
static bool quiet_installed, uart_drained, fail_idle_config, fail_led_config;
static esp_err_t rule_save_error, rule_commit_error, rule_open_error, rule_read_error;
static bool invalid_rule_size, invalid_rule_value;
static unsigned boot_fault;
static uint64_t idle_pin_mask;
#undef portENTER_CRITICAL
#undef portEXIT_CRITICAL
#define portENTER_CRITICAL() control_enter()
#define portEXIT_CRITICAL() control_exit()
#include <stdlib.h>
_Noreturn void test_control_abort(void);
#undef ESP_ERROR_CHECK
#define ESP_ERROR_CHECK(expr) do { if ((expr) != ESP_OK) test_control_abort(); } while (0)
#define abort test_control_abort
#include "main.c"
#undef abort
static uint8_t cal_saved[2][4], cal_pending[4];
static size_t cal_sizes[2], cal_pending_size;
static int cal_pending_kind = -1;
static esp_err_t cal_read_error, cal_open_error;
static int cal_read_kind = -1;
static void control_enter(void) {
    critical_depth++;
    if (drop_led_once) {
        drop_led_once = false; led_race_done = true; led_enabled = false;
    }
    if (led_race_mode) {
        if (led_race_mode == 1) led_learning = false;
        else if (led_race_mode == 2) led_learning = true;
        else if (led_race_mode == 3) led_enabled = true;
        else { led_enabled = false; led_learning = true; }
        led_race_mode = 0;
    }
}
static void control_exit(void) { assert(--critical_depth >= 0); }
static unsigned wait_enter_logs, wait_done_logs, wait_key_logs;
static unsigned conversion_enter_logs, conversion_done_logs, dispatch_logs;
static unsigned release_enter_logs, release_done_logs;
static char last_battery_log[512];
void esp_log_level_set(const char *tag, int level) {
    assert(strcmp(tag, "*") == 0 && level == ESP_LOG_NONE);
}
putchar_like_t esp_log_set_putchar(putchar_like_t fn) {
    assert(fn('x') == 'x'); quiet_installed = true; return NULL;
}
void uart_tx_wait_idle(uint8_t uart) {
    assert(uart == 0 && !auto_sleep && critical_depth == 0); uart_drained = true;
}
static jmp_buf finished;
static unsigned abort_calls;
_Noreturn void test_control_abort(void) { abort_calls++; longjmp(finished, 2); }
static TickType_t start_tick;
static uint32_t now_ms, end_ms, notified, ap_start, hold_until[17];
static uint32_t sample_times[512], send_times[512];
static int sample_count, send_count, pm_calls, blocked_keys;
static int ap_starts, ap_stops;
static int button_wakes[2];
static uint32_t stopped_at;
static bool ap, ap_used, ir_busy, fail_pm, fail_wakeup, sensor_error;
static bool fail_pm_restore, fail_led_task, frozen_ticks, missing_ir;
static bool fail_portal_stop_once;
static bool fail_portal_start_once, boot_held_s1;
static bool boot_ir_busy;
static uint32_t report_delay;
static unsigned zero_waits;
static void advance_time(uint32_t target);
static ir_state_t learn_mock = IR_WAITING;
static TickType_t frozen_value;
static bool led_test;
static unsigned led_waits;
static unsigned led_fail_at, led_calls;
static bool led_disable_first;
static unsigned led_flow, led_step, led_notifies;
static unsigned trace_report_calls;
static TickType_t max_notify_wait;
void sleep_trace_report(void) {
    assert(!auto_sleep);
    trace_report_calls++;
    if (report_delay) {
        uint32_t delay = report_delay; report_delay = 0;
        advance_time(now_ms + delay);
    }
}
static unsigned cpu_mhz = TEST_CPU_MHZ;
static unsigned cpu_hz = TEST_CPU_MHZ * 1000000U;
int esp_clk_cpu_freq(void) { return boot_fault == 13 ? 0 : cpu_hz; }
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
            hold_until[pin] = ev.ms + ev.hold;
            if (GPIO.pin[pin].int_type == GPIO_INTR_LOW_LEVEL) {
                if (auto_sleep) {
                    assert(GPIO.pin[pin].wakeup_enable);
                    button_wakes[ev.action - 1]++;
                }
                button_isr(ev.action == 1 ? NULL : (void *)1);
                assert(GPIO.pin[pin].int_type == GPIO_INTR_DISABLE);
            } else blocked_keys++;
        }
    }
    now_ms = target;
    GPIO.in = (now_ms >= hold_until[12] ? 1U << 12 : 0) |
              (now_ms >= hold_until[13] ? 1U << 13 : 0);
}
TickType_t xTaskGetTickCount(void) { return frozen_ticks ? frozen_value : start_tick + pdMS_TO_TICKS(now_ms); }
TaskHandle_t xTaskGetCurrentTaskHandle(void) { return (void *)1; }
BaseType_t xTaskCreate(TaskFunction_t fn, const char *name, unsigned stack,
                      void *arg, unsigned pri, TaskHandle_t *handle) {
    (void)fn; (void)name; (void)stack; (void)arg; (void)pri;
    if (fail_led_task) return pdFALSE;
    if (handle) *handle = (void *)2;
    return pdPASS;
}
void vTaskDelete(TaskHandle_t handle) { (void)handle; assert(fail_led_config); }
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
BaseType_t xTaskNotifyGive(TaskHandle_t task) {
    assert(task == (void *)2); led_notifies++; return pdPASS;
}
uint32_t ulTaskNotifyTake(BaseType_t clear, TickType_t ticks) {
    assert(clear == pdTRUE);
    if (led_test) {
        if (led_flow == 3) {
            assert(led_learning && led_level == 0);
            if (led_step++ == 0) {
                assert(ticks == pdMS_TO_TICKS(500)); return 1;
            }
            assert(ticks == portMAX_DELAY); longjmp(finished, 1);
        }
        if (led_flow == 1) {
            switch (led_step++) {
            case 0:
                assert(ticks == pdMS_TO_TICKS(500) && led_level == 0);
                app_set_learning(true); return 1;
            case 1:
                assert(ticks == portMAX_DELAY && led_level == 0);
                app_set_learning(false); return 1;
            case 2:
                assert(ticks == pdMS_TO_TICKS(500) && led_level == 0); return 0;
            default:
                assert(ticks == pdMS_TO_TICKS(500) && led_level == 1);
                longjmp(finished, 1);
            }
        }
        if (led_flow == 2) {
            assert(ticks == portMAX_DELAY);
            switch (led_step++) {
            case 0:
                assert(led_level == 1); app_set_learning(true); return 1;
            case 1:
                assert(led_level == 0);
                set_led_enabled(true); set_led_enabled(false);
                assert(led_level == 0);
                app_set_learning(false); return 1;
            default:
                assert(led_level == 1); longjmp(finished, 1);
            }
        }
        if (ticks == portMAX_DELAY) {
            assert(led_level == 1);
            longjmp(finished, 1);
        }
        assert(ticks == pdMS_TO_TICKS(500));
        assert(led_level == (led_waits || led_race_done ? 1 : 0));
        if (++led_waits == 2 || led_disable_first) led_enabled = false;
        return 0;
    }
    assert(ticks <= pdMS_TO_TICKS(SLEEP_WAIT_MS));
    if (ticks > max_notify_wait) max_notify_wait = ticks;
    if (notified) { uint32_t count = notified; notified = 0; return count; }
    if (!ticks) { zero_waits++; return 0; }
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
    if (++led_calls == led_fail_at) return ESP_FAIL;
    if (pin == 2) led_level = value;
    return ESP_OK;
}
int gpio_get_level(int pin) { return now_ms >= hold_until[pin]; }
esp_err_t gpio_wakeup_enable(int pin, int type) {
    if (fail_wakeup) return ESP_FAIL;
    GPIO.pin[pin].int_type = type; GPIO.pin[pin].wakeup_enable = true; return ESP_OK;
}
esp_err_t esp_sleep_enable_gpio_wakeup(void) { return boot_fault == 14 ? ESP_FAIL : ESP_OK; }
esp_err_t esp_pm_configure(const void *cfg) {
    pm_calls++;
    bool enable = ((const esp_pm_config_esp8266_t *)cfg)->light_sleep_enable;
    if (enable && fail_pm) return ESP_FAIL;
    if (!enable && fail_pm_restore) return ESP_FAIL;
    if (enable) assert(!ap && !ir_busy);
    return ESP_OK;
}
esp_err_t nvs_flash_init(void) { return boot_fault == 1 ? ESP_FAIL : ESP_OK; }
esp_err_t nvs_open(const char *name, int mode, nvs_handle *handle) {
    (void)name; *handle = 1;
    if (mode == NVS_READONLY && cal_open_error) return cal_open_error;
    return boot_fault == 3 ? ESP_FAIL : rule_open_error;
}
esp_err_t nvs_get_blob(nvs_handle handle, const char *key, void *data, size_t *size) {
    if (strcmp(key, "temp_adj") == 0 || strcmp(key, "bat_adj") == 0) {
        int kind = strcmp(key, "temp_adj") == 0 ? 0 : 1;
        if (cal_read_error && (cal_read_kind < 0 || kind == cal_read_kind)) return cal_read_error;
        if (!cal_sizes[kind]) return ESP_ERR_NVS_NOT_FOUND;
        assert(*size >= cal_sizes[kind]);
        *size = cal_sizes[kind]; memcpy(data, cal_saved[kind], *size); return ESP_OK;
    }
    (void)handle; assert(*size == sizeof(rule_cfg_t));
    *(rule_cfg_t *)data = (rule_cfg_t){ .threshold10=260, .rising=1,
        .enabled = strcmp(key, "rule0") == 0 };
    if (enable_down && strcmp(key, "rule1") == 0)
        *(rule_cfg_t *)data = (rule_cfg_t){ .threshold10=280, .rising=0, .enabled=1 };
    if (invalid_rule_size) (*size)--;
    if (invalid_rule_value) ((rule_cfg_t *)data)->threshold10 = 501;
    return rule_read_error;
}
esp_err_t sensor_init(void) { return boot_fault == 5 ? ESP_FAIL : ESP_OK; }
esp_err_t adc_init(adc_config_t *cfg) {
    assert(cfg->mode == ADC_READ_TOUT_MODE && cfg->clk_div == 8);
    return boot_fault == 6 ? ESP_FAIL : ESP_OK;
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
esp_err_t ir_init(void) { return boot_fault == 7 ? ESP_FAIL : ESP_OK; }
void ir_report_last_send(void) { assert(!auto_sleep); }
bool ir_has_code(int slot) { (void)slot; return !missing_ir; }
bool ir_is_busy(void) { return ir_busy; }
ir_state_t ir_state(void) { return ir_busy ? learn_mock : IR_IDLE; }
esp_err_t ir_send(int slot) {
    assert(!auto_sleep && !ir_busy && send_count < 512);
    send_slots[send_count] = slot;
    send_times[send_count++] = now_ms;
    if (fail_send_once) { fail_send_once = false; return ESP_FAIL; }
    return ESP_OK;
}
esp_err_t portal_init(void) { return boot_fault == 10 ? ESP_FAIL : ESP_OK; }
esp_err_t portal_start(void) {
    if (fail_portal_start_once) { fail_portal_start_once = false; return ESP_FAIL; }
    assert(!auto_sleep); ap = true; ap_used = false;
    ap_start = now_ms; ap_starts++; return ESP_OK;
}
esp_err_t portal_stop(void) {
    assert(!auto_sleep && !ir_busy);
    if (fail_portal_stop_once) { fail_portal_stop_once = false; return ESP_FAIL; }
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
    if (boot_held_s1) hold_until[12] = 100;
    memset(last_send, 0, sizeof(last_send));
    memset(send_recorded, 0, sizeof(send_recorded));
    s1_pending = s2_pending = led_enabled = led_learning = auto_sleep = sleep_failed = false;
    adc_sleep_seen = false;
    battery_ap_active = battery_after_ap = false;
    battery_off_tick = battery_off_samples = 0;
    last_battery_log[0] = '\0';
    button_count[0] = button_count[1] = 0;
    wait_enter_logs = wait_done_logs = wait_key_logs = 0;
    conversion_enter_logs = conversion_done_logs = dispatch_logs = 0;
    release_enter_logs = release_done_logs = 0;
    ap = ap_used = ir_busy = false;
    ir_busy = boot_ir_busy;
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
    GPIO.in = (boot_held_s1 ? 0 : 1U << 12) | (1U << 13);
    events = script; event_count = count; event_pos = 0;
    if (!setjmp(finished)) app_main();
    assert(battery_reads == sample_count);
    assert(critical_depth == 0 && fast_reads == 0 && single_reads == battery_reads);
}
#include "rules_cases.h"

int main(void) {
    run_rule_cases();
    rule_open_error = ESP_ERR_NVS_NOT_FOUND;
    assert(load_rules() == ESP_OK && !current.rules[0].enabled && !current.rules[1].enabled);
    rule_open_error = ESP_FAIL;
    assert(load_rules() == ESP_FAIL);
    rule_open_error = ESP_OK; rule_read_error = ESP_FAIL;
    assert(load_rules() == ESP_FAIL);
    rule_read_error = ESP_ERR_NVS_NOT_FOUND;
    assert(load_rules() == ESP_OK);
    rule_read_error = ESP_OK; invalid_rule_size = true;
    assert(load_rules() == ESP_ERR_INVALID_STATE);
    invalid_rule_size = false;
    invalid_rule_value = true;
    assert(load_rules() == ESP_ERR_INVALID_STATE);
    invalid_rule_value = false;
    assert(load_rules() == ESP_OK);
    rule_cfg_t before = current.rules[0], replacement = before;
    replacement.threshold10 = 250;
    rule_open_error = ESP_FAIL;
    assert(app_save_rule(0, &replacement) == ESP_FAIL);
    rule_open_error = ESP_OK; rule_save_error = ESP_FAIL;
    assert(app_save_rule(0, &replacement) == ESP_FAIL);
    rule_save_error = ESP_OK; rule_commit_error = ESP_FAIL;
    assert(app_save_rule(0, &replacement) == ESP_FAIL);
    assert(memcmp(&current.rules[0], &before, sizeof(before)) == 0);
    rule_commit_error = ESP_OK;
    assert(app_save_rule(-1, &replacement) == ESP_ERR_INVALID_ARG);
    assert(app_save_rule(2, &replacement) == ESP_ERR_INVALID_ARG);
    assert(app_save_rule(0, NULL) == ESP_ERR_INVALID_ARG);
    ap = ir_busy = auto_sleep = sleep_failed = false;
    fail_pm = fail_pm_restore = true;
    set_auto_sleep(true);
    assert(sleep_failed && !auto_sleep);
    fail_pm = false; sleep_failed = false; auto_sleep = true;
    if (!setjmp(finished)) { set_auto_sleep(false); assert(false); }
    assert(abort_calls == 1);
    fail_pm_restore = false; auto_sleep = sleep_failed = false;
    fail_led_task = true;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(abort_calls == 2 && sample_count == 0);
    fail_led_task = false;
    missing_ir = true;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(sample_count == 1 && send_count == 0 && !states[0].primed);
    missing_ir = false;
    set_auto_sleep(false); /* The main loop disables sleep before update_temp. */
    frozen_ticks = true; frozen_value = trend.times[trend.count - 1] / portTICK_PERIOD_MS;
    if (!setjmp(finished)) { update_temp(); assert(false); }
    assert(abort_calls == 3);
    frozen_ticks = false;
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
    const int16_t reported[] = {-55, 259, 260, 261};
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
    assert(conversion_enter_logs == 3 && conversion_done_logs == 3);
    assert(wait_enter_logs >= 5 && wait_done_logs + 1 == wait_enter_logs && dispatch_logs == 0);
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
    assert(button_count[0] == 2 && button_count[1] == 3);
    assert(dispatch_logs == 5 && release_enter_logs == 5 && release_done_logs == 5);
    assert(wait_key_logs > 0);
    assert(sample_count == 13 && send_count == 0 && trend.count == 0);
    const uint32_t expected[] = {0,2000,4000,6000,8000,10000,12000,
        70000,72000,74000,76000,78000,80000};
    for (int i = 0; i < 13; i++) assert(sample_times[i] == expected[i]);
    const event_t sleep_keys[] = {{1000,2,0}, {35000,2,0}};
    run_control(130000, sleep_keys, 2, false, false, false, 0);
    assert(sample_count == 3 && send_count == 1 && auto_sleep && !ap && !led_enabled);
    for (int i = 0; i < 3; i++) assert(sample_times[i] == (uint32_t)i * 60000);
    assert(send_times[0] == 60760);
    assert(states[0].primed && states[0].fired && !states[0].armed);
    assert(button_wakes[1] == 2 && button_wakes[0] == 0);
    const event_t stuck_button[] = {{1000,2,200000}};
    run_control(130000, stuck_button, 1, false, false, false, 0);
    assert(release_enter_logs == 1 && release_done_logs == 0 && dispatch_logs == 1);
    assert(sample_count == 3 && send_count == 1 && button_count[1] == 1);
    assert(gpio_get_level(13) == 0 && !ap && !auto_sleep);
    for (int i = 0; i < 3; i++) assert(sample_times[i] == (uint32_t)i * 60000);
    assert(send_times[0] == 60760);
    const event_t held_then_pressed[] = {{1000,2,70000}, {72000,2,0}};
    run_control(130000, held_then_pressed, 2, false, false, false, 0);
    assert(sample_count == 3 && button_count[1] == 2 && release_done_logs == 2);
    assert(auto_sleep && !ap);
    const event_t overlapping_keys[] = {{1000,2,70000}, {2000,1,0}};
    run_control(74000, overlapping_keys, 2, false, false, false, 0);
    assert(button_count[0] == 1 && button_count[1] == 1);
    assert(release_enter_logs == 1 && release_done_logs == 1);
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
    assert(current.battery_valid && current.battery_mv == 4345);
    adc_raw = 0;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 0);
    adc_raw = 1023;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 5198);
    adc_raw = UINT16_MAX;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    assert(current.temp_valid);
    adc_error = ESP_FAIL;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_FAIL && current.temp_valid);
    adc_error = ESP_OK; adc_raw = 855;
    run_control(61000, NULL, 0, false, false, true, 0);
    assert(!current.temp_valid && current.battery_valid && current.battery_mv == 3996);
    adc_raw = 888;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4512);
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4151);
    const event_t battery_ap[] = {{1000,1,0}};
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(ap && current.battery_mv == 4548);
    run_control(61000, NULL, 0, true, false, false, 0);
    assert(current.battery_mv == 4512 && !adc_sleep_seen);
    /* AP 保留原系数；boot/sleep 使用稳定的 3795 mV 对照拟合。 */
    adc_raw = 786;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_valid && current.battery_mv == 3994);
    const uint16_t ap_adc[] = {0, 701, 702, 703, 683, 684};
    const unsigned ap_mv[] = {0, 3590, 3595, 3600, 3498, 3503};
    for (unsigned i = 0; i < 6; i++) {
        adc_raw = ap_adc[i];
        run_control(4000, battery_ap, 1, false, false, false, 0);
        assert(ap && current.battery_mv == ap_mv[i]);
    }
    adc_error = ESP_FAIL;
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(ap && !current.battery_valid && current.battery_error == ESP_FAIL);
    adc_error = ESP_OK; adc_raw = 1024;
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(ap && !current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    adc_raw = 910;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4253 && adc_sleep_seen);
    adc_raw = 909;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4249 && adc_sleep_seen);
    adc_raw = 749;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3501);
    adc_raw = 748;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv < 3500);
    adc_raw = UINT16_MAX;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(!current.battery_valid && current.battery_error == ESP_ERR_INVALID_RESPONSE);
    adc_raw = 855;
    led_test = true; led_handle = (void *)2;
    for (led_flow = 1; led_flow <= 2; led_flow++) {
        led_step = led_notifies = 0;
        led_enabled = led_flow == 1; led_learning = false;
        if (!setjmp(finished)) led_task(NULL);
        assert(!led_learning && led_notifies == (led_flow == 1 ? 2U : 4U));
    }
    led_flow = 0;
    led_enabled = false; led_test = true;
    if (!setjmp(finished)) led_task(NULL);
    led_enabled = true; led_waits = 0;
    if (!setjmp(finished)) led_task(NULL);
    assert(led_waits == 2 && !led_enabled && led_level == 1);
    led_disable_first = true; led_enabled = true; led_waits = 0;
    if (!setjmp(finished)) led_task(NULL);
    assert(led_waits == 1 && !led_enabled && led_level == 1);
    led_disable_first = false;
    drop_led_once = true; led_enabled = true; led_waits = led_calls = 0;
    if (!setjmp(finished)) led_task(NULL);
    assert(led_race_done && led_waits == 1 && !led_enabled && led_level == 1);
    led_race_done = false;
    for (unsigned mode = 1; mode <= 3; mode++) {
        led_fail_at = mode == 3 ? 1 : mode;
        led_enabled = mode != 3; led_calls = led_waits = 0;
        unsigned before_abort = abort_calls;
        if (!setjmp(finished)) { led_task(NULL); assert(false); }
        assert(abort_calls == before_abort + 1 && led_calls == led_fail_at);
        critical_depth = 0; /* Fatal path terminates the task; reset the fixture. */
    }
    led_fail_at = 1; led_calls = 0; led_enabled = true;
    unsigned before_led = abort_calls;
    if (!setjmp(finished)) { set_led_enabled(false); assert(false); }
    assert(abort_calls == before_led + 1 && led_calls == 1);
    led_fail_at = 0; critical_depth = 0;
    led_learning = true; led_enabled = false; led_fail_at = 1; led_calls = 0;
    unsigned before_learn_led = abort_calls;
    if (!setjmp(finished)) { led_task(NULL); assert(false); }
    assert(abort_calls == before_learn_led + 1 && led_calls == 1);
    led_fail_at = 0; critical_depth = 0;
    for (unsigned race = 1; race <= 3; race++) {
        led_learning = race == 1; led_enabled = false; led_level = 1;
        led_race_mode = race; led_calls = 0;
        if (!setjmp(finished)) led_task(NULL);
        assert(led_race_mode == 0 && critical_depth == 0 && led_calls == 0);
    }
    led_learning = false; led_enabled = false;
    led_enabled = true; led_race_mode = 4; led_flow = 3;
    led_step = 0; led_calls = 0;
    if (!setjmp(finished)) led_task(NULL);
    assert(led_race_mode == 0 && critical_depth == 0 && led_calls > 0);
    led_flow = 0; led_learning = false; led_enabled = false;
    puts("学习 LED 故障及进入临界区前状态变化检查通过");
    fail_led_config = true;
    led_task(NULL);
    fail_led_config = false;
    led_test = false;
    for (boot_fault = 1; boot_fault <= 13; boot_fault++) {
        unsigned before_abort = abort_calls;
        run_control(1000, NULL, 0, false, false, false, 0);
        assert(abort_calls == before_abort + 1 && sample_count == 0 && send_count == 0);
    }
    boot_fault = 0;
    for (boot_fault = 11; boot_fault <= 12; boot_fault++) {
        unsigned before_abort = abort_calls;
        TickType_t high_at = xTaskGetTickCount() - pdMS_TO_TICKS(20);
        bool high = true;
        if (!setjmp(finished)) { wait_button_release(&high_at, &high); assert(false); }
        assert(abort_calls == before_abort + 1);
    }
    boot_fault = 0;
    app_reset_rule(-1); app_reset_rule(2);
    TickType_t high_at = 0;
    bool high = true;
    frozen_ticks = true; frozen_value = pdMS_TO_TICKS(10);
    assert(!wait_button_release(&high_at, &high) && high);
    frozen_ticks = false;
    assert(app_save_rule(1, &replacement) == ESP_OK);
    led_handle = NULL; led_enabled = false;
    set_led_enabled(true);
    assert(led_enabled && critical_depth == 0);
    led_enabled = false; led_handle = (void *)2;
#if defined(CONFIG_APP_IDLE_BOOT_PINS) || defined(CONFIG_APP_QUIET_UART)
    fail_idle_config = true;
    unsigned before_idle = abort_calls;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(abort_calls == before_idle + 1 && sample_count == 0);
    fail_idle_config = false;
#endif
    const event_t capture_events[] = {{0, 3, 0}};
    learn_mock = IR_CAPTURING;
    run_control(1000, capture_events, 1, false, false, false, 0);
    assert(send_count == 0 && current.temp_valid && !states[0].primed);
    learn_mock = IR_WAITING;
    boot_ir_busy = true;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(send_count == 0 && conversion_awake == 1 && conversion_sleeps == 0);
    boot_ir_busy = false;
    const event_t retry_stop[] = {{500, 1, 20}, {1000, 2, 20}};
    fail_portal_stop_once = true;
    run_control(5000, retry_stop, 2, false, false, false, 0);
    assert(!ap && ap_stops == 1);
    const event_t debounce_s1[] = {{1000, 1, 20}, {1050, 1, 20}};
    run_control(2000, debounce_s1, 2, false, false, false, 0);
    assert(ap && ap_starts == 1);
    const event_t bounce_s1[] = {{1000, 1, 20}, {1030, 1, 20}};
    run_control(2000, bounce_s1, 2, false, false, false, 0);
    assert(ap && ap_starts == 1 && blocked_keys == 1);
    const event_t bounce_s2[] = {{1000, 2, 20}, {1030, 2, 20}};
    run_control(2000, bounce_s2, 2, false, false, false, 0);
    assert(!ap && blocked_keys == 1);
    const event_t debounce_s2[] = {{1000, 2, 20}, {1050, 2, 20}};
    run_control(2000, debounce_s2, 2, false, false, false, 0);
    assert(!ap && ap_stops == 0);
    boot_held_s1 = true;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(ap && ap_starts == 1 && send_count == 0);
    boot_held_s1 = false;
    boot_fault = 14;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(sleep_failed && !auto_sleep && sample_count == 1);
    boot_fault = 0;
    fail_portal_start_once = true;
    run_control(2000, debounce_s1, 1, false, false, false, 0);
    assert(!ap && ap_starts == 0);
    fail_portal_stop_once = true;
    run_control(185000, debounce_s1, 1, false, false, false, 0);
    assert(!ap && ap_stops == 1);
    unsigned before_zero = zero_waits;
    report_delay = 61000;
    run_control(70000, NULL, 0, false, false, false, 0);
    assert(zero_waits > before_zero && sample_count == 2);
    /* 网页校准基于未追加校准的样本；模拟提交、重启及错误，不访问真实 NVS。 */
    bool storage_failed = true;
    assert(app_calibrate(false, 250, NULL) == ESP_ERR_INVALID_ARG);
    assert(app_calibrate(false, 501, &storage_failed) == ESP_ERR_INVALID_ARG && !storage_failed);
    assert(app_calibrate(true, 2499, &storage_failed) == ESP_ERR_INVALID_ARG);
    adc_raw = 702;
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(base_battery_mv == 3595 && base_temp10 == 260);
    states[0].primed = true; trend.count = 3; last_send[0] = 123; send_recorded[0] = true;
    assert(app_calibrate(false, 280, &storage_failed) == ESP_OK && !storage_failed);
    assert(current.temp10 == 280 && temp_adjust10 == 20 && trend.count == 0 && !states[0].primed);
    assert(last_send[0] == 123 && send_recorded[0]);
    assert(app_calibrate(false, 280, &storage_failed) == ESP_OK && temp_adjust10 == 20);
    assert(app_calibrate(false, 311, &storage_failed) == ESP_ERR_INVALID_ARG);
    assert(app_calibrate(false, 210, &storage_failed) == ESP_OK && temp_adjust10 == -50);
    assert(app_calibrate(false, 209, &storage_failed) == ESP_ERR_INVALID_ARG && temp_adjust10 == -50);
    assert(app_calibrate(false, 310, &storage_failed) == ESP_OK && temp_adjust10 == 50);
    assert(app_calibrate(false, 280, &storage_failed) == ESP_OK && temp_adjust10 == 20);
    assert(app_calibrate(true, 4000, &storage_failed) == ESP_OK && current.battery_mv == 4000);
    assert(app_calibrate(true, 4000, &storage_failed) == ESP_OK && battery_adjust.base_mv == 3595);
    assert(adjusted_battery(3994) == 4444); /* boot/sleep 已换算值再应用统一比例。 */
    now_ms += 6000;
    assert(app_calibrate(false, 270, &storage_failed) == ESP_ERR_INVALID_STATE);
    assert(app_calibrate(true, 3900, &storage_failed) == ESP_ERR_INVALID_STATE);
    run_control(4000, battery_ap, 1, false, false, false, 0);
    assert(temp_adjust10 == 20 && current.temp10 == 280 && current.battery_mv == 4000);
    rule_open_error = ESP_FAIL;
    assert(app_calibrate(false, 270, &storage_failed) == ESP_FAIL && storage_failed);
    rule_open_error = ESP_OK; rule_save_error = ESP_ERR_INVALID_STATE;
    assert(app_calibrate(true, 3900, &storage_failed) == ESP_ERR_INVALID_STATE && storage_failed);
    rule_save_error = ESP_OK; rule_commit_error = ESP_FAIL;
    assert(app_calibrate(false, 270, &storage_failed) == ESP_FAIL && storage_failed);
    assert(temp_adjust10 == 20 && current.temp10 == 280 && current.battery_mv == 4000);
    rule_commit_error = ESP_OK;
    current.temp_valid = false;
    assert(app_calibrate(false, 270, &storage_failed) == ESP_ERR_INVALID_STATE && !storage_failed);
    current.temp_valid = true; current.battery_valid = false;
    assert(app_calibrate(true, 3900, &storage_failed) == ESP_ERR_INVALID_STATE);
    current.battery_valid = true; base_battery_mv = 0;
    assert(app_calibrate(true, 3900, &storage_failed) == ESP_ERR_INVALID_STATE);
    base_battery_mv = 1000;
    assert(app_calibrate(true, 3900, &storage_failed) == ESP_ERR_INVALID_ARG);
    base_battery_mv = 3595; battery_sample_ap = false;
    assert(app_calibrate(true, 3900, &storage_failed) == ESP_ERR_INVALID_STATE);
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.temp10 == 270 && current.battery_mv == 3969 && !ap);
    assert(send_count == 1); /* 追加温度偏移参与规则判断。 */
    assert(app_calibrate(false, 270, &storage_failed) == ESP_ERR_INVALID_STATE);
    adc_raw = 910;
    run_control(61000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 4732 && adc_sleep_seen && current.temp10 == 280);
    assert(strstr(last_battery_log, "base_mv=4253 ratio=4000/3595 phase=cold-start off_sample=2 off_ms=0"));
    /* 扣除已有网页比例后拟合 boot/sleep，保留 AP，不重复追加补偿。 */
    battery_adjust_t observed_voltage = {3794, 3790};
    memcpy(cal_saved[1], &observed_voltage, sizeof(observed_voltage));
    adc_raw = 746;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(current.battery_mv == 3795 && base_battery_mv == 3791);
    assert(strstr(last_battery_log, "cal=boot base_mv=3791 ratio=3794/3790 phase=cold-start"));
    adc_raw = 811;
    const event_t off_battery[] = {{1000,1,0}, {5000,2,0}};
    run_control(66000, off_battery, 2, false, false, false, 0);
    assert(current.battery_mv == 3795 && battery_off_samples == 1);
    assert(strstr(last_battery_log, "cal=sleep base_mv=3791 ratio=3794/3790 phase=after-ap off_sample=1 off_ms="));
    adc_raw = 812;
    run_control(66000, off_battery, 2, false, false, false, 0);
    assert(current.battery_mv == 3799);
    adc_raw = 748;
    run_control(66000, off_battery, 2, false, false, false, 0);
    assert(current.battery_mv == 3500);
    adc_raw = 747;
    run_control(66000, off_battery, 2, false, false, false, 0);
    assert(current.battery_mv < 3500);
    adc_raw = 811;
    run_control(186000, off_battery, 2, false, false, false, 0);
    assert(battery_off_samples == 3 && strstr(last_battery_log, "phase=after-ap off_sample=3"));
    const event_t reopen_battery[] = {{1000,1,0}, {5000,2,0}, {65000,1,0}, {70000,2,0}};
    run_control(132000, reopen_battery, 4, false, false, false, 0);
    assert(battery_off_samples == 1 && strstr(last_battery_log, "phase=after-ap off_sample=1"));
    adc_error = ESP_FAIL;
    run_control(66000, off_battery, 2, false, false, false, 0);
    assert(!current.battery_valid && strstr(last_battery_log, "battery read failed:") &&
           strstr(last_battery_log, "phase=after-ap off_sample=1"));
    adc_error = ESP_OK;
    /* 网页目标修改及重启后，boot/AP/sleep 均使用新比例，不固定为3795mV。 */
    const int voltage_targets[] = {3500, 3795, 4000};
    for (unsigned i = 0; i < 3; i++) {
        int target = voltage_targets[i];
        adc_raw = 740;
        run_control(4000, battery_ap, 1, false, false, false, 0);
        assert(base_battery_mv == 3790);
        assert(app_calibrate(true, target, &storage_failed) == ESP_OK);
        assert(app_calibrate(true, target, &storage_failed) == ESP_OK);
        assert(current.battery_mv == target && battery_adjust.base_mv == 3790 &&
               battery_adjust.reference_mv == target);
        adc_raw = 746;
        run_control(1000, NULL, 0, false, false, false, 0);
        assert(current.battery_mv >= target && current.battery_mv <= target + 2);
        adc_raw = 811;
        run_control(66000, off_battery, 2, false, false, false, 0);
        assert(current.battery_mv >= target && current.battery_mv <= target + 2);
    }
    battery_adjust_t saved_voltage = {4000, 3595};
    memcpy(cal_saved[1], &saved_voltage, sizeof(saved_voltage));
    assert(load_calibration() == ESP_OK);
    cal_read_error = ESP_FAIL;
    assert(load_calibration() == ESP_FAIL && temp_adjust10 == 20);
    cal_read_error = ESP_OK;
    cal_sizes[0] = 1;
    assert(load_calibration() == ESP_ERR_INVALID_STATE);
    cal_sizes[0] = 2; int16_t bad_offset = 51;
    memcpy(cal_saved[0], &bad_offset, sizeof(bad_offset));
    assert(load_calibration() == ESP_ERR_INVALID_STATE);
    bad_offset = 20; memcpy(cal_saved[0], &bad_offset, sizeof(bad_offset));
    battery_adjust_t bad_voltage = {4000, 0};
    memcpy(cal_saved[1], &bad_voltage, sizeof(bad_voltage));
    assert(load_calibration() == ESP_ERR_INVALID_STATE);
    memset(cal_sizes, 0, sizeof(cal_sizes));
    assert(load_calibration() == ESP_OK && temp_adjust10 == 0 && battery_adjust.reference_mv == 1);
    /* 校准新增边界、独立存储失败与启动致命路径。 */
    app_set_learning(false); led_handle = NULL;
    app_set_learning(true); app_set_learning(false);
    assert(!led_learning && critical_depth == 0);
    assert(app_calibrate(true, 4501, &storage_failed) == ESP_ERR_INVALID_ARG);
    assert(app_calibrate(false, -101, &storage_failed) == ESP_ERR_INVALID_ARG);
    const battery_adjust_t invalid_voltage[] = {
        {2499, 3000}, {4501, 3000}, {4000, 0}, {2500, 5001}, {4500, 2999}
    };
    for (unsigned i = 0; i < sizeof(invalid_voltage) / sizeof(invalid_voltage[0]); i++) {
        assert(!battery_adjust_valid(&invalid_voltage[i]));
        cal_sizes[1] = sizeof(invalid_voltage[i]);
        memcpy(cal_saved[1], &invalid_voltage[i], cal_sizes[1]);
        assert(load_calibration() == ESP_ERR_INVALID_STATE);
        assert(temp_adjust10 == 0 && battery_adjust.reference_mv == 1);
    }
    assert(battery_adjust_valid(&(battery_adjust_t){2500, 5000}));
    assert(battery_adjust_valid(&(battery_adjust_t){4500, 3000}));
    cal_sizes[1] = 1;
    assert(load_calibration() == ESP_ERR_INVALID_STATE);
    int16_t negative_offset = -51;
    cal_sizes[0] = sizeof(negative_offset);
    memcpy(cal_saved[0], &negative_offset, sizeof(negative_offset));
    assert(load_calibration() == ESP_ERR_INVALID_STATE);
    memset(cal_sizes, 0, sizeof(cal_sizes));
    cal_read_kind = 1; cal_read_error = ESP_FAIL;
    assert(load_calibration() == ESP_FAIL);
    cal_read_kind = -1; cal_read_error = ESP_OK;
    cal_open_error = ESP_ERR_NVS_NOT_FOUND;
    temp_adjust10 = 20; battery_adjust = (battery_adjust_t){4000, 3595};
    assert(load_calibration() == ESP_OK && temp_adjust10 == 0);
    assert(battery_adjust.reference_mv == 1 && battery_adjust.base_mv == 1);
    cal_open_error = ESP_FAIL;
    assert(load_calibration() == ESP_FAIL);
    cal_open_error = ESP_OK; cal_read_error = ESP_FAIL;
    unsigned before_cal_abort = abort_calls;
    run_control(1000, NULL, 0, false, false, false, 0);
    assert(abort_calls == before_cal_abort + 1 && sample_count == 0);
    cal_read_error = ESP_OK;
    run_control(1000, NULL, 0, false, false, false, 0);
    set_auto_sleep(false);
    battery_off_samples = UINT32_MAX;
    update_temp();
    assert(battery_off_samples == UINT32_MAX);
    puts("校准边界、存储失败、启动失败及采样计数饱和检查通过");
    puts("power control: web calibration persistence/failures/freshness, state voltage, trend, LED, battery and AP lifecycle passed");
    return 0;
}

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
#if defined(TEST_IDLE_PINS) || defined(TEST_IR_NVS)
    char record[512];
    va_list record_args;
    va_start(record_args, fmt);
    vsnprintf(record, sizeof(record), fmt, record_args);
    va_end(record_args);
#endif
#ifdef TEST_IDLE_PINS
    if (strstr(fmt, "battery=") || strstr(fmt, "battery read failed:"))
        snprintf(last_battery_log, sizeof(last_battery_log), "%s", record);
    if (strstr(fmt, "button_trace:")) {
        assert(critical_depth == 0 && !auto_sleep);
        assert(strstr(record, "levels=") && strstr(record, "intr=") &&
               strstr(record, "wake=") && strstr(record, "isr=") && strstr(record, "pending="));
        if (strstr(record, "stage=wait-enter ")) wait_enter_logs++;
        if (strstr(record, "stage=wait-done ")) {
            wait_done_logs++;
            if (strstr(record, "notified=1 ")) wait_key_logs++;
        }
        if (strstr(record, "stage=conversion-enter ")) conversion_enter_logs++;
        if (strstr(record, "stage=conversion-done ")) conversion_done_logs++;
        if (strstr(record, "stage=button-dispatch ")) dispatch_logs++;
        if (strstr(record, "stage=release-enter ")) release_enter_logs++;
        if (strstr(record, "stage=release-done ")) release_done_logs++;
    }
#endif
#ifdef TEST_IR_NVS
    if (strstr(record, "learn RX:")) rx_trace_logs++;
    if (strstr(record, "learn slot") && strstr(record, "stage="))
        snprintf(last_learn_stage, sizeof(last_learn_stage), "%s", strstr(record, "stage=") + 6);
    if (strstr(record, "rejected: ESP_ERR_INVALID_STATE")) busy_reject_logs++;
    if (strstr(record, "previous NVS code restored and verified")) restore_ok_logs++;
    if (strstr(record, "NVS restore failed:")) {
        assert(strstr(record, "persistent code uncertain, re-learn required"));
        restore_error_logs++;
    }
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
SemaphoreHandle_t xSemaphoreCreateMutex(void) {
#ifdef TEST_IDLE_PINS
    if (boot_fault == 2) return NULL;
#endif
    return (void *)1;
}
SemaphoreHandle_t xSemaphoreCreateBinary(void) {
#ifdef TEST_IR_NVS
    if (ir_init_testing && ir_init_result() != ESP_OK) return NULL;
#endif
    return (void *)2;
}
BaseType_t xSemaphoreGive(SemaphoreHandle_t sem) { (void)sem; return pdTRUE; }
esp_err_t gpio_config(const gpio_config_t *cfg) {
#ifdef TEST_SENSOR_INIT
    if (fail_sensor_config) return ESP_FAIL;
#endif
#ifdef TEST_IR_NVS
    if (ir_init_testing && ir_init_result() != ESP_OK) return ESP_FAIL;
#endif
#ifdef TEST_IDLE_PINS
    if (boot_fault == 4 && (cfg->pin_bit_mask & (1U << 12))) return ESP_FAIL;
    if ((cfg->pin_bit_mask & (1U << 2)) && fail_led_config) return ESP_FAIL;
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
#ifdef TEST_IDLE_PINS
    if ((boot_fault == 11 && pin == 12) || (boot_fault == 12 && pin == 13)) return ESP_FAIL;
#endif
#ifdef TEST_IR_NVS
    assert(pin == 5 && type == GPIO_INTR_ANYEDGE && rx_handler == capture_isr);
    assert(GPIO.pin[5].int_type == GPIO_INTR_DISABLE && GPIO.status_w1tc == (1U << 5));
    rx_enable_calls++;
    if (rx_enable_error) return rx_enable_error;
#endif
    GPIO.pin[pin].int_type = type; return ESP_OK;
}
esp_err_t gpio_isr_handler_add(int pin, TaskFunction_t cb, void *arg) {
#ifdef TEST_IDLE_PINS
    if ((boot_fault == 8 && pin == 12) || (boot_fault == 9 && pin == 13)) return ESP_FAIL;
#endif
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
esp_err_t gpio_install_isr_service(int flags) {
    (void)flags;
#ifdef TEST_IR_NVS
    if (ir_init_testing) return ir_init_result();
#endif
    return ESP_OK;
}
void nvs_close(nvs_handle handle) {
    (void)handle;
#ifdef TEST_IDLE_PINS
    cal_pending_kind = -1;
#endif
}
#ifndef TEST_IR_NVS
esp_err_t nvs_set_blob(nvs_handle handle, const char *key, const void *data, size_t size) {
#ifdef TEST_IDLE_PINS
    if (rule_save_error) return rule_save_error;
    if (strcmp(key, "temp_adj") == 0 || strcmp(key, "bat_adj") == 0) {
        assert(size <= sizeof(cal_pending));
        cal_pending_kind = strcmp(key, "temp_adj") == 0 ? 0 : 1;
        cal_pending_size = size; memcpy(cal_pending, data, size);
    }
#endif
    (void)handle; (void)key; (void)data; (void)size; return ESP_OK;
}
esp_err_t nvs_set_u16(nvs_handle handle, const char *key, uint16_t value) {
    (void)handle; (void)key; (void)value; return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle handle) {
#ifdef TEST_IDLE_PINS
    if (rule_commit_error) return rule_commit_error;
    if (cal_pending_kind >= 0) {
        cal_sizes[cal_pending_kind] = cal_pending_size;
        memcpy(cal_saved[cal_pending_kind], cal_pending, cal_pending_size);
    }
#endif
    (void)handle; return ESP_OK;
}
#endif
