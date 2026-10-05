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
