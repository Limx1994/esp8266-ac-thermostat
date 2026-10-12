# 关键路径矩阵

历史快照：保留原始统计与当时结论。自 2026-10-12 起不执行路径覆盖测试，不重新生成报告或路径矩阵，本文件不作为 1.0A 验收要求。最新状态见 [本地发布](../../../Sof/README.md#本地发布)；用户已确认全部功能实机验证通过。

每行代表一组有实际断言的场景，不代表所有可能路径均已覆盖。

| 路径组 | 输入/故障 | 断言 | 依据 |
|---|---|---|---|
| 规则/趋势 | 等号、禁用、首次满足、两组计时、噪声/尖峰、速度饱和、回绕 | 匹配结果、独立成功时间、120～600 秒间隔 | tests/rules_test.c；tests/test_power.py CONTROL |
| 传感器/ADC | CRC/无设备、12 位修正、校准正负舍入、清理失败、ADC越界 | 失败不发布有效温度；校准与规则共享结果 | tests/test_power.py SENSOR/CONTROL |
| 红外学习/NVS | 采集超时、溢出、错误段、set/commit/readback失败、损坏编码 | 错误上报、旧 RAM 编码保持、成功断电模拟重载一致 | tests/test_power.py IR |
| 红外发送 | I2S/软件发送、36/38/40kHz、NMI延迟、计数回绕、清理失败 | 包络边沿、返回错误、休眠锁/资源释放和重试 | tests/test_power.py IR |
| 按键/休眠 | S1/S2、忙碌延后、长按、PM失败、定时器暂停/恢复 | 状态转换、采样继续、降级、保留真实定时期限 | tests/test_power.py CONTROL/TRACE/SDK checks |
| 热点/DNS/API | 超时、DNS非法/A/AAAA查询、资源失败、分片JSON、非法参数与动作失败 | 状态码、槽位转换、动作计数、RF/socket清理 | tests/test_portal.py TEST |
| HTTP | 长URI/header、非法协议、截断POST、chunk、socket errno、分配失败、unrecv过长 | 一次错误回复、连接清理、分块内容、截断不破坏状态、重试注册 | tests/test_portal.py WIRE |
| 页面 | 温度空值/非数、保存/发送/学习、错误状态、网络失败、低电边界 | 请求参数、阻止非法提交、提示内容与恢复 | tests/check_page.js |
| 工具/产物 | 布局缺失/越界/重叠、HEX校验、COM歧义、构建失败、ELF布局变化 | 拒绝非法输入、释放映射、SDK保护、真实BIN/HEX一致 | tests/test_tools.py；tests/test_flash_port.py；run_coverage.py |
| 启动跟踪 | PHY范围内/外UART和RF调用、RF错误返回 | 原调用次数、返回值、日志范围与标记恢复 | tests/startup_test.c |
