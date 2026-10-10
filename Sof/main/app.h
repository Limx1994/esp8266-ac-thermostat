#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "rules.h"

/* 状态快照：温度单位为 0.1 ℃，电池电压单位为 mV。
 * valid 为 false 时对应读数不可用，应查看 error；规则和发送错误按槽位 0、1 排列。 */
typedef struct {
    int16_t temp10;
    bool temp_valid;
    esp_err_t sensor_error;
    uint16_t battery_mv;
    bool battery_valid;
    esp_err_t battery_error;
    esp_err_t send_error[2];
    rule_cfg_t rules[2];
} app_status_t;

/* 复制受互斥锁保护的状态；调用方须传入有效的输出指针，并在初始化后调用。 */
void app_get_status(app_status_t *status);
/* slot 为 0 或 1；校验并提交 NVS 成功后才更新内存，失败返回参数或存储错误。 */
esp_err_t app_save_rule(int slot, const rule_cfg_t *rule);
/* 清空指定槽位的规则运行状态；不清除红外码或发送间隔记录，无效槽位不处理。 */
void app_reset_rule(int slot);
/* 学习开始/结束时通知现有 LED 任务，学习期间常亮。 */
void app_set_learning(bool active);
/* reference 为 0.1 ℃整数或 mV；只用最近 5 秒 AP 样本，提交后生效。
 * storage_failed 区分存储失败和输入/样本错误，调用方必须传入有效指针。 */
esp_err_t app_calibrate(bool battery, int reference, bool *storage_failed);
