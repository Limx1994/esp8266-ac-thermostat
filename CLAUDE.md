# 项目工作约定

本项目是 ESP-12F 空调温控固件，使用 ESP8266 RTOS SDK 3.4。功能、接线和操作以 [README.md](README.md) 与 [ESP-12F硬件引脚与链路说明.md](ESP-12F硬件引脚与链路说明.md) 为准；本机工具路径见 [ESP8266编译环境路径.md](ESP8266编译环境路径.md)。

## 修改范围

- 修改前阅读目标文件及其调用关系，沿用现有 C 代码风格，只改与任务直接相关的内容。
- GPIO4 为 DS18B20，GPIO5 为红外接收，GPIO14 为红外发射，GPIO12、GPIO13 分别为 S1、S2；改变引脚用途前须核对硬件文档。
- 两组规则与红外编码分别保存到 NVS。首次有效读数满足阈值即发送；持续满足时，每组距离上次成功自动发送至少 120 秒才再次发送，不使用回差或单次跨越触发。
- S2 关闭热点并进入休眠温控，不暂停采温。正常休眠、S2、规则或编码变更及测温失败不清空成功发送间隔；测温失败阻止本次发送，恢复后重新判断条件。
- 两组共用 36/38/40 kHz 载波并持久化。AP 开启使用 I2S WS + FRC1，关闭使用 GPIO14 软件载波；软件整帧保护最多 750 ms，保留 NMI 看门狗，迟到超过 5 μs 报错。清理失败保留休眠锁，不能把流程完成当作空调接收成功。
- 热点关闭每 30 秒测温，开启每 2 秒；未使用 3 分钟、使用后空闲 10 分钟关闭。状态轮询及后台探测不延长超时。项目仅使用单手机配置，不涉及多客户端。
- 修复故障前先检查可用日志；没有运行日志时明确记录这一限制，不用构建成功代替实机结论。

## 构建与验证

- 在 Windows 上优先使用 PowerShell。运行 `python build.py` 构建；脚本临时映射空闲的 `Z:`，避免 SDK 处理中文工程路径时出错，产物位于 `build\auto\`。
- 脚本使用本机 SDK 默认路径，也接受环境变量 `IDF_PATH`；路径见编译环境文档。所有 Ninja 编译至少使用 `-j 12`。
- `flash.py` 默认烧录速率为 230400 baud，可用 `--baud 115200` 降速；UART0 固件日志和串口监视器为 115200 baud，由 `sdkconfig.defaults` 配置。本地生成的 `sdkconfig` 不纳入 Git。
- 完整验证命令见 [README 的软件检查](README.md#软件检查)。规则测试使用 `tests\build.ninja`；主机行为测试为 `tests\test_power.py`、`tests\test_portal.py`；串口测试使用 `python -m unittest discover -s tests -p test_flash_port.py`；控制页检查为 `tests\check_page.js`。清理后先创建 `build_ascii` 输出目录。
- 烧录布局使用 `python flash.py --port COM3 --dry-run` 预检，不访问串口。不传 `--port` 时，仅在系统恰有 COM1 和另一个串口时选择后者，其他情况明确报错。
- 自动休眠需启用 `CONFIG_PM_ENABLE`；CPU 保持 160 MHz，晶振与 Flash 各 26 MHz。HTTP 请求头与 URI 上限分别为 2048、1024 字节。defaults 不覆盖已有 `sdkconfig`，须核对生成配置。
- 无实机时，红外波形、空调响应、Wi-Fi 弹页、传感器和按键唤醒均须标为未验证。

## 发布

- 当前版本、改动摘要、产物校验及验证结果统一记录在 [README 的本地发布](README.md#本地发布)，历史版本通过 `git log` 查询。发布前核对文档与实际产物，保留实机待验项；不新增或恢复独立发布 Markdown。烧录命令见 [工具说明](tools/README.md)。
- `build\`、`build_ascii\` 等构建产物不纳入 Git；提交前核对暂存清单与敏感信息。完整镜像会覆盖 NVS，保留数据时使用分段烧录。
- `clean.ps1` 默认仅预览，`-Apply -WhatIf` 模拟删除，`-Apply` 实际清理；保留当前固件，目标含跟踪文件或重解析点时停止。用途未确认的 CSV、二进制及缓存不得混入发布提交。
