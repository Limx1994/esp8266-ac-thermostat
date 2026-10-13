#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* 初始化 GPIO4 的 1-Wire 总线；测量配置下空闲时切为输入，返回 GPIO 错误。 */
esp_err_t sensor_init(void);
/* 唤醒状态下启动转换，external_power 必须有效，用于返回是否为外部供电。
 * 只支持独立供电，命令发送成功后至少等待 750 ms 再调用 sensor_finish。
 * 启动阶段不探测 busy，使用固定等待，不产生 busy not observed 警告。
 * 转换前核验 12 位分辨率；低分辨率只修正 RAM 并读回确认，不写 EEPROM。
 * 启动事务时序超时最多完整重试三次，其他错误立即返回；每次失败记录原因。
 * 返回参数、GPIO、设备未找到、CRC 或配置读回错误。 */
esp_err_t sensor_start(bool *external_power);
/* temp10 必须有效，成功读数先应用构建配置偏移，再舍入到 0.1 ℃；
 * 状态位时序超时最多重读三次，不复位；真实 busy 不放行。
 * CRC、设备未找到或 scratchpad 时序超时最多完整读三次，每次校验。
 * 分辨率不是 12 位时返回无效状态。
 * 完整等待后确认 ready 再读取；拒绝异常结构及 -55～125 ℃外的原始温度。
 * 固定等待方式无法区分真实 85 ℃与上电默认值，保守拒绝该数值。
 * raw16 可为 NULL，否则返回 1/16 ℃原始读数，用于合并偏移后统一舍入。
 * 测量配置下，成功或失败退出均尝试释放为输入；释放失败也会上报。
 * 只有读取及总线清理全部成功后才写出 temp10/raw16，失败不改变输出。 */
esp_err_t sensor_finish(int16_t *temp10, int16_t *raw16);

/* 编译与网页偏移在原始读数上合并，仅舍入一次到 0.1 ℃。 */
static inline int16_t sensor_temperature(int16_t raw16, int offset10)
{
    int scaled = raw16 * 10 + (CONFIG_APP_TEMP_OFFSET10 + offset10) * 16;
    return (scaled + (scaled >= 0 ? 8 : -8)) / 16;
}
