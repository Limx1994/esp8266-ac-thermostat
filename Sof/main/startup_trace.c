#include <stdbool.h>
#include <stdint.h>
#include "esp_log.h"
#include "esp_phy_init.h"
#include "rom/uart.h"

static const char *TAG = "startup_trace";
static bool trace_phy;

/* 链接器 --wrap 保留原 SDK 实现；仅在 PHY 初始化期间跟踪内部调用。 */
extern void __real_esp_phy_load_cal_and_init(phy_rf_module_t module);
extern void __real_uart_tx_wait_idle(uint8_t uart_no);
/* 原型对应 SDK esp8266/source/phy.h。 */
extern int __real_register_chipv6_phy(uint8_t *init_data);

void __wrap_esp_phy_load_cal_and_init(phy_rf_module_t module)
{
    ESP_LOGI(TAG, "PHY load/calibration enter: module=%d", (int)module);
    trace_phy = true;
    __real_esp_phy_load_cal_and_init(module);
    trace_phy = false;
    ESP_LOGI(TAG, "PHY load/calibration returned");
}

void __wrap_uart_tx_wait_idle(uint8_t uart_no)
{
    if (trace_phy) ESP_LOGI(TAG, "UART%u idle wait enter", (unsigned)uart_no);
    __real_uart_tx_wait_idle(uart_no);
    if (trace_phy) ESP_LOGI(TAG, "UART%u idle wait returned", (unsigned)uart_no);
}

int __wrap_register_chipv6_phy(uint8_t *init_data)
{
    if (trace_phy) {
        ESP_LOGI(TAG, "RF register enter");
        /* RF 注册会切换 APB 时钟，先发完新增日志，沿用 SDK 的 UART 等待。 */
        __real_uart_tx_wait_idle(0);
    }
    int result = __real_register_chipv6_phy(init_data);
    if (trace_phy) ESP_LOGI(TAG, "RF register returned: result=%d", result);
    return result;
}
