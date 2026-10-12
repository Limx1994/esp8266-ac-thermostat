# 软件覆盖验收报告

历史快照：保留原始统计与当时结论。自 2026-10-12 起不执行路径覆盖测试，不重新生成报告或路径矩阵，本文件不作为 1.0A 验收要求。最新状态见 [本地发布](../../../Sof/README.md#本地发布)；用户已确认全部功能实机验证通过。

覆盖缺口存在时状态为未完成；通过测试不表示全覆盖。
C 行/函数按源码位置合并；分支按各编译变体分别计数，汇总为变体机会总数，不能视为去重语义分支覆盖率。
SDK、第三方工具及测试源码不计入业务覆盖率。未插桩源码单列，不从验收范围删除。

| 模块 | 行命中/总数 | 函数命中/总数 | 分支命中/变体总数 |
|---|---:|---:|---:|
| components/esp_http_server/httpd_main.c | 203/203 | 13/13 | 135/135 |
| components/esp_http_server/httpd_parse.c | 437/437 | 25/25 | 185/185 |
| components/esp_http_server/httpd_txrx.c | 286/286 | 23/23 | 154/154 |
| components/esp_http_server/httpd_uri.c | 114/114 | 8/8 | 231/231 |
| main/ir.c | 未插桩 | 未插桩 | 未插桩 |
| main/main.c | 未插桩 | 未插桩 | 未插桩 |
| main/noise_timer.c | 未插桩 | 未插桩 | 未插桩 |
| main/portal.c | 326/326 | 25/25 | 446/446 |
| main/rules.c | 67/67 | 5/5 | 58/58 |
| main/sensor.c | 未插桩 | 未插桩 | 未插桩 |
| main/sleep_trace.c | 未插桩 | 未插桩 | 未插桩 |
| main/startup_trace.c | 19/19 | 3/3 | 8/8 |
| tools/dhcps_arp.inc | 2/2 | 1/1 | 0/0 |
| tools/dhcps_trace.inc | 103/103 | 7/7 | 90/90 |
| tools/dhcps_wifi.inc | 55/55 | 5/5 | 82/82 |
| tools/lwip_timers.inc | 未插桩 | 未插桩 | 未插桩 |
| 已插桩 C 总计 | 1612/1612 | 115/115 | 1389/1389 |

## 相同 gcov 图结构汇总

仅将函数块数、源行 block IDs 和全部分支边结构完全相同的图汇总；用于识别重复测量，不代替逐配置验收或语义路径证明。原始分母和缺口保留。

| 模块 | 图结构数 | 汇总命中/总数 |
|---|---:|---:|
| components/esp_http_server/httpd_main.c | 3 | 135/135 |
| components/esp_http_server/httpd_parse.c | 1 | 185/185 |
| components/esp_http_server/httpd_txrx.c | 1 | 154/154 |
| components/esp_http_server/httpd_uri.c | 1 | 77/77 |
| main/portal.c | 2 | 446/446 |
| main/rules.c | 1 | 58/58 |
| main/startup_trace.c | 1 | 8/8 |
| tools/dhcps_arp.inc | 1 | 0/0 |
| tools/dhcps_trace.inc | 1 | 90/90 |
| tools/dhcps_wifi.inc | 1 | 82/82 |

## Python

| 模块 | 行命中/总数 | 分支命中/总数 |
|---|---:|---:|
| build.py | 134/134 | 44/44 |
| flash.py | 168/168 | 70/70 |
| tools\expose_timers.py | 51/51 | 16/16 |
| tools\wifi_driver_eval.py | 169/169 | 60/60 |

页面 V8：函数 12/12；块范围 121/121。
V8 块范围不是 GCC 分支或源码行指标；偏移针对 page.h 解码后的 script（UTF-16）。

## 执行结果

检查组：通过 10，失败 1，跳过 0。
详情见 results.json；单测数量见执行日志。

验收状态：未完成；覆盖缺口模块 6。
未执行实机验收 6 类：波形、真实休眠/功耗、温度准确度、手机弹页、ADC 多电压点、24 小时运行；本次范围仅软件。

## 缺口位置与处理

- main/ir.c：现有主机测试未编译该源文件；需增加实际源码 mock harness；未命中行：全部；分支/范围见 gaps.json。
- main/main.c：现有主机测试未编译该源文件；需增加实际源码 mock harness；未命中行：全部；分支/范围见 gaps.json。
- main/noise_timer.c：现有主机测试未编译该源文件；需增加实际源码 mock harness；未命中行：全部；分支/范围见 gaps.json。
- main/sensor.c：现有主机测试未编译该源文件；需增加实际源码 mock harness；未命中行：全部；分支/范围见 gaps.json。
- main/sleep_trace.c：现有主机测试未编译该源文件；需增加实际源码 mock harness；未命中行：全部；分支/范围见 gaps.json。
- tools/lwip_timers.inc：现有主机测试未编译该源文件；需增加实际源码 mock harness；未命中行：全部；分支/范围见 gaps.json。

## 修复与验证边界

- httpd_txrx.c：unrecv 使用截断后的长度复制；过长输入先复现 pending_len 被覆盖，再修复并回归。
- httpd_uri.c：strdup 分配失败后将已释放槽位置空；先复现悬空槽位，再修复并验证重新注册/注销。
- httpd_parse.c：按主版本拒绝非 HTTP/1.x，修复 2.1 被放行；保留 1.0 和同主版本兼容。日志见 version_repro.log 和 branch_http.log。
- portal.c：部分启动状态再次 start 返回 INVALID_STATE；RF/Wi-Fi 停止后独立清理 noise/network 定时器，避免首个错误跳过第二组清理。日志见 portal_cleanup_repro.log、portal_pause_repro.log 和 portal_cleanup_fixed.log。
- ir.c：发送脚初始化为低电平失败时立即返回错误，避免忽略 GPIO 故障；10 个初始化步骤独立注入。日志见 ir_init_repro.log 和 ir_init_fixed.log。
- main.c：关闭热点请求仅在 portal_stop 成功后清除，首次停止失败后仍会重试。日志见 control_stop_repro.log 和 control_stop_fixed.log。
- 复现和修复日志分别为 unrecv_repro.log/unrecv_fixed.log、uri_alloc_repro.log/uri_alloc_fixed.log。
- 本轮固件构建日志见 ../coverage_fix/build.log；真实镜像布局、HEX校验及生成配置由本次运行重新验证，哈希见 products.json。
- 关键路径矩阵见 path_matrix.md。所有未命中分支均保留，未自动豁免；不可达判定需逐项源码证明。
- tools/*.cmake 和组件 CMakeLists 由真实固件构建验证，无行/分支插桩；clean.ps1 不在本次构建/烧录测试范围。
- 主机 GPIO/寄存器、任务与网络均为 mocks；代码覆盖不证明芯片时序、真实并发或电气特性。
- HTTP 发送返回零字节时立即报错，避免无进展循环；复现及修复日志见 zero_send_repro.log/zero_send_fixed.log。
- URI 缺少路径字段时 default 可达，已有失败返回和无发送断言；已删除此前错误的不可达说明。
- 主机临界区及核心线程锁 assert 保留在测试辅助函数中；SDK 错误检查仍计入自有源码原始分支，未自动排除。
