#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include "startup_trace.c"

static unsigned loads, waits, registers, logs;
static uint8_t payload;
void mock_log(const char *tag, const char *format, ...)
{
    assert(tag && format);
    logs++;
}
void __real_uart_tx_wait_idle(uint8_t uart_no)
{
    assert(uart_no == 0 || uart_no == 1);
    waits++;
}
int __real_register_chipv6_phy(uint8_t *data)
{
    assert(data == &payload);
    registers++;
    return -7;
}
void __real_esp_phy_load_cal_and_init(phy_rf_module_t module)
{
    assert(module == 3 && trace_phy);
    loads++;
    __wrap_uart_tx_wait_idle(1);
    assert(__wrap_register_chipv6_phy(&payload) == -7);
}
int main(void)
{
    __wrap_uart_tx_wait_idle(0);
    assert(waits == 1 && logs == 0);
    assert(__wrap_register_chipv6_phy(&payload) == -7);
    assert(registers == 1 && waits == 1 && logs == 0);
    __wrap_esp_phy_load_cal_and_init(3);
    assert(loads == 1 && registers == 2 && waits == 3 && logs == 6);
    assert(!trace_phy);
    __wrap_uart_tx_wait_idle(0);
    assert(waits == 4 && logs == 6);
    puts("startup: PHY scope, UART forwarding and RF error result passed");
    return 0;
}
