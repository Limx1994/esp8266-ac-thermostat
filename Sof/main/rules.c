#include "rules.h"
#include <limits.h>

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

void rule_trend_reset(rule_trend_t *trend)
{
    *trend = (rule_trend_t){ .target_ms = 600000, .interval_ms = 600000 };
}

static int32_t trend_rate(int16_t start, int16_t end, uint32_t elapsed)
{
    int64_t rate = (int64_t)((int32_t)end - start) * 6000000 / elapsed;
    /* 极短间隔的速度饱和；此范围内的速度均已对应最短发送间隔。 */
    if (rate > INT32_MAX) return INT32_MAX;
    if (rate < -INT32_MAX) return -INT32_MAX;
    return (int32_t)rate;
}

bool rule_trend_step(rule_trend_t *trend, int16_t temp10, uint32_t now_ms)
{
    if (!trend) return false;
    if (trend->count) {
        uint32_t elapsed = now_ms - trend->times[trend->count - 1];
        if (!elapsed) return false;
        if (elapsed > 120000) rule_trend_reset(trend);
    } else rule_trend_reset(trend);
    if (trend->count == 5) {
        for (unsigned i = 1; i < 5; i++) {
            trend->temps[i - 1] = trend->temps[i];
            trend->times[i - 1] = trend->times[i];
        }
        trend->count--;
    }
    unsigned next = trend->count++;
    trend->temps[next] = temp10;
    trend->times[next] = now_ms;
    trend->robust_milli = trend->fast_milli = 0;
    if (trend->count == 5) {
        int32_t rates[10];
        unsigned count = 0;
        for (unsigned i = 0; i < 4; i++) {
            for (unsigned j = i + 1; j < 5; j++) {
                int32_t rate = trend_rate(trend->temps[i], trend->temps[j],
                                          trend->times[j] - trend->times[i]);
                unsigned pos = count++;
                while (pos && rates[pos - 1] > rate) {
                    rates[pos] = rates[pos - 1];
                    pos--;
                }
                rates[pos] = rate;
            }
        }
        int32_t median = ((int64_t)rates[4] + rates[5]) / 2;
        trend->robust_milli = median < 0 ? -median : median;
    }
    if (trend->count >= 3) {
        unsigned end = trend->count - 1;
        int32_t first = trend_rate(trend->temps[end - 2], trend->temps[end - 1],
                                   trend->times[end - 1] - trend->times[end - 2]);
        int32_t second = trend_rate(trend->temps[end - 1], trend->temps[end],
                                    trend->times[end] - trend->times[end - 1]);
        if ((first > 0 && second > 0) || (first < 0 && second < 0)) {
            uint32_t a = first < 0 ? -first : first;
            uint32_t b = second < 0 ? -second : second;
            trend->fast_milli = a < b ? a : b;
        }
    }
    uint32_t speed = trend->robust_milli > trend->fast_milli ?
        trend->robust_milli : trend->fast_milli;
    uint32_t target = speed ? (60000000ULL + speed - 1) / speed : 600000;
    if (target < 120000) target = 120000;
    if (target > 600000) target = 600000;
    trend->target_ms = target;
    if (target <= trend->interval_ms) trend->interval_ms = target;
    else {
        uint32_t longer = trend->interval_ms + 60000;
        trend->interval_ms = longer < target ? longer : target;
    }
    return true;
}
