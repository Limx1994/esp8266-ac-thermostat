# 0.1B 本地发布说明

日期：2026-09-27。此版本仅在本地记录与保存，尚未烧录或完成实机验收。

## 内容

- 延续两组温度阈值规则、红外学习与测试发送、S1 配置热点和 S2 暂停控制的 light sleep；使用方法见 [README.md](README.md)。
- 增加自动扫描源文件的 `build.py`，生成分段固件及完整的 4 MB BIN、Intel HEX 镜像。
- 补齐 UART0 上的启动配置、测温、规则触发与保存、红外学习与发送、热点及休眠状态日志。

## 固件产物

使用 ESP8266 RTOS SDK 3.4，通过 `python build.py` 调用 Ninja `-j 12` 构建，目标为 4 MB Flash：

| 文件 | 烧录地址 | 大小 |
| --- | --- | ---: |
| `build\auto\bootloader\bootloader.bin` | `0x0` | 9,968 字节 |
| `build\auto\partition_table\partition-table.bin` | `0x8000` | 3,072 字节 |
| `build\auto\ac_thermostat.bin` | `0x10000` | 508,864 字节 |
| `build\auto\full_flash.bin` | `0x0` | 4,194,304 字节 |
| `build\auto\full_flash.hex` | 按 Intel HEX 记录地址 | 11,535,372 字节 |

完整镜像的未使用区域填充 `0xFF`，整片写入会清除 NVS 中保存的规则和红外编码；保留数据时使用分段烧录。构建目录由 `.gitignore` 排除，不纳入本地 Git 提交。

## 已验证

- `git diff --check`、`build.py` 语法检查及 `node --check tests\check_page.js` 通过。
- `tests\build.ninja` 以 `-j 12` 编译规则测试，`build_ascii\rules_test.exe` 运行并输出 `rules_test: all cases passed`。
- `node tests\check_page.js` 通过，控制页脚本和四个 API 路径检查通过。
- `python build.py` 的 12 路增量构建通过；完整 BIN 长度为 4 MB，分段镜像位于 `flasher_args.json` 指定偏移，HEX 所有记录校验和有效，`Z:` 已解除映射。

## 未验证

当前无接入的 ESP-12F 设备，尚未验证烧录、UART0 实际日志、Wi-Fi 自动弹页、DS18B20 测温、NVS 重启持久化、两组红外编码学习与发射波形、空调响应及按键唤醒。构建与主机测试通过不代表这些实机功能已通过。
