# ESP-12F 空调温控

本工程使用 ESP8266 RTOS SDK 3.4，实现两组温度规则、红外学习与发送及手机配置页。GPIO4 接 DS18B20，GPIO5 接 HS0038B，GPIO14 驱动红外 LED；S1/GPIO12 控制配置热点，S2/GPIO13 暂停或恢复温控。项目使用单手机配置，不涉及多客户端。

当前本地版本为 **0.1G（2026-10-05）**。发布内容、产物和本轮验证见 [RELEASE.md](RELEASE.md)，历史版本见 [CHANGELOG.md](CHANGELOG.md)。接线见 [硬件说明](ESP-12F硬件引脚与链路说明.md)，开发约定见 [CLAUDE.md](CLAUDE.md) 和 [AGENTS.md](AGENTS.md)。

## 手机配置

1. 按 S1 开启热点，连接开放 Wi-Fi `空调智能温控`。未自动弹页时访问 `http://192.168.4.1`。
2. 设置两组规则的触发温度（−10～50 °C）、升温或降温方向，保存规则。
3. 点击对应组的“学习红外”，在 15 秒内按一次遥控器目标按键；学习成功后先用“测试发送”验证，再启用并保存规则。
4. 两组共用红外发送频率（36/38/40 kHz，默认 38 kHz）。修改后保存到 NVS，并影响所有已学习编码的后续发送。HS0038B 不能测出遥控器载波频率，需用目标空调验证兼容性。

页面每 2 秒刷新温度和电池电压。电压以 V 显示、保留两位小数，由 ADC 按 330 kΩ / 82 kΩ 分压换算，随测温周期采集；刷新页面不会增加采样频率。电压读取失败显示错误码，不影响温度控制；精度尚未实机校准。

## 运行行为

| 状态 | 测温与控制 | 指示灯 |
| --- | --- | --- |
| 开机、热点关闭 | 开机立即测温，之后每 30 秒测温并检查规则 | 熄灭 |
| 热点开启 | 每 2 秒测温并检查规则 | 每秒亮 500 ms |
| S2 暂停 | 不测温、不自动发送红外，允许自动 light sleep | 熄灭 |

S1 可提前关闭热点；红外学习或发送期间将关闭请求延后到红外空闲，再按 S1 可取消待处理请求。S2 暂停后，S1 唤醒并开热点，S2 唤醒恢复监测；红外忙碌或热点关闭失败时，S2 请求会报错，不进入暂停。DS18B20 转换期间的按键需等待约 750 ms 加一个 FreeRTOS tick 后处理；长按只产生一次操作。热点关闭失败会记录错误，保留状态供再次操作。

热点开启后，未访问控制页或操作配置 API 时，3 分钟后关闭；使用后从最后一次上述操作起空闲 10 分钟关闭。状态轮询、系统探测及后台请求不延长期限；红外忙碌时延后关闭。

首次有效温度读数只建立规则基线；成功触发后须反向回退 0.5 °C 才能再次触发。上电、S2 暂停后恢复、修改规则、重新学习编码或测温错误恢复时重新建立基线；正常自动休眠保留基线和触发状态。DS18B20 读取失败会暂停自动发送，并在页面和串口显示错误。30 秒采样可能漏掉两次采样之间的短暂越界。

红外学习按 10 μs 单位保存完整解调时序，最多 960 段、总时长不超过 750 ms。捕获使用 `esp_timer_get_time()` 计时，保存尾部空闲段；超限、无效波形或保存失败均报错，保留旧编码。I2S 载波仅在发送时运行，发送结束或失败后停止；清理失败会报错并阻止自动休眠。

## 休眠与供电

正常测温间隔和 S2 暂停使用 SDK 自动 light sleep。热点开启、1-Wire 通信、红外学习或发送期间保持唤醒。每次测温先检测 DS18B20 供电：独立供电、热点关闭且红外空闲时，GPIO4 切为输入，由板上 4.7 kΩ 上拉维持 DQ 高电平，转换等待允许休眠；读取前关闭自动休眠并恢复开漏输出。

转换等待保持 750 ms，并额外等待一个 tick 防止提前读取；不改变传感器分辨率。寄生供电时输出一次警告，保持唤醒等待，不提供强上拉支持。主任务每段阻塞等待最多 10 秒，用于限制 SDK 计时补偿范围，不改变测温周期；实际睡眠时长由 SDK 调度器决定。休眠配置失败后尝试关闭自动休眠并继续温控；若已启用的休眠无法关闭，则中止运行并报错。

电池端功耗测量、按键和连续运行验收见 [功耗验收](tests/功耗验收.md)。当前节电比例与续航尚未确认。

## 构建与烧录

在仓库根目录使用 PowerShell：

```powershell
python build.py
python flash.py --port COM3 --dry-run
```

构建脚本扫描 `main` 源文件，临时映射空闲的 `Z:`，使用 CMake 和 Ninja `-j 12`，产物位于 `build\auto\`。SDK 可通过 `IDF_PATH` 覆盖，工具路径见 [编译环境说明](ESP8266编译环境路径.md)。从其他目录运行时使用脚本的绝对路径。

`sdkconfig.defaults` 设置 CPU 160 MHz、晶振与 Flash 各 26 MHz、`CONFIG_PM_ENABLE=y`、HTTP 请求头上限 2048 字节和 URI 上限 1024 字节。已有 `sdkconfig` 不会被 defaults 覆盖，实际参数以构建生成的 `sdkconfig.h` 和 `flasher_args.json` 为准。

项目 `components\esp_http_server` 覆盖 SDK 的路由、解析和 socket 错误处理，其余实现、头文件及 Kconfig 继续使用指定 SDK。末尾 `*` 匹配剩余路径，`/generate_204_*` 探测重定向至控制页，`/mmtls/*` 的 GET/POST 返回 404。不支持的协议起始字节直接关闭连接，以 INFO 记录原因；HTTP 解析失败返回错误并关闭连接，收发错误保留真实 `errno`。

dry-run 只检查布局，不打开串口、不写 Flash。实际接线与烧录命令见 [工具说明](tools/README.md)；分段偏移以本次构建为准。完整 4 MB 镜像的未使用区域填 `0xFF`，整片写入会清除 NVS；保留规则和编码时使用分段烧录。

## 软件检查

以下命令逐条执行，成功后再执行下一条：

```powershell
New-Item -ItemType Directory -Force build_ascii | Out-Null
& "D:\APPS\Espressif\tools\ninja\1.9.0\ninja.exe" -f tests\build.ninja -j 12
.\build_ascii\rules_test.exe
python tests\test_power.py
python tests\test_portal.py
python -m unittest discover -s tests -p test_flash_port.py
node --check tests\check_page.js
node tests\check_page.js
python flash.py --port COM3 --dry-run
git diff --check
```

规则测试检查阈值、基线、回差和单次触发；功耗主机测试检查实际控制、传感器和红外代码的流程与错误处理；HTTP 主机测试检查路由、解析、请求体清理、超时与 socket 错误；串口测试检查自动选择条件；页面检查验证五个 API 路径、2 秒刷新、共享载波保存及温度/电池错误显示。

主机 tests 使用现有 GCC 和 SDK mocks，产物保存在 `build_ascii\`。这些测试不验证实际睡眠、电流、红外波形或手机弹页；本轮结果与硬件待验项见 [发布说明](RELEASE.md)。

## 清理

在 Windows PowerShell 5.1 中执行 `.\clean.ps1` 预览、`.\clean.ps1 -Apply -WhatIf` 模拟删除、`.\clean.ps1 -Apply` 实际清理。脚本可通过绝对路径从其他目录调用。

清理范围为 `build\s1_checkpoint`、`build\s1_build.log`、整个 `build_ascii`、根目录 Ninja 状态及 `main`、`components`、`tests` 中的 Python 缓存。保留 `build\auto`、其他检查点、`sdkconfig`、源码、测试、文档、CSV、工具和 `.git`。目标含 Git 跟踪文件或重解析点时停止；输出删除、跳过及失败统计。清理后需先重建 `build_ascii` 再运行规则测试。

## 串口与验证状态

使用 3.3 V USB-UART 接 P3-2（TXD）和 P3-4（GND），以 115200 baud 接收 UART0 固件日志。ROM 早期启动为 74880 baud，开头可能乱码。固件默认输出启动、规则、红外、热点、暂停及错误日志；普通测温为 DEBUG，默认不输出。

历史用户日志和反馈曾确认旧构建的 Android 自动弹页、红外学习保存及发送日志，不能代表 0.1G 已实机通过。本轮不烧录；当前固件仍需验证空调响应、载波、NVS 持久化、测温、唤醒、功耗和稳定性。
