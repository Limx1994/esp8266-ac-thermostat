# 复用 SDK bootloader 组件，构建覆盖只改变驱动来源。
set(bootloader_sdk_dir "$ENV{IDF_PATH}/components/bootloader")
file(TO_CMAKE_PATH "${bootloader_sdk_dir}" bootloader_sdk_dir)
file(READ "${bootloader_sdk_dir}/CMakeLists.txt" bootloader_cmake)
string(REPLACE "FLASH_FILE_TEMPLATE flash_bootloader_args.in"
    "FLASH_FILE_TEMPLATE ${bootloader_sdk_dir}/flash_bootloader_args.in"
    bootloader_cmake "${bootloader_cmake}")
set(bootloader_generated "${CMAKE_CURRENT_BINARY_DIR}/sdk_component.cmake")
file(WRITE "${bootloader_generated}" "${bootloader_cmake}")
include("${bootloader_generated}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${bootloader_sdk_dir}/CMakeLists.txt")
