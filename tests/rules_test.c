#include <assert.h>
#include <stdio.h>
#include "rules.h"

int main(void)
{
    rule_cfg_t up = { .threshold10 = 260, .rising = 1, .enabled = 1 };
    rule_state_t state = { 0 };
    assert(rule_valid(&up));
    assert(!rule_step(&up, &state, 270)); /* startup does not send */
    assert(!rule_step(&up, &state, 255)); /* first entry below threshold */
    assert(rule_step(&up, &state, 260));
    assert(!rule_step(&up, &state, 270)); /* no repeated sends */
    assert(!rule_step(&up, &state, 256)); /* hysteresis not reached */
    assert(!rule_step(&up, &state, 255));
    assert(rule_step(&up, &state, 265));

    state = (rule_state_t){ 0 };
    assert(!rule_step(&up, &state, 258)); /* first reading only sets baseline */
    assert(rule_step(&up, &state, 260));
    assert(!rule_step(&up, &state, 259));
    assert(!rule_step(&up, &state, 260)); /* hysteresis after sending */
    assert(!rule_step(&up, &state, 255));
    assert(rule_step(&up, &state, 260));

    state = (rule_state_t){ 0 };
    assert(!rule_step(&up, &state, 270));
    assert(!rule_step(&up, &state, 258)); /* first entry below threshold */
    assert(rule_step(&up, &state, 260));

    rule_cfg_t down = { .threshold10 = 220, .rising = 0, .enabled = 1 };
    state = (rule_state_t){ 0 };
    assert(!rule_step(&down, &state, 225));
    assert(rule_step(&down, &state, 220));
    assert(!rule_step(&down, &state, 218));
    assert(!rule_step(&down, &state, 225));
    assert(rule_step(&down, &state, 219));

    state = (rule_state_t){ 0 };
    assert(!rule_step(&down, &state, 222));
    assert(rule_step(&down, &state, 220));
    assert(!rule_step(&down, &state, 224));
    assert(!rule_step(&down, &state, 219));
    assert(!rule_step(&down, &state, 225));
    assert(rule_step(&down, &state, 220));

    state = (rule_state_t){ 0 };
    assert(!rule_step(&down, &state, 218));
    assert(!rule_step(&down, &state, 222));
    assert(rule_step(&down, &state, 220));

    up.enabled = 0;
    state = (rule_state_t){ 0 };
    assert(!rule_step(&up, &state, 255));
    assert(!state.primed);
    up.threshold10 = 501;
    assert(!rule_valid(&up));
    puts("rules_test: all cases passed");
    return 0;
}
