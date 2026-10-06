# Reuse the installed SDK component, as with the existing HTTP override.
# Keep its imported archive targets in scope for the build-local timer aliases.
set(esp8266_local_dir "${CMAKE_CURRENT_SOURCE_DIR}")
set(esp8266_local_component "${COMPONENT_DIR}")
set(esp8266_sdk_dir "$ENV{IDF_PATH}/components/esp8266")
file(TO_CMAKE_PATH "${esp8266_sdk_dir}" esp8266_sdk_dir)
set(COMPONENT_DIR "${esp8266_sdk_dir}")
file(READ "${esp8266_sdk_dir}/CMakeLists.txt" esp8266_cmake)
string(REPLACE "\"source/" "\"\${esp8266_sdk_dir}/source/" esp8266_cmake "${esp8266_cmake}")
string(REPLACE "\"driver/" "\"\${esp8266_sdk_dir}/driver/" esp8266_cmake "${esp8266_cmake}")
string(REPLACE "set(include_dirs \"include\" \"include/driver\")"
    "set(include_dirs \${esp8266_sdk_dir}/include \${esp8266_sdk_dir}/include/driver)"
    esp8266_cmake "${esp8266_cmake}")
string(REPLACE "set(COMPONENT_ADD_INCLUDEDIRS include)"
    "set(COMPONENT_ADD_INCLUDEDIRS \${esp8266_sdk_dir}/include)" esp8266_cmake "${esp8266_cmake}")
string(REPLACE "set(COMPONENT_SRCS source/ets_printf.c source/crc.c source/esp_fast_boot.c)"
    "set(COMPONENT_SRCS \${esp8266_sdk_dir}/source/ets_printf.c \${esp8266_sdk_dir}/source/crc.c \${esp8266_sdk_dir}/source/esp_fast_boot.c)"
    esp8266_cmake "${esp8266_cmake}")
string(REPLACE "\${CMAKE_CURRENT_SOURCE_DIR}" "\${esp8266_sdk_dir}" esp8266_cmake "${esp8266_cmake}")
string(REPLACE "\${CMAKE_CURRENT_LIST_DIR}" "\${esp8266_sdk_dir}" esp8266_cmake "${esp8266_cmake}")
string(REPLACE "\"ld/" "\"\${esp8266_sdk_dir}/ld/" esp8266_cmake "${esp8266_cmake}")
string(REPLACE "set(fragments linker.lf ld/esp8266_fragments.lf ld/esp8266_bss_fragments.lf)"
    "set(fragments \${esp8266_sdk_dir}/linker.lf \${esp8266_sdk_dir}/ld/esp8266_fragments.lf \${esp8266_sdk_dir}/ld/esp8266_bss_fragments.lf)"
    esp8266_cmake "${esp8266_cmake}")
set(esp8266_generated "${CMAKE_CURRENT_BINARY_DIR}/sdk_component.cmake")
file(WRITE "${esp8266_generated}" "${esp8266_cmake}")
include("${esp8266_generated}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${esp8266_sdk_dir}/CMakeLists.txt")
set(COMPONENT_DIR "${esp8266_local_component}")

if(CONFIG_APP_PAUSE_NOISE_TIMER AND NOT BOOTLOADER_BUILD)
    include("${esp8266_local_dir}/../../tools/noise_power.cmake")
endif()
