# 当前进度

日期：2026-09-05。状态仍为 **0.0.10 Software Release Candidate / Pre-Hardware-Validation**。
本轮修复生产指示灯初始化遗漏、空选校准启动顺序、校准 build capability/中心门禁、
ALIGN_START 同步大栈处理与通信任务栈预算。新增的运行时 C/Host 修改已登记 FCCG importer
归属；栈检查工具和运行时文档保存在 `tools/reference_overlays/`。

空选/OneFace/SixFace/两者的 capability 为 `0x01/03/05/07`；空选初始化与 RESET 均为
NONE identity READY，Required CALIBRATION_RESULT 保留。Alignment 完整 Process 与校准
solve 由 FlightTask 推进。SS0.5 GPIO6 / PA1 低电平点亮映射保持不变。

Release/Debug 栈检查覆盖全部静态任务，包含 Idle；溢出故障记录保存稳定任务身份、系统状态
及带有效标志的缓存 HWM。AIR M0、Maintenance/SSLOG 0.0、decoder 1.1 版本与 layout 不变。
本轮最终 pytest 318 passed，Host 67 executables / 12415 checks / 0 failures；
Release/Debug、Architecture、Power of Ten、-fanalyzer、Artifact 和 stack report 均通过。
完整 ELF 闭包及 RAM/stack 数值见根目录 `VALIDATION.md`。
仍需真实 SS0.5 连续运行、重复 AIR/Serial 命令、HWM/MSP、电气与日志验证。
外部参考固件、GSHC 和 FLP 保持只读；没有 commit/push/tag。

# 前轮进度（历史记录）

日期：2026-09-02

状态：**SilverStar 0.0.10 Software Release Candidate / Pre-Hardware-Validation**。
本轮完成SS0.5已验证板卡固定资源映射修复，没有创建Release或Tag、没有提交或推送，也
没有修改外部参考固件或SilverStar_FLP。当前`main`基准HEAD为
`533b4aa091d37bc6f6980a27f470e053fcbd49f5`；本轮变更仍在工作区中。

## 本轮完成

- 修复了已验证Board资源被CubeMX inventory扫描顺序覆盖的问题。SS0.5现在只从Board插件
  `connections.json`取得固定logical ID、`c_id`、索引和用途；`.ioc`与生成符号只负责解析、
  交叉验证物理alias，不再决定逻辑序号。
- SS0.5 GPIO固定映射已验证为：0 `RADIO_NSS`、1 `RADIO_RST`、2 `RADIO_BUSY`、
  3 `RADIO_DIO1`、4 `P_CONTROL1`、5 `P_CONTROL2`、6 `IMU_CAL_LED`、7 `GNSS_RST`、
  8 `GNSS_TIMEPULSE`。UART/SPI/ADC/TIME同样使用Board声明的稳定逻辑ID。
- 增加严格Platform Resource Closure Check：拒绝重复JSON key、重复固定物理alias、缺失alias、
  resource kind或生成符号漂移，以及Requirement→Assignment→Board logical ID→physical alias→
  generated symbol→最终C表不闭合；错误会报告逻辑ID、期望alias、实际符号和Board插件来源。
- 自定义CubeMX硬件保持原有manual/imported `logical_index`语义，不套用SS0.5固定映射。
- resource-binding fingerprint覆盖Board ID/版本/manifest hash、logical ID、physical alias、生成
  符号和renderer contract，并写入hardware-preparation与ownership元数据；变化会正确使工程
  进入Dirty/stale，而展示性provenance仍不参与generation fingerprint。

## 本轮实际验收摘要

- `python -m compileall -q src main.py tools`：通过。
- 完整`pytest`：298 passed in 577.04s（0:09:37）；固定资源focused suite为9 passed，最终组合
  mapping/lifecycle slice为15 passed。
- 新鲜SS0.5工程首轮生成518个文件，Source Graph为138个C源文件+1个ASM；二次生成added 0、
  modified 0、preserved 485，生成、重载和二次应用后均为Ready。
- `.ssdecoder`为103122 bytes，SHA-256
  `df885c2b48a62baa2cac15fb780797c1e90895d913d26a9ea2c462f701f9d657`；resource-binding
  fingerprint为`b8af03e219b3412f1f7d42331a954bb1f7533e092e474dddcd8e8af80343991d`。
- Release与Debug均通过：Release `text/data/bss=259408/1072/119064`，Debug为
  `275656/1072/119088`。
- Host Tests：56个可执行文件、9123项检查、0失败、8个compile-pass和16个预期拒绝；
  Architecture 255/255；Power of Ten 5895项；GCC `-fanalyzer`与Artifact Check均通过。
- Release产物：FLASH 260480/524288，main SRAM 77264/131072，CCMRAM 42872/65536，heap为0。

本轮没有改变AIR M0 wire、校准、GSHC、FLP、日志容器/decoder schema或多实例语义。真实GPIO
电气、I²C/PWM电气、烧录、HIL、第二硬件平台和飞行验证仍未完成。

## 上一轮完成：同型号多实例与最小故障切换

- 官方JY901B、NEO-M9N、SX1281插件各支持最多4个同型号实例；GUI可新增/删除实例，稳定
  Device Instance顺序形成默认备用顺序，显式Canonical Source/Source Override仍决定主源。
- Manifest以通用`instance_resource_binding`声明每实例静态资源结构、accessor、数量符号和
  有界runtime context；每个实例的UART/SPI/GPIO/IRQ/时间资源独立解析，独占资源不可复用。
- JY901B、M9N与SX1281驱动及SX1280 HAL已context化，mutable parser/FIFO/状态/缓存不再
  singleton；生成代码仍只编译一份驱动源码，通过静态instance facade分派。
- 所有IMU/GNSS实例持续写Native日志。IMU只在校准/对准前选择并随后锁定；GNSS按基础
  liveness单向切换；AIR仅因当前本地transport连续10次真实TX timeout单向切换。成功发送
  清零计数，备用耗尽后仍在每个正常周期重试最后source，不做单次无限重试。
- Source-change继续复用现有EVENT Record，仅增加可恢复的old/new/reason语义；AIR M0、维护
  0.0、SSLOG 0.0、Record ID/layout、`.ssdecoder`/Project Semantics 1.1均未升级。

## 上一轮实际验收摘要

- `python -m pytest -q`：289 passed in 524.38s（0:08:44）。
- `python -m compileall -q src main.py tools`：通过。
- 最终单实例与2×IMU+2×GNSS+2×Telemetry工程各生成518个文件；多实例Source Graph为
  138个C源文件+1个ASM。
- 多实例`.ssdecoder`：114272 bytes，SHA-256
  `cb735adfe49221ac61f3c3d35bd950668ab2c0f2634769222d98fdb91fb066c0`。
- 单实例/多实例Release与Debug均通过。Release多实例相对单实例增加592 bytes FLASH与
  14600 bytes data+bss；Debug增加1064 bytes FLASH与14600 bytes data+bss。
- Host Tests：56个可执行文件、9139项检查、0失败、8个compile-pass和16个预期拒绝；
  Architecture 255/255；Power of Ten 5895项；GCC `-fanalyzer`和Artifact Check均通过。
- 多实例Release产物：FLASH 261072/524288，main SRAM 91864/131072，CCMRAM
  42872/65536，heap为0。精确构建表和质量门禁见根目录`VALIDATION.md`。

## 只读参考

参考固件保持clean `main`：`cc0b377ded690556d037a412a55f87fe334c42d0`，snapshot digest
`7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`。导入器连续重建
结果确定，FCCG没有修改、格式化、构建、提交或推送该目录。

## 尚未完成

- 双IMU、双GNSS、双radio真实冗余硬件的电气、EMC、射频、HIL与飞行验证。
- I²C外部上拉及PWM波形、极性、安全电平的真实电气测试。
- 第二套真实硬件平台的双平台内部测试；当前合成H743 fixture不等于H7支持。
- 烧录、SD介质耐久、射频、执行器台架、HIL与飞行验证。
- 后续SilverStar_FLP：每次导入一个日志、严格匹配`.ssdecoder`、不兼容未发布旧日志，且
  离线算法比较不受机载算法清单限制。
