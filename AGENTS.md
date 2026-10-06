# 仓库工作规范

## 项目结构

`main\` 存放 ESP8266 固件：`main.c` 负责启动与控制，`sensor.c`、`ir.c`、`rules.c` 和 `portal.c` 分别处理测温、红外、规则和配置热点；`sleep_trace.c`、`startup_trace.c` 记录休眠与启动诊断，`noise_timer.c` 处理 RF 关闭时的噪声定时器。控制页内嵌于 `page.h`，没有独立资源目录。`components\esp_http_server\` 保存 SDK HTTP 组件的局部覆盖，`components\esp8266\` 复用 SDK 组件并接入构建目录中的休眠副本。`tests\` 包含规则、功耗、HTTP、串口选择和页面检查。`tools\` 保存烧录工具、SDK 定时器构建脚本及说明；不修改已安装 SDK。硬件接线以 [硬件说明](ESP-12F硬件引脚与链路说明.md) 为准。项目仅使用单手机配置，不涉及多客户端。

## 构建与测试

在仓库根目录使用 PowerShell：

```powershell
python build.py
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

以上命令逐条执行，失败时停止依赖步骤。`build.py` 使用 ESP8266 RTOS SDK 3.4 和 Ninja `-j 12`，临时映射空闲的 `Z:`，将固件写入 `build\auto\`；SDK 路径可通过 `IDF_PATH` 覆盖。规则测试检查阈值等号、首次满足、持续满足及禁用；主机测试使用实际源码与 mocks，覆盖 80/160 MHz、温度偏移及分辨率核验、每组 120 秒间隔、休眠诊断、网络/噪声定时器、软件/I2S 发送、清理失败及 NVS。功耗测试依赖本次构建生成的 SDK 副本，必须先构建。页面检查验证脚本、五个 API 路径及错误显示。dry-run 不访问串口。`git diff --check` 检查空白错误，不替代 Markdown 链接与结构检查。

## 代码风格与测试范围

沿用现有 C 风格：四空格缩进、`snake_case` 函数和变量名、模块名与文件名对应。函数名、变量名不超过 40 字符，单文件原则上不超过 4800 行。修改前阅读相关头文件、调用方和配置并搜索现有实现；只改当前任务所需代码。修复前先查看可用日志，缺少运行日志时明确记录。规则行为变更时扩展 `tests\rules_test.c`，页面变更时更新 `tests\check_page.js`；控制、传感器、红外和 HTTP 行为变更使用对应主机测试。仓库未设覆盖率门槛或统一格式化工具。构建和主机测试通过后，仍须单独记录未完成的实机验证。

## 提交与 Pull Request

近期提交使用简短中文祈使描述，例如“发布本地版本并更新项目文档”；提交信息应说明实际改动。Pull Request 写明目的、涉及模块、验证命令与结果，并列出未验证的硬件功能；涉及控制页时附界面截图，涉及硬件时注明接线或日志依据。版本、产物及验证结果集中记录在 [README 的本地发布](README.md#本地发布)，历史通过 Git 查询；不恢复已删除文档，不新增 Markdown。

## 配置与安全

将可提交的默认设置放在 `sdkconfig.defaults`；生成的 `sdkconfig`、`build\`、`build_ascii\` 和 Python 缓存不入库。defaults 不覆盖已有 `sdkconfig`，实际参数以生成配置为准。CPU 固定为 80 MHz（按配置重新构建可回退 160 MHz），ESP-12F 晶振与 Flash 频率各为 26 MHz，属于不同配置项；自动休眠需要 `CONFIG_PM_ENABLE=y`。不得提交密钥或真实凭证；烧录参数与 NVS 数据保留方式见 [工具说明](tools/README.md)。
