#pragma once
#include <stdint.h>
#include "esp_err.h"

esp_err_t sensor_init(void);
esp_err_t sensor_read(int16_t *temp10);
