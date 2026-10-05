#include "rules.h"

bool rule_valid(const rule_cfg_t *rule)
{
    return rule && rule->threshold10 >= -100 && rule->threshold10 <= 500 &&
           rule->rising <= 1 && rule->enabled <= 1;
}

bool rule_step(const rule_cfg_t *rule, rule_state_t *state, int16_t temp10)
{
    if (!rule->enabled) return false;
    /* 条件持续满足时每次都返回 true；是否发送由调用方结合每组发送间隔决定。 */
    bool fire = rule->rising ? temp10 >= rule->threshold10
                            : temp10 <= rule->threshold10;
    state->primed = true;
    state->armed = !fire;
    state->fired = fire;
    return fire;
}
