#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "rom/ets_sys.h"
#include "sensor.h"

#define DQ GPIO_NUM_4

static bool reset_bus(void)
{
    gpio_set_level(DQ, 0);
    ets_delay_us(480);
    portENTER_CRITICAL();
    gpio_set_level(DQ, 1);
    ets_delay_us(70);
    bool present = gpio_get_level(DQ) == 0;
    portEXIT_CRITICAL();
    ets_delay_us(410);
    return present;
}

static void write_bit(int bit)
{
    portENTER_CRITICAL();
    gpio_set_level(DQ, 0);
    ets_delay_us(bit ? 6 : 60);
    gpio_set_level(DQ, 1);
    ets_delay_us(bit ? 64 : 10);
    portEXIT_CRITICAL();
}

static int read_bit(void)
{
    portENTER_CRITICAL();
    gpio_set_level(DQ, 0);
    ets_delay_us(3);
    gpio_set_level(DQ, 1);
    ets_delay_us(10);
    int bit = gpio_get_level(DQ);
    ets_delay_us(57);
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

esp_err_t sensor_init(void)
{
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << DQ, .mode = GPIO_MODE_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_DISABLE, .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    esp_err_t err = gpio_config(&cfg);
    if (err == ESP_OK) err = gpio_set_level(DQ, 1);
    return err;
}

esp_err_t sensor_read(int16_t *temp10)
{
    if (!temp10) return ESP_ERR_INVALID_ARG;
    if (!reset_bus()) return ESP_ERR_NOT_FOUND;
    write_byte(0xcc);
    write_byte(0x44);
    vTaskDelay(pdMS_TO_TICKS(750));
    if (!reset_bus()) return ESP_ERR_NOT_FOUND;
    write_byte(0xcc);
    write_byte(0xbe);
    uint8_t data[9];
    for (int i = 0; i < 9; i++) data[i] = read_byte();
    if (crc8(data, 8) != data[8]) return ESP_ERR_INVALID_CRC;
    int16_t raw = (int16_t)((data[1] << 8) | data[0]);
    if (raw == 0x0550) return ESP_ERR_INVALID_STATE;
    *temp10 = (raw * 10 + (raw >= 0 ? 8 : -8)) / 16;
    return ESP_OK;
}
