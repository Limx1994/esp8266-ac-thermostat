idf_component_register(SRC_DIRS "." INCLUDE_DIRS ".")

# 包装器保留原 SDK 调用；记录 Wi-Fi 冷启动阶段及休眠诊断。
target_link_libraries(${COMPONENT_LIB} INTERFACE
    "-Wl,--wrap=esp_phy_load_cal_and_init"
    "-Wl,--wrap=uart_tx_wait_idle"
    "-Wl,--wrap=register_chipv6_phy"
    "-Wl,--wrap=esp_sleep_start"
    "-Wl,--wrap=prvGetExpectedIdleTime"
    "-Wl,--wrap=pm_set_sleep_cycles"
    "-Wl,--wrap=vTaskDelay"
    "-Wl,--wrap=ulTaskNotifyTake"
    "-Wl,--wrap=xQueueReceive"
    "-Wl,--wrap=vTaskPlaceOnEventList"
    "-Wl,--wrap=vTaskPlaceOnEventListRestricted"
    "-Wl,--wrap=pm_rtc_clock_cali_proc"
    "-Wl,--wrap=rtc_light_sleep_start")

if(CONFIG_APP_PAUSE_NOISE_TIMER)
    target_link_libraries(${COMPONENT_LIB} INTERFACE
        "-Wl,--wrap=os_timer_arm" "-Wl,--wrap=os_timer_arm_us")
endif()
