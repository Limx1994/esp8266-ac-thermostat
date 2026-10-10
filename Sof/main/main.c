#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "driver/rtc.h"
#include "esp8266/gpio_struct.h"
#include "esp_wifi.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include "esp_attr.h"
#include "esp_clk.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "app.h"
#include "sensor.h"
#include "ir.h"
#include "portal.h"
#include "sleep_trace.h"
#include "rom/uart.h"

static const char *TAG = "thermostat";
static SemaphoreHandle_t status_lock;
static app_status_t current;
static rule_state_t states[2];
static rule_trend_t trend;
static TickType_t last_send[2];
static bool send_recorded[2];
static volatile bool s1_pending;
static volatile bool s2_pending;
static volatile uint32_t button_count[2];
static TaskHandle_t main_handle;
static volatile bool led_enabled;
static volatile bool led_learning;
static TaskHandle_t led_handle;
static bool auto_sleep;
static bool sleep_failed;
static bool adc_sleep_seen;
static bool battery_ap_active, battery_after_ap;
static TickType_t battery_off_tick;
static uint32_t battery_off_samples;
static int16_t temp_adjust10;
typedef struct { uint16_t reference_mv, base_mv; } battery_adjust_t;
static battery_adjust_t battery_adjust = {1, 1};
static int16_t base_temp10;
static uint16_t base_battery_mv;
static TickType_t temp_sample_tick, battery_sample_tick;
static bool battery_sample_ap;

#ifdef CONFIG_APP_QUIET_UART
static int quiet_log(int ch)
{
    return ch;
}
#endif

static esp_err_t init_idle_pins(void)
{
    gpio_config_t cfg = {
        .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE
    };
#ifdef CONFIG_APP_IDLE_BOOT_PINS
    cfg.pin_bit_mask = (1ULL << GPIO_NUM_0) | (1ULL << GPIO_NUM_15);
    esp_err_t err = gpio_config(&cfg);
    if (err != ESP_OK) return err;
#endif
#ifdef CONFIG_APP_QUIET_UART
    ESP_LOGI(TAG, "power measurement: runtime logs off; GPIO1 input");
    esp_log_level_set("*", ESP_LOG_NONE);
    esp_log_set_putchar(quiet_log);
    uart_tx_wait_idle(CONFIG_ESP_CONSOLE_UART_NUM);
    cfg.pin_bit_mask = 1ULL << GPIO_NUM_1;
    return gpio_config(&cfg);
#else
    (void)cfg;
    return ESP_OK;
#endif
}

/* 限制单次等待，兼容 80/160 MHz 下的 SDK 32 位休眠时钟补偿。 */
#define SLEEP_WAIT_MS (UINT32_MAX / (CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ * 1000U) - 1000U)
/* boot/sleep 使用同一 3994 mV 标尺，随后统一应用网页人工校准比例。 */
#define BATTERY_CAL_MV 3994U
/* 2026-10-10：boot ADC746、稳定参考 3795 mV，扣除网页比例 3794/3790。 */
#define BATTERY_BOOT_ADC 786U
/* 2026-10-10 AP 同步对照：adc=702，电池端实测 3595 mV。 */
#define BATTERY_AP_CAL_MV 3595U
#define BATTERY_AP_ADC_X2 1404U
/* 2026-10-10：11 次 ADC 均值 811.09、实测 3795 mV，扣除网页比例 3794/3790。 */
#define BATTERY_SLEEP_ADC_X2 1709U

static esp_err_t check_cpu_freq(void)
{
    unsigned expected = CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ;
    unsigned hardware = rtc_clk_cpu_freq_get() == RTC_CPU_FREQ_80M ? 80U : 160U;
    unsigned software = esp_clk_cpu_freq();
    if (hardware != expected || software != expected * 1000000U) {
        ESP_LOGE(TAG, "CPU frequency mismatch: expected=%u MHz hardware=%u MHz software=%u Hz",
                 expected, hardware, software);
        return ESP_ERR_INVALID_STATE;
    }
    ESP_LOGI(TAG, "CPU frequency verified: %u MHz", expected);
    return ESP_OK;
}

/* 休眠配置失败后尝试禁用并锁定降级状态；若无法退出已开启的休眠则终止。 */
static void set_auto_sleep(bool enabled)
{
    if (sleep_failed || auto_sleep == enabled) return;
    esp_pm_config_esp8266_t cfg = { .light_sleep_enable = enabled };
    esp_err_t err = esp_pm_configure(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "automatic sleep configuration failed: %s", esp_err_to_name(err));
        cfg.light_sleep_enable = false;
        esp_err_t restore = esp_pm_configure(&cfg);
        if (restore != ESP_OK) {
            ESP_LOGE(TAG, "could not disable automatic sleep: %s", esp_err_to_name(restore));
            if (auto_sleep) abort();
        }
        auto_sleep = false;
        sleep_failed = true;
        ESP_LOGW(TAG, "automatic sleep disabled; temperature control continues");
        return;
    }
    auto_sleep = enabled;
}

static void set_led_enabled(bool enabled)
{
    if (led_enabled == enabled) return;
    portENTER_CRITICAL();
    led_enabled = enabled;
    if (!enabled && !led_learning) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
    portEXIT_CRITICAL();
    if (led_handle) xTaskNotifyGive(led_handle);
}

void app_set_learning(bool active)
{
    portENTER_CRITICAL();
    led_learning = active;
    portEXIT_CRITICAL();
    if (led_handle) xTaskNotifyGive(led_handle);
}

static void IRAM_ATTR button_isr(void *arg)
{
    int pin = arg ? GPIO_NUM_13 : GPIO_NUM_12;
    button_count[arg ? 1 : 0]++;
    /* 按键持续低电平时先禁用中断；主任务确认释放后再启用，防止反复唤醒。 */
    GPIO.pin[pin].int_type = GPIO_INTR_DISABLE;
    GPIO.status_w1tc = 1U << pin;
    if (arg) s2_pending = true;
    else s1_pending = true;
    BaseType_t wake = pdFALSE;
    vTaskNotifyGiveFromISR(main_handle, &wake);
    if (wake) portYIELD_FROM_ISR();
}

/* 只在任务上下文输出；快照不等于硬件唤醒原因。 */
static void trace_buttons(const char *stage, TickType_t wait, uint32_t notices)
{
    portENTER_CRITICAL();
    uint32_t s1_count = button_count[0], s2_count = button_count[1];
    bool s1 = s1_pending, s2 = s2_pending;
    uint32_t levels = GPIO.in;
    unsigned intr1 = GPIO.pin[GPIO_NUM_12].int_type;
    unsigned intr2 = GPIO.pin[GPIO_NUM_13].int_type;
    unsigned wake1 = GPIO.pin[GPIO_NUM_12].wakeup_enable;
    unsigned wake2 = GPIO.pin[GPIO_NUM_13].wakeup_enable;
    portEXIT_CRITICAL();
    ESP_LOGI(TAG, "button_trace: stage=%s tick=%u wait_ticks=%u notified=%u auto=%d busy=%d levels=%u/%u intr=%u/%u wake=%u/%u isr=%u/%u pending=%d/%d",
             stage, (unsigned)xTaskGetTickCount(), (unsigned)wait, (unsigned)notices,
             auto_sleep, ir_is_busy(), (unsigned)((levels >> 12) & 1),
             (unsigned)((levels >> 13) & 1), intr1, intr2, wake1, wake2,
             (unsigned)s1_count, (unsigned)s2_count, s1, s2);
}

static void led_task(void *arg)
{
    (void)arg;
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << GPIO_NUM_2,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    esp_err_t err = gpio_config(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "led gpio_config failed: %s", esp_err_to_name(err));
        vTaskDelete(NULL);
        return;
    }
    while (true) {
        if (led_learning) {
            portENTER_CRITICAL();
            if (led_learning) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 0));
            portEXIT_CRITICAL();
            ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        } else if (led_enabled) {
            portENTER_CRITICAL();
            if (led_enabled || led_learning) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 0));
            portEXIT_CRITICAL();
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(500));
            portENTER_CRITICAL();
            if (!led_learning) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
            portEXIT_CRITICAL();
            if (led_enabled && !led_learning) ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(500));
        } else {
            portENTER_CRITICAL();
            if (!led_learning && !led_enabled) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
            portEXIT_CRITICAL();
            ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        }
    }
}

/* 规则默认禁用；允许 NVS 尚无配置，但已有配置损坏时返回错误。 */
static esp_err_t load_rules(void)
{
    current.rules[0] = (rule_cfg_t){ .threshold10 = 220, .rising = 0, .enabled = 0 };
    current.rules[1] = (rule_cfg_t){ .threshold10 = 260, .rising = 1, .enabled = 0 };
    nvs_handle handle;
    esp_err_t err = nvs_open("ac", NVS_READONLY, &handle);
    if (err == ESP_ERR_NVS_NOT_FOUND) return ESP_OK;
    if (err != ESP_OK) return err;
    for (int i = 0; i < 2; i++) {
        size_t size = sizeof(rule_cfg_t);
        err = nvs_get_blob(handle, i == 0 ? "rule0" : "rule1", &current.rules[i], &size);
        if (err == ESP_ERR_NVS_NOT_FOUND) continue;
        if (err != ESP_OK || size != sizeof(rule_cfg_t) || !rule_valid(&current.rules[i])) {
            ESP_LOGE(TAG, "invalid stored rule %d: %s", i + 1, esp_err_to_name(err));
            nvs_close(handle);
            return err == ESP_OK ? ESP_ERR_INVALID_STATE : err;
        }
    }
    nvs_close(handle);
    return ESP_OK;
}

void app_get_status(app_status_t *status)
{
    xSemaphoreTake(status_lock, portMAX_DELAY);
    *status = current;
    xSemaphoreGive(status_lock);
}

static bool battery_adjust_valid(const battery_adjust_t *value)
{
    return value->reference_mv >= 2500 && value->reference_mv <= 4500 &&
           value->base_mv && value->reference_mv * 2U >= value->base_mv &&
           value->reference_mv * 2U <= value->base_mv * 3U;
}

static uint16_t adjusted_battery(unsigned base)
{
    return ((uint32_t)base * battery_adjust.reference_mv + battery_adjust.base_mv / 2U) /
           battery_adjust.base_mv;
}

static esp_err_t load_calibration(void)
{
    int16_t offset = 0;
    battery_adjust_t voltage = {1, 1};
    nvs_handle handle;
    esp_err_t err = nvs_open("ac", NVS_READONLY, &handle);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        temp_adjust10 = offset;
        battery_adjust = voltage;
        return ESP_OK;
    }
    if (err != ESP_OK) return err;
    size_t size = sizeof(offset);
    err = nvs_get_blob(handle, "temp_adj", &offset, &size);
    if (err == ESP_ERR_NVS_NOT_FOUND) { offset = 0; err = ESP_OK; }
    else if (err == ESP_OK && (size != sizeof(offset) || offset < -50 || offset > 50))
        err = ESP_ERR_INVALID_STATE;
    if (err == ESP_OK) {
        size = sizeof(voltage);
        err = nvs_get_blob(handle, "bat_adj", &voltage, &size);
        if (err == ESP_ERR_NVS_NOT_FOUND) { voltage = (battery_adjust_t){1, 1}; err = ESP_OK; }
        else if (err == ESP_OK && (size != sizeof(voltage) || !battery_adjust_valid(&voltage)))
            err = ESP_ERR_INVALID_STATE;
    }
    nvs_close(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "calibration load failed: %s", esp_err_to_name(err));
        return err;
    }
    temp_adjust10 = offset;
    battery_adjust = voltage;
    ESP_LOGI(TAG, "calibration loaded: offset10=%d voltage=%u/%u",
             offset, (unsigned)voltage.reference_mv, (unsigned)voltage.base_mv);
    return ESP_OK;
}

esp_err_t app_calibrate(bool battery, int reference, bool *storage_failed)
{
    if (!storage_failed) return ESP_ERR_INVALID_ARG;
    *storage_failed = false;
    if (battery ? (reference < 2500 || reference > 4500) :
                  (reference < -100 || reference > 500)) return ESP_ERR_INVALID_ARG;
    xSemaphoreTake(status_lock, portMAX_DELAY);
    TickType_t age = xTaskGetTickCount() - (battery ? battery_sample_tick : temp_sample_tick);
    bool valid = battery ? current.battery_valid && battery_sample_ap && base_battery_mv :
                           current.temp_valid;
    if (!portal_is_on() || !valid || age > pdMS_TO_TICKS(5000)) {
        xSemaphoreGive(status_lock);
        return ESP_ERR_INVALID_STATE;
    }
    int offset = reference - base_temp10;
    battery_adjust_t voltage = {(uint16_t)reference, base_battery_mv};
    if (battery ? !battery_adjust_valid(&voltage) : (offset < -50 || offset > 50)) {
        xSemaphoreGive(status_lock);
        return ESP_ERR_INVALID_ARG;
    }
    nvs_handle handle;
    esp_err_t err = nvs_open("ac", NVS_READWRITE, &handle);
    if (err == ESP_OK) {
        int16_t stored_offset = offset;
        err = nvs_set_blob(handle, battery ? "bat_adj" : "temp_adj",
                           battery ? (const void *)&voltage : (const void *)&stored_offset,
                           battery ? sizeof(voltage) : sizeof(stored_offset));
        if (err == ESP_OK) err = nvs_commit(handle);
        nvs_close(handle);
    }
    *storage_failed = err != ESP_OK;
    if (err == ESP_OK) {
        if (battery) {
            battery_adjust = voltage;
            current.battery_mv = adjusted_battery(base_battery_mv);
        } else {
            temp_adjust10 = offset;
            current.temp10 = base_temp10 + temp_adjust10;
            memset(states, 0, sizeof(states));
            rule_trend_reset(&trend);
        }
    }
    xSemaphoreGive(status_lock);
    if (err != ESP_OK) ESP_LOGE(TAG, "calibration save failed: %s", esp_err_to_name(err));
    else if (battery) ESP_LOGI(TAG, "battery calibration saved: reference_mv=%u base_mv=%u",
                              (unsigned)voltage.reference_mv, (unsigned)voltage.base_mv);
    else ESP_LOGI(TAG, "temperature calibration saved: offset10=%d", offset);
    return err;
}

esp_err_t app_save_rule(int slot, const rule_cfg_t *rule)
{
    if (slot < 0 || slot > 1 || !rule_valid(rule)) return ESP_ERR_INVALID_ARG;
    nvs_handle handle;
    esp_err_t err = nvs_open("ac", NVS_READWRITE, &handle);
    if (err != ESP_OK) return err;
    err = nvs_set_blob(handle, slot == 0 ? "rule0" : "rule1", rule, sizeof(*rule));
    if (err == ESP_OK) err = nvs_commit(handle);
    nvs_close(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "rule %d save failed: %s", slot + 1, esp_err_to_name(err));
        return err;
    }
    xSemaphoreTake(status_lock, portMAX_DELAY);
    /* 仅在持久化成功后发布新规则，避免页面状态与 NVS 不一致。 */
    current.rules[slot] = *rule;
    memset(&states[slot], 0, sizeof(states[slot]));
    xSemaphoreGive(status_lock);
    ESP_LOGI(TAG, "rule %d saved: threshold10=%d rising=%d enabled=%d",
             slot + 1, rule->threshold10, rule->rising, rule->enabled);
    return ESP_OK;
}

void app_reset_rule(int slot)
{
    if (slot < 0 || slot > 1) return;
    xSemaphoreTake(status_lock, portMAX_DELAY);
    memset(&states[slot], 0, sizeof(states[slot]));
    xSemaphoreGive(status_lock);
}

static esp_err_t init_buttons(void)
{
    gpio_config_t cfg = {
        .pin_bit_mask = (1ULL << GPIO_NUM_12) | (1ULL << GPIO_NUM_13),
        .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE
    };
    return gpio_config(&cfg);
}

/* 等待两键都释放并经过 20 ms 确认，再恢复低电平唤醒中断。 */
static void wait_button_release(void)
{
    trace_buttons("release-enter", 0, 0);
    while (true) {
        while (gpio_get_level(GPIO_NUM_12) == 0 || gpio_get_level(GPIO_NUM_13) == 0)
            vTaskDelay(pdMS_TO_TICKS(20));
        vTaskDelay(pdMS_TO_TICKS(20));
        if (gpio_get_level(GPIO_NUM_12) && gpio_get_level(GPIO_NUM_13)) break;
    }
    ESP_ERROR_CHECK(gpio_set_intr_type(GPIO_NUM_12, GPIO_INTR_LOW_LEVEL));
    ESP_ERROR_CHECK(gpio_set_intr_type(GPIO_NUM_13, GPIO_INTR_LOW_LEVEL));
    trace_buttons("release-done", 0, 0);
}

static void update_temp(void)
{
    ir_report_last_send();
    ESP_LOGI(TAG, "sampling: AP=%s", portal_is_on() ? "on" : "off");
    sleep_trace_report();
    uint16_t raw;
    esp_err_t battery_err = adc_read(&raw);
    TickType_t adc_tick = xTaskGetTickCount();
    if (battery_err == ESP_OK && raw > 1023) battery_err = ESP_ERR_INVALID_RESPONSE;
    bool ap_on = portal_is_on();
    if (!ap_on && battery_off_samples < UINT32_MAX) battery_off_samples++;
    uint32_t off_ms = !ap_on && battery_after_ap ?
        (adc_tick - battery_off_tick) * portTICK_PERIOD_MS : 0;
    const char *sample_phase = ap_on ? "ap" : battery_after_ap ? "after-ap" : "cold-start";
    bool compensate = adc_sleep_seen && !ap_on;
    unsigned cal_adc = ap_on ? BATTERY_AP_ADC_X2 :
        compensate ? BATTERY_SLEEP_ADC_X2 : BATTERY_BOOT_ADC * 2U;
    unsigned cal_mv = ap_on ? BATTERY_AP_CAL_MV : BATTERY_CAL_MV;
    const char *cal_state = ap_on ? "ap" : compensate ? "sleep" : "boot";
    unsigned measured_mv = 0;
    if (battery_err == ESP_OK)
        measured_mv = ((uint32_t)raw * 412000U + 41943U) / 83886U;
    int16_t temp10;
    bool external_power;
    esp_err_t err = sensor_start(&external_power);
    if (err == ESP_OK) {
        bool conversion_sleep = external_power && !portal_is_on() && !ir_is_busy();
        TickType_t conversion_wait = pdMS_TO_TICKS(750) + 1;
        if (conversion_sleep) {
            trace_buttons("conversion-enter", conversion_wait, 0);
#ifndef CONFIG_APP_QUIET_UART
            uart_tx_wait_idle(CONFIG_ESP_CONSOLE_UART_NUM);
#endif
        }
        set_auto_sleep(conversion_sleep);
        /* 多等待一个 tick，避免首个 tick 不完整导致实际转换时间不足 750 ms。 */
        vTaskDelay(conversion_wait);
        if (auto_sleep) adc_sleep_seen = true;
        set_auto_sleep(false);
        if (conversion_sleep) trace_buttons("conversion-done", conversion_wait, 0);
        err = sensor_finish(&temp10);
    }
    bool fire[2] = { false, false };
    bool control_on = !portal_is_on();
    unsigned battery_base = 0, battery_mv = 0;
    battery_adjust_t voltage;
    xSemaphoreTake(status_lock, portMAX_DELAY);
    voltage = battery_adjust;
    current.battery_error = battery_err;
    current.battery_valid = battery_err == ESP_OK;
    if (battery_err == ESP_OK) {
        /* 单点增益校准，保留 ADC 变化；其他电压点的精度仍待实测。 */
        base_battery_mv = ((uint32_t)raw * cal_mv * 2U + cal_adc / 2U) / cal_adc;
        battery_sample_tick = adc_tick;
        battery_sample_ap = ap_on;
        current.battery_mv = adjusted_battery(base_battery_mv);
        battery_base = base_battery_mv;
        battery_mv = current.battery_mv;
    }
    current.sensor_error = err;
    current.temp_valid = err == ESP_OK;
    if (err == ESP_OK) {
        base_temp10 = temp10;
        temp_sample_tick = xTaskGetTickCount();
        temp10 += temp_adjust10;
        current.temp10 = temp10;
        if (control_on) {
            uint32_t now_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;
            if (!rule_trend_step(&trend, temp10, now_ms)) {
                ESP_LOGE(TAG, "trend update failed: duplicate or invalid sample time");
                abort();
            }
        } else rule_trend_reset(&trend);
        for (int i = 0; i < 2; i++) {
            if (!control_on) continue;
            ir_state_t learn = ir_state();
            if (learn == IR_WAITING || learn == IR_CAPTURING) continue;
            if (ir_has_code(i)) {
                bool matched = rule_step(&current.rules[i], &states[i], temp10);
                /* 共用动态间隔，两组独立计时；只有成功发送才更新时间。 */
                fire[i] = matched && (!send_recorded[i] ||
                    xTaskGetTickCount() - last_send[i] >=
                    (trend.interval_ms + portTICK_PERIOD_MS - 1) / portTICK_PERIOD_MS);
            }
            else memset(&states[i], 0, sizeof(states[i]));
        }
    } else {
        memset(states, 0, sizeof(states));
        rule_trend_reset(&trend);
    }
    xSemaphoreGive(status_lock);
    ESP_LOGI(TAG, "trend: control=%s points=%u robust_milli=%u fast_milli=%u target_ms=%u interval_ms=%u (speed: 0.001 C/min)",
             control_on ? "on" : "paused", trend.count, (unsigned)trend.robust_milli,
             (unsigned)trend.fast_milli, (unsigned)trend.target_ms, (unsigned)trend.interval_ms);
    if (battery_err != ESP_OK) {
        ESP_LOGE(TAG, "battery read failed: %s (phase=%s off_sample=%u off_ms=%u)",
                 esp_err_to_name(battery_err), sample_phase,
                 (unsigned)(ap_on ? 0 : battery_off_samples), (unsigned)off_ms);
    } else {
        ESP_LOGI(TAG, "battery=%u.%03u V (adc=%u measured=%u.%03u V compensated=%d cal=%s base_mv=%u ratio=%u/%u phase=%s off_sample=%u off_ms=%u)",
                 battery_mv / 1000, battery_mv % 1000, (unsigned)raw,
                 measured_mv / 1000, measured_mv % 1000, compensate, cal_state,
                 battery_base, (unsigned)voltage.reference_mv, (unsigned)voltage.base_mv,
                 sample_phase, (unsigned)(ap_on ? 0 : battery_off_samples), (unsigned)off_ms);
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "temperature read failed: %s", esp_err_to_name(err));
        return;
    }
    int magnitude = temp10 < 0 ? -(int)temp10 : temp10;
    ESP_LOGI(TAG, "temperature=%s%d.%d℃", temp10 < 0 ? "-" : "",
             magnitude / 10, magnitude % 10);
    /* 离开状态锁后发送红外，避免长时间阻塞 HTTP 状态读取。 */
    for (int i = 0; i < 2; i++) {
        if (!fire[i]) continue;
        ESP_LOGI(TAG, "rule %d triggered at temperature10=%d", i + 1, temp10);
        err = ir_send(i);
        xSemaphoreTake(status_lock, portMAX_DELAY);
        current.send_error[i] = err;
        if (err == ESP_OK) {
            last_send[i] = xTaskGetTickCount();
            send_recorded[i] = true;
        } else states[i].armed = true;
        xSemaphoreGive(status_lock);
        ESP_LOGI(TAG, "automatic send: rule=%d interval_ms=%u result=%s",
                 i + 1, (unsigned)trend.interval_ms, esp_err_to_name(err));
        if (err != ESP_OK) ESP_LOGE(TAG, "rule %d send failed: %s", i + 1, esp_err_to_name(err));
        if (i == 0 && fire[1]) vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "starting");
    main_handle = xTaskGetCurrentTaskHandle();
    rule_trend_reset(&trend);
    ESP_ERROR_CHECK(nvs_flash_init());
    status_lock = xSemaphoreCreateMutex();
    if (!status_lock) abort();
    ESP_ERROR_CHECK(load_rules());
    ESP_ERROR_CHECK(load_calibration());
    ESP_ERROR_CHECK(init_buttons());
    ESP_ERROR_CHECK(sensor_init());
    adc_config_t adc_cfg = { .mode = ADC_READ_TOUT_MODE, .clk_div = 8 };
    ESP_ERROR_CHECK(adc_init(&adc_cfg));
    ESP_ERROR_CHECK(ir_init());
    ESP_ERROR_CHECK(gpio_isr_handler_add(GPIO_NUM_12, button_isr, NULL));
    ESP_ERROR_CHECK(gpio_isr_handler_add(GPIO_NUM_13, button_isr, (void *)1));
    ESP_ERROR_CHECK(portal_init());
    esp_err_t wake_err = esp_sleep_enable_gpio_wakeup();
    if (wake_err == ESP_OK) wake_err = gpio_wakeup_enable(GPIO_NUM_12, GPIO_INTR_LOW_LEVEL);
    if (wake_err == ESP_OK) wake_err = gpio_wakeup_enable(GPIO_NUM_13, GPIO_INTR_LOW_LEVEL);
    if (wake_err != ESP_OK) {
        sleep_failed = true;
        ESP_LOGE(TAG, "button wakeup setup failed; automatic sleep disabled: %s",
                 esp_err_to_name(wake_err));
    }
    ESP_ERROR_CHECK(gpio_set_intr_type(GPIO_NUM_12, GPIO_INTR_LOW_LEVEL));
    ESP_ERROR_CHECK(gpio_set_intr_type(GPIO_NUM_13, GPIO_INTR_LOW_LEVEL));
    if (xTaskCreate(led_task, "led", 2048, NULL, 1, &led_handle) != pdPASS) {
        ESP_LOGE(TAG, "could not start LED task: no memory");
        abort();
    }
    for (int i = 0; i < 2; i++) {
        ESP_LOGI(TAG, "rule %d: threshold10=%d rising=%d enabled=%d ir=%s",
                 i + 1, current.rules[i].threshold10, current.rules[i].rising,
                 current.rules[i].enabled, ir_has_code(i) ? "ready" : "missing");
    }
    ESP_ERROR_CHECK(check_cpu_freq());
#ifdef CONFIG_APP_DISABLE_DHCP_CLIENT_TIMERS
    ESP_LOGI(TAG, "DHCP client cyclic timers disabled (AP-only test); DHCP server retained");
#else
    ESP_LOGI(TAG, "DHCP client cyclic timers enabled (SDK baseline)");
#endif
    ESP_LOGI(TAG, "ready; temperature interval: AP off 60 seconds, AP on 2 seconds; automatic IR: trend 120-600 seconds per rule, paused while AP on");
    ESP_ERROR_CHECK(init_idle_pins());
    TickType_t last_temp = xTaskGetTickCount();
    TickType_t last_s1 = last_temp - pdMS_TO_TICKS(200);
    TickType_t last_s2 = last_s1;
    bool sample_now = true;
    bool close_pending = false;
    if (gpio_get_level(GPIO_NUM_12) == 0) s1_pending = true;
    while (true) {
        set_auto_sleep(false);
        if (s1_pending || s2_pending) trace_buttons("button-dispatch", 0, 0);
        portENTER_CRITICAL();
        bool s1 = s1_pending;
        bool s2 = s2_pending;
        s1_pending = s2_pending = false;
        portEXIT_CRITICAL();
        TickType_t now = xTaskGetTickCount();
        if (s1 && now - last_s1 >= pdMS_TO_TICKS(200)) {
            last_s1 = now;
            if (portal_is_on()) {
                close_pending = !close_pending;
                if (ir_is_busy()) ESP_LOGI(TAG, "portal close request %s",
                                          close_pending ? "queued until IR idle" : "cancelled");
            } else {
                close_pending = false;
                esp_err_t err = portal_start();
                if (err != ESP_OK) ESP_LOGE(TAG, "portal start: %s", esp_err_to_name(err));
            }
        }
        if (s2 && now - last_s2 >= pdMS_TO_TICKS(200)) {
            last_s2 = now;
            close_pending = true;
            ESP_LOGI(TAG, "S2: low-power control requested; temperature monitoring continues");
        }
        /* 按键关闭请求延后到红外空闲，避免中断学习或发送。 */
        if (close_pending && !ir_is_busy()) {
            esp_err_t err = portal_stop();
            close_pending = err != ESP_OK;
            if (err != ESP_OK) ESP_LOGE(TAG, "portal button stop: %s", esp_err_to_name(err));
        }
        if (s1 || s2) {
            trace_buttons("button-action-done", 0, 0);
            set_led_enabled(portal_is_on());
            wait_button_release();
        }
        if (portal_is_on() && portal_idle_ms() >= portal_timeout_ms() &&
            !ir_is_busy()) {
            esp_err_t err = portal_stop();
            if (err != ESP_OK) ESP_LOGE(TAG, "portal timeout stop: %s", esp_err_to_name(err));
        }
        set_led_enabled(portal_is_on());
        bool ap_active = portal_is_on();
        if (ap_active != battery_ap_active) {
            battery_ap_active = ap_active;
            battery_off_samples = 0;
            battery_after_ap = !ap_active;
            if (!ap_active) battery_off_tick = xTaskGetTickCount();
        }
        if (portal_is_on()) rule_trend_reset(&trend);
        /* 热点开启时每 2 秒测温，关闭时每 60 秒测温并执行趋势温控。 */
        TickType_t interval = pdMS_TO_TICKS(portal_is_on() ? 2000 : 60000);
        if (sample_now || xTaskGetTickCount() - last_temp >= interval) {
            last_temp = xTaskGetTickCount();
            sample_now = false;
            update_temp();
        }
        /* 等待时间取采样期限、热点超时和单次休眠上限的最小值；按键通知可提前唤醒。 */
        TickType_t wait = pdMS_TO_TICKS(SLEEP_WAIT_MS);
        TickType_t elapsed = xTaskGetTickCount() - last_temp;
        TickType_t remaining = elapsed < interval ? interval - elapsed : 0;
        if (remaining < wait) wait = remaining;
        if (portal_is_on()) {
            uint32_t idle = portal_idle_ms();
            uint32_t timeout = portal_timeout_ms();
            TickType_t remaining = pdMS_TO_TICKS(idle < timeout ? timeout - idle : 5000);
            if (remaining < wait) wait = remaining;
            if (close_pending && wait > pdMS_TO_TICKS(100)) wait = pdMS_TO_TICKS(100);
        }
        bool allow_sleep = !portal_is_on() && !ir_is_busy();
        bool trace_wait = !portal_is_on() && wait;
        if (trace_wait) {
            trace_buttons("wait-enter", wait, 0);
#ifndef CONFIG_APP_QUIET_UART
            uart_tx_wait_idle(CONFIG_ESP_CONSOLE_UART_NUM);
#endif
        }
        set_auto_sleep(allow_sleep);
        uint32_t notices = ulTaskNotifyTake(pdTRUE, wait);
        if (auto_sleep && wait) adc_sleep_seen = true;
        if (trace_wait) {
            set_auto_sleep(false);
            trace_buttons("wait-done", wait, notices);
        }
    }
}
