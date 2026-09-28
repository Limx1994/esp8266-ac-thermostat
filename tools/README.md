# ESP8266 烧录工具

`esptool-v4.12.0\esptool.exe` 是乐鑫发布的 Windows x64 版 esptool 4.12.0，支持本项目的 ESP8266。来源：[官方发布页](https://github.com/espressif/esptool/releases/tag/v4.12.0)。本地可执行文件的 SHA256 为 `1cd8386a7934862eb6ce1e14af3cc2309b0a743de1171fd09fab2f2ef2f5d1a3`；原版 `README.md` 和 `LICENSE` 保存在同一目录。可在 PowerShell 中用 `Get-FileHash -Algorithm SHA256 .\tools\esptool-v4.12.0\esptool.exe` 核对。

先运行 `python build.py` 生成固件。用 3.3 V USB-UART 将 TX 接 P3-3（RXD）、RX 接 P3-2（TXD），并共接 P3-4（GND）；短接 P4 后复位，使 ESP8266 进入下载模式。在项目根目录的 PowerShell 中运行以下命令，将 `COM3` 改为实际端口：

```powershell
& .\tools\esptool-v4.12.0\esptool.exe --chip esp8266 --port COM3 --baud 115200 `
  --before no_reset --after no_reset write_flash `
  --flash_mode dio --flash_size 4MB --flash_freq 40m `
  0x0 .\build\auto\bootloader\bootloader.bin `
  0x8000 .\build\auto\partition_table\partition-table.bin `
  0x10000 .\build\auto\ac_thermostat.bin
```

分段偏移及 Flash 参数以本次构建的 `build\auto\flasher_args.json` 为准；若其中参数与示例不同，应按该文件调整命令。烧录完成后断开 P4 短接并复位。`full_flash.bin` 从 `0x0` 整片写入会清除 NVS 中保存的规则和红外编码；需保留数据时使用上面的分段命令。当前仅验证了工具版本与固件镜像解析，未连接设备执行烧录。
