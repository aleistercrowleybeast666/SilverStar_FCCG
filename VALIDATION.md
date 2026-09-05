# Validation — 2026-09-05 runtime indicator, stack and calibration repair

本节记录本轮实际验证。仍为 **0.0.10 Software Release Candidate / Pre-Hardware-Validation**，
适用范围为 STM32F407VET6 / SS0.5 默认组成。没有烧录、HIL 或飞行验证。

## 工作区与持久归属

- Branch：`main`；基准 HEAD：`ad7ee8acb4677a45bfbcf2d27d555b02a1623a9a`，主题“修改硬件连接问题”。
- 修改仍在工作区，没有 commit、push、Tag 或 Release。
- 所有修改和验证输出均在 FCCG 仓库；测试、编译器临时文件和生成工程位于 `tests/`。
  外部参考固件、GSHC、FLP 未修改。参考固件导入审计为 clean，commit 为
  `cc0b377ded690556d037a412a55f87fe334c42d0`。
- Core 的运行时 C/H、Host fixtures、任务配置和架构检查器，以及 OS overflow hook，
  已在 `tools/import_reference_components.py` 登记 FCCG-owned source-of-truth。
  `check_task_stacks.py` 和运行时文档由 `tools/reference_overlays/` 持有。
- 最终连续两次只读参考导入：**629 个文件，第二次 0 个哈希变化**。
  同时修复导入文档重放：已修正的 Storage ownership 不再被当作未知内容，附加章节不重复，
  Board 固定映射、多实例说明和当前版本文档不被旧参考说明覆盖。

## 修复与命令语义

主要实现入口：

- `plugins/builtin/silverstar_core_0_0_10/payload/APP/Src/app_tasks.c`：production init、正常 HWM 缓存、稳定故障任务映射。
- 同一 Core payload 的 `APP/Inc/app_task_config.h` 与 `APP/Src/estimator_task.c`：静态栈配置和非等待式 origin reset。
- 同一 Core payload 的 `System/Calibration/{Inc,Src}/system_calibration*`：build mask、中心门禁和 NONE 初始化/重置。
- 同一 Core payload 的 `System/Alignment/Src/system_alignment.c`：立即校验和延后完整 Process。
- 同一 Core payload 的 `Common/{Inc,Src}/silverstar_assert.*` 与 OS payload 的
  `OS/FreeRTOS/freertos_hooks.c`：静态 fault record 与 overflow hook。
- `src/silverstar_fccg/generator/render.py`、`tools/reference_overlays/check_task_stacks.py`、
  `tools/import_reference_components.py`：Make 栈报告、调用链预算和持久导入归属。

`AppTasks_Init()` 原先遗漏 `SystemIndicator_Init()`，因此周期 Process 在写 GPIO 前就返回。
现在生产路径先初始化 Calibration、Alignment、Indicator，再创建任务。启动集成测试调用
真实 App Init、真实 Indicator 和 GPIO service，没有测试侧补 Init；验证 GPIO6 的低电平
点亮与周期翻转。SS0.5 的 `IMU_CAL_LED` / PA1、Board fixed mapping 和 polarity 未改变。

空选校准原先在 Alignment Init 之前调用 CAL_START(NONE)，还依赖开机阶段未必已经存在的
新鲜 IMU 样本。现在 Calibration Init 直接建立 NONE、零 bias、单位 scale、READY；RESET
也恢复该状态并推进生效快照 sequence。启用 Logging 时 Required `CALIBRATION_RESULT`
继续描述实际生效校正，不代表执行过物理采样。

| 校准选择 | build procedure mask | AIR calibration_mode_mask |
| --- | ---: | ---: |
| 空选 | 0x00 | 0x01 |
| OneFace | 0x02 | 0x03 |
| SixFace | 0x04 | 0x05 |
| OneFace + SixFace | 0x06 | 0x07 |

共享 header 在编译时拒绝 procedure mask 的未知位；bit0 只由 capability getter 添加。
`SystemCalibration_Start()` 在锁定来源或使校准/对准失效之前执行 build gate。不支持的
procedure 返回现有 UNSUPPORTED；非法参数、生命周期状态和 BUSY 仍使用现有结果。
AIR/Serial 共同受这一中心入口约束，ACK result mapping、token 和 framing 未改变。

`SystemAlignment_Start()` 保留立即状态、calibration-ready、build/source capability、
source lock、action 和 backend-reset 检查；不再调用完整 `SystemAlignment_Process()`。
后续由现有 FlightTask 周期路径推进。真实 Telemetry task/service/codec 和 Alignment runtime
集成测试验证 ACK OK 后没有 backend status/guard 重处理；再调用生产周期 operation 验证其推进，
并由最终 ELF 证明该 operation 属于 FlightTask 路径。这里没有把 Host stub 当作完整 RTOS 调度验证。

CAL_START/CAL_FACE/CAL_RESET 与 Serial 共用路径已审计：通信端保留有界验证/重置，采样仍在
IMU 路径，求解仍在 FlightTask。`EstimatorTask_OriginsReset()` 将“冻结后等待另一个任务”
改为临界区内检查 collection busy，忙时立即返回 BUSY，空闲时执行原有短重置。

Overflow hook 保留原始 task handle 和 task_name 地址，并通过静态任务表记录稳定 task ID、
有限可信名称、system state 和带有效标志的缓存 HWM；Idle 单独识别，未知任务显式标记。
原始名称指针即使为无效地址也不解引用，hook 不扫描可能损坏的 TCB。HWM 来自正常上下文
最近一次 snapshot，未采样时为 invalid，不伪装成故障时测量。静态 fault record、assert、
`configCHECK_FOR_STACK_OVERFLOW=2` 和 HardFault fail-stop 保留；没有 heap 或诊断 I/O。

## 最终生成与自动检查

最终工程：`tests/acceptance_runtime16_verified/`；详细日志：`tests/artifacts/runtime16/`。

- 默认 Generate：523 个文件，未编译；第二次 Apply：0 added / 0 modified / 490 preserved。
  Generate、reload、second apply 均 Ready。Source Graph 为 **138 C + 1 ASM**。
- `python -m compileall -q src main.py tools`：通过；Python cache 重定向到 `tests/`。
- 冻结源码后的定向测试：**21 passed**，含本轮 20 项测试和工程计划一致性复验。
- `python -m pytest -q --basetemp=tests/.pytest-runtime16-complete`：**318 passed in 627.45 s (0:10:27)**。
- Release / Debug：`mingw32-make -j8 CONFIG=<config> stack-report artifact-check` 均返回 0，
  ELF/MAP/HEX/BIN 齐全；每个配置有 138 份对应当前 C source graph 的 `.su`。
- Host：`pwsh -NoProfile -File Tests/Host/run_tests.ps1`，**67 executables / 12415 checks /
  0 failures / 8 compile-pass cases / 16 expected compile rejections**。
- Architecture：**270 checks，0 failures**。独立 stack-report 只读取已经链接的 ELF；
  精确许可该目标，不允许编译目标依赖它；新增反例验证依然拒绝构建期 Python generator。
- Power of Ten：**6008 checks，94 first-party C files，2258 functions**。
- `mingw32-make -j8 CONFIG=Release static-analysis`：first-party `-fanalyzer`、依赖编译和链接通过。
- 两个配置的 Artifact Check 均通过，runtime heap symbols 为 0。

最终目标固件构建使用匹配的 Arm GNU Toolchain **14.3.Rel1 / GCC 14.3.1 20250623**。
Host 使用本机 GCC；PowerShell、TEMP/TMP 仅使用本次进程设置，未修改全局环境或 PATH。

## Release / Debug 静态任务栈预算

| Task | Configured B | Release estimate B | Release margin B | Debug estimate B | Debug margin B |
| --- | ---: | ---: | ---: | ---: | ---: |
| Device | 2048 | 1496 | 552 | 1320 | 728 |
| INS | 3072 | 2040 | 1032 | 1808 | 1264 |
| Estimator | 4096 | 1964 | 2132 | 1868 | 2228 |
| Flight | 4096 | 3428 | 668 | 2292 | 1804 |
| Logger | 3072 | 1336 | 1736 | 1296 | 1776 |
| Serial | 6144 | 4200 | 1944 | 2928 | 3216 |
| Telemetry | 4096 | 1980 | 2116 | 1660 | 2436 |
| Idle | 512 | 256 | 256 | 256 | 256 |

单位均为 bytes；estimate 已包含 256 B Cortex-M4F exception/FPU context reserve，margin
是在此基础上额外剩余的空间。规则要求 margin >= 256 B。原 Device 1536 B、INS 2048 B
在 Release 下仅余 40 B / 8 B，因此也增大；Serial 从 2048 B 增至 6144 B，Telemetry 从
1536 B 增至 4096 B。全部静态任务栈总量为 27136 B，比原配置增加 8192 B。

工具读取真实 `.su`、匹配的 linked ELF `objdump` 与 `nm`。每个当前 C source 必须有 `.su`，
遗漏直接失败；不会把缺失报告的工程源码当库汇编估计。Inline frame 由 `.su` 计入；direct
和 tail-call 都保守相加。无 `.su` 的链接库汇编按 constant pushes/SP decrements 累加，包含
`strd [sp, #-16]!`；单一 FatFs SD_Driver callback 经实际绑定校验后闭合。未知间接调用、
无界 frame、递归和不能解释的 SP 操作会拒绝报告。新增测试覆盖缺失报告、库 SP 占用、
不足余量、未知 indirect 与递归。它是可复现的 worst-known 静态预算，不是运行 HWM 或任意
未来插件的数学证明；MSP 上的嵌套中断仍需另行实测。

完整逐函数路径、frame bytes、compiler、ELF hash 和检查结论见：
`tests/artifacts/runtime16/stack-budget-release.json`、`stack-budget-debug.json`。
Release Serial 最深已知路径仍经过 Console formatting；Telemetry 最深路径为 IMU stream
读取，已经没有同步完整 Alignment Process；Flight 预算覆盖 Alignment 的深层路径。

## 内存和最终 ELF

| Config | text B | data B | bss B | FLASH (text + data) B |
| --- | ---: | ---: | ---: | ---: |
| Release | 259736 | 1128 | 127296 | 260864 |
| Debug | 276064 | 1128 | 127320 | 277192 |

Release 主 SRAM 使用 77360 / 131072 B，剩 53712 B；Debug 使用 77384 B，剩 53688 B。
两者 CCMRAM 使用 51064 / 65536 B，剩 **14472 B**；heap reserved/runtime symbols 都为 0。
FLASH 容量 524288 B，Release 剩 263424 B，Debug 剩 247096 B。

- Release ELF SHA-256：`bea64d4c292578b06ea445a00ef8481e93a85f90531817a7760018fe1ec163f8`。
- Debug ELF SHA-256：`257770a5ce8adb5693256eeb9ec1d75665a93601d54dc8aa79e6e3a175d6710e`。

两个最终 ELF 的下列检查全部为 true：

1. `main -> AppTasks_Init` 闭包包含 `SystemIndicator_Init`。
2. `SystemAlignment_Start` 闭包不包含完整 `SystemAlignment_Process`。
3. Telemetry 和 Serial task 闭包均不包含完整 Alignment Process。
4. FlightTask 闭包包含 Alignment Process。
5. 7 个应用静态任务及 Idle 均有 stack budget；当前 timer task 未启用。

## 协议与剩余实机验证

AIR M0、Maintenance 0.0、SSLOG 0.0、`.ssdecoder` 1.1 的版本、字段布局、CRC、endianness、
Record size 和现有 command tokens 均未改变；没有 breaking wire change。修正的是既有
calibration_mode_mask 的广告值。参考导入仍逐项核对四个协议/Console C 文件的 SHA-256，
Host/Python 覆盖四种 handshake bytes、Golden/codec round-trip、Required calibration snapshot、
decoder、source selector、多实例和 verified-board mapping 回归。

仍需真实 SS0.5 持续验证：上电指示灯及 polarity、重复 AIR/Serial ALIGN/CAL/RESET 命令、
所有任务的长期 HWM、MSP/中断嵌套、来源锁定/失效场景、SD 会话中的实际校准快照。
本轮没有实际运行 HWM、native EIDE build、烧录、电气、HIL 或飞行验证，不扩大硬件支持范围。

下文保留此前轮次的历史验证数据；其 HEAD、测试数量和内存数值不属于本轮。

---

# Validation — 2026-09-02 SS0.5 verified Board fixed-resource mapping repair

This section records validation actually performed for the verified-Board fixed-resource mapping
repair. The result remains an internal **Software Release Candidate / Pre-Hardware-Validation**
result. It is not a flash, electrical, HIL, dual-platform, or flight qualification.

## Current commit and worktree identity

- Branch: `main`
- Base `HEAD`: `533b4aa091d37bc6f6980a27f470e053fcbd49f5`
- Base subject: `新增IMU，GNSS，遥测的新增接口`
- Worktree at validation time: intentionally dirty with this repair, tests, and documentation. No
  commit, push, Release, or Tag was requested or performed.
- External reference firmware and SilverStar_FLP remained read-only and were not built, modified,
  formatted, committed, or pushed.

## Root cause and repaired contract

The verified SS0.5 Board `connections.json` mapping was merged with imported CubeMX inventory
metadata, and the renderer then consumed the inventory `logical_index`. Inventory enumeration order
could therefore override the Board plugin's stable ABI and place correct physical aliases into the
wrong `PlatformGpioId` slots.

For a verified Board, `connections.json` is now the sole authority for logical ID, `c_id`, fixed
index, and purpose. The bundled `.ioc` and generated STM32 symbols only resolve and validate the
declared physical alias. Duplicate JSON keys, duplicate fixed aliases, missing aliases, kind drift,
symbol drift, and selected-requirement closure failures are rejected before publication. Custom
CubeMX projects retain their existing imported/manual `logical_index` behavior and do not inherit
the verified-Board contract.

The validated SS0.5 GPIO mapping is:

| Logical ID | Physical alias |
| ---: | --- |
| 0 | `RADIO_NSS` |
| 1 | `RADIO_RST` |
| 2 | `RADIO_BUSY` |
| 3 | `RADIO_DIO1` |
| 4 | `P_CONTROL1` |
| 5 | `P_CONTROL2` |
| 6 | `IMU_CAL_LED` |
| 7 | `GNSS_RST` |
| 8 | `GNSS_TIMEPULSE` |

## Python and generation validation

- `python -m compileall -q src main.py tools`: passed.
- `python -m pytest -q --basetemp=tests/.pytest-prompt15-full`: **298 passed in 577.04 s
  (0:09:37)**.
- Focused fixed-resource suite: **9 passed in 9.31 s**; the final combined mapping/lifecycle slice
  was **15 passed in 13.02 s**.
- A broader resource/generator regression slice was **73 passed in 189.41 s**.
- Fresh SS0.5 acceptance project: first apply added **518 files**; the second deterministic apply
  added 0, modified 0, and preserved 485 project-owned files. Readiness was `Ready` after generate,
  reload, and second apply.
- Source Graph: **138 C + 1 ASM source**. Optional platform sources: none.
- Generated decoder: **103122 bytes**, SHA-256
  `df885c2b48a62baa2cac15fb780797c1e90895d913d26a9ea2c462f701f9d657`.
- Resource-binding fingerprint in both hardware-preparation and ownership metadata:
  `b8af03e219b3412f1f7d42331a954bb1f7533e092e474dddcd8e8af80343991d`.

Focused tests cover the exact golden mapping, shuffled/wrong inventory indexes, verified-versus-
custom index authority, missing-alias rejection without fallback, duplicate fixed-alias rejection,
generated-table closure rejection, binding-fingerprint inputs, readiness invalidation, and custom
CubeMX compatibility.

## Generated-project builds and quality gates

Both Arm GNU configurations returned 0 and produced ELF, MAP, HEX, and BIN artifacts:

| Config | text | data | bss | text + data (FLASH) | data + bss |
| --- | ---: | ---: | ---: | ---: | ---: |
| Release | 259408 | 1072 | 119064 | 260480 | 120136 |
| Debug | 275656 | 1072 | 119088 | 276728 | 120160 |

- Host Tests: **56 executables, 9123 checks, 0 failures**, 8 compile-pass cases, and 16 expected
  compile rejections.
- Architecture Check: **255 checks, 0 failures**.
- Power of Ten: **5895 checks** over 94 first-party C files and 2206 functions.
- Arm GCC `-fanalyzer` Static Analysis: passed first-party analysis, dependency compilation, link,
  size, HEX, and BIN stages; `text=259408`, `data=1072`, `bss=119064`.
- Artifact Check: passed; ELF **2781544 bytes**, BIN/FLASH **260480 bytes**, main SRAM
  **77264/131072**, CCMRAM **42872/65536**, heap reserved 0, runtime allocator symbols 0.

This repair changes resource binding and validation only. AIR M0 wire values, maintenance and SSLOG
containers, calibration behavior, GSHC semantics, FLP behavior, decoder schemas, and multi-instance
semantics were not changed. Real GPIO electrical behavior, I2C/PWM electrical validation, hardware
flashing, HIL, dual-platform testing, and flight validation remain not done.

## Prior validation — 2026-09-01 bounded multi-instance follow-up

This document records validation actually performed for the bounded same-model multi-instance and
minimal failover follow-up on FCCG 0.0.10. The result remains an internal **Software Release
Candidate / Pre-Hardware-Validation** result. It is not a public release, tag, flash result,
electrical qualification, redundant-hardware qualification, dual-platform qualification, or
flight qualification.

## Current commit and worktree identity

- Branch: `main`
- Base `HEAD`: `f44f49e7e7163e4260a186d409fd1cdaa6f1ec1b`
- Base subject: `修改测试与文档，完成基础功能`
- Worktree at validation time: intentionally dirty with the current multi-instance implementation,
  tests, and documentation. This follow-up was not committed or pushed, and no Release or Tag was
  created.
- External reference firmware and SilverStar_FLP remained read-only and were not built, modified,
  formatted, committed, or pushed.

## Current multi-instance acceptance

- `python -m compileall -q src main.py tools`: passed.
- `python -m pytest -q`: **289 passed in 524.38 s (0:08:44)**.
- Focused multi-instance/prompt acceptance: **34 passed in 16.79 s**.
- Fresh single-device and `2 x JY901B + 2 x NEO-M9N + 2 x SX1281` projects each materialized
  **518 files**. The multi-instance Source Graph resolved to **138 C + 1 ASM source**, 46 include
  directories, and 12 defines.
- Final generated `.ssdecoder`: `SilverStar_Multi_Instance_Acceptance.ssdecoder`, **114272 bytes**,
  SHA-256 `cb735adfe49221ac61f3c3d35bd950668ab2c0f2634769222d98fdb91fb066c0`.
  Package schema and Project Semantics remain `silverstar.ssdecoder.package-schema/1.1`; the AIR M0,
  Serial Maintenance 0.0, SSLOG container 0.0, and existing Record IDs/layouts remain unchanged.

Final Arm GNU builds from fresh generated projects all returned 0:

| Project | Config | text | data | bss | text + data (FLASH) | data + bss |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| single device | Release | 259408 | 1072 | 119064 | 260480 | 120136 |
| multi instance | Release | 260000 | 1072 | 133664 | 261072 | 134736 |
| single device | Debug | 275656 | 1072 | 119088 | 276728 | 120160 |
| multi instance | Debug | 276720 | 1072 | 133688 | 277792 | 134760 |

The bounded multi-instance Release delta is **+592 bytes FLASH** and **+14600 bytes data+bss**;
the Debug delta is **+1064 bytes FLASH** and **+14600 bytes data+bss**. The increased static storage
is the compile-time-bounded per-instance parser, FIFO, driver, HAL, and selector state; no runtime
heap was introduced.

Final multi-instance quality gates:

- Host Tests: **56 executables, 9139 checks, 0 failures**, 8 compile-pass cases, and 16 expected
  compile rejections; observed wall time was about **123 s**. The new direct context tests report
  JY901B 25, NEO-M9N 29, SX1280 HAL 21, SX1281 28, and source selector 221 checks.
- Architecture Check: **255 checks, 0 failures**.
- Power of Ten: **5895 checks** over 94 first-party C files and 2206 functions.
- Arm GCC `-fanalyzer` Static Analysis: passed strict first-party analysis, dependency compilation,
  link, size, HEX, and BIN stages; result size `text=260000`, `data=1072`, `bss=133664`.
- Artifact Check: passed; ELF **2778856 bytes**, BIN/FLASH **261072 bytes**, main SRAM
  **91864/131072**, CCMRAM **42872/65536**, heap reserved 0, runtime allocator symbols 0.

Software tests verify independent resource tables and mutable contexts, all-instance IMU/GNSS
native logging, pre-alignment IMU selection followed by a lock, one-way GNSS liveness failover, and
one-way AIR transport failover after 10 consecutive real TX timeouts. Exhausted/single telemetry
chains keep retrying the last source once per normal send period; they do not stop or enter an
unbounded retry loop. TX completion is only local-radio success and does not prove ground-station
reception or antenna health.

Physical dual-IMU, dual-GNSS, dual-radio electrical/EMC/RF, HIL, and flight validation remains not
done. I2C pull-up and PWM waveform/polarity/safe-level electrical testing and a second real hardware
platform also remain not done.

## Prior 2026-08-31 freeze commit identity

- Branch: `main`
- Commit: `f44f49e7e7163e4260a186d409fd1cdaa6f1ec1b`
- Subject: `修改测试与文档，完成基础功能`
- Parent: `0fb9101a31ab949c25e41da3c0d61dbb6b9f8efd`

## Environment

- Windows PowerShell 7.6.4
- Python 3.14.0
- PySide6 6.10.1
- Arm GNU Toolchain 14.3.Rel1, GCC 14.3.1
- GNU Make 4.4.1 (`mingw32-make`)
- MSYS2 UCRT64 Host GCC 16.1.0, target `x86_64-w64-mingw32`
- Builtin catalog: 36 strict packages
- Platform/FCCG/generated-firmware release identity: 0.0.10
- Project format: 11
- Decoder package/project-semantics schema: 1.1

AIR M0, Serial Maintenance 0.0, Flight Log Format/SSLOG container 0.0, FreeRTOS 11.3.0,
SS0.5, STM32F407VET6, CubeMX, and STM32Cube FW retain their independent versions.

## Read-only reference and reproducibility

- Path: `C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5`
- Branch: `main`
- Commit: `cc0b377ded690556d037a412a55f87fe334c42d0`
- Subject: `完善同能力多实例与日志配置契约`
- Working tree: clean
- Snapshot digest: `7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`
- Deterministic recorded UTC time: `2026-08-27T18:07:29+00:00`, derived from the commit

The importer was run repeatedly against that exact read-only snapshot. Each run completed the
required-file and maintenance-document audits with no missing files/findings, and the second
publication produced no further tree change. The external repository was not modified, formatted,
built, committed, or pushed.

The four frozen wire-source SHA-256 values still match the read-only reference:

- `Protocol/Src/air_protocol.c`:
  `4537b3588b65baa051c13605eed5715a42f530abe5a0bdfad11a4925a2a0b418`
- `System/Src/system_console.c`:
  `c1efc4849c33c9fca361015ec6068d027eeac95bd275f56d139146ea3c781d99`
- `Protocol/SSLOG/Src/sslog_protocol.c`:
  `b065b6733fe87dea5e220e8eaed4ef61569fff831e3dd3d14f1c218fc6aaa3bc`
- `Protocol/SSLOG/Src/sslog_records.c`:
  `871b73bd1cecf9a39a2b95006f34bb32d303a5cba23d55aa02aedb934fe03d30`

## Python, schema, GUI, and model regression

- `python -m compileall -q src main.py tools`: passed
- `python -m pytest -q`: **276 passed in 478.64 s (0:07:58)**
- Strict builtin/plugin/project/schema loading passed.
- Root-CWD portable-path tests passed while actual `WorkspacePolicy` root authorization remained
  rejected; traversal, absolute/drive/UNC, dot/empty segment, backslash, control, reserved-name,
  trailing-space/dot, and unsafe build-field cases remained rejected.
- F407 target lock, mismatch/tamper detection, save/reload/reconcile, render paths, and a fully
  test-only synthetic `SilverStar_H743_Test` MCU/Board/OS/storage fixture passed. The fixture is
  architecture coverage only and is not an H7 product-support claim.
- Calibration GUI/model/migration/semantics tests passed for empty, OneFace, SixFace, and both;
  the pre-release Existing combinations migrate deterministically and are never serialized again.
- Host-level NONE/identity/READY/corrected-IMU/Required `CALIBRATION_RESULT` field checks passed.

## Fresh default generation and deterministic outputs

Fresh project: `tests/acceptance_final_freeze_0_0_10_r2`.

- First materialization: **504 generated/copied files**
- Resolved Source Graph: **136 C + 1 ASM source**
- Readiness before second apply: Ready, no missing or stale paths
- Second apply: 0 files added, 0 files modified, 472 project-owned component files preserved
- Release, Debug, static-analysis, EIDE, and VS Code consume this same Source Graph

Generated decoder package:

- File: `FCCG_Final_0_0_10.ssdecoder`
- Size: **102390 bytes**
- SHA-256: `696d09226fc8a574602514e342667b46e7cf4e707c1f580740b62640927482d3`
- Package schema ID: `silverstar.ssdecoder.package-schema/1.1`
- Entries: only `README.md`, `checksums.sha256`, `manifest.json`, `project_semantics.json`, and
  `record_catalog.json`; no executable code

Generated Host golden log:

- File: `FCCG_Final_0_0_10_golden.sslog`
- Size: 1350 bytes
- SHA-256: `bf0ffeb23344390764377807ce6e4aa9a4a02ad4416687e7fe9516edccb69fed`

The `.ssdecoder.algorithms` list is verified/documented as onboard composition, not an FLP offline
algorithm whitelist. FCCG did not modify FLP or implement old-log compatibility.

## Eight optional-Protocol combinations

`tools/check_optional_protocol_combinations.py` freshly generated every Telemetry/Maintenance/
Logging combination below `tests/acceptance_optional_protocols_0_0_10_final_freeze/`. All 16
Release/Debug builds returned 0. `arm-none-eabi-nm` found every enabled task function/stack/TCB and
found none of those three allocation symbols for each disabled Protocol.

Each row also contains one startup ASM source.

| Telemetry | Maintenance | Logging | C sources | Release | Debug | task symbol audit |
| --- | --- | --- | ---: | --- | --- | --- |
| 1 | 1 | 1 | 136 | passed | passed | passed |
| 1 | 1 | 0 | 126 | passed | passed | passed |
| 1 | 0 | 1 | 132 | passed | passed | passed |
| 1 | 0 | 0 | 122 | passed | passed | passed |
| 0 | 1 | 1 | 133 | passed | passed | passed |
| 0 | 1 | 0 | 123 | passed | passed | passed |
| 0 | 0 | 1 | 129 | passed | passed | passed |
| 0 | 0 | 0 | 119 | passed | passed | passed |

## Calibration build combinations

The default empty selection completed both Release and Debug plus the full Host suite. Three fresh
additional projects supplied representative toolchain coverage:

| Calibration procedures | Configuration | Source Graph | Result |
| --- | --- | --- | --- |
| empty → NONE/identity | Release + Debug + Host | 136 C + 1 ASM | passed |
| OneFace | Release | 136 C + 1 ASM | passed |
| SixFace | Debug | 136 C + 1 ASM | passed |
| OneFace + SixFace | Release | 136 C + 1 ASM | passed |

Empty selection retained the calibration subsystem and required result producer. No Record ID,
72-byte payload layout, endian, CRC, or SSLOG 0.0 container change was made.

## Generated firmware quality gates

All commands ran against the fresh default F407/SS0.5 project and returned 0.

- Release: `text=248680`, `data=1072`, `bss=118976`, `dec=368728`
- Debug: `text=262472`, `data=1072`, `bss=118992`, `dec=382536`
- Host Tests: 51 executables, 8799 checks, 0 failures, 8 compile-pass cases, and 16 expected
  compile rejections. Expected rejections retained raw GCC details and counted as successful gates.
- Architecture Check: 250 checks, 0 failures
- Power of Ten: 5601 checks over 92 first-party C files and 2074 functions
- Static Analysis: full first-party Arm GCC `-fanalyzer` build with strict warnings, link, size,
  HEX, and BIN stages passed
- Artifact Check: ELF 2630264 bytes, BIN/FLASH 249752 bytes; FLASH 249752/524288, main SRAM
  77176/131072, CCMRAM 42872/65536, heap reserved 0, runtime allocator symbols 0

## Source-package and repository closeout

The final documentation snapshot is followed by two consecutive deterministic source-package
exports. Both contain **757 entries**, are byte-for-byte identical, and contain no absolute/drive
entry names, acceptance/build/cache directories, or binary/object/dependency/listing artifacts.
The final archive size and SHA-256 are reported in the handoff after the last export because the
archive includes this document itself; embedding its own hash would change that hash.

## Remaining validation

- Physical I²C external-pull-up and PWM waveform/polarity/safe-level electrical tests are not done.
- Dual real-hardware-platform internal testing is not done; the synthetic H743 fixture is not a
  substitute.
- Flash/upload, SD-card media endurance, radio link, actuator bench, HIL, and flight tests are not
  done.
- A normal Classic CAN consumer/filter/router/bus-off contract is not implemented.
- SilverStar_FLP single-log import, exact decoder matching, rejection of unpublished old logs, and
  offline-algorithm comparison remain a separate follow-up task.
