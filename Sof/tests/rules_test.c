#include <assert.h>
#include <stdio.h>
#include "rules.h"

static void test_trend(void)
{
    rule_trend_t trend;
    rule_trend_reset(&trend);
    assert(!trend.count && trend.interval_ms == 600000);
    assert(!rule_trend_step(NULL, 250, 0));
    assert(rule_trend_step(&trend, 250, 0));
    assert(!rule_trend_step(&trend, 251, 0) && trend.count == 1);
    assert(rule_trend_step(&trend, 255, 60000));
    assert(trend.interval_ms == 600000 && !trend.fast_milli);
    assert(rule_trend_step(&trend, 260, 120000));
    assert(trend.fast_milli == 500 && trend.interval_ms == 120000);
    for (unsigned i = 3; i < 5; i++)
        assert(rule_trend_step(&trend, 250 + i * 5, i * 60000));
    assert(trend.robust_milli == 500 && trend.target_ms == 120000);
    /* 反向变化仍按速度绝对值处理。 */
    assert(rule_trend_step(&trend, 265, 300000));
    assert(rule_trend_step(&trend, 260, 360000));
    assert(trend.fast_milli == 500 && trend.interval_ms == 120000);
    for (unsigned i = 7; i < 20; i++) {
        uint32_t before = trend.interval_ms;
        assert(rule_trend_step(&trend, 260, i * 60000));
        assert(trend.interval_ms <= before + 60000);
        assert(trend.interval_ms >= 120000 && trend.interval_ms <= 600000);
    }
    assert(!trend.robust_milli && !trend.fast_milli && trend.interval_ms == 600000);
    const int16_t noise[] = {250, 251, 250, 251, 250};
    rule_trend_reset(&trend);
    for (unsigned i = 0; i < 5; i++) {
        assert(rule_trend_step(&trend, noise[i], i * 60000));
        assert(trend.interval_ms == 600000);
    }
    assert(trend.robust_milli == 0);
    /* 尖峰分别位于窗口的五个位置，不应主导最终速度。 */
    for (unsigned spike = 0; spike < 5; spike++) {
        rule_trend_reset(&trend);
        for (unsigned i = 0; i < 5; i++)
            assert(rule_trend_step(&trend, i == spike ? 300 : 250, i * 60000));
        assert(!trend.robust_milli && !trend.fast_milli && trend.interval_ms == 600000);
    }
    for (int direction = -1; direction <= 1; direction += 2) {
        rule_trend_reset(&trend);
        for (unsigned i = 0; i < 5; i++)
            assert(rule_trend_step(&trend, 250 + direction * (int)i * 2, i * 60000));
        assert(trend.robust_milli == 200 && trend.fast_milli == 200);
        assert(trend.interval_ms == 300000);
    }
    /* 持续趋势中的单点异常仍应保留真实斜率。 */
    const int16_t rising_spike[] = {250, 255, 400, 265, 270};
    rule_trend_reset(&trend);
    for (unsigned i = 0; i < 5; i++)
        assert(rule_trend_step(&trend, rising_spike[i], i * 60000));
    assert(trend.robust_milli == 500 && !trend.fast_milli);
    /* 定点除法向上取整间隔，不能因舍入提前发送。 */
    rule_trend_reset(&trend);
    for (unsigned i = 0; i < 3; i++)
        assert(rule_trend_step(&trend, 250 + i * 2, i * 60001));
    assert(trend.fast_milli == 199 && trend.interval_ms == 301508);
    /* 实际时间差、过期、回绕和零速度。 */
    rule_trend_reset(&trend);
    assert(rule_trend_step(&trend, 250, UINT32_MAX - 60000));
    assert(rule_trend_step(&trend, 255, 59999));
    assert(rule_trend_step(&trend, 260, 119999));
    assert(trend.fast_milli == 250 && trend.interval_ms == 240000);
    assert(rule_trend_step(&trend, 265, 240000));
    assert(trend.count == 1 && trend.interval_ms == 600000);
    /* 突然加速，两段确认后立即缩短。 */
    assert(rule_trend_step(&trend, 265, 300000));
    assert(rule_trend_step(&trend, 270, 360000));
    assert(trend.interval_ms == 600000);
    assert(rule_trend_step(&trend, 275, 420000));
    assert(trend.interval_ms == 120000);
    puts("trend: noise/spikes, signed median, fast confirmation, gradual extension, timing/reset/wrap passed");
}

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
    test_trend();
    puts("rules_test: threshold equality, repeated sends, startup/recovery and disabled rules passed");
    return 0;
}
