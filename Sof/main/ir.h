#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* 学习状态依次为：空闲、等待信号、采集中、保存成功、失败；不表示发送进度。 */
typedef enum { IR_IDLE, IR_WAITING, IR_CAPTURING, IR_SAVED, IR_ERROR } ir_state_t;

/* 初始化收发硬件并加载 NVS；初始化失败返回 SDK 错误，损坏码记录日志并标记不可用。 */
esp_err_t ir_init(void);
/* slot 为 0 或 1；异步启动学习，ESP_OK 仅表示任务已启动，结果通过状态接口查询。
 * 无效槽位、正在学习或发送、任务内存不足分别返回相应错误。 */
esp_err_t ir_start_learn(int slot);
/* 两组共用载波频率，单位 kHz，默认 38。 */
int ir_get_carrier(void);
/* 仅接受 36、38、40 kHz；NVS 提交成功才更新共用频率，已有红外码按新频率发送。 */
esp_err_t ir_set_carrier(int carrier_khz);
/* slot 为 0 或 1；同步发送，返回参数、忙碌、缺少有效码、时序或硬件清理错误。 */
esp_err_t ir_send(int slot);
/* 在后续唤醒采样时输出上次发送报告，避免 RF 关闭期间的 UART 日志丢失。 */
void ir_report_last_send(void);
/* 无效槽位返回 false；有效槽位按码格式和时长限制检查是否可发送。 */
bool ir_has_code(int slot);
/* 学习、发送或发送硬件尚未恢复空闲时为 true，主循环据此禁止休眠或关闭热点。 */
bool ir_is_busy(void);
/* 查询学习状态及最近一次学习错误；这些接口不返回发送结果。 */
ir_state_t ir_state(void);
esp_err_t ir_last_error(void);
