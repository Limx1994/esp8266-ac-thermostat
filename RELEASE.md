# 0.1A 本地发布说明

日期：2026-09-27。此版本仅在本地记录与保存，尚未烧录或完成实机验收。

## 内容

- 固件提供两组独立的温度阈值规则、红外学习与测试发送、S1 开启配置热点及 S2 暂停控制的 light sleep。使用方法见 [README.md](README.md)。
- 修复首次有效读数位于阈值前 0.5°C 范围内时，首次跨越可能漏触发的问题；触发后的 0.5°C 回差仍然有效。

## 固件产物

使用 ESP8266 RTOS SDK 3.4 和 Ninja `-j 12` 构建，目标为 4 MB Flash：

| 文件 | 烧录地址 | 大小 |
| --- | --- | ---: |
| `build_ascii\bootloader\bootloader.bin` | `0x0` | 9,968 字节 |
| `build_ascii\partition_table\partition-table.bin` | `0x8000` | 3,072 字节 |
| `build_ascii\ac_thermostat.bin` | `0x10000` | 508,016 字节 |

构建目录由 `.gitignore` 排除；本地 Git 提交仅保存源码和发布文档。

## 已验证

- 固件增量构建通过，使用 `ninja -j 12`。
- `rules_test.c` 以 `-Wall -Wextra -Werror` 编译并运行，阈值跨越和回差测试通过。该电脑上测试程序 `.exe` 无法稳定启动，本次通过临时 DLL 调用同一测试源码的 `main()` 完成验证。
- `node --check tests\check_page.js` 与 `node tests\check_page.js` 通过，控制页脚本语法及四个 API 路径检查通过。
- SDK 自带 `esptool.py image_info` 能解析应用镜像，checksum 有效；工具同时对两个 IROM 段输出 `Suspicious segment` 警告，仍需实机烧录验证。

## 未验证

当前无接入的 ESP-12F 设备，尚未验证烧录、Wi-Fi 自动弹页、DS18B20 测温、NVS 重启持久化、两组红外编码学习与发射波形、空调响应及按键唤醒。构建与主机测试通过不代表这些实机功能已通过。
