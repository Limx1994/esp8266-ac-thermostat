#pragma once
#include <stdbool.h>
#include <stdint.h>

/* threshold10 单位为 0.1 ℃，有效范围为 -10～50 ℃；
 * rising 为 1 表示大于等于阈值，为 0 表示小于等于阈值，enabled 为 0 时禁用。 */
typedef struct {
    int16_t threshold10;
    uint8_t rising;
    uint8_t enabled;
} rule_cfg_t;

/* 记录启用规则最近一次判断：primed 表示已判断，armed 表示条件未满足，fired 表示满足。 */
typedef struct {
    bool primed;
    bool armed;
    bool fired;
} rule_state_t;

/* 检查指针、温度范围以及 rising/enabled 是否为 0 或 1。 */
bool rule_valid(const rule_cfg_t *rule);
/* rule 和 state 必须有效；返回本次是否满足阈值，禁用时不更新状态。
 * 不实现回差或单次触发；自动发送间隔由主控制模块限制。 */
bool rule_step(const rule_cfg_t *rule, rule_state_t *state, int16_t temp10);

/* 仅用于 RAM 趋势调度，不改变 rule_cfg_t/NVS 布局。
 * 速度单位为 0.001 ℃/分钟；时间为可回绕的 uint32_t 毫秒。 */
typedef struct {
    int16_t temps[5];
    uint32_t times[5];
    unsigned count;
    uint32_t robust_milli, fast_milli;
    uint32_t target_ms, interval_ms;
} rule_trend_t;

/* trend 必须有效；清空历史并恢复 600 秒间隔。 */
void rule_trend_reset(rule_trend_t *trend);
/* 添加有效采样；间隔超过 120 秒会重新积累历史。
 * NULL 或重复时间返回 false；调用方必须上报，不可使用本次结果。
 * 速度取五点样本对斜率中位数绝对值与最近两段同向速度较小值中的较大者。
 * 间隔 120～600 秒，缩短立即生效，每个有效采样最多延长 60 秒。 */
bool rule_trend_step(rule_trend_t *trend, int16_t temp10, uint32_t now_ms);
