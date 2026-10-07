# ESP8266 烧录工具

项目脚本使用 `esptool-v4.12.0\esptool.exe`，即已有的 Windows x64 esptool 4.12.0，支持 ESP8266。来源记录：[上游发布页](https://github.com/espressif/esptool/releases/tag/v4.12.0)。已有本地核验记录的版本输出为 4.12.0，SHA256 为：`1cd8386a7934862eb6ce1e14af3cc2309b0a743de1171fd09fab2f2ef2f5d1a3`。同目录保留 [上游说明的中文整理](esptool-v4.12.0/README.md) 和原始 `LICENSE`；可用 `Get-FileHash -Algorithm SHA256 .\tools\esptool-v4.12.0\esptool.exe` 核对。该记录未重新下载或在线比对上游二进制；当前本地文件可按上述命令重新核验。

## 推荐烧录流程

先运行 `python build.py` 生成固件。用 3.3 V USB-UART 将 TX 接 P3-3（RXD）、RX 接 P3-2（TXD），并共接 P3-4（GND）；短接 P4 后复位，使 ESP8266 进入下载模式。在 `Sof` 固件目录的 PowerShell 中运行 `python flash.py --port COM3`，将 `COM3` 改为实际端口。脚本从 `build\auto\flasher_args.json` 读取 Flash 参数和分段偏移，检查文件后调用本目录的 esptool；默认分段烧录，保留未覆盖的 NVS。可先运行 `python flash.py --port COM3 --dry-run` 只检查布局，不访问串口。运行时会输出配置文件、每段地址及 sector、准备执行的命令和烧录结果；`python flash.py --help` 显示完整用法。若需手动烧录，使用以下等效命令：

```powershell
& .\tools\esptool-v4.12.0\esptool.exe --chip esp8266 --port COM3 --baud 460800 `
  --before no_reset --after no_reset write_flash `
  --flash_mode dio --flash_size 4MB --flash_freq 26m `
  0x0 .\build\auto\bootloader\bootloader.bin `
  0x8000 .\build\auto\partition_table\partition-table.bin `
  0x10000 .\build\auto\ac_thermostat.bin
```

不传 `--port` 时可运行 `python flash.py`：脚本会读取系统串口列表，仅在恰有两个串口且其中一个是 COM1 时选择另一个。其他情况会报错，请使用 `--port COMx` 明确指定。`python flash.py --dry-run` 也会自动选择串口，但不会打开串口或写入 Flash。

默认烧录波特率为 `460800`，esptool 默认启用压缩传输。连接不稳定时使用 `python flash.py --port COM3 --baud 115200`；`--baud` 接受 9600～921600 的整数，实际可用速率还取决于串口设备。总耗时取决于传输、擦除、写入和校验，实际提速尚未实机测量。烧录波特率不改变固件日志的 115200 baud。

分段偏移及 Flash 参数以本次构建的 `build\auto\flasher_args.json` 为准；若其中 Flash 频率不是 `26m`，请更新本地 `sdkconfig` 并重新运行 `python build.py`，烧录脚本会拒绝旧的 40 MHz 产物。烧录完成后断开 P4 短接并复位。`full_flash.bin` 从 `0x0` 整片写入会清除 NVS 中保存的规则、红外编码及共享载波；需保留数据时使用分段命令。固件产物及最新验证见 [本地发布](../README.md#本地发布)。主机预检通过不代表设备烧录成功，实机验证须另行连接设备执行。

## SDK 定时器构建工具

`lwip_power.cmake` 按配置生成构建目录中的 `lwip_timeouts.c`，`lwip_timers.inc` 提供网络周期暂停/恢复实现。`noise_power.cmake` 与 `expose_timers.py` 生成项目内静态库及休眠源码副本，为实际 SDK 定时器对象添加符号别名。`components\esp8266` 接入这些副本；不会修改已安装 SDK，匹配失败时停止构建。开关、回退条件和验收见 [休眠与供电](../README.md#休眠与供电) 与 [功耗验收](../README.md#功耗验收)。

## 本地额外工具

工作区另有 `flash_download_tool\flash_download_tool_3.9.11.exe`，未被 `flash.py` 使用。已有只读检查记录称其包含 esptool/ESP8266 资源，采用 PyInstaller 打包且无版本元数据或数字签名；本次未重新核验这些属性。文件名不足以确认实际版本、来源和运行行为。该额外工具未纳入 Git，不属于项目构建或自动烧录流程。

该文件大小为 26,519,970 字节，本地 SHA256 为 `193f4f4113e5f315ad19175dd33456ba632801699f5b67e52ce164f11d7a54ca`，仅用于识别本地文件，不代表来源已核验。
