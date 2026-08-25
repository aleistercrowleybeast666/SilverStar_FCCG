# SilverStar_FCCG 当前进度

更新时间：2026-08-26（Asia/Shanghai）

状态：本轮“完成生成代码功能”修改已实现，完整 FCCG 回归、固件编译、静态规则和主机测试验收均已通过。reference firmware 与 reference GUI 始终只读。

## 本轮完成

- 正式区分 Raw/Data Capability 与 Qualified Capability；设备插件声明资格，Strategy 插件声明需求，Resolver 自动决定可用性，不按 JY901B 型号硬编码。
- JY901B 的磁场原始数据仍存在，但双矢量绝对参考资格不存在；六轴/九轴权威姿态与冲击检测资格也明确为不具备。
- 四种对准 Strategy 与三种着陆 Strategy 的可用矩阵、中文原因、GUI 禁用状态和测试已同步。
- 必选 Strategy 下拉框不再插入“请选择策略”；真实可选的 None 仅保留在可选槽位，不可用 Strategy/Board 以灰色显示。
- 新工程默认选择“自定义 STM32 硬件”，不再显示“尚未选择硬件配置”；手动自定义模式不显示“准备硬件文件”。
- 板卡硬件规划已移到后台线程；QRunnable 在完成信号派发后才释放，真实准备流程点击 0.001 秒返回、3.222 秒完成且 100% 后正常退出。
- Landing 采用一个共享 Common 和三个选择器；当前 reference 的集中式 `flight_landing.c` 没有被复制三份。
- 所有普通用户可见板名统一为 `SS0.5`，稳定内部 ID 和 `SILVERSTAR_0_5` 构建符号保留。
- 第四页改为“代码生成与构建”：正常区只保留生成/应用、打开 VS Code/工程、Arm GNU 与 Make；固件输出目录只有存在 ELF/HEX/BIN/MAP 时才可打开。
- 起飞点火与火工开伞均可独立取消：无起飞点火时按外部点火处理，START 合法且不生成 GPIO；无开伞输出时清空并禁用开伞模式，不会循环自动加回。
- 开伞模式参数由清单声明并生成 `project_flight_config.h`；默认阈值为 -2 m/s、45°、60 s，延时生成时转换为毫秒。
- AIR 紧凑 V0、维护 0.0、SSLOG0 作为独立协议配置；Native 日志按 Recordable 判断，Estimator=None 时 BARO_NATIVE 可用、BARO_MEASUREMENT 不可用。
- Core 通过清单 `strategy_sources` 在 KF6 估算器任务和独立纯 INS/不融合任务间选择；Estimator=None 的 Make/EIDE 源码图不含 KF6，也不依赖第一方 C 条件编译。
- 日志编辑改为信号快照 + 下一事件循环事务 + 增量控件更新，50 次连续信号压力测试通过。
- 硬件连接支持 UART/SPI/I2C/PWM 与 GPIO 电气/安全初值约束；“完成手动分配并检查”通过后保存指纹，相关配置改变即失效。
- 删除独立“构建发布版本”按钮；高级“验证构建”默认 Release。
- Make、VS Code 与 EIDE 默认 Release，同时保留 Debug；Release 为 `-O2 -g`，Debug 为 `-Og -g3 -gdwarf-2`，均不定义 `NDEBUG`。
- 普通工具状态仅显示 Arm GNU 与 Make；objcopy/size 从 Arm GNU 同目录推导，Host GCC 位于高级质量检查，静态分析复用 Arm GCC。
- EIDE 改为无 Pack 的一致状态：`deviceName: null`、`packDir: null`，Release 在前，workspace 根路径为 `.`。
- 重复应用按字节比较受管文件，不重写未变化内容、不清理 build，并保留 Make `.d` 依赖文件。

## 最终验收

默认工程：`tests/acceptance_generation_code_complete_20260825_v4/`（478 个文件）；不融合/无任务功率输出变体：`tests/acceptance_optional_external_ignition_20260825_v5/`（475 个文件）。

- Python：`compileall` 通过；严格插件目录 29 个；完整回归 111 passed in 419.12s。
- 默认 Release：text 241,584 / data 1,160 / bss 114,144；ELF 2,535,504；BIN 242,744 bytes。
- 默认 Debug：text 254,064 / data 1,160 / bss 114,152；ELF 3,862,348；BIN 255,224 bytes。
- Host Tests：50 executables，8,221 checks，0 failures。
- Architecture Check：186 checks，0 failures。
- Power of Ten：5,302 checks，87 个第一方 C 文件，1,955 个函数；违规 fixture 已验证会非零失败。
- Arm GCC `-fanalyzer`：独立 Release 目录全量重编通过；告警 fixture 已验证会在 warnings-as-errors 下失败。
- Artifact Check：默认 Release/Debug 均通过，heap symbols 为 0。
- 不融合变体：源码图只含 `APP/Src/estimator_task_none.c`；Release text 203,028 / data 1,160 / bss 96,104；Architecture 188/188、Power of Ten 5,124、Artifact Check 均通过，KF6 未进入工程。

## EIDE 实际状态

当前机器安装 VS Code 1.133.0 与 EIDE 3.27.2。当前启动器已使用 `Code.exe --new-window <绝对工作区路径>` 成功打开新生成且 Ready 的工作区，并观察到独立可见窗口。VS Code CLI 无法直接触发扩展命令，因此未声称 EIDE 原生 UI 编译通过；仍需手工确认 EIDE 工程树/include/target、选择 Release 并执行 EIDE Build。

## 当前限制

- 当前 Landing 三个选择器共享 reference 的集中式状态机，不是三套独立底层实现。
- 当前只正式支持 Arm GNU 固件编译和 STM32CubeMX 硬件提供器。
- 没有真正多 IMU、多 EKF、Guidance、Control、Control Allocation 或 PWM actuator。
- Power of Ten 和 `-fanalyzer` 都不是形式化证明或第三方安全认证。
- EIDE CLI 编译、硬件烧录、电气测试以及 FLP 导入 `.ssdecoder` 尚未完成。

## 工作区说明

保留当前所有修改，不要 reset/clean，也不要写入 reference firmware/GUI。后续继续时以 `VALIDATION.md` 和本文件为当前基线。
