# 仓库工作规范

## 项目结构

`main\` 存放 ESP8266 固件：`main.c` 负责启动与控制，`sensor.c`、`ir.c`、`rules.c` 和 `portal.c` 分别处理测温、红外、规则和配置热点；控制页内嵌于 `page.h`，没有独立资源目录。`tests\` 包含规则测试和页面脚本检查。`tools\` 保存烧录工具及说明。硬件接线以 `ESP-12F硬件引脚与链路说明.md` 为准。

## 构建与测试

在仓库根目录使用 PowerShell：

```powershell
python build.py
& "D:\APPS\Espressif\tools\ninja\1.9.0\ninja.exe" -f tests\build.ninja -j 12
.\build_ascii\rules_test.exe
node --check tests\check_page.js
node tests\check_page.js
python flash.py --port COM3 --dry-run
```

`build.py` 使用 ESP8266 RTOS SDK 3.4 和 Ninja `-j 12`，临时映射空闲的 `Z:`，将固件写入 `build\auto\`；SDK 路径可通过 `IDF_PATH` 覆盖。规则测试检查阈值、回差与单次触发；页面检查验证脚本语法及 API 路径。运行 `git diff --check` 检查空白错误。

## 代码风格与测试范围

沿用现有 C 风格：四空格缩进、`snake_case` 函数和变量名、模块名与文件名对应。修改前阅读相关头文件、调用方和配置；只改当前任务所需代码。规则行为变更时扩展 `tests\rules_test.c`，页面变更时更新 `tests\check_page.js`。仓库未设覆盖率门槛或统一格式化工具。构建和主机测试通过后，仍须单独记录未完成的实机验证。

## 提交与 Pull Request

近期提交使用简短中文祈使描述，例如“发布本地版本并更新项目文档”；提交信息应说明实际改动。Pull Request 写明目的、涉及模块、验证命令与结果，并列出未验证的硬件功能；涉及控制页时附界面截图，涉及硬件时注明接线或日志依据。发布版本时同步检查 `README.md`、`CHANGELOG.md` 和 `RELEASE.md`。

## 配置与安全

将可提交的默认设置放在 `sdkconfig.defaults`；生成的 `sdkconfig`、`build\` 和 `build_ascii\` 不入库。ESP-12F 晶振与当前 Flash 频率均设为 26 MHz，但属于不同配置项。不得提交密钥或真实凭证；烧录参数与 NVS 数据保留方式见 `tools\README.md`。
