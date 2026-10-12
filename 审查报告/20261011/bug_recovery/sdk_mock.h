
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
extern unsigned test_log_seq, test_learn_wait, test_learn_end;
extern unsigned crc_logs;
extern unsigned test_send_start;
extern unsigned test_send_reports;
extern bool drop_send_logs;
typedef int esp_err_t;
typedef int BaseType_t;
typedef uint32_t TickType_t;
typedef void *TaskHandle_t;
typedef void *QueueHandle_t;
typedef struct { unsigned unused; } List_t;
#define configMAX_TASK_NAME_LEN 16
typedef void *SemaphoreHandle_t;
typedef void (*TaskFunction_t)(void *);
typedef int nvs_handle;
typedef int gpio_num_t;
typedef int gpio_int_type_t;
enum { ESP_OK, ESP_FAIL, ESP_ERR_INVALID_ARG, ESP_ERR_INVALID_STATE,
       ESP_ERR_NO_MEM, ESP_ERR_NOT_FOUND, ESP_ERR_TIMEOUT, ESP_ERR_INVALID_SIZE,
       ESP_ERR_INVALID_RESPONSE, ESP_ERR_INVALID_CRC, ESP_ERR_NVS_NOT_FOUND };
enum { GPIO_NUM_0=0, GPIO_NUM_1=1, GPIO_NUM_2=2, GPIO_NUM_4=4, GPIO_NUM_5=5, GPIO_NUM_12=12,
       GPIO_NUM_13=13, GPIO_NUM_14=14, GPIO_NUM_15=15 };
enum { ESP_LOG_NONE };
typedef int (*putchar_like_t)(int);
void esp_log_level_set(const char *, int);
putchar_like_t esp_log_set_putchar(putchar_like_t);
enum { GPIO_INTR_DISABLE, GPIO_INTR_NEGEDGE, GPIO_INTR_LOW_LEVEL,
       GPIO_INTR_ANYEDGE, GPIO_MODE_INPUT, GPIO_MODE_OUTPUT, GPIO_MODE_OUTPUT_OD,
       GPIO_PULLUP_DISABLE, GPIO_PULLUP_ENABLE, GPIO_PULLDOWN_DISABLE };
enum { NVS_READONLY, NVS_READWRITE };
enum { I2S_NUM_0, I2S_MODE_MASTER, I2S_BITS_PER_SAMPLE_16BIT,
       I2S_CHANNEL_FMT_RIGHT_LEFT, I2S_COMM_FORMAT_I2S, I2S_COMM_FORMAT_I2S_MSB };
enum { TIMER_CLKDIV_16=4, TIMER_EDGE_INT=0 };
enum { PERIPHS_IO_MUX_MTMS_U, FUNC_GPIO14, FUNC_I2SI_WS };
typedef struct {
    uint64_t pin_bit_mask;
    int mode, pull_up_en, pull_down_en, intr_type;
} gpio_config_t;
typedef struct {
    int mode, sample_rate, bits_per_sample, channel_format;
    int communication_format, dma_buf_count, dma_buf_len;
} i2s_config_t;
typedef struct {
    int bck_o_en, ws_o_en, bck_i_en, ws_i_en, data_out_en, data_in_en;
} i2s_pin_config_t;
typedef struct { bool light_sleep_enable; } esp_pm_config_esp8266_t;
enum { ADC_READ_TOUT_MODE };
typedef struct { int mode; uint8_t clk_div; } adc_config_t;
esp_err_t adc_init(adc_config_t *);
esp_err_t adc_read(uint16_t *);
esp_err_t adc_read_fast(uint16_t *, uint16_t);
struct mock_gpio {
    uint32_t in, out_w1tc, out_w1ts, status, status_w1tc;
    struct { int int_type; bool wakeup_enable; } pin[17];
};
extern struct mock_gpio GPIO;
extern struct mock_i2s {
    struct { unsigned tx_slave_mod, rx_slave_mod, bck_div_num, clkm_div_num; } conf;
} I2S0;
extern struct mock_timer {
    struct { uint32_t data; } count, load;
    struct { unsigned div, reload, en, intr_type; } ctrl;
} frc1;
extern int test_pin_func;
#define CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ TEST_CPU_MHZ
typedef enum { RTC_CPU_FREQ_80M, RTC_CPU_FREQ_160M } rtc_cpu_freq_t;
rtc_cpu_freq_t rtc_clk_cpu_freq_get(void);
int esp_clk_cpu_freq(void);
typedef uint32_t esp_irqflag_t;
esp_irqflag_t soc_save_local_irq(void);
void soc_restore_local_irq(esp_irqflag_t);
extern volatile uint32_t test_rtc_counter;
#define RTC_SLP_CNT_VAL 0
uint32_t test_read_reg(uint32_t);
#define REG_READ(reg) test_read_reg(reg)
extern uint32_t g_esp_ticks_per_us;
uint32_t soc_get_ccompare(void);
#define CONFIG_ESP_CONSOLE_UART_NUM 0
#define IRAM_ATTR
#define pdFALSE 0
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY UINT32_MAX
#ifndef TEST_TICK_MS
#define TEST_TICK_MS 10U
#endif
#define pdMS_TO_TICKS(ms) ((TickType_t)(ms) / TEST_TICK_MS)
#define portTICK_PERIOD_MS TEST_TICK_MS
#define portENTER_CRITICAL() ((void)0)
#define portEXIT_CRITICAL() ((void)0)
#define portYIELD_FROM_ISR() ((void)0)
#define ESP_ERROR_CHECK(expr) assert((expr) == ESP_OK)
#define PIN_FUNC_SELECT(pin, fn) ((void)(pin), test_pin_func = (fn))
#define ESP_LOGI(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGD(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGE(tag, ...) test_log(tag, __VA_ARGS__)
#define ESP_LOGW(tag, ...) test_log(tag, __VA_ARGS__)
void test_log(const char *, const char *, ...);
const char *esp_err_to_name(esp_err_t);
TickType_t xTaskGetTickCount(void);
TaskHandle_t xTaskGetCurrentTaskHandle(void);
char *pcTaskGetName(TaskHandle_t);
BaseType_t xTaskCreate(TaskFunction_t, const char *, unsigned, void *, unsigned, TaskHandle_t *);
void vTaskDelete(TaskHandle_t);
void vTaskDelay(TickType_t);
void vTaskNotifyGiveFromISR(TaskHandle_t, BaseType_t *);
BaseType_t xTaskNotifyGive(TaskHandle_t);
uint32_t ulTaskNotifyTake(BaseType_t, TickType_t);
SemaphoreHandle_t xSemaphoreCreateMutex(void);
SemaphoreHandle_t xSemaphoreCreateBinary(void);
BaseType_t xSemaphoreTake(SemaphoreHandle_t, TickType_t);
BaseType_t xSemaphoreGive(SemaphoreHandle_t);
BaseType_t xSemaphoreGiveFromISR(SemaphoreHandle_t, BaseType_t *);
esp_err_t gpio_config(const gpio_config_t *);
esp_err_t gpio_set_level(gpio_num_t, uint32_t);
esp_err_t gpio_set_direction(gpio_num_t, int);
void ets_delay_us(uint32_t);
uint32_t soc_get_ccount(void);
void uart_tx_wait_idle(uint8_t);
int gpio_get_level(gpio_num_t);
esp_err_t gpio_set_intr_type(gpio_num_t, gpio_int_type_t);
esp_err_t gpio_wakeup_enable(gpio_num_t, gpio_int_type_t);
esp_err_t gpio_isr_handler_add(gpio_num_t, TaskFunction_t, void *);
esp_err_t gpio_isr_handler_remove(gpio_num_t);
esp_err_t gpio_install_isr_service(int);
esp_err_t esp_pm_configure(const void *);
esp_err_t esp_sleep_enable_gpio_wakeup(void);
void esp_sleep_lock(void);
void esp_sleep_unlock(void);
int64_t esp_timer_get_time(void);
esp_err_t nvs_flash_init(void);
esp_err_t nvs_open(const char *, int, nvs_handle *);
void nvs_close(nvs_handle);
esp_err_t nvs_get_blob(nvs_handle, const char *, void *, size_t *);
esp_err_t nvs_set_blob(nvs_handle, const char *, const void *, size_t);
esp_err_t nvs_get_u16(nvs_handle, const char *, uint16_t *);
esp_err_t nvs_set_u16(nvs_handle, const char *, uint16_t);
esp_err_t nvs_commit(nvs_handle);
esp_err_t nvs_erase_key(nvs_handle, const char *);
esp_err_t i2s_driver_install(int, const i2s_config_t *, int, void *);
esp_err_t i2s_set_pin(int, const i2s_pin_config_t *);
esp_err_t i2s_set_sample_rates(int, uint32_t);
esp_err_t i2s_start(int);
esp_err_t i2s_stop(int);
esp_err_t hw_timer_init(TaskFunction_t, void *);
esp_err_t hw_timer_alarm_us(uint32_t, bool);
esp_err_t hw_timer_disarm(void);
