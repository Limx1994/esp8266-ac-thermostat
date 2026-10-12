# Pinned official archives; reject missing or changed files.
set(esp8266_driver_rev "858c7c2eb9004691f2c736c64a23715f6ea900c4")
set(esp8266_driver_files
    "VERSION|469aa0250cb011552af1931fd4d55304a3f54578b1f98e2cac5c737716445466"
    "libcore.a|526c23b9079361dcccb6ce3b7807602e899a719728ab347cab7409dbf6db18b7"
    "libcore_dbg.a|987643c203f92a008769daf9e260ecc42d40def3a287789bfe05dec431563b9f"
    "libespnow.a|e77171af84e0090c40d69531c80315566286327770755212baf6fc0e45529c8e"
    "libespnow_dbg.a|f38e0db67eda0ea9fd7358fb5ff29e653997ff4241343fe8f9506b66d88fad64"
    "libnet80211.a|8bfae78356d82db98f6f0fceafb9b10a6788e4f94887f4b0ce47f06daf3d78e3"
    "libnet80211_dbg.a|d62a64f849fe099c67634c61e558873eceb2f257f432db79d1d5a58ea446900e"
    "libphy.a|806da2ef0f8f5fa5f9a265dfe0bb8dd54a578cd1e75bf1f3aa0415586fc6e178"
    "libpp.a|430c0b2893dfa6aa29ae965ce390135a698a04f4a039e8a78ffd29022e167821"
    "libpp_dbg.a|2f70073992ace791f9b0c030f1c5f4b892039a9eb93b8f5bb85b6270d0739a06"
    "librtc.a|347d020d5d520dd7c93f254447c0f61dd3cb160147986ef2ca01ffeed541a355"
    "libsmartconfig.a|89e417befc8cea4eda72f16e6529bd02536f2c5893018639d927ce1b9bde4941"
)
foreach(entry ${esp8266_driver_files})
    string(REPLACE "|" ";" fields "${entry}")
    list(GET fields 0 name)
    list(GET fields 1 expected)
    set(archive "${esp8266_local_dir}/lib/${name}")
    file(SHA256 "${archive}" actual)
    if(NOT actual STREQUAL expected)
        message(FATAL_ERROR "Official driver archive hash mismatch: ${name}")
    endif()
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${archive}")
endforeach()
foreach(blob core net80211 pp phy rtc espnow smartconfig)
    set_property(TARGET ${blob} PROPERTY IMPORTED_LOCATION "${esp8266_local_dir}/lib/lib${blob}.a")
endforeach()
message(STATUS "Official ESP8266 driver: ${esp8266_driver_rev}; PHY 1167.0")
