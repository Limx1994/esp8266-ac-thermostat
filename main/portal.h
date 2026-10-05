#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t portal_init(void);
esp_err_t portal_start(void);
esp_err_t portal_stop(void);
bool portal_is_on(void);
uint32_t portal_idle_ms(void);
uint32_t portal_timeout_ms(void);
