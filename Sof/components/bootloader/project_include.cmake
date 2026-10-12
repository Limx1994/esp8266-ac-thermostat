# 将项目 esp8266 覆盖组件传入 bootloader 子构建，禁止链接 SDK 旧库。
set(bootloader_sdk_dir "$ENV{IDF_PATH}/components/bootloader")
file(TO_CMAKE_PATH "${bootloader_sdk_dir}" bootloader_sdk_dir)
file(READ "${bootloader_sdk_dir}/project_include.cmake" bootloader_include)
set(bootloader_extra_arg "-DEXTRA_COMPONENT_DIRS=\${CMAKE_CURRENT_LIST_DIR}")
string(FIND "${bootloader_include}" "${bootloader_extra_arg}" bootloader_arg_offset)
if(bootloader_arg_offset EQUAL -1)
    message(FATAL_ERROR "SDK bootloader component argument differs; refusing old driver fallback")
endif()
string(REPLACE "${bootloader_extra_arg}"
    "\"-DEXTRA_COMPONENT_DIRS=${bootloader_sdk_dir}|${PROJECT_DIR}/components/esp8266\""
    bootloader_include "${bootloader_include}")
string(REPLACE "externalproject_add(bootloader"
    "externalproject_add(bootloader\n    LIST_SEPARATOR |"
    bootloader_include "${bootloader_include}")
string(REPLACE "\${CMAKE_CURRENT_LIST_DIR}" "${bootloader_sdk_dir}"
    bootloader_include "${bootloader_include}")
set(bootloader_generated "${CMAKE_BINARY_DIR}/bootloader_project.cmake")
file(WRITE "${bootloader_generated}" "${bootloader_include}")
include("${bootloader_generated}")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${bootloader_sdk_dir}/project_include.cmake")
