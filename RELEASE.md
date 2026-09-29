# 0.1F 本地发布说明

日期：2026-09-29。此版本仅在本地记录与保存，尚未烧录或完成实机验收。

## 内容

- 在 `sdkconfig.defaults` 中分别将 ESP-12F 晶振和 Flash 频率设为 26 MHz；`build.py` 检查构建后的 Flash 频率，输出构建进度、分段布局和产物信息。
- 新增 `flash.py`：从本次构建的 `flasher_args.json` 读取分段偏移及 Flash 参数，烧录前检查文件、容量和 4 KiB sector 冲突；支持不访问串口的 `--dry-run`。用法见 [烧录工具说明](tools/README.md)。
- 两组温度规则、红外学习与发送、配置热点和 light sleep 未改动；使用方法见 [README.md](README.md)。

## 固件产物

使用 ESP8266 RTOS SDK 3.4，通过 `python build.py` 调用 Ninja `-j 12` 构建，目标为 4 MB Flash：

| 文件 | 用途或烧录偏移 | 文件大小 |
| --- | --- | ---: |
| `build\auto\bootloader\bootloader.bin` | bootloader，`0x0` | 10,096 字节 |
| `build\auto\partition_table\partition-table.bin` | partition table，`0x8000` | 3,072 字节 |
| `build\auto\ac_thermostat.bin` | 应用固件，`0x10000` | 508,848 字节 |
| `build\auto\full_flash.bin` | 从 `0x0` 开始的完整 4 MB Flash 镜像 | 4,194,304 字节 |
| `build\auto\full_flash.hex` | 同一 4 MB 镜像的 Intel HEX 文本格式 | 11,535,372 字节 |
| `build\auto\flasher_args.json` | 分段偏移及 Flash 参数 | 815 字节 |

`flasher_args.json` 指定 DIO、26 MHz Flash 频率、4 MB 容量；ESP-12F 晶振频率也设为 26 MHz，属于独立配置项。分段烧录以本次构建的偏移为准。完整镜像的未使用区域填充 `0xFF`，整片写入会清除 NVS 中保存的规则和红外编码；保留数据时使用分段烧录。构建目录由 `.gitignore` 排除，不纳入本地 Git 提交。

## 已验证

- 项目 Markdown 的空白、标题间距与本地链接 lint、`git diff --check` 通过。
- `tests\build.ninja` 以 `-j 12` 构建规则测试，`build_ascii\rules_test.exe` 输出 `rules_test: all cases passed`。
- `node --check tests\check_page.js` 与 `node tests\check_page.js` 通过；控制页脚本及四个 API 路径检查通过。
- `python build.py` 以 Ninja `-j 12` 构建通过；Flash 参数为 DIO、26 MHz、4 MB，产物大小与上表一致，完整 BIN 在指定偏移与三个分段文件逐字节一致，`Z:` 已解除映射。
- `python flash.py --port COM3 --dry-run` 通过，确认三个分段未超出容量且未占用相同 4 KiB sector；该检查未访问串口或写入 Flash。
- 本地 `esptool.exe` 返回 4.12.0，SHA256 与 [工具说明](tools/README.md)一致；`image_info` 可解析应用镜像且校验和有效，但报告两条 `Suspicious segment` 警告。

## 未验证

当前无接入的 ESP-12F 设备，尚未验证烧录、UART0 实际日志、Wi-Fi 自动弹页、DS18B20 测温、NVS 重启持久化、两组红外编码学习与发射波形、空调响应及按键唤醒。`image_info` 的警告也需结合实机验收判断；构建与主机测试通过不代表这些实机功能已通过。
