#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* 初始化 GPIO4 的 1-Wire 总线；测量配置下空闲时切为输入，返回 GPIO 错误。 */
esp_err_t sensor_init(void);
/* 唤醒状态下启动转换，external_power 必须有效，用于返回是否为外部供电。
 * 成功后至少等待 750 ms，再在唤醒状态调用 sensor_finish；寄生供电时保持唤醒。
 * 转换前核验 12 位分辨率；低分辨率只修正 RAM 并读回确认，不写 EEPROM。
 * 返回参数、GPIO、设备未找到、CRC 或配置读回错误。 */
esp_err_t sensor_start(bool *external_power);
/* temp10 必须有效，成功读数先应用构建配置偏移，再舍入到 0.1 ℃；
 * CRC 错误或设备未找到最多读三次。分辨率不是 12 位时返回无效状态。
 * 其他错误立即返回，包含 GPIO 错误和读到上电默认值 85 ℃的无效状态。
 * 测量配置下，成功或失败退出均尝试释放为输入；释放失败也会上报。 */
esp_err_t sensor_finish(int16_t *temp10);
