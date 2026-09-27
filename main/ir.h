#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

typedef enum { IR_IDLE, IR_WAITING, IR_CAPTURING, IR_SAVED, IR_ERROR } ir_state_t;

esp_err_t ir_init(void);
esp_err_t ir_start_learn(int slot, int carrier_khz);
esp_err_t ir_send(int slot);
bool ir_has_code(int slot);
ir_state_t ir_state(void);
esp_err_t ir_last_error(void);
