#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "driver/gpio.h"
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
static volatile bool s1_pending;
static volatile bool s2_pending;

static void IRAM_ATTR button_isr(void *arg)
{
    if (arg) s2_pending = true;
    else s1_pending = true;
}

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
        .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_NEGEDGE
    };
    return gpio_config(&cfg);
}

static esp_err_t sleep_until_button(bool *open_portal)
{
    *open_portal = false;
    esp_err_t err = gpio_isr_handler_remove(GPIO_NUM_12);
    if (err != ESP_OK) goto restore;
    err = gpio_isr_handler_remove(GPIO_NUM_13);
    if (err != ESP_OK) goto restore;
    err = gpio_set_intr_type(GPIO_NUM_12, GPIO_INTR_DISABLE);
    if (err != ESP_OK) goto restore;
    err = gpio_set_intr_type(GPIO_NUM_13, GPIO_INTR_DISABLE);
    if (err != ESP_OK) goto restore;
    err = gpio_wakeup_enable(GPIO_NUM_12, GPIO_INTR_LOW_LEVEL);
    if (err != ESP_OK) goto restore;
    err = gpio_wakeup_enable(GPIO_NUM_13, GPIO_INTR_LOW_LEVEL);
    if (err != ESP_OK) goto restore;
    err = esp_sleep_enable_gpio_wakeup();
    if (err != ESP_OK) goto restore;
    err = esp_sleep_enable_timer_wakeup(3600000000U);
    if (err != ESP_OK) goto restore;
    ESP_LOGI(TAG, "sleeping; automatic control paused");
    while (true) {
        err = esp_light_sleep_start();
        if (err != ESP_OK) break;
        if (gpio_get_level(GPIO_NUM_12) == 0) {
            *open_portal = true;
            break;
        }
        if (gpio_get_level(GPIO_NUM_13) == 0) break;
    }
restore:
    esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    gpio_wakeup_disable(GPIO_NUM_12);
    gpio_wakeup_disable(GPIO_NUM_13);
    while (gpio_get_level(GPIO_NUM_12) == 0 || gpio_get_level(GPIO_NUM_13) == 0)
        vTaskDelay(pdMS_TO_TICKS(20));
    esp_err_t restore = gpio_set_intr_type(GPIO_NUM_12, GPIO_INTR_NEGEDGE);
    if (restore == ESP_OK) restore = gpio_set_intr_type(GPIO_NUM_13, GPIO_INTR_NEGEDGE);
    if (restore == ESP_OK) restore = gpio_isr_handler_add(GPIO_NUM_12, button_isr, NULL);
    if (restore == ESP_OK) restore = gpio_isr_handler_add(GPIO_NUM_13, button_isr, (void *)1);
    if (err == ESP_OK) err = restore;
    s1_pending = s2_pending = false;
    memset(states, 0, sizeof(states));
    if (err == ESP_OK)
        ESP_LOGI(TAG, "awake by S%d; automatic control resumed", *open_portal ? 1 : 2);
    return err;
}

static void update_temp(void)
{
    int16_t temp10;
    esp_err_t err = sensor_read(&temp10);
    bool fire[2] = { false, false };
    xSemaphoreTake(status_lock, portMAX_DELAY);
    current.sensor_error = err;
    current.temp_valid = err == ESP_OK;
    if (err == ESP_OK) {
        current.temp10 = temp10;
        for (int i = 0; i < 2; i++) {
            ir_state_t learn = ir_state();
            if (learn == IR_WAITING || learn == IR_CAPTURING) continue;
            if (ir_has_code(i)) fire[i] = rule_step(&current.rules[i], &states[i], temp10);
            else memset(&states[i], 0, sizeof(states[i]));
        }
    } else memset(states, 0, sizeof(states));
    xSemaphoreGive(status_lock);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "temperature read failed: %s", esp_err_to_name(err));
        return;
    }
    ESP_LOGI(TAG, "temperature10=%d", temp10);
    for (int i = 0; i < 2; i++) {
        if (!fire[i]) continue;
        ESP_LOGI(TAG, "rule %d triggered at temperature10=%d", i + 1, temp10);
        err = ir_send(i);
        xSemaphoreTake(status_lock, portMAX_DELAY);
        current.send_error[i] = err;
        if (err != ESP_OK) states[i].armed = true;
        xSemaphoreGive(status_lock);
        if (err != ESP_OK) ESP_LOGE(TAG, "rule %d send failed: %s", i + 1, esp_err_to_name(err));
        if (i == 0 && fire[1]) vTaskDelay(pdMS_TO_TICKS(500));
    }
}

void app_main(void)
{
    ESP_LOGI(TAG, "starting");
    ESP_ERROR_CHECK(nvs_flash_init());
    status_lock = xSemaphoreCreateMutex();
    if (!status_lock) abort();
    ESP_ERROR_CHECK(load_rules());
    ESP_ERROR_CHECK(init_buttons());
    ESP_ERROR_CHECK(sensor_init());
    ESP_ERROR_CHECK(ir_init());
    ESP_ERROR_CHECK(gpio_isr_handler_add(GPIO_NUM_12, button_isr, NULL));
    ESP_ERROR_CHECK(gpio_isr_handler_add(GPIO_NUM_13, button_isr, (void *)1));
    ESP_ERROR_CHECK(portal_init());
    for (int i = 0; i < 2; i++) {
        ESP_LOGI(TAG, "rule %d: threshold10=%d rising=%d enabled=%d ir=%s",
                 i + 1, current.rules[i].threshold10, current.rules[i].rising,
                 current.rules[i].enabled, ir_has_code(i) ? "ready" : "missing");
    }
    ESP_LOGI(TAG, "ready; monitoring temperature every 5 seconds");
    TickType_t last_temp = xTaskGetTickCount() - pdMS_TO_TICKS(5000);
    TickType_t last_s1 = xTaskGetTickCount() - pdMS_TO_TICKS(200);
    TickType_t last_s2 = last_s1;
    s1_pending = gpio_get_level(GPIO_NUM_12) == 0;
    while (true) {
        if (s1_pending && xTaskGetTickCount() - last_s1 >= pdMS_TO_TICKS(200)) {
            s1_pending = false;
            last_s1 = xTaskGetTickCount();
            esp_err_t err = portal_start();
            if (err != ESP_OK) ESP_LOGE(TAG, "portal start: %s", esp_err_to_name(err));
        }
        if (s2_pending && xTaskGetTickCount() - last_s2 >= pdMS_TO_TICKS(200)) {
            s2_pending = false;
            last_s2 = xTaskGetTickCount();
            esp_err_t err = portal_stop();
            if (err != ESP_OK) ESP_LOGE(TAG, "portal stop: %s", esp_err_to_name(err));
            else {
                while (gpio_get_level(GPIO_NUM_13) == 0) vTaskDelay(pdMS_TO_TICKS(20));
                bool open_portal;
                err = sleep_until_button(&open_portal);
                if (err != ESP_OK) ESP_LOGE(TAG, "sleep failed: %s", esp_err_to_name(err));
                else if (open_portal) {
                    err = portal_start();
                    if (err != ESP_OK) ESP_LOGE(TAG, "portal start: %s", esp_err_to_name(err));
                }
                last_temp = xTaskGetTickCount() - pdMS_TO_TICKS(5000);
            }
        }
        if (portal_is_on() && portal_idle_ms() >= 600000 &&
            ir_state() != IR_WAITING && ir_state() != IR_CAPTURING) {
            esp_err_t err = portal_stop();
            if (err != ESP_OK) ESP_LOGE(TAG, "portal timeout stop: %s", esp_err_to_name(err));
        }
        if (xTaskGetTickCount() - last_temp >= pdMS_TO_TICKS(5000)) {
            last_temp = xTaskGetTickCount();
            update_temp();
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
