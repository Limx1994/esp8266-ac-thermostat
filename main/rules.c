#include "rules.h"

bool rule_valid(const rule_cfg_t *rule)
{
    return rule && rule->threshold10 >= -100 && rule->threshold10 <= 500 &&
           rule->rising <= 1 && rule->enabled <= 1;
}

bool rule_step(const rule_cfg_t *rule, rule_state_t *state, int16_t temp10)
{
    if (!rule->enabled) return false;
    if (!state->primed) {
        state->primed = true;
        state->armed = rule->rising ? temp10 < rule->threshold10
                                    : temp10 > rule->threshold10;
        return false;
    }
    if (!state->armed) {
        bool ready = rule->rising
            ? (state->fired ? temp10 <= rule->threshold10 - 5
                            : temp10 < rule->threshold10)
            : (state->fired ? temp10 >= rule->threshold10 + 5
                            : temp10 > rule->threshold10);
        if (ready) state->armed = true;
        return false;
    }
    if (rule->rising ? temp10 >= rule->threshold10
                     : temp10 <= rule->threshold10) {
        state->armed = false;
        state->fired = true;
        return true;
    }
    return false;
}
