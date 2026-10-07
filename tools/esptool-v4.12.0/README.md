# esptool.py

基于 Python 的开源跨平台工具，用于与 Espressif 芯片的 ROM bootloader 通信。本文件于 2026-10-05 按本项目用途整理为中文，保留上游链接、作者署名与许可；工具程序和 LICENSE 未修改。

[![Test esptool](https://github.com/espressif/esptool/actions/workflows/test_esptool.yml/badge.svg?branch=master)](https://github.com/espressif/esptool/actions/workflows/test_esptool.yml) [![Build esptool](https://github.com/espressif/esptool/actions/workflows/build_esptool.yml/badge.svg?branch=master)](https://github.com/espressif/esptool/actions/workflows/build_esptool.yml)

## 文档与本项目用法

上游 [文档](https://docs.espressif.com/projects/esptool/) 和工具帮助提供完整说明；在线文档可能对应更新版本，本地参数以本目录 4.12.0 可执行文件的 `-h` 输出为准。本目录保存 Windows 可执行版，本项目的接线、参数、校验值及 NVS 保留方法见 [烧录工具说明](../README.md)。在仓库根目录的 PowerShell 中可运行：

```powershell
& .\tools\esptool-v4.12.0\esptool.exe version
& .\tools\esptool-v4.12.0\esptool.exe -h
```

推荐使用项目 `flash.py` 读取构建布局，项目脚本默认 460800 baud、分段烧录并保留未覆盖的 NVS；该默认值属于项目脚本，不代表上游 esptool 默认值。先执行 `python flash.py --port COM3 --dry-run` 检查布局，不打开串口；实际偏移和参数以 `build\auto\flasher_args.json` 为准，不将其他芯片示例直接用于 ESP8266。工具不负责判断空调是否接收红外，项目脚本位于 `Sof` 仓库根目录，不能从外层工作区直接执行。当前固件的产物与验证记录见 [本地发布](../../README.md#本地发布)。

## 贡献

参与上游开发请阅读 [贡献指南](https://docs.espressif.com/projects/esptool/en/latest/contributing.html)。

## 作者与维护

按上游说明，esptool.py 最初由 Fredrik Ahlberg（@[themadinventor](https://github.com/themadinventor/)）创建，后由 Angus Gratton（@[projectgus](https://github.com/projectgus/)）维护，并由 Espressif Systems 支持；社区成员也参与了改进。

## 许可

本文件与附带源码沿用上游的 GNU General Public License Version 2 or later。参见本目录 [LICENSE](LICENSE) 及原始 [上游 LICENSE 链接](https://github.com/espressif/esptool/blob/master/LICENSE)。
