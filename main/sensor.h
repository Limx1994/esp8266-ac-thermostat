#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t sensor_init(void);
/* Call awake; wait at least 750 ms before sensor_finish(), also called awake. */
esp_err_t sensor_start(bool *external_power);
esp_err_t sensor_finish(int16_t *temp10);
