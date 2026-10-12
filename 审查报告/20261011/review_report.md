# 工程审查报告

审查日期：2026-10-12。审查对象：`D:\空调温度` 当前工作区。此次仅审查；未修复业务代码、测试或配置。工作区已有未提交修改，审查对象是当前工作区，并非仅 HEAD；本轮不覆盖这些修改。

## 后续状态 · 2026-10-12

本报告正文保留审查时的事实和失败证据，不作为当前工作区的最终验证结果。原 3 项 P2 已完成后续修复，见 [修复记录](repair_report.md)；1.0A 的本轮检查结果见 [本地发布](../../Sof/README.md#本地发布)。用户已于 2026-10-12 确认全部功能实机验证通过。

路径覆盖测试自 2026-10-12 起停用。正文中的重跑覆盖建议和覆盖失败描述仅属于历史审查上下文，不作为当前发布要求；原始证据不改写。

## 裁决摘要

确认 3 项 P2：默认 Wi-Fi 驱动评估的候选库未进入实际链接；Ninja 规则测试遗漏头文件依赖；新增 AP 配置调用缺少对应主机 mock，导致功耗测试无法编译。未确认达到准入标准的性能问题或死代码问题；这不构成对所有运行场景无缺陷的保证。

有效问题均具备明确代码定位、常规触发路径及验证证据。专员已反证入口、动态引用、链接别名和测试范围，未将理论风险、泛化优化或通用安全建议纳入问题。

## 确认问题

- **[P2] 默认 Wi-Fi 驱动评估实际仍链接生产固定库**
  - **领域**：功能完整度
  - **位置**：`D:\空调温度\Sof\tools\wifi_driver_eval.py:112`
  - **函数/符号**：`main`；7 个 archive target 的 `IMPORTED_LOCATION`；noise archive alias。
  - **触发条件**：满足工具现有 SDK、候选缓存或网络条件，执行默认 `python tools\wifi_driver_eval.py`，不加 `--latest`，进入实际 CMake 构建。
  - **实际影响**：默认候选为 `620605a`，但应用 archive 被改指向评估目录内复制的生产 `858c7c2` 库；报告不能证明默认候选驱动的实际表现。
  - **证据（代码调用链/引用分析）**：评估入口复制生产 `components` → 候选只安装到 shadow SDK → 组件包含本地 `driver.cmake` → 该文件第 29 行重写 7 个 `IMPORTED_LOCATION` 到生产组件 `lib`；noise 工具也由本地组件生成别名。评估入口的路径子串检查无法区分这两个同名库目录。
  - **验证结果**：真实 CMake configure 成功；7 个 imported library 路径均从候选 SDK 路径改为生产组件路径，版本记录为 `858c7c2eb9004691f2c736c64a23715f6ea900c4`。证据：[reproductions.json](D:/空调温度/审查报告/20261011/reproductions.json)、[configure.json](D:/空调温度/审查报告/20261011/driver_probe/configure.json)。候选路径使用占位探针，未下载、完整运行评估或烧录；结论限于确定的链接来源覆盖。
  - **交叉审查意见（其他专员的质询与复核结论）**：Bug 与功能专员分别核对调用链；性能专员要求 archive 和 noise alias 同源；死代码专员确认候选库仍有 ABI 分析用途，不能据此删除。生产固定库设计本身不列为问题；`--latest` 与生产固定版本相同，不泛化为版本错链。
  - **建议修复**：在评估入口让 archive 和 noise alias 统一使用所选候选来源，并核对实际链接路径及哈希与候选 revision；保留生产固定库选择行为。

- **[P2] Ninja 规则测试遗漏头文件依赖，增量运行旧测试**
  - **领域**：Bug
  - **位置**：`D:\空调温度\Sof\tests\build.ninja:2`
  - **函数/符号**：`cc` rule；`rules_test.o`；`rules_cases.h`；`rules.h`。
  - **触发条件**：按 README 首次构建成功后，仅修改 `rules_cases.h` 或 `rules.h`，再执行现有 Ninja 增量测试入口。
  - **实际影响**：头文件改动未触发重新编译，旧测试可执行文件仍返回成功；新接口或断言未被验证。
  - **证据（代码调用链/引用分析）**：`rules_test.c` 包含 `rules_cases.h`，后者包含 `rules.h`；构建图只登记 `.c`，既没有显式 header 依赖，也没有生成及消费 depfile。README 第 160–162 行使用增量入口，清理是独立操作。
  - **验证结果**：项目内独立 fixture 首次构建退出 0；只给 fixture 的 `rules_cases.h` 添加 `#error` 后，Ninja 仍输出 `no work to do` 并退出 0，旧测试退出 0；相同源码 fresh GCC 编译退出 1。证据：[after_header.json](D:/空调温度/审查报告/20261011/ninja_probe/after_header.json)、[stale_test.json](D:/空调温度/审查报告/20261011/ninja_probe/stale_test.json)、[fresh_compile.json](D:/空调温度/审查报告/20261011/ninja_probe/fresh_compile.json)。真实项目头文件未被修改。
  - **交叉审查意见（其他专员的质询与复核结论）**：Bug 与功能专员独立复现并确认；性能专员认可按依赖重建，未建议每次全量清理；死代码专员确认测试头被使用。`run_coverage.py` 的规则检查直接重新调用 GCC，不受该增量缺陷影响。
  - **建议修复**：沿现有 `cc` rule 生成并消费 header depfile，或显式列出相关头文件依赖；验证只改 header 能重建、无修改不重建。

- **[P2] 新增 AP 配置调用未同步 SDK mock，功耗测试无法编译**
  - **领域**：功能完整度
  - **位置**：`D:\空调温度\Sof\tests\test_power.py:28`；头文件生成位置 `D:\空调温度\Sof\tests\test_power.py:2956`
  - **函数/符号**：`SDK`、`HEADERS`、`COMMON`、`CONTROL`；`wifi_config_t`、`ESP_IF_WIFI_AP`、`esp_wifi_get_config`、`esp_wifi_set_config`。
  - **触发条件**：对当前源码执行现有 `test_power.py` 或由 `run_coverage.py` 调度该脚本。
  - **实际影响**：首个 CONTROL 组合编译失败，功耗回归组停止，统一覆盖验收退出 1。当前固件在真实 SDK 下构建通过；此问题不证明生产 AP 行为错误。
  - **证据（代码调用链/引用分析）**：当前 `main.c:621–625` 调用 AP 配置接口 → 主机测试包含实际 `main.c` → 测试生成的 `esp_wifi.h` 只包含 `sdk_mock.h` → `SDK` 与 harness 未提供所需类型、枚举及接口 → GCC 报未知类型、未定义枚举、隐式函数声明。
  - **验证结果**：统一覆盖检查真实退出 1，日志记录上述编译错误；Bug 专员原样生成当前 SDK/COMMON/CONTROL 并独立 `gcc -fsyntax-only`，同样退出 1。证据：[coverage_run.log](D:/空调温度/审查报告/20261011/coverage_run.log)、[control_mock_repro.json](D:/空调温度/审查报告/20261011/bug_recovery/control_mock_repro.json)、[results.json](D:/空调温度/审查报告/20261011/coverage_snapshot/results.json)。未修改测试以掩盖失败。
  - **交叉审查意见（其他专员的质询与复核结论）**：功能专员核对真实 SDK 接口及测试调用链，认可 Bug 专员独立复现；性能专员限定为主机 mock 回归，无生产性能证据；死代码专员确认生产调用与测试均有明确用途，不能删除来消除失败。
  - **建议修复**：按现有 mock 方式补全实际使用的最小 Wi-Fi 配置类型、枚举、get/set 接口及确定性状态；验证信道已为 9、修改成功及 get/set 失败反馈，随后重跑完整功耗组与覆盖检查。

## 当前验证结果

| 检查 | 结果 | 证据与边界 |
|---|---|---|
| 固件构建，12 并行 | 通过，退出 0 | `build.log`、`build_result.json`；不等同于实机验证 |
| Python 单测 | 22 项，0 失败、0 错误 | `coverage_snapshot/results.json` |
| 统一检查组 | 10 通过、1 失败、0 跳过 | 功耗 28 组合与 SDK 定时器组首 CONTROL 编译失败 |
| 当前覆盖验收 | 未通过，退出 1 | `coverage_result.json`；存在 6 个未形成有效覆盖的模块 |
| 清理脚本解析与 `-WhatIf` | 通过；实际删除 0 | 解析错误 0、跳过 7 个目标、失败 0；没有实际清理 |
| `git diff --check` | 通过 | `diff_check_result.json`；不证明功能正确 |

本轮其他通过组包括规则、启动诊断、热点与 HTTP、完整 HTTP 主循环、DHCP/ARP/WiFi、页面、烧录 dry-run、构建配置及 BIN/HEX。没有实际烧录。

覆盖输出将 `ir.c`、`main.c`、`noise_timer.c`、`sensor.c`、`sleep_trace.c`、`lwip_timers.inc` 列为 gaps。其自动 reason 提示“需增加 harness”，但现有 harness 实际存在；本轮功耗组首编译被阻断，未产出这些模块的有效覆盖，不能据此判定没有测试实现，也不能沿用旧覆盖通过结论。

## 范围、快照及边界

当前固定清单为 912 个文件：794 个 `Sof\build\auto` 构建产物、2 个 Python cache、116 个其他输入。新增审查证据目录不属于产品输入清单。生成物按来源、链接和接口核对；登记文件不等于逐文件语义审查。

| 批次 | 模块 | 角色重点 |
|---|---|---|
| A | main/rules/sensor/ir 与头文件 | 状态与调用链；采样/发送实际频率；需求闭环；回调和外部入口引用 |
| B | portal/page、HTTP 覆盖组件 | 请求与配置链；高频 I/O 和资源；页面/API 闭环；注册处理器引用 |
| C | noise/sleep/startup、SDK 网络与定时器覆盖 | 计时与返回分支；休眠/唤醒；配置生效；wrap/alias/链接引用 |
| D | build/flash/clean、驱动评估及 tools | 实际构建来源；资源及执行次数；工具闭环；CLI/动态入口 |
| E | tests、Ninja、coverage、C/JS/Python harness | 当前编译与断言；测试执行成本；增量/覆盖闭环；测试引用 |
| F | MD、Kconfig、CMake、sdkconfig、manifest | 实现与文档对照；配置影响；使用路径；保留用途 |
| G | PDF/BOM/CSV/ZIP、CAD/JPG/DXF、二进制库/工具 | 文本、单元格、目录及外部接口；专有内部结构和实机限制 |
| H | 构建产物及 cache | 记录来源与哈希，不作为独立手写代码或自动死代码 |

原 1476 文件清单及部分审查存档后来消失，原因无法确认。保留的旧 `main.c` 哈希与当前不同；另 4 个保留源文件哈希一致，不能扩展为全项目一致。当前报告采用重新固定的 912 文件快照和当前复核，不声称恢复了原清单。旧构建、覆盖全部通过不能代表当前代码。

附件当前提取记录见 `completeness_attachments_current.json`：PDF 文本、BOM 单元格、两个 CSV 数据及 ZIP 成员目录读取成功并与当前 baseline 哈希一致。PDF提取工具出现 startxref/Object Streams 修复提示，未做全页视觉检查。文本提取不证明图形、电气连接或电源性能；历史波形不代表当前固件实测。CAD 专有二进制、DXF 几何、JPG 视觉内容、archive/EXE 内部实现未进行完整语义审查。实机功耗、时序、射频、烧录行为未验证。

生产固定库、候选 ABI 输入、链接 wrap/alias、HTTP 注册回调、测试及硬件资料均有保留用途或明确审查边界，未因单次文本零命中认定为死代码。没有无法现实复现的性能建议进入确认问题。

## 完成记录

四角色逐文件台账均为 912 项，路径集合一致；可读业务代码、脚本、MD 与配置的 source_gaps 均为空，二进制及生成物限制保留。最终核对文件缺失 0，非构建输入哈希漂移 0；14 个构建产物因重新构建变化，台账保存 baseline/current 双哈希。

[逐文件台账](D:/空调温度/审查报告/20261011/coverage.csv)、[核对摘要](D:/空调温度/审查报告/20261011/coverage_summary.json)、[确认问题](D:/空调温度/审查报告/20261011/confirmed_issues.json) 已保存。Bug、性能、功能、死代码各自阅读范围及继承证据分别见对应角色 JSON；统计口径不同，不把登记项合并为全文语义阅读。

工具选择：原生 collaboration 用于独立委派与交叉质询；PowerShell、rg、项目现有 build/test 脚本及 GCC/CMake/Ninja 用于源码定位与验证；PDF、spreadsheet 技能用于现有附件的只读提取。已注册的 code_review MCP 仅提供 PR CI 查询，本次本地全项目审查无相应 PR，因此未调用；浏览器、外部连接器、写入工具不参与审查。

审查当时已完成至上述边界，3 项问题在当时尚未修复，覆盖失败证据保留。后续修复状态见本报告开头及修复记录。
