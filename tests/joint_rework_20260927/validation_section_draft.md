# Validation — 2026-09-27 joint navigation / ESKF15

本节记录本轮执行结果；后续历史章节保持当时语义。联合行为、数学、状态机与下一次台架计划见
[JOINT_REWORK_REPORT.md](JOINT_REWORK_REPORT.md)。精确执行日志及哈希位于
`tests/joint_rework_20260927/evidence_final/`，新驱动逐型号证据见
[SENSOR_LIBRARY_VALIDATION.md](docs/SENSOR_LIBRARY_VALIDATION.md)。

六配置最终固件门禁、三产品完整回归、五日志重算和目标计时工具补验已完成。
本节区分全量基线与最后修复补测，没有任何实机验证声明。

## 身份、实现与交付边界

- 起点 FCCG `d013ae10924a308e95478445f91c370601871f19`；配套 FLP `c4605f4`、GSHC `cbee51e`。
- FCCG/Platform 0.0.12、GSHC 0.0.3；FLP 0.0.5。Project format 12、decoder/semantics 1.2，
  新 decoder 的 FLP 最低版本为 0.0.5；ESKF15 revision 1、公共质量 revision 3，历史 KF6 revision 2 保留。
- 65 个 builtin packages，包括真实 ESKF15 与 26 条新增传感器型号/接口编译路径。
  三仓库 `docs/contracts/navigation_v1.json` byte-identical；35 个 ESKF 实参均由项目/manifest 产生。
- 新导航记录 0x21–0x27 与状态事件 0x2F；原 28 条记录布局及基础 AIR 9-byte 帧不变。
- SS_0_5_TEST_3 五份原始 BIN 与 HARDWARE 中 matching decoder 只读，六个 SHA256 保持不变。
  本轮所有固件构建在 FCCG `tests/` 内完成，没有改写用户测试固件目录。
- 用户后续授权三个仓库提交/推送，并取消关机。没有烧录、物理输出、tag、Release 或发布。

## 正式生成工程与全路径门禁

入口 `tools/validate_joint_navigation.py` 通过真实 FccgService 生成/校验工程；
`Gates_Run` 在同一已解析 source graph 执行 Release 和 Debug：

```text
mingw32-make -j4 SHELL=cmd.exe CONFIG=Release all stack-report memory-report artifact-check
mingw32-make -j4 SHELL=cmd.exe CONFIG=Release architecture-check power10-check static-analysis
mingw32-make -j4 SHELL=cmd.exe CONFIG=Debug all stack-report memory-report artifact-check
mingw32-make -j4 SHELL=cmd.exe CONFIG=Debug architecture-check power10-check static-analysis
mingw32-make -j4 SHELL=cmd.exe CONFIG=Release host-tests
```

工具链为 Arm GNU 14.3.Rel1 / MinGW Host GCC；没有变更全局 PATH、安装环境或扩大内存预算。
完整运行 `FinalMatrix_20260927_081706_010978` 与最终修复 `FinalDelta_20260927_085218_568926`
全部 exit 0；最终 source audit 对六配置的产品输入逐字核对，差异为 0。
Host 仅在生成配置选择日志时执行相关 codec/storage fixture；
关闭日志仍执行真正的 kernel、START、选源、故障和遥测检查，不虚构 logger mock 的使用。

以下是最终 linked ELF 的字节数；Flight/Test 分别生成和验证，资源相同。

| 配置 | Release Flash / main SRAM / CCM | Debug Flash / main SRAM / CCM |
|---|---:|---:|
| KF6 Flight/Test | 286184 / 101840 / 56216 | 303192 / 101864 / 56216 |
| ESKF15 Flight/Test | 272320 / 100440 / 65080 | 287888 / 100464 / 65080 |
| ESKF15 无日志 | 233444 / 68060 / 62008 | 249284 / 68100 / 62008 |
| Pure INS | 253592 / 82512 / 44800 | 268976 / 82536 / 44800 |

Flash/主 SRAM 物理/CCM 容量分别 524288/131072/65536 B；主 SRAM reviewed budget 102400 B。
最紧 CCM 余量 456 B；最紧 reviewed main-SRAM 余量 536 B。预算不变，runtime heap symbols 为 0。
ESKF Debug 配置/静态估计：Device 2048/1328、INS 3072/2096、Estimator 4096/2000、
Flight 4096/2320、Logger 3072/1336、Serial 6144/3008、Telemetry 4096/1904、Idle 512/256 B。

完整基线 Host（本轮真实执行，均 0 failures）：KF6 每配置 72 executables / 4392885 checks；
ESKF Flight/Test 每配置 71 / 4360252；无日志 61 / 152301；Pure INS 70 / 4358689。
每配置另有 8 compile-pass / 16 expected-compile-rejection cases。
最后 C 修复后全部 R/D 门禁重跑，并按影响重跑 Host：health 每配置 1853 checks；
KF6 air 706、replay 33531、实际准备 288；ESKF logging backend 1575、准备 241；
无日志准备 241；Pure INS 准备 231。以上不冒称第二次全量 Host。

最终 R/D Power of Ten 的 checks / first-party C files / functions 分别为 KF6 6459/99/2427、
ESKF logging 6270/99/2354、无日志 5938/95/2238、Pure INS 6118/96/2303。
architecture 启用日志各 318 checks、无日志 184；全部 0 failures；GCC `-fanalyzer` 通过。

目标工具 `Tests/Target/timing_bench*` 为显式 opt-in，默认生产 graph 无这些源，资源表不受影响。
真实 CMSIS DWT/PRIMASK adapter 和 APP snapshot/HWM 示例在 ARM O2/Og 下以 `-Werror` 编译、
生成 `.su` 并核对 PRIMASK 指令；Host O2/Og 各 2089 checks / 0 failures。
六项新工具测试加六项文档检查合计 **12 passed / 14.42 s / exit 0**，
覆盖 wrap、owner、嵌套、系统异常拒绝、时钟错误、饱和、导入归属、默认图排除与实际源码导出。
未链接的三对象 text 合计 O2 1412 B / Og 1516 B，BSS 各 272 B；不是生产 ELF 增量预算。
首次专项 2 failed / 10 passed 原因为测试未支持 generated Make 变量位于 EOF，修正读取后重跑通过。
该工具没有运行于实机；snapshot getter 成本示例不代表算法执行时间，完整 INS/ESKF/Logger/ISR
插桩说明见 `Tests/Target/TIMING_BENCH.md`。真实 CPU、最坏耗时、ISR、SD 和动态 task HWM 仍待测。

## 数学、健康与实际日志闭环

- C/Python float32/float64 四种运动情景：2000 prediction / 1000 measurement groups，
  最大 p/v/q/bg/ba/P 差 `1.032e-5/9.416e-6/7.533e-6/5.680e-7/5.175e-7/3.127e-6`，
  保持 absolute `2e-4`、relative `3e-4`，包含独立 Jacobian/边界反例。
- 250 Hz 混合延迟最大差 `5.383e-6`，178 replay steps；100 Hz 最大差 `3.16e-6`。
  CLIPPED/NaN/P/prefix/capacity 失败不得提前提交 anchor/history，最终跨仓库针对性 20 tests 通过。
- 双 10 s/错位 5 s 窗口 context ARM sizeof 184 B；ESKF state/workspace/history 为
  992/3980/16992 B，BODY/event 64/72 B。192 BODY + 208 events，600 ms history。
- 新的真实 APP correction/pairing/frontend/ESKF C fixture：801 raw → 400 BODY / 2 s，
  200 Hz BODY、120/192 history、0 overflow，4413 checks / 0 failures。2/3 ms proxy 保留 TIME_UNCERTAIN。
- 最终 health C fixture 1853 checks / 0 failures；model mismatch 锁存，不同 source 同 tick 可区分，
  同源重复/倒序不计证据。2 s DR / 10 s INVALID；有限非零 gain 的实际 commit 才刷新最后成功时刻。
- KF6 有限且至少一个非零 Kalman gain 才能提交更新，零创新但正常增益仍可成功；
  浮点下溢为全零 gain 返回 NUMERIC_ERROR，状态/P/成功计数不变。所需组软降权、R>1 或最新物理无效
  使总体 DEGRADED；失辅 DR/INVALID 优先。生产者记录 satellite×Pos-EN-only-window×actual-robust 的倍率。
- 659-record direct C codec/当次 generated decoder，正序及跨队列乱序均可 FAITHFUL；
  full-P 最大差 `1.633e-6`。491-record 实际校准/ESKF backend/LoggerBus/LoggerTask 闭环另行核验，
  99 条量测准入及结果严格匹配，FLP p/v/q/P 最大差约 `9.512e-9/1.2761e-7/8.663e-8/7.302e-7`。
  后者为实际生产 C + 合成 Host 时钟/输入/文件 sink，不是目标机飞行或 DMA 时序证明。
- 最终桥接重新编译 2078 checks / 0 failures；491 records / 58931 B，strict audit 通过。
  BIN SHA256 `253dd88e57bb7f672ad2ed174979f19f632cee58e71a36eb6d7452455bc20e07`；
  decoder SHA256 `2c58fa36a1e40a27801e775b02640f6a460df00d12b58a0640bc3331b4102c46`。
  与上一轮仅 descriptor/设备 identity 及最后两轮健康字段不同，p/v/q/bias/P 和量测 payload 逐字相同。
  最终 pair 由现有 FLP 产品重新导入为 clean / EXACT / FAITHFUL；99 条量测严格匹配，
  20 STATE + 20 NAV_QUALITY 的健康值按精确时间比较 40/40 一致。361 导出零失败，
  两幅缺少旧 IMU_CORRECTED 流的图明确不可用。
  此 fixture 覆盖软加权结果；ACCEPTED 且 R>1、KF6 零 gain 拒绝另由最终 FLP 针对性用例验证。

## Storage 的真实负载与失败恢复

完整 FatFs/diskio/Logger/DMA Host 模型，80 ordinary / 48 estimator 容量未扩充。
Flight/Test 正常运行均 0 drop、0 producer failure：HWM 分别 `65/80,46/48` 与 `77/80,46/48`。
有限超载分别 449/453 drops，frame 1500 的累计即最终累计，恢复后无新 drop；sequence gaps 保留。
BODY 100 Hz，四 GNSS group 各 25 Hz，Baro 100 Hz；Test 额外 25 Hz×4 full-P 分片。
Host 注入最大 write 126 ms / sync 108 ms / iteration 316.12 ms；不能作为目标 WCET。
119 B @ offset 37 与 partial-sector、prefix/关键 flush/uncertain-write 真实 LoggerTask 533 checks；
LoggerBus 2,102,778 checks。CRC/framing 审计不重同步取得 PASS。

## 传感器与 GUI/打包

69 项传感器合并测试通过，包含 26 个实际生成 ARM source/include/resource 路径；
原 Power10 对驱动路径 2897 checks / 66 C files / 1106 functions，0 failures。
BMI088 Sync400 I2C/SPI 使用 6144 B 官方 BSD 配置块、明确同步网绑定、完整初始化/readback与IRQ负测。
ARM sample/driver/adapter ABI 80/112/256 B；Sync400 O2 对象 7325 B text/const、0 data/BSS。
普通 BMI088 raw200 不宣称同步资格；ST320X 高 g 独立，MPU6050 不提供假 SPI。
所有新传感器：MOCK_VALIDATED / COMPILE_VALIDATED / HARDWARE_UNVERIFIED。
默认 RAM 配置；JY 无盲 SAVE，M8 持久层无法独立比较时 UNSUPPORTED，M9/M10/F10 显式分层差异持久化。

FCCG 导出源包离线启动 8 s，发现 65 插件与 ESKF/Sync400 资源；4 张中英/Light/Dark 截图实际
1000×700 logical / 2000×1400 pixels，英文完整产品标题换行。C fixtures 位于永久 tests/fixtures，源包保留。
FLP 最终完整套件 **483 passed / 9 原条件 skipped / 373.07 s / exit 0**；
针对性回归 90 passed，最终套件无 warning，NaN/inf 负例局部断言预期告警。
最终 wheel 349169 B、SHA256 `8526dff3f49dd1bc9f4722f73881e9357745b9d2a91068610c34487b3fdf7869`，
离线解包后的真实 GUI/ESKF 插件启动通过，102 个 Python/JSON 产品文件与当前源码逐字一致。
此前 293.61 s 套件与旧包保留；最终套件和包已包含三处 `m/s²` 显示单位编码修复及其断言。
九项 skip 为原有外部条件 fixture：current-log 1、旧 joint C golden 1、SS_TEST_0 3、SS0007 3、SS0014 1。
本轮新 C oracle、两个 659-record golden、五真实日志及实际 backend bridge 已另行执行。
GSHC 最终窗口修复后 425 passed + 3 subtests；1000×700/200% 的中英 Light/Dark 共 16 张实际全窗口截图。
GSHC PyInstaller 包启动 8 s 存活、stderr 0；九项导航准备可见，任务状态卡使用垂直滚动。
实体触屏、OpenGL 驱动及无线网关没有在本轮硬件认证。

## 五份真实旧日志与尚缺证据

四路 A recorded / B old-revision / C quality-revision-3 KF6 What-if / D ESKF15 What-if 均保留。
SS0002 的 B/C 继续报 gnss_origin_unavailable，D 无 GNSS 操作，不补造 origin。
D 的 SS0000/2/4 最终 INVALID，SS0001 HEALTHY、SS0003 DEGRADED 是内部诊断，无真值不能称定位精度通过。
五份 finite/P-PSD/q-normalized 不等于物理正确；新质量 flags、硬件读回与采样时间证据缺失，均明确近似。
最终新目录 five_logs_quality_fix_kf6 / five_logs_quality_fix_eskf 与旧结果独立保存。
四份成功 C 各 165 个既有非健康数组完全一致；D 的 SS0000/1/3/4 各 141 个、SS0002 的 45 个
非健康数组完全一致。D 的健康变化 epoch 数依次 130/181/0/865/769，SS0003 末状态由 HEALTHY 修正为 DEGRADED。
D 五组最长失辅均不变；C 仅 SS0001/3 VelU 的初始最大间隔分别由 280000/290000 改为 290321/304296 us，
因为旧离线 helper 从首输出起计，产品从实际 START 起计；正式原日志导入核对差值 10321/14296 us。
该差异不是融合结果变化。73 份旧报告/NPZ/图和全部原始输入哈希不变。
完整比较、逐组计数和时间见 FLP approved_quality_comparison.json / approved_quality_clock_basis.json，
窗口/bias/15P 与失败曲线仍保留于 five_logs_contract_final、four_way_comparison。

## 回归命令、修复记录与最终状态

完整产品回归显式枚举 `tests/test_*.py`（受维护顶层套件），生成的临时项目不是产品 pytest。
冻结前一轮 519 passed / 5 failed / 1 skipped：4 个 63→65 插件目录数量断言及 1 个文档命名检查失败，
均保留失败日志并修复；随后针对性 9 tests passed。
最终完整 rerun：**533 passed / 1 skipped / 0 failed，2306.98 s，exit 0**，
`fccg_delivery_final.log/.exit`。最后 C 修复由独立六配置 delta 覆盖；随后新增目标计时工具的六项测试
及六项文档回归单独通过，没有把这次补测描述为第二次全量运行。
原 1 skip 原因：旧只读 reference firmware 工作树非 clean，原 skip 条件未改。五份实际任务日志来自 SS_0_5_TEST_3。
一次宽泛递归收集误入历史 generated fixture 导致 collection errors，保留日志；没有删除用户旧临时数据。
首个 wheel 命令误用相对 TEMP 路径，pip 使用系统临时目录；已以严格错误处理、repo-local TEMP/no-cache 重跑通过，
没有全局安装或配置修改。此操作失误不被描述成首次就符合临时输出约束。
变更 Python Ruff `E4,E7,E9,F,I`、134 Python files compileall、80 JSON 解析及 git diff --check 通过。

此前 FLP 四个 revision-3 接入文件的自动审批阻塞已由用户“可以继续修改flp”的明确回复解除。
四个产品调用点已实际接入，最终五日志、完整产品回归与实际桥接复验通过。
目标计时工具补充验证已通过。当前软件状态为 IMPLEMENTATION_COMPLETE / SOFTWARE_GATES_PASS，
可进入 READY_FOR_JY901B_BENCH_VALIDATION；这不是已执行台架或实飞验收。
GSHC 已本地提交 `8be9fd6a7d03be8a7edd96a78454b33701869ad0`；最终 Git 交付以三仓实际提交/远端核对为准。
新传感器仍 HARDWARE_UNVERIFIED，整套 NOT_FIELD_VALIDATED。

---
