# Keep original SDK binaries/source intact. Only alias actual timer storage.
set(noise_sdk "$ENV{IDF_PATH}")
file(TO_CMAKE_PATH "${noise_sdk}" noise_sdk)
set(noise_dir "${CMAKE_BINARY_DIR}/noise_power")
execute_process(COMMAND ${PYTHON} "${CMAKE_CURRENT_LIST_DIR}/expose_timers.py"
    --sdk "${noise_sdk}" --out "${noise_dir}" --ar "${CMAKE_AR}" --objcopy "${CMAKE_OBJCOPY}"
    RESULT_VARIABLE expose_result)
if(NOT expose_result EQUAL 0)
    message(FATAL_ERROR "Cannot expose SDK timer storage; refusing noise pause build")
endif()
set_property(TARGET core PROPERTY IMPORTED_LOCATION "${noise_dir}/libcore.a")
set_property(TARGET pp PROPERTY IMPORTED_LOCATION "${noise_dir}/libpp.a")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_LIST_DIR}/expose_timers.py"
    "${noise_sdk}/components/esp8266/lib/libcore.a"
    "${noise_sdk}/components/esp8266/lib/libpp.a")

set(sleep_original "${noise_sdk}/components/esp8266/source/esp_sleep.c")
file(READ "${sleep_original}" sleep_code)
string(REPLACE "\r\n" "\n" sleep_code "${sleep_code}")
set(sleep_match "if (clk->frc2_enable) {\n        const uint32_t frc2_sleep_ticks")
string(FIND "${sleep_code}" "${sleep_match}" sleep_offset)
if(sleep_offset EQUAL -1)
    message(FATAL_ERROR "SDK sleep deadline implementation differs; refusing noise pause patch")
endif()
string(REPLACE "${sleep_match}"
    "if (clk->frc2_enable && app_os_timer_pending()) {\n        const uint32_t frc2_sleep_ticks"
    sleep_code "${sleep_code}")
string(REPLACE "#define FRC2_LOAD" "extern int app_os_timer_pending(void);\n\n#define FRC2_LOAD"
    sleep_code "${sleep_code}")
set(sleep_generated "${CMAKE_BINARY_DIR}/esp_sleep.c")
file(WRITE "${sleep_generated}" "${sleep_code}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${sleep_original}")
idf_component_get_property(sleep_lib esp8266 COMPONENT_LIB)
get_target_property(sleep_sources ${sleep_lib} SOURCES)
list(FIND sleep_sources "${sleep_original}" sleep_index)
if(sleep_index EQUAL -1)
    message(FATAL_ERROR "SDK esp_sleep.c source missing; refusing noise pause patch")
endif()
list(REMOVE_ITEM sleep_sources "${sleep_original}")
list(APPEND sleep_sources "${sleep_generated}")
set_property(TARGET ${sleep_lib} PROPERTY SOURCES "${sleep_sources}")
message(STATUS "RF-off: noise timer paused; empty queue ignores stale FRC2 alarm")
