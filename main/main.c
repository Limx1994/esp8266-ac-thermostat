#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "esp8266/gpio_struct.h"
#include "esp_wifi.h"
#include "esp_sleep.h"
#include "esp_log.h"
#include "esp_attr.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "app.h"
#include "sensor.h"
#include "ir.h"
#include "portal.h"

static const char *TAG = "thermostat";
static SemaphoreHandle_t status_lock;
static app_status_t current;
static rule_state_t states[2];
static TickType_t last_send[2];
static bool send_recorded[2];
static volatile bool s1_pending;
static volatile bool s2_pending;
static TaskHandle_t main_handle;
static volatile bool led_enabled;
static TaskHandle_t led_handle;
static bool auto_sleep;
static bool sleep_failed;
static bool adc_sleep_seen;

/* 限制单次等待，避免 SDK 在 160 MHz 下进行 32 位休眠时钟补偿时溢出。 */
#define SLEEP_WAIT_MS 10000
#define SEND_INTERVAL_MS 120000
/* 根据实测 ADC 计数 808 / 888 设置的临时热点关闭电压补偿。 */
#define BATTERY_SLEEP_NUM 101U
#define BATTERY_SLEEP_DEN 111U

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
    if (!enabled) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
    portEXIT_CRITICAL();
    if (led_handle) xTaskNotifyGive(led_handle);
}

static void IRAM_ATTR button_isr(void *arg)
{
    int pin = arg ? GPIO_NUM_13 : GPIO_NUM_12;
    /* 按键持续低电平时先禁用中断；主任务确认释放后再启用，防止反复唤醒。 */
    GPIO.pin[pin].int_type = GPIO_INTR_DISABLE;
    GPIO.status_w1tc = 1U << pin;
    if (arg) s2_pending = true;
    else s1_pending = true;
    BaseType_t wake = pdFALSE;
    vTaskNotifyGiveFromISR(main_handle, &wake);
    if (wake) portYIELD_FROM_ISR();
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
        if (led_enabled) {
            portENTER_CRITICAL();
            if (led_enabled) ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 0));
            portEXIT_CRITICAL();
            ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(500));
            ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
            if (led_enabled) ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(500));
        } else {
            ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_2, 1));
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
    while (true) {
        while (gpio_get_level(GPIO_NUM_12) == 0 || gpio_get_level(GPIO_NUM_13) == 0)
            vTaskDelay(pdMS_TO_TICKS(20));
        vTaskDelay(pdMS_TO_TICKS(20));
        if (gpio_get_level(GPIO_NUM_12) && gpio_get_level(GPIO_NUM_13)) break;
    }
    ESP_ERROR_CHECK(gpio_set_intr_type(GPIO_NUM_12, GPIO_INTR_LOW_LEVEL));
    ESP_ERROR_CHECK(gpio_set_intr_type(GPIO_NUM_13, GPIO_INTR_LOW_LEVEL));
}

static void update_temp(void)
{
    ir_report_last_send();
    ESP_LOGI(TAG, "sampling: AP=%s", portal_is_on() ? "on" : "off");
    uint16_t raw;
    esp_err_t battery_err = adc_read(&raw);
    if (battery_err == ESP_OK && raw > 1023) battery_err = ESP_ERR_INVALID_RESPONSE;
    /* 只有经历过允许自动休眠的等待且热点关闭时，才应用临时电压补偿。 */
    bool compensate = adc_sleep_seen && !portal_is_on();
    unsigned measured_mv = 0;
    if (battery_err == ESP_OK)
        measured_mv = ((uint32_t)raw * 412000U + 41943U) / 83886U;
    int16_t temp10;
    bool external_power;
    esp_err_t err = sensor_start(&external_power);
    if (err == ESP_OK) {
        set_auto_sleep(external_power && !portal_is_on() && !ir_is_busy());
        /* 多等待一个 tick，避免首个 tick 不完整导致实际转换时间不足 750 ms。 */
        vTaskDelay(pdMS_TO_TICKS(750) + 1);
        if (auto_sleep) adc_sleep_seen = true;
        set_auto_sleep(false);
        err = sensor_finish(&temp10);
    }
    bool fire[2] = { false, false };
    xSemaphoreTake(status_lock, portMAX_DELAY);
    current.battery_error = battery_err;
    current.battery_valid = battery_err == ESP_OK;
    if (battery_err == ESP_OK) {
        /* ADC 每计数对应 1/1023 V；电池经 330 kΩ / 82 kΩ 分压后测量。 */
        current.battery_mv = compensate ?
            (measured_mv * BATTERY_SLEEP_NUM + BATTERY_SLEEP_DEN / 2) /
            BATTERY_SLEEP_DEN : measured_mv;
    }
    current.sensor_error = err;
    current.temp_valid = err == ESP_OK;
    if (err == ESP_OK) {
        current.temp10 = temp10;
        for (int i = 0; i < 2; i++) {
            ir_state_t learn = ir_state();
            if (learn == IR_WAITING || learn == IR_CAPTURING) continue;
            if (ir_has_code(i)) {
                bool matched = rule_step(&current.rules[i], &states[i], temp10);
                /* 每组独立限频；只有成功发送才更新时间，失败不占用两分钟间隔。 */
                fire[i] = matched && (!send_recorded[i] ||
                    xTaskGetTickCount() - last_send[i] >= pdMS_TO_TICKS(SEND_INTERVAL_MS));
            }
            else memset(&states[i], 0, sizeof(states[i]));
        }
    } else memset(states, 0, sizeof(states));
    xSemaphoreGive(status_lock);
    if (battery_err != ESP_OK) {
        ESP_LOGE(TAG, "battery read failed: %s", esp_err_to_name(battery_err));
    } else {
        unsigned battery_mv = current.battery_mv;
        ESP_LOGI(TAG, "battery=%u.%03u V (adc=%u measured=%u.%03u V compensated=%d)",
                 battery_mv / 1000, battery_mv % 1000, (unsigned)raw,
                 measured_mv / 1000, measured_mv % 1000, compensate);
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
        if (err != ESP_OK) ESP_LOGE(TAG, "rule %d send failed: %s", i + 1, esp_err_to_name(err));
        if (i == 0 && fire[1]) vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "starting");
    main_handle = xTaskGetCurrentTaskHandle();
    ESP_ERROR_CHECK(nvs_flash_init());
    status_lock = xSemaphoreCreateMutex();
    if (!status_lock) abort();
    ESP_ERROR_CHECK(load_rules());
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
    ESP_LOGI(TAG, "ready; temperature interval: AP off 30 seconds, AP on 2 seconds; IR interval: 120 seconds per rule");
    TickType_t last_temp = xTaskGetTickCount();
    TickType_t last_s1 = last_temp - pdMS_TO_TICKS(200);
    TickType_t last_s2 = last_s1;
    bool sample_now = true;
    bool close_pending = false;
    if (gpio_get_level(GPIO_NUM_12) == 0) s1_pending = true;
    while (true) {
        set_auto_sleep(false);
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
            close_pending = false;
            esp_err_t err = portal_stop();
            if (err != ESP_OK) ESP_LOGE(TAG, "portal button stop: %s", esp_err_to_name(err));
        }
        if (s1 || s2) {
            set_led_enabled(portal_is_on());
            wait_button_release();
        }
        if (portal_is_on() && portal_idle_ms() >= portal_timeout_ms() &&
            !ir_is_busy()) {
            esp_err_t err = portal_stop();
            if (err != ESP_OK) ESP_LOGE(TAG, "portal timeout stop: %s", esp_err_to_name(err));
        }
        set_led_enabled(portal_is_on());
        /* 热点开启时每 2 秒采温，关闭时每 30 秒采温；两种模式都继续温控。 */
        TickType_t interval = pdMS_TO_TICKS(portal_is_on() ? 2000 : 30000);
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
        set_auto_sleep(!portal_is_on() && !ir_is_busy());
        ulTaskNotifyTake(pdTRUE, wait);
        if (auto_sleep && wait) adc_sleep_seen = true;
    }
}
