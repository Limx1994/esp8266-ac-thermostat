# 审查问题修复记录

本文件保留当时修复及验证结果。1.0A 的最新软件检查见 [本地发布](../../Sof/README.md#本地发布)；2026-10-12 用户确认全部功能已实机验证通过。路径覆盖测试自该日起停用，以下既有统计仅供追溯。

已修复此前确认的 3 项 P2，仅修改 4 个现有文件，未改动生产业务逻辑或生产固定驱动配置。与审查快照逐文件比较，其他非构建输入无变化；原有工作区修改保留。

| 问题 | 修改 |
|---|---|
| 默认驱动评估仍链接生产库 | `wifi_driver_eval.py` 把选定 SDK 的 archive 同步到评估组件，并依据这些实际文件生成评估用 revision/hash pin。现有 archive 链接及 timer alias 共用该组件；检查实际 LINK_LIBRARIES 中的组件路径、core/pp alias，以及候选文件哈希。生产组件未修改。 |
| Ninja 忽略头文件修改 | `build.ninja` 使用 GCC `-MMD -MF` 并配置 Ninja `depfile`、`deps = gcc`。 |
| 功耗主机 mock 缺少 AP 配置接口 | `test_power.py` 补齐最小类型、接口与配置状态，加入信道变更成功、已经为 9、get 失败、set 失败四个实际控制循环场景。 |

`test_wifi_eval.py` 同步验证候选 archive 内容与 pin，覆盖错误链接来源及构建后候选文件被改动的拒绝路径。

验证结果：

- 固件 `python build.py`（脚本内部 Ninja `-j 12`） 通过，退出 0。
- 主机功耗测试通过，包括 28 组合及 SDK 定时器检查。
- 最终统一覆盖检查退出 0：22 项 Python 单测通过，11 个检查组全部通过，`gaps=[]`。
- 真实 Ninja fixture 首次构建和无改动增量通过；只给 fixture 头文件添加 `#error` 后立即重编译并失败；恢复头文件后构建与规则测试通过。
- 真实 CMake fixture 使用本地 SDK archive 作为选定来源，7 个 imported target 均指向评估组件且哈希与选定来源一致。为避免旧 CMake 对中文路径编码错误，使用临时 ASCII drive mapping，验证后已解除。
- `git diff --check` 通过。

第一次覆盖检查的所有组通过，但新增候选哈希错误分支未命中；补充注入场景后最终检查通过。CMake 探针最初发生中文路径编码导致的断言失败；使用项目现有 drive mapping 方式解决后通过，没有将失败当作成功。

证据：[覆盖报告](D:/空调温度/Sof/build/coverage/report.md)、[覆盖日志](D:/空调温度/Sof/build/repair_coverage.log)、[构建日志](D:/空调温度/Sof/build/repair_build.log)、[独立探针](D:/空调温度/审查报告/20261011/repair_validation/results.json)。

未执行远程候选下载及完整驱动评估构建，该次修复验证未烧录或独立验证实机行为；后续用户已确认全部功能实机通过。驱动修复已由离线入口测试及真实 CMake 来源/哈希探针验证；当时离线修复验证不包含实机性能测量。
