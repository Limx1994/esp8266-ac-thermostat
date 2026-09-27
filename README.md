# ESP-12F 空调温控

本工程使用 ESP8266 RTOS SDK 3.4。GPIO4 接 DS18B20，GPIO5 接 HS0038B，GPIO14 驱动红外 LED；S1/GPIO12 开配置热点，S2/GPIO13 进入暂停自动控制的 light sleep。开机默认监测温度，热点关闭。

本地版本为 **0.1A**。版本内容与验证范围见 [发布说明](RELEASE.md) 和 [变更记录](CHANGELOG.md)；项目修改约定见 [CLAUDE.md](CLAUDE.md)。

## 使用

按 S1，连接 `AC-Temp-XXXX` 开放 Wi‑Fi。手机如未自动弹出控制页，访问 `http://192.168.4.1`。每组规则设置温度、升温或降温方向，点击“学习红外”，在 15 秒内按一次遥控器目标按键。学习完成后可先用“测试发送”验证，再启用规则。无操作 10 分钟后热点关闭；学习期间不会主动关闭热点。

温度每 5 秒读取一次；触发后必须反向回退 0.5 °C 才会再次触发。上电、唤醒、修改规则或重新学习编码后的第一次有效读数只建立基线。DS18B20 读数失败时暂停发送，错误在页面及串口中显示。休眠期间不测温、不发红外，S1 唤醒并开热点，S2 唤醒恢复监测。

红外学习保留完整的解调时序，最多 960 段、750 毫秒，按 10 微秒单位存储。超过限制或波形无效会报错并保留旧编码。HS0038B 不能测出遥控器载波频率，页面需选 36/38/40 kHz；实际兼容性必须用目标遥控器验证。

## 构建

本机 SDK 的 Windows 构建脚本无法正确处理中文工程路径。已创建英文路径入口 `D:\ESP8266-AC`，它指向本目录；若在其他电脑构建，需建立自己的英文路径入口。PowerShell 中设置 `IDF_PATH` 为说明文件中的 SDK 路径，将工具链、CMake 和 Ninja 加入 `PATH`，然后从英文路径执行 CMake 配置与 `ninja -C build_ascii -j 12`。输出为 `build_ascii\ac_thermostat.bin`、`build_ascii\bootloader\bootloader.bin`、`build_ascii\partition_table\partition-table.bin`。

烧录需 3.3 V USB-UART 接 P3，并短接 P4 后复位进入下载模式。按构建输出中的 `build_ascii\flasher_args.json` 烧录：bootloader 在 `0x0`，partition table 在 `0x8000`，应用在 `0x10000`。当前电脑未接入设备，尚未执行烧录或实机验收。

## 检查

`ninja -f tests\build.ninja -j 12` 后运行 `build_ascii\rules_test.exe`，检查阈值、回差和单次触发。`node tests\check_page.js` 检查控制页脚本语法与 API 路径。实机仍需验证 Wi‑Fi 弹页、NVS 重启持久化、DS18B20 读数、两组红外学习与重放及按键唤醒。
