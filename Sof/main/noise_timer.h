#pragma once
#include <stdbool.h>
#include "esp_err.h"

/* Main control task only: pause after RF shutdown, resume before AP start. */
esp_err_t noise_timer_set_active(bool active);
/* IRAM accessor for the SDK's actual pending os_timer queue. */
int app_os_timer_pending(void);
