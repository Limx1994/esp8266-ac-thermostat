cmake_minimum_required(VERSION 3.5)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(ac_thermostat)

if(CONFIG_APP_DISABLE_DHCP_CLIENT_TIMERS OR CONFIG_APP_PAUSE_NETWORK_TIMERS)
    include(tools/lwip_power.cmake)
endif()
