#include <assert.h>
#include <stdio.h>
#include "rules.h"

int main(void)
{
    rule_cfg_t up = { .threshold10 = 260, .rising = 1, .enabled = 1 };
    rule_state_t state = { 0 };
    assert(rule_valid(&up));
    assert(rule_step(&up, &state, 270)); /* 启动时已超过阈值也应匹配。 */
    assert(rule_step(&up, &state, 270)); /* 条件持续满足时继续匹配，限频由控制模块验证。 */
    assert(rule_step(&up, &state, 260)); /* 等于阈值也应匹配。 */
    assert(!rule_step(&up, &state, 259));
    assert(rule_step(&up, &state, 260)); /* 规则判断不使用回差抑制。 */
    state = (rule_state_t){ 0 }; /* 模拟恢复或保存规则后清空运行状态。 */
    assert(rule_step(&up, &state, 260));

    rule_cfg_t down = { .threshold10 = 220, .rising = 0, .enabled = 1 };
    state = (rule_state_t){ 0 };
    assert(rule_step(&down, &state, 218));
    assert(rule_step(&down, &state, 218));
    assert(rule_step(&down, &state, 220));
    assert(!rule_step(&down, &state, 221));
    assert(rule_step(&down, &state, 220));
    state = (rule_state_t){ 0 };
    assert(rule_step(&down, &state, 220));

    /* 覆盖负温边界、禁用规则不更新状态，以及超范围配置拒绝。 */
    down.threshold10 = -100;
    assert(rule_valid(&down));
    assert(rule_step(&down, &state, -100));
    assert(!rule_step(&down, &state, -99));
    up.enabled = 0;
    state = (rule_state_t){ 0 };
    assert(!rule_step(&up, &state, 270));
    assert(!state.primed);
    up.threshold10 = 501;
    assert(!rule_valid(&up));
    up.threshold10 = 260;
    up.rising = 2;
    assert(!rule_valid(&up));
    puts("rules_test: threshold equality, repeated sends, startup/recovery and disabled rules passed");
    return 0;
}
