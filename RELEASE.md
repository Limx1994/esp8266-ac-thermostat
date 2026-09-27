# 0.1C 本地发布说明

日期：2026-09-27。此版本仅在本地记录与保存，尚未烧录或完成实机验收。

## 内容

- 延续 0.1B 的两组温度阈值规则、红外学习与测试发送、S1 配置热点和 S2 暂停控制的 light sleep；使用方法见 [README.md](README.md)。
- 将 UART0 固件日志和串口监视器统一为 115200 baud；烧录速率也是 115200 baud。ESP8266 ROM 的早期启动输出仍为 74880 baud。
- 更新构建产物、烧录偏移及验证范围的文档。

## 固件产物

使用 ESP8266 RTOS SDK 3.4，通过 `python build.py` 调用 Ninja `-j 12` 构建，目标为 4 MB Flash：

| 文件 | 用途或烧录偏移 | 文件大小 |
| --- | --- | ---: |
| `build\auto\bootloader\bootloader.bin` | bootloader，`0x0` | 10,096 字节 |
| `build\auto\partition_table\partition-table.bin` | partition table，`0x8000` | 3,072 字节 |
| `build\auto\ac_thermostat.bin` | 应用固件，`0x10000` | 508,864 字节 |
| `build\auto\full_flash.bin` | 从 `0x0` 开始的完整 4 MB Flash 镜像 | 4,194,304 字节 |
| `build\auto\full_flash.hex` | 同一 4 MB 镜像的 Intel HEX 文本格式 | 11,535,372 字节 |
| `build\auto\flasher_args.json` | 分段偏移及 Flash 参数 | 815 字节 |

`flasher_args.json` 指定 DIO、40 MHz、4 MB Flash；分段烧录时以其中的偏移为准。完整镜像的未使用区域填充 `0xFF`，整片写入会清除 NVS 中保存的规则和红外编码；保留数据时使用分段烧录。构建目录由 `.gitignore` 排除，不纳入本地 Git 提交。

## 已验证

- 6 份 Markdown 的空白、标题间距和本地链接 lint、`git diff --check`、`build.py` 语法检查通过。
- `tests\build.ninja` 以 `-j 12` 构建规则测试，`build_ascii\rules_test.exe` 输出 `rules_test: all cases passed`。
- `node --check tests\check_page.js` 与 `node tests\check_page.js` 通过；控制页脚本和四个 API 路径检查通过。
- `python build.py` 以 Ninja `-j 12` 构建通过；产物大小与上表一致，完整 BIN 在指定偏移与三个分段文件逐字节一致，生成配置中的烧录、监视器及 UART0 固件日志速率均为 115200 baud，`Z:` 已解除映射。

## 未验证

当前无接入的 ESP-12F 设备，尚未验证烧录、UART0 实际日志、Wi-Fi 自动弹页、DS18B20 测温、NVS 重启持久化、两组红外编码学习与发射波形、空调响应及按键唤醒。构建与主机测试通过不代表这些实机功能已通过。
