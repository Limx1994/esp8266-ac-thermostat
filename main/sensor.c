#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "driver/gpio.h"
#include "driver/soc.h"
#include "esp8266/gpio_struct.h"
#include "esp_attr.h"
#include "rom/ets_sys.h"
#include "esp_log.h"
#include "sensor.h"

#define DQ GPIO_NUM_4
#if CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ != 80 && CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ != 160
#error 1-Wire slot timing requires a configured 80 or 160 MHz CPU clock
#endif
#define CPU_CYCLES_PER_US CONFIG_ESP8266_DEFAULT_CPU_FREQ_MHZ
static bool power_warned;

static esp_err_t release_bus(esp_err_t err)
{
#ifdef CONFIG_APP_SENSOR_IDLE_INPUT
    esp_err_t cleanup = gpio_set_direction(DQ, GPIO_MODE_INPUT);
    if (cleanup != ESP_OK) {
        ESP_LOGE("sensor", "bus release failed: %s", esp_err_to_name(cleanup));
        if (err == ESP_OK) err = cleanup;
    }
#endif
    return err;
}

/* 调用时已屏蔽 RTOS tick 中断，避免 ccount 被 tick 重置。
 * 边沿、延时和采样全程位于 IRAM，避免依赖 Flash cache。
 */
static void IRAM_ATTR slot_wait(uint32_t start, uint32_t us)
{
    while ((uint32_t)(soc_get_ccount() - start) < us * CPU_CYCLES_PER_US) { }
}

static bool IRAM_ATTR reset_bus(void)
{
    /* 在临界区内完成复位及存在脉冲采样，避免任务切换拉长时序。 */
    portENTER_CRITICAL();
    GPIO.out_w1tc = 1U << DQ;
    uint32_t start = soc_get_ccount();
    slot_wait(start, 480);
    GPIO.out_w1ts = 1U << DQ;
    slot_wait(start, 550);
    bool present = (GPIO.in & (1U << DQ)) == 0;
    portEXIT_CRITICAL();
    ets_delay_us(410);
    return present;
}

static void IRAM_ATTR write_bit(int bit)
{
    portENTER_CRITICAL();
    GPIO.out_w1tc = 1U << DQ;
    uint32_t start = soc_get_ccount();
    slot_wait(start, bit ? 6 : 60);
    GPIO.out_w1ts = 1U << DQ;
    slot_wait(start, 70);
    portEXIT_CRITICAL();
}

static int IRAM_ATTR read_bit(void)
{
    portENTER_CRITICAL();
    GPIO.out_w1tc = 1U << DQ;
    uint32_t start = soc_get_ccount();
    slot_wait(start, 3);
    GPIO.out_w1ts = 1U << DQ;
    slot_wait(start, 13);
    int bit = (GPIO.in >> DQ) & 1U;
    slot_wait(start, 70);
    portEXIT_CRITICAL();
    return bit;
}

static void write_byte(uint8_t value)
{
    for (int i = 0; i < 8; i++) write_bit((value >> i) & 1);
}

static uint8_t read_byte(void)
{
    uint8_t value = 0;
    for (int i = 0; i < 8; i++) value |= read_bit() << i;
    return value;
}

/* DS18B20 scratchpad 使用低位优先 CRC8，反向多项式为 0x8c。 */
static uint8_t crc8(const uint8_t *data, int len)
{
    uint8_t crc = 0;
    for (int i = 0; i < len; i++) {
        uint8_t b = data[i];
        for (int j = 0; j < 8; j++) {
            uint8_t mix = (crc ^ b) & 1;
            crc >>= 1;
            if (mix) crc ^= 0x8c;
            b >>= 1;
        }
    }
    return crc;
}

static esp_err_t read_scratchpad(uint8_t data[9])
{
    if (!reset_bus()) return ESP_ERR_NOT_FOUND;
    write_byte(0xcc);
    write_byte(0xbe);
    for (int i = 0; i < 9; i++) data[i] = read_byte();
    uint8_t expected_crc = crc8(data, 8);
    if (expected_crc != data[8]) {
        ESP_LOGW("sensor", "scratchpad=%02x %02x %02x %02x %02x %02x %02x %02x %02x; expected CRC=%02x",
                 data[0], data[1], data[2], data[3], data[4],
                 data[5], data[6], data[7], data[8], expected_crc);
        return ESP_ERR_INVALID_CRC;
    }
    return ESP_OK;
}

static esp_err_t ensure_resolution(void)
{
    uint8_t data[9], verified[9];
    esp_err_t err = read_scratchpad(data);
    if (err != ESP_OK) return err;
    if ((data[4] & 0x60) == 0x60) return ESP_OK;
    unsigned resolution = 9 + ((data[4] >> 5) & 3);
    if (!reset_bus()) return ESP_ERR_NOT_FOUND;
    write_byte(0xcc);
    write_byte(0x4e);
    /* 保留 TH/TL，只修改 RAM 分辨率；不执行 Copy Scratchpad 写 EEPROM。 */
    write_byte(data[2]);
    write_byte(data[3]);
    write_byte(data[4] | 0x60);
    err = read_scratchpad(verified);
    if (err != ESP_OK) return err;
    if (verified[2] != data[2] || verified[3] != data[3] ||
        verified[4] != (uint8_t)(data[4] | 0x60)) {
        ESP_LOGE("sensor", "12-bit configuration readback failed");
        return ESP_ERR_INVALID_RESPONSE;
    }
    ESP_LOGI("sensor", "resolution corrected: %u -> 12 bits", resolution);
    return ESP_OK;
}

esp_err_t sensor_init(void)
{
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << DQ, .mode = GPIO_MODE_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    esp_err_t err = gpio_config(&cfg);
    if (err == ESP_OK) err = gpio_set_level(DQ, 1);
    return release_bus(err);
}

static esp_err_t start_conversion(bool *external_power)
{
    if (!external_power) return ESP_ERR_INVALID_ARG;
    *external_power = false;
    esp_err_t err = gpio_set_direction(DQ, GPIO_MODE_OUTPUT_OD);
    if (err != ESP_OK) return err;
    if (!reset_bus()) return ESP_ERR_NOT_FOUND;
    write_byte(0xcc);
    /* Read Power Supply：返回位为 1 表示外部供电，否则按寄生供电处理。 */
    write_byte(0xb4);
    bool powered = read_bit() != 0;
    if (!powered && !power_warned) {
        ESP_LOGW("sensor", "parasite power detected; conversion sleep disabled");
        power_warned = true;
    }
    err = ensure_resolution();
    if (err != ESP_OK) return err;
    if (!reset_bus()) return ESP_ERR_NOT_FOUND;
    write_byte(0xcc);
    write_byte(0x44);
    if (powered) {
        /* 外部供电时由板上 4.7 kΩ 上拉保持 DQ 高电平，转换期间可释放输出。 */
        err = gpio_set_direction(DQ, GPIO_MODE_INPUT);
        if (err != ESP_OK) return err;
    }
    *external_power = powered;
    return ESP_OK;
}

esp_err_t sensor_start(bool *external_power)
{
    if (!external_power) return ESP_ERR_INVALID_ARG;
    esp_err_t err = start_conversion(external_power);
    return err == ESP_OK ? err : release_bus(err);
}

static esp_err_t read_temp(int16_t *temp10)
{
    esp_err_t err = gpio_set_direction(DQ, GPIO_MODE_OUTPUT_OD);
    if (err != ESP_OK) return err;
    uint8_t data[9];
    err = read_scratchpad(data);
    if (err != ESP_OK) return err;
    if ((data[4] & 0x60) != 0x60) return ESP_ERR_INVALID_STATE;
    int16_t raw = (int16_t)((data[1] << 8) | data[0]);
    /* 拒绝 85 ℃上电默认值；在舍入前加偏移，按校准后的符号处理负温度。 */
    if (raw == 0x0550) return ESP_ERR_INVALID_STATE;
    int scaled = raw * 10 + CONFIG_APP_TEMP_OFFSET10 * 16;
    *temp10 = (scaled + (scaled >= 0 ? 8 : -8)) / 16;
    ESP_LOGI("sensor", "raw16=%d resolution=12 offset10=%d temperature10=%d",
             (int)raw, CONFIG_APP_TEMP_OFFSET10, (int)*temp10);
    return ESP_OK;
}

esp_err_t sensor_finish(int16_t *temp10)
{
    if (!temp10) return ESP_ERR_INVALID_ARG;
    esp_err_t err = ESP_FAIL;
    /* 只重试 CRC 错误和设备未找到；其他错误直接上报，避免掩盖故障。 */
    for (int attempt = 1; attempt <= 3; attempt++) {
        err = read_temp(temp10);
        if (err == ESP_OK || attempt == 3 ||
            (err != ESP_ERR_INVALID_CRC && err != ESP_ERR_NOT_FOUND)) break;
        ESP_LOGW("sensor", "scratchpad read attempt %d failed: %s; retrying",
                 attempt, esp_err_to_name(err));
    }
    return release_bus(err);
}
