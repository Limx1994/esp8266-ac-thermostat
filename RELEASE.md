# 0.1G 本地发布说明

日期：2026-10-05。此版本在本地保存 0.1F 之后的既有项目改动并更新全部 Markdown；本轮没有追加业务代码修改，不推送、不烧录。

## 发布内容

- 温控与功耗：热点关闭每 30 秒、开启每 2 秒测温；正常间隔及 S2 暂停使用自动 light sleep。独立供电 DS18B20 转换期间允许休眠，保留 750 ms 加一个 tick 的等待；测温错误停止发送，正常休眠保留规则状态。
- 热点与按键：未使用 3 分钟、使用后空闲 10 分钟关闭；轮询及后台探测不延长期限。S1 可提前关闭，红外忙碌时延后处理并允许取消；S2 暂停后由 S1/S2 恢复。
- 红外：捕获使用微秒计时并补齐尾部空闲段；两组共用 36/38/40 kHz 载波，默认 38 kHz，单独保存到 NVS。I2S 仅在发送时运行，清理失败会阻止自动休眠。
- 页面：增加电池电压、共享载波选项和按钮按下反馈，每 2 秒刷新；读取及保存失败明确显示错误。
- HTTP：项目内覆盖 SDK 路由、解析和 socket 错误处理，支持探测路径、后台请求及长 URI/请求头；不支持的协议起始直接关闭，HTTP 解析失败回复错误后关闭，保留真实 `errno`。
- 工具与测试：保存现有自动串口选择、清理脚本和功耗/HTTP/串口主机测试；整理接线、开发、构建、烧录、功耗及第三方工具说明。

使用方法见 [README](README.md)，历史记录见 [CHANGELOG](CHANGELOG.md)，实机验收见 [功耗验收](tests/功耗验收.md)。

## 接口与兼容性

`GET /api/status` 增加 `batteryMv`、`batteryValid`、`batteryError` 和共用 `carrier`；`POST /api/carrier` 接收 `{"carrier":36}`、38 或 40；`POST /api/learn` 仅需 `{"slot":1}` 或 2。两组发送统一使用当前共享载波。规则和红外编码 blob 布局沿用原有格式；旧 NVS 没有共用载波键时使用 38 kHz，需要不同频率时在页面重新选择。

完整镜像整片写入会清除规则、编码及载波设置。分段烧录只保留未覆盖的 NVS 区域；烧录方法见 [工具说明](tools/README.md)。本项目使用单手机配置，不涉及多客户端。

## 固件产物

本轮 `python build.py` 使用 ESP8266 RTOS SDK 3.4、Xtensa GCC 8.4.0 和 Ninja `-j 12` 增量构建。Flash 为 DIO、26 MHz、4 MB；CPU 为 160 MHz，晶振另设为 26 MHz，自动休眠已启用。生成配置确认 HTTP 请求头上限 2048 字节、URI 上限 1024 字节。

| 文件（相对项目根目录） | 用途或偏移 | 大小（字节） |
| --- | --- | ---: |
| `build\auto\bootloader\bootloader.bin` | bootloader，`0x0` | 9,984 |
| `build\auto\partition_table\partition-table.bin` | partition table，`0x8000` | 3,072 |
| `build\auto\ac_thermostat.bin` | 应用，`0x10000` | 514,848 |
| `build\auto\full_flash.bin` | 从 `0x0` 开始的完整 4 MB 镜像 | 4,194,304 |
| `build\auto\full_flash.hex` | 同一镜像的 Intel HEX | 11,535,372 |
| `build\auto\flasher_args.json` | 分段布局及 Flash 参数 | 815 |

SHA256（文件均位于 `build\auto\`）：

| 文件 | SHA256 |
| --- | --- |
| `bootloader\bootloader.bin` | `ecdb88728ed8d851731066c50fc668edb295221b0ac0eacc52315e78bd408883` |
| `partition_table\partition-table.bin` | `5d1dbc1e3c50d7bc93b123215900b57fdfda24131e76da03999a54fe9b554ec3` |
| `ac_thermostat.bin` | `a13dee082f755b588970c6c2f744ac4e9c54eb7d7d1878739bfdbfdece3b1367` |
| `full_flash.bin` | `a00b9b7a4da19263c2b86dbef4ec1d6b809ee3c1bef5a2cdb235f6d5b43a3026` |
| `full_flash.hex` | `5314775aa4d7b6725798d1301f64d92ea745692a129cb7d22087e391b17bb159` |
| `flasher_args.json` | `4e5fa5bf7fb2b043f552875f746925d0e3c1600a4fdffd2fca2010c8fc155f13` |

完整 BIN 的三个分段逐字节与原文件一致，其他区域均为 `0xFF`；HEX 的记录校验和、覆盖字节数及重建内容均与 BIN 一致。构建结束后 `Z:` 已解除映射。构建产物不纳入 Git；0.1G 是文档发布编号，本轮 SDK 自动推导的 project version 为 `61c2d49-dirty`，未修改固件版本配置。

## 本轮软件验证

以下项目于 2026-10-05 执行；Markdown 与空白检查在最终文档完成后通过。

| 检查 | 命令或方法 | 结果 |
| --- | --- | --- |
| 固件构建 | `python build.py`，Ninja `-j 12` | 通过，增量构建 |
| 规则单元测试 | Ninja `-f tests\build.ninja -j 12` 后运行 `build_ascii\rules_test.exe` | 全部用例通过 |
| 功耗主机测试 | `python tests\test_power.py` | control、sensor、IR 三组通过 |
| HTTP 主机测试 | `python tests\test_portal.py` | portal、HTTP 两组通过 |
| 串口选择单元测试 | `python -m unittest discover -s tests -p test_flash_port.py` | 4 项通过 |
| 页面语法与行为 | `node --check tests\check_page.js`、`node tests\check_page.js` | 通过，覆盖五个 API、刷新及错误显示 |
| 烧录冒烟预检 | `python flash.py --port COM3 --dry-run` | 三段容量及 4 KiB sector 检查通过，未访问串口 |
| 产物一致性 | 核对生成配置、大小、SHA256、BIN 分段/填充、HEX 校验和及内容 | 通过 |
| esptool | 本地版本、文件 SHA256、应用 `image_info` | 版本与已有记录一致，镜像 checksum 有效；见下方警告 |
| 清理脚本冒烟 | `.\clean.ps1`、`.\clean.ps1 -Apply -WhatIf` | 通过，各跳过 6 个目标，删除 0 个文件，失败 0 次 |
| Markdown lint | 全部 10 个项目 Markdown 的本地链接、锚点、标题、表格及代码块检查 | 通过，37 个本地链接/锚点；修正一处标题前空行 |
| 空白检查 | `git diff --check`、暂存后 `git diff --cached --check` | 通过 |

仓库没有统一 lint 工具，本轮使用内存检查完成 Markdown lint，不新增依赖；主机 C 测试使用现有脚本的警告检查。测试使用 mocks，不验证 ESP8266 实际时序或电流。dry-run 自身不检查工具文件，本轮另行核对了 esptool。

构建出现 SDK `pkg_resources` 弃用提示及 Perl 未找到提示；构建退出码为 0，依赖检查通过。`image_info` 报告两个 `Suspicious segment`（地址 `0x40210010`、`0x40273ab8`），checksum 为 `20 (valid)`；警告尚未通过本次实机启动验证，不据此认定固件已可正常运行。

## 实机限制与本地保存范围

历史用户日志及反馈曾确认旧构建的 Android 弹页、红外学习保存及发送日志。本轮仅找到构建日志，没有 0.1G 实机运行日志，也没有烧录；以下均未验证：当前固件启动、协议处理后的手机弹页、目标空调响应、红外载波及波形、NVS 重启持久化、DS18B20 转换休眠、按键唤醒、电池电压精度、整机电流和 24 小时稳定性。GPIO2 实际 LED 接线仍需核验，节电比例及续航不作结论。

本地提交包含已核对的源码、配置、测试、清理脚本与全部 Markdown，共 31 个文件；暂存清单及工作区内容一致，凭证模式检查未检出敏感信息。CSV、缓存、构建产物和来源/版本未确认的额外下载工具不提交；原文件保留。额外工具的本地识别结果见 [工具说明](tools/README.md#本地额外工具)。本次没有远程发布或创建 Git 标签。
