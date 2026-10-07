#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

/* 初始化 Wi-Fi AP 配置并关闭 RF；此时尚未开启热点，失败返回 SDK 错误。 */
esp_err_t portal_init(void);
/* 开启热点、HTTP 和 DNS；已开启时刷新空闲计时，启动失败执行资源清理并返回错误。 */
esp_err_t portal_start(void);
/* 关闭 DNS、HTTP、Wi-Fi 和 RF；红外忙碌返回无效状态，DNS 未退出返回超时。 */
esp_err_t portal_stop(void);
/* 报告模块记录的 AP 开启状态；停止失败时可能仍为 true。 */
bool portal_is_on(void);
/* 距最近一次页面访问或控制操作的毫秒数；状态轮询和系统探测不刷新计时。 */
uint32_t portal_idle_ms(void);
/* 未使用热点时为 180000 ms，发生页面访问或控制操作后为 600000 ms。 */
uint32_t portal_timeout_ms(void);
