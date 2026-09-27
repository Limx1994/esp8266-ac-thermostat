# ESP-12F 空调温控

本工程使用 ESP8266 RTOS SDK 3.4。GPIO4 接 DS18B20，GPIO5 接 HS0038B，GPIO14 驱动红外 LED；S1/GPIO12 开配置热点，S2/GPIO13 进入暂停自动控制的 light sleep。开机默认监测温度，热点关闭。

本地版本为 **0.1B**。版本内容与验证范围见 [发布说明](RELEASE.md) 和 [变更记录](CHANGELOG.md)；项目修改约定见 [CLAUDE.md](CLAUDE.md)。

## 使用

按 S1，连接 `AC-Temp-XXXX` 开放 Wi‑Fi。手机如未自动弹出控制页，访问 `http://192.168.4.1`。每组规则设置温度、升温或降温方向，点击“学习红外”，在 15 秒内按一次遥控器目标按键。学习完成后可先用“测试发送”验证，再启用规则。无操作 10 分钟后热点关闭；学习期间不会主动关闭热点。

温度每 5 秒读取一次；触发后必须反向回退 0.5 °C 才会再次触发。上电、唤醒、修改规则或重新学习编码后的第一次有效读数只建立基线。DS18B20 读数失败时暂停发送，错误在页面及串口中显示。休眠期间不测温、不发红外，S1 唤醒并开热点，S2 唤醒恢复监测。

红外学习保留完整的解调时序，最多 960 段、750 毫秒，按 10 微秒单位存储。超过限制或波形无效会报错并保留旧编码。HS0038B 不能测出遥控器载波频率，页面需选 36/38/40 kHz；实际兼容性必须用目标遥控器验证。

## 构建

在 PowerShell 中运行 `python build.py`。脚本扫描 `main` 中的 C/C++/汇编源文件，临时映射空闲的 `Z:` 以避开中文路径，再通过 CMake 和 Ninja（`-j 12`）增量构建；从其他目录运行时使用脚本的绝对路径。SDK 默认使用本机路径，也可通过 `IDF_PATH` 指定，详见 [编译环境路径](ESP8266编译环境路径.md)。

| 产物 | 用途 |
| --- | --- |
| `build\auto\bootloader\bootloader.bin`、`build\auto\partition_table\partition-table.bin`、`build\auto\ac_thermostat.bin` | 按各自偏移分段烧录 |
| `build\auto\full_flash.bin`、`build\auto\full_flash.hex` | 同一份 4 MB 整片镜像，分别为 BIN 和 Intel HEX 格式 |

烧录需 3.3 V USB-UART 接 P3，并短接 P4 后复位进入下载模式。分段偏移以 `build\auto\flasher_args.json` 为准：bootloader 在 `0x0`，partition table 在 `0x8000`，应用在 `0x10000`。完整镜像的其余字节填 `0xFF`；整片写入会清除 NVS 中已保存的规则和红外编码，保留设备数据时请使用分段烧录。当前电脑未接入设备，尚未执行烧录或实机验收。

## 检查

使用本机 Ninja 执行 `& "D:\APPS\Espressif\tools\ninja\1.9.0\ninja.exe" -f tests\build.ninja -j 12`，再运行 `build_ascii\rules_test.exe` 检查阈值、回差和单次触发。`node --check tests\check_page.js` 与 `node tests\check_page.js` 检查控制页脚本和 API 路径。实际测试结果见 [发布说明](RELEASE.md)；实机仍需验证 Wi‑Fi 弹页、NVS 重启持久化、DS18B20 读数、两组红外学习与重放及按键唤醒。

P3 的 TXD（P3-2）和 GND（P3-4）接 3.3 V USB-UART，以 74880 baud 查看 UART0 日志。固件记录启动配置、每次测温（`temperature10` 单位为 0.1 °C）、规则触发、保存、红外学习与发送结果、热点和休眠状态及错误；尚未用实机验证串口输出。
