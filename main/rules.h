#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int16_t threshold10;
    uint8_t rising;
    uint8_t enabled;
} rule_cfg_t;

typedef struct {
    bool primed;
    bool armed;
    bool fired;
} rule_state_t;

bool rule_valid(const rule_cfg_t *rule);
bool rule_step(const rule_cfg_t *rule, rule_state_t *state, int16_t temp10);
