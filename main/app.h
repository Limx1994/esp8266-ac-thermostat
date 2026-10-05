#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "rules.h"

typedef struct {
    int16_t temp10;
    bool temp_valid;
    esp_err_t sensor_error;
    uint16_t battery_mv;
    bool battery_valid;
    esp_err_t battery_error;
    esp_err_t send_error[2];
    rule_cfg_t rules[2];
} app_status_t;

void app_get_status(app_status_t *status);
esp_err_t app_save_rule(int slot, const rule_cfg_t *rule);
void app_reset_rule(int slot);
