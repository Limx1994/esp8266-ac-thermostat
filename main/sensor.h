#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* 初始化 GPIO4 的 1-Wire 开漏总线；返回 GPIO 配置错误。 */
esp_err_t sensor_init(void);
/* 唤醒状态下启动转换，external_power 必须有效，用于返回是否为外部供电。
 * 成功后至少等待 750 ms，再在唤醒状态调用 sensor_finish；寄生供电时保持唤醒。
 * 返回参数、GPIO 或设备未找到错误。 */
esp_err_t sensor_start(bool *external_power);
/* temp10 必须有效，成功读数单位为 0.1 ℃；CRC 错误或设备未找到最多读三次。
 * 其他错误立即返回，包含 GPIO 错误和读到上电默认值 85 ℃的无效状态。 */
esp_err_t sensor_finish(int16_t *temp10);
