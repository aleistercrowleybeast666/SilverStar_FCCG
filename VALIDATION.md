# Validation — 2026-09-12 Algorithm actual parameters / decoder 1.2

## 2026-09-16 — Sparse preflight logging closeout

Initial source worktree clean at `b5904e3`. No reset, checkout, commit or push. Production
change is limited to the two defaults and explicit compiler-override guards in the builtin
System/User/system_user_config.h. Platform 0.0.10, project format 12, decoder/project-semantics
1.2, SSLOG/AIR/maintenance layouts and versions are unchanged. KF6/INS mathematics, Q/R/P0,
GNSS qualification/reacquisition, START transaction and deployment algorithms were not edited.

### Root cause and producer audit

Both existing preflight macros defaulted to 1, allowing continuous native/corrected sensor records
through their existing producer-side gates. They now default to 0 under #ifndef guards.

- DeviceNativeLog_Process / ImuProcess return before logging snapshot reads, dedup advancement
  or LoggerBus push outside FLIGHT/RECOVERY. IMU_NATIVE, GNSS_NATIVE, BARO_NATIVE, MAG_NATIVE
  and HW_QUAT_NATIVE are gated. Underlying DeviceTask startup/device processing still runs.
- ImuSampleBus continues SystemInertial_NextGet, source-sequence validation,
  SystemCalibration_ImuSampleProcess and consumer queueing; only CorrectedLog skips IMU_CORRECTED.
- InsTask's pre-existing mission/lifecycle gate controls flight mechanization outputs; preflight
  alignment remains active. EstimatorTask's pre-existing prediction gate controls measurement,
  state/covariance/diagnostic output; GNSS/Baro origin collection remains separate and active.
- Power/Health/Stats and event-driven diagnostics retain their original cadence/policies.
  No LoggerBus admission policy, queue capacity, drop counter or writer integrity code changed.

Preserved: file header; decoder profile, SYSTEM_CONFIG, DEVICE_DESCRIPTOR, ALGORITHM_DESCRIPTOR,
LOG_STREAM_DESCRIPTOR; boot/self-test/config diagnostics; calibration and alignment start/result/
failure; final GNSS/Baro origins; mission config, INITIAL_STATE, START/START_REJECTED and fault events.
LoggerTask still creates the session at boot and drains throughout preflight.

START still performs Prepare → origin freeze → navigation initialization → flight-queue reset
before committing FLIGHT; FlightTask then writes the start snapshots/events. The change introduces
no queue reset and does not advance native dedup while gated. Host tests confirm the first native,
corrected and navigation-output records at START and each 10 ms IMU sample throughout 20 s.
This is a Host boundary result, not a target task-scheduling guarantee.

LANDING retains the original lifecycle gates, 1000 ms grace, drain, flush, finalize and fault
behavior. The fixture enters LANDED and arms real LoggerBus finalization with the landing time;
ordinary native/corrected flight logging ends and low-rate tail records continue until closure.

Diagnostic full preflight remains available by changing the generated header values to 1U, or
passing `-DSYSTEM_LOG_PREFLIGHT_NATIVE_ENABLE=1U` and
`-DSYSTEM_LOG_PREFLIGHT_CORRECTED_IMU_ENABLE=1U` to the compiler. Both Release and Debug otherwise
use sparse defaults. No new checkbox, manifest parameter, project field or decoder field was added.
See [policy and producer ownership](docs/PREFLIGHT_LOGGING.md).

### Files and regression coverage

- `plugins/builtin/silverstar_core_0_0_10/payload/System/User/system_user_config.h`: defaults/guards.
- Its `Tests/Host/storage_integrity/test_sparse_preflight.h`: Host device/inertial/calibration-state
  facades and preflight/flight/landing workload; calls real native producer, ImuSampleBus and
  calibration correction implementation. Sampling and calibration-consumer calls continue for
  all 14,100 samples in the 120 s case, with zero sample-bus source gaps or overflow.
- Its `Tests/Host/storage_integrity/test_logger_storage.c`, `run_storage_integrity.py`: link actual
  producer sources into the existing real LoggerBus→LoggerTask→codec→FatFs→diskio delayed-DMA
  chain; build both default and explicit diagnostic macro configurations; retain prior corruption,
  storage-fault, 200 Hz startup and finite-overload recovery cases.
- `tests/test_storage_integrity.py`: generated-header defaults, exact decoder matching, critical
  records, first START timestamps, complete task IMU cadence, sequence/CRC/no-overflow checks,
  30/120 s duration comparison, and machine-readable size/record report.
- `tools/import_reference_components.py`: register the new Host fixture as FCCG-owned for reference
  re-import; runtime config remains the existing FCCG-owned source of truth.
- `docs/PREFLIGHT_LOGGING.md`, `docs/README.md`, this report: policy, operational instructions and evidence.

### Exact generated-project comparison

Reference project is actually generated below `tests/.pytest-sparse-0916e/storage-integrity0`.
The same selected-stream policy is used in both configurations. Size workload: 100 Hz IMU/native
attitude, 25 Hz native Baro, 12.5 Hz native GNSS, 50 Hz modeled navigation outputs, 1 Hz low-rate
status; no selected standalone magnetometer. 20 s FLIGHT then 1 s existing landing grace.
The navigation outputs and device source values are Host models; this byte-integrity workload
is not presented as a physically meaningful navigation golden trajectory.

| Mode / preflight | Whole file bytes | Whole records | Preflight bytes including header | Preflight records |
| --- | ---: | ---: | ---: | ---: |
| Normal / 30 s | 1,679,603 | 15,303 | 10,140 | 190 |
| Normal / 120 s | 1,696,523 | 15,573 | 27,060 | 460 |
| Diagnostic / 30 s | 2,623,263 | 25,745 | 923,244 | 10,294 |
| Diagnostic / 120 s | 5,385,183 | 56,390 | 3,685,164 | 40,939 |

120 s preflight bytes decrease by **99.27%**. Extra waiting only adds retained low-rate status:
normal IMU_NATIVE/IMU_CORRECTED/HW_QUAT_NATIVE remain 2,000 records each, BARO_NATIVE 500,
GNSS_NATIVE 250 for both durations. First record timestamp equals START for each; mission IMU
samples exactly match range(START, LANDING, 10000). All four runs have zero record-sequence gaps,
zero LoggerBus overflow, intact CRC/framing, one successful session and safe finalization.
No audit resynchronization or sequence renumbering is used.

The comparative fixture is explicitly 100 Hz. An exploratory 200 Hz combined diagnostic workload
with the delayed-card model exceeded the existing queue near START; this was not hidden or treated
as a pass, and queue capacity was not enlarged. Diagnostic logging remains bounded by real SD latency
and stream load. The independent existing 200 Hz startup fixture passed its normal zero-drop case;
its intentional overload remains observable and recovers with valid CRC/framing. Neither result
certifies all possible 200 Hz target/card workloads.

### Commands and acceptance

All temporary/generated/build output is below tests; test PYTHONDONTWRITEBYTECODE=1,
QT_QPA_PLATFORM=offscreen, TEMP/TMP point below tests. No reference firmware or other source tree
is modified by FCCG generation/testing.

```powershell
python -m pytest tests/test_storage_integrity.py -q -x --basetemp=tests/.pytest-sparse-0916e -o cache_dir=tests/.pytest_cache/sparse0916
& tests/.pytest-sparse-0916e/storage-integrity0/Tests/Host/run_tests.ps1
python -m pytest -q --basetemp=tests/.pytest-work-closeout0916 --ignore-glob='tests/.pytest-runtime*' --ignore-glob='tests/.pytest-sparse-*' --ignore-glob='tests/.pytest-env-*' -o cache_dir=tests/.pytest-cache/closeout0916
```

Focused storage: **11 passed in 69.97 s**.
Generated Host: **67 executables, 14,484 checks, 0 failures**, 8 positive compile cases,
16 expected compile rejections; all storage cases pass. Full pytest: **386 passed, 1 skipped in 816.00 s**.
The one skip is `tests/test_prompt_acceptance.py:287`: its read-only reference firmware
working tree is not clean (the test labels this "task is still active"). No reference files
were changed; this comparison is not claimed as a pass.
The complete suite includes logging streams, generation, decoder/SSLOG, algorithms and frozen
C trajectory/golden checks. Golden fixtures were not modified.

Release and Debug were also built from this generated project with Arm GNU Toolchain 14.3,
using the existing Make graph and strict first-party warnings:

```powershell
# Working directory: tests/.pytest-sparse-0916e/storage-integrity0
D:/msys64/ucrt64/bin/mingw32-make.exe -j4 SHELL=cmd.exe CONFIG=Release all stack-report memory-report artifact-check
D:/msys64/ucrt64/bin/mingw32-make.exe -j4 SHELL=cmd.exe CONFIG=Debug all stack-report memory-report artifact-check
```

Both commands exit 0. Each configuration supplies 138 .su files plus linked-ELF analysis;
all eight enabled tasks (including Idle) pass their stack budgets. Artifact checks verify
ELF/MAP/BIN/HEX, FLASH, main SRAM, CCMRAM and zero heap symbols.

| Configuration | FLASH bytes | Main SRAM bytes | CCMRAM bytes | Minimum task stack margin |
| --- | ---: | ---: | ---: | ---: |
| Release | 261,304 / 524,288 | 78,032 / 131,072 | 51,064 / 65,536 | 256 bytes (Idle) |
| Debug | 278,840 / 524,288 | 78,048 / 131,072 | 51,064 / 65,536 | 256 bytes (Idle) |

Release ELF SHA-256: `fe0588625ca6e293445cde623ae35eec2ac86c985729fbc797717bf71baa332e`.
Debug ELF SHA-256: `611bd41b843f3baa6752ded893664142ffba7fb562cee3e1898092d4ca7e2d74`.
Stack budgets are static bounds, not measured hardware high-water marks.

Evidence:
- `tests/.pytest-cache/target-release-closeout0916.log`, `target-debug-closeout0916.log`
- Generated `build/FCCG/SilverStar_F407/{Release,Debug}/stack-budget.json` and ELF/MAP/BIN/HEX
- `tests/.pytest-cache/sparse0916-final.log`
- `tests/.pytest-cache/host-closeout0916.log`
- `tests/.pytest-cache/full-closeout0916.log`
- `tests/.pytest-sparse-0916e/storage-integrity0/build/FCCG/Host/Tests/StorageIntegrity/`:
  `integrity.log`, four preflight-*.sslog files and `preflight-comparison.json`.

No board flash, physical SD, GNSS-origin convergence or flight acceptance is claimed. Real target
START scheduling, sensor rates and card latency remain hardware validation items. FLP's separate
exact synthetic import/replay acceptance is recorded in its own VALIDATION.md.
`git diff --check` passes; protocol/schema/version and protected algorithm files are outside the diff.

<!-- closeout-git-begin -->
### Final Git snapshot

Tracked diff (new files are listed separately by status):

```text
 VALIDATION.md                                      | 180 +++++++++++++++++++++
 docs/README.md                                     |   1 +
 .../payload/System/User/system_user_config.h       |  10 +-
 .../storage_integrity/run_storage_integrity.py     |  18 +++
 .../Host/storage_integrity/test_logger_storage.c   |  54 +++++--
 tests/test_storage_integrity.py                    |  61 ++++++-
 tools/import_reference_components.py               |   1 +
 7 files changed, 313 insertions(+), 12 deletions(-)
```

```text
 M VALIDATION.md
 M docs/README.md
 M plugins/builtin/silverstar_core_0_0_10/payload/System/User/system_user_config.h
 M plugins/builtin/silverstar_core_0_0_10/payload/Tests/Host/storage_integrity/run_storage_integrity.py
 M plugins/builtin/silverstar_core_0_0_10/payload/Tests/Host/storage_integrity/test_logger_storage.c
 M tests/test_storage_integrity.py
 M tools/import_reference_components.py
?? docs/PREFLIGHT_LOGGING.md
?? plugins/builtin/silverstar_core_0_0_10/payload/Tests/Host/storage_integrity/test_sparse_preflight.h
```
<!-- closeout-git-end -->


## 2026-09-14 — Protocol GUI mapping and touch-scrolling closeout

Scope: GUI/helper, translation strings, GUI tests and documentation only. The initial working
tree was clean. No model/schema, generator semantics, builtin payload, firmware runtime, algorithm,
KF6/INS/GNSS, log format/semantics, protocol wire, version, commit or push was changed.

<!-- touch-git-snapshot -->
### Modified files and Git snapshot

- `VALIDATION.md`
- `docs/GUI_STYLE_GUIDE.md`
- `src/silverstar_fccg/i18n/en_US.json`
- `src/silverstar_fccg/i18n/zh_CN.json`
- `src/silverstar_fccg/ui/main_window.py`
- `src/silverstar_fccg/ui/pages/base.py`
- `src/silverstar_fccg/ui/pages/build.py`
- `src/silverstar_fccg/ui/pages/components.py`
- `src/silverstar_fccg/ui/touch_scroll.py`
- `src/silverstar_fccg/ui/widgets.py`
- `tests/test_protocol_gui_mapping.py`
- `tests/test_touch_scroll.py`

`git diff --stat` (tracked files only; new files are listed above):

```text
 VALIDATION.md                              | 104 +++++++++++++++++++++++++++++
 docs/GUI_STYLE_GUIDE.md                    |  16 +++++
 src/silverstar_fccg/i18n/en_US.json        |   1 +
 src/silverstar_fccg/i18n/zh_CN.json        |   1 +
 src/silverstar_fccg/ui/main_window.py      |   2 +
 src/silverstar_fccg/ui/pages/base.py       |   2 +
 src/silverstar_fccg/ui/pages/build.py      |   3 +
 src/silverstar_fccg/ui/pages/components.py |  27 +++++++-
 src/silverstar_fccg/ui/widgets.py          |   3 +
 9 files changed, 157 insertions(+), 2 deletions(-)
```

`git status --short`:

```text
 M VALIDATION.md
 M docs/GUI_STYLE_GUIDE.md
 M src/silverstar_fccg/i18n/en_US.json
 M src/silverstar_fccg/i18n/zh_CN.json
 M src/silverstar_fccg/ui/main_window.py
 M src/silverstar_fccg/ui/pages/base.py
 M src/silverstar_fccg/ui/pages/build.py
 M src/silverstar_fccg/ui/pages/components.py
 M src/silverstar_fccg/ui/widgets.py
?? src/silverstar_fccg/ui/touch_scroll.py
?? tests/test_protocol_gui_mapping.py
?? tests/test_touch_scroll.py
```
<!-- /touch-git-snapshot -->

### Cause and repair

Protocols_Set previously used Qt findData(selected_tuple) and max(0, index), conflating a failed
mapping with a genuine None selection. A missing plugin/profile therefore silently looked like
"not used". It now normalizes selection and tuple/list itemData to string pairs and compares
items explicitly. An unmapped existing selection gets a disabled, localized unavailable item,
tooltip and validation marker while retaining its identity. Signal connections are made only
after restoration; refresh leaves ProjectModel intact. Existing availability, transport and
logging-enable handling is unchanged.

The current PySide6 6.10.1 probe returned list itemData and successfully matched an equal fresh
tuple using findData. Thus the exact field-only QVariant failure was not reproduced here;
tests explicitly simulate a failed Qt lookup and exercise both tuple and list representations.
The proven defect is GUI failure-to-None fallback. No underlying model corruption was observed
or repaired; genuine model None and valid telemetry/maintenance/logging selections are all tested.

Touch coverage: all ScrollableLocalizedPage viewports (the normal configuration pages),
SmoothTableWidget/EngineeringTable including plugin and configuration tables, navigation list,
build summary/detail logs, and StandardComboBox popup views. The local helper only registers
QScrollArea, ordinary item views and text views; it excludes headers and leaves pixel-scroll modes,
mouse handlers, inputs, sliders and graphics alone. No cross-repository runtime dependency added.

### Executed checks

- `python -B -m pytest tests/test_gui_smoke.py tests/test_service_gui.py -q --basetemp=tests/.pytest-work-touch-focused -o cache_dir=tests/.pytest-cache-touch`: **14 passed**, 94.94 s.
- `python -B -m pytest tests/test_protocol_gui_mapping.py tests/test_touch_scroll.py -q --basetemp=tests/.pytest-work-touch-new2 -o cache_dir=tests/.pytest-cache-touch`: **25 passed**, 9.41 s.
- Full `python -B -m pytest -q --ignore-glob='tests/.pytest-runtime*' --basetemp=tests/.pytest-work-touch-full -o cache_dir=tests/.pytest-cache-touch`: **382 passed, 1 skipped**, 665.03 s; includes existing configuration/protocol/generation regression tests.
- Additional final Protocol tests (three model-None cases were added after full-run collection): `python -B -m pytest tests/test_protocol_gui_mapping.py -q --basetemp=tests/.pytest-work-touch-mapping-final -o cache_dir=tests/.pytest-cache-touch`: **10 passed**, 9.47 s.
- GUI compileall, `git diff --check`, static scroll inventory and protected-source diff audit: **passed**.

New tests exercise all three Protocol categories, tuple/list itemData, simulated QVariant miss,
missing-profile display, zero refresh signals, unchanged ProjectModel, model None, real-window
scroll coverage, excluded input/graphics/header targets, preserved mouse row selection/scrollbars,
and synthesized finger swipes that actually move page/list/table/text scrollbars.

Runs use offscreen Qt and repository-local test output directories. The full-run log and source
scope audit are `tests/.pytest-cache-touch/full.log` and `scope-audit.json` under the same directory.
The original full collection attempt encountered nine access-denied errors in existing
`tests/.pytest-runtime*` generated-cache directories; its log is `collection-error.log`.
Only these cache directories were excluded on retry; no source test was removed or disabled.

### Remaining validation limits

The existing reference-payload test skips when read-only reference firmware provenance reports
an unclean working tree. Its legacy message "task is still active" does not establish another
agent's status. No reference firmware was edited. No physical CF-33 touch/stylus, target hardware,
flash or new numerical algorithm acceptance is claimed. No failing executed GUI regression remains.


## 2026-09-12 — Algorithm actual parameters / decoder 1.2 closeout

Baseline commit: `b2e05fb`. This working-tree change keeps SilverStar Platform **0.0.10**;
Project format is **12**, parameter declaration schema is `silverstar.algorithm-parameters/1.0`,
and `.ssdecoder` package/project-semantics are **1.2**, rejecting package 1.1.
The selected Pure INS/KF6 manifests declare **22 actual parameters** (1 + 21).
See [parameter inventory and semantics](docs/ALGORITHM_PARAMETERS.md).

### Executed checks

- Full pytest: **356 passed, 1 skipped**, **692.14 s**. The skip at
  `tests/test_prompt_acceptance.py:287` is the pre-existing reference-payload synchronization
  check: the read-only reference firmware working tree is not clean. Its legacy message says
  “task is still active”; this is not an inspection of other Codex tasks.
- Focused parameter/schema/project/UI/decoder/documentation regressions: **58 passed**.
  An additional **8 passed** cover strict decoder schema-lock validation and invalid values.
- Release and Debug: `all artifact-check stack-report` passed using Arm GNU Toolchain
  **14.3.Rel1**, compiler **14.3.1 20250623**. Both have **138 .su files** and all **8 static tasks**
  meet the linked-ELF stack budget. Heap symbols: **0**.
- Architecture: **270 checks, 0 failures**. The new parameter header is explicitly registered
  in the reviewed thin-glue set; Make/EIDE source-graph consistency remains enforced.
- Power of Ten: **5,930 checks, 94 first-party C files, 2,223 functions**, passed.
- Host: **67 executables, 14,484 checks, 0 failures, 8 compile-pass cases and 16 expected
  compile failures**. Golden logs use the actual C codec; storage byte audit and delayed-DMA
  fixtures also passed against the schema-1.2 package. Negative missing-noise cases explicitly
  remove generated actual noise before testing absence; capability assertions are retained.
- Release static analysis passed with the original analyzer flags and policy intact.
- Reference importer ownership audit passed for both parameter declarations/algorithm sources,
  system/task bindings, Host fixtures and decoder/architecture tools. Reference files were read only.
- New page rendered and inspected in Simplified Chinese/English and Light/Dark; it precedes
  Hardware Connection. Parameter edits preserve advanced-section disclosure; old widgets are
  hidden before deferred deletion. Save/reopen/Save As and Dirty behavior are covered.

### Default numerical equivalence

The old project sources and full Host Golden were frozen under `tests/artifacts/parameters24/baseline`
before firmware bindings changed. The same C trajectory fixture runs against those frozen old sources
and the new generated default project with GCC **16.1.0 x86_64-w64-mingw32**, C11, `-O2`.
It covers **2,000 IMU steps / 1,000 updates**, quaternion, Pure INS position/velocity, KF6 state
and complete covariance, with GNSS/barometer updates. **52,045 float outputs**, **5,005 lines**,
**1,109,911 normalized bytes** are **bit-identical**; there is no rounding-tolerance exception.
Changing saved gravity/P0/process sigma/GNSS sigma/barometer sigma changes the compiled trajectory.

Trajectory SHA-256: `ad64bc875b4ec87f0bafdd65e868bb99822b79dfe79fc0debf13ec9484486aa1`.

Only configuration references and the KF6 initialization/reset constants changed. Mathematical
equations, structure dimensions, operation/update order, fusion timing and GNSS reacquisition policy
were preserved. Pure INS mechanization source is unchanged. Logger, Calibration, Alignment,
Board/MCU/hardware binding, AIR and SSLOG record-layout sources were not changed. FLP/GSHC were not modified.

### Target resources and stack budgets

| Configuration | FLASH used / available | Main SRAM used / available | CCM used / available |
|---|---:|---:|---:|
| Release | 261,232 / 524,288 B | 78,032 / 131,072 B | 51,064 / 65,536 B |
| Debug | 278,816 / 524,288 B | 78,048 / 131,072 B | 51,064 / 65,536 B |

| Task | Configured bytes | Release worst known / margin | Debug worst known / margin |
|---|---:|---:|---:|
| Device | 2048 | 1496 / 552 | 1320 / 728 |
| INS | 3072 | 2040 / 1032 | 1808 / 1264 |
| Estimator | 4096 | 1964 / 2132 | 1868 / 2228 |
| Flight | 4096 | 3428 / 668 | 2292 / 1804 |
| Logger | 3072 | 1376 / 1696 | 1368 / 1704 |
| Serial | 6144 | 4200 / 1944 | 2928 / 3216 |
| Telemetry | 4096 | 1980 / 2116 | 1660 / 2436 |
| Idle | 512 | 256 / 256 | 256 / 256 |

Release ELF SHA-256: `9fceecd3b5db4b42a1046205355bca5aebf3e3245a9040dab2f0f98b3337d703`.

Debug ELF SHA-256: `5d62999c65ee93fddb778e2cb832b34d7b58fa71a0577e8ca5fe5dc3257f30be`.

Record Catalog SHA-256 (equal to pre-change baseline): `a3fb7bd69a6f9d13a99e0654a9a74c14f057d4c0625af68da913884a427f5795`.

Project semantics SHA-256: `cccae38b7e2e365a1918a7f6ef5829984130ab5bdedba571e056bff8bbf473e6`.

Generation profile SHA-256: `2edc759219fc2b23bd20512895d40c001559ffb18253426ea86980cc11140de4`.

### Scope and reproduction

Acceptance outputs/logs/screenshots remain under `tests/artifacts/parameters24/`; temporary helpers
are under its ignored `helpers/` directory. The reproducible numerical regression is
`python -B -m pytest tests/test_algorithm_parameters.py`; run `python -B -m pytest -q` for the suite.
Generate a fresh reference project, then run Release/Debug `all artifact-check stack-report`,
`architecture-check power10-check host-tests` and Release `static-analysis` from its directory.
Development outputs and compiler temporary files must stay below repository `tests/`.

Normal Apply preserves project-owned C. Older generated projects must deliberately port the
documented bindings or use a fresh output before relying on actual parameter configuration.
No target flashing, hardware timing/flight acceptance or live FLP compatibility run is claimed.
All edits remain uncommitted for review. No shutdown was requested or executed in this round.

---

## Historical snapshot — 2026-09-12 Logger startup burst closeout (prompt 22)

以下保留上一轮验收时的版本与结果；本轮算法参数 / decoder 1.2 验收见文首。

本轮基线为 `90c14dc`，开始时工作区干净。只修改FCCG；外部reference、FLP/GSHC均未写入。
SilverStar 0.0.10、AIR M0、Maintenance/SSLOG 0.0、`.ssdecoder`/Project Semantics 1.1不变。
SDIO、FatFs、Storage/LogSink实现、SSLOG IDs/layout/CRC与独立审计判定均未改动。
当前结论仍是软件验证，不能替代SS0.5实卡验收。

## 根因与证据边界

旧Logger在session成功打开后仍无条件delay 10 ms；普通周期流在header、decoder和集中自检报告
落盘前已可入队。报告尚未完成时，旧代码还会关闭已成功打开的session并等待重开。这些窗口
使单个低优先级consumer暂时无法跟上启动producer。修复不通过增加队列或调整飞控任务优先级完成。

`tests/artifacts/startup22/baseline`保存修改前生成的生产源码及Release/Debug产物。将本轮相同
多流Host输入/延迟模型接到旧生产Logger/Bus，移除fixture中旧API不存在的新诊断断言，仅将旧版本
验收期待改成“有真实drop”，复现 **629次overflow、3段gap/629 IDs**，CRC/length/framing仍正确。
这次比较保留旧writer，未给旧代码添加bootstrap。原始日志为`baseline-startup-repro.log`。

用户提供的新实机日志摘要为CRC/length/sync/unknown均0、START后连续、启动3段gap/12 IDs、
logger overflow39、IMU overflow0；本轮没有该BIN与匹配decoder的本地输入，因此**没有复测这组39/12**，
也不声称629就是该实机的丢失量。日志可能受首条记录前drop、末条STATS和采集窗口影响；
仅凭摘要无法逐条归因。上一轮字节修复与本轮启动队列修复必须分开判断。

## 实现与持久所有权

- `APP/Src/logger_bus.c` / `APP/Inc/logger_bus.h`：唯一BOOTSTRAP/STREAMING_READY准入状态；
  普通周期流未准入计数与实际accepted、overflow、state/capacity拒绝分开。关键事件/descriptor/
  Calibration/Alignment/Mission/Initial State保持可入队，producer无等待。
- `APP/Src/logger_task.c` / `APP/Inc/logger_task.h`：成功open立即drain；保留pending自检的session；
  decoder排空后补启动System/Device/Algorithm/Stream配置，写完整自检并sync后，在临界区确认两队列
  为空才开放streaming。已排队BOOT/关键记录仍保持原FIFO顺序，满队列仍可消费并重试decoder。
  START原有配置/Initial State记录保留。Mission config纳入关键flush批次。
- 增加iteration/drain、open尝试/失败/session、append/flush/serialize/close失败、discarded_bytes、
  write count/total/max、ready时间内部诊断。Storage原有health与延迟诊断保留。64-bit延迟更新受保护。
  capacity拒绝也包含尚未提交的SystemConfig批次预检；真正drop仍只来自queue overflow，并沿用原序号
  增量算法。没有成功写入后重排sequence、重放不确定aggregate或将错误收尾伪装成finalized。
- 修改的C/H、Host fixture、runner及两份包内Storage文档已在既有`fccg_owned_files`/owned-doc映射中；
  本轮扩展`test_storage_sources_survive_reference_reimport`验证其逐字节回导保留。
  这些builtin路径本来就是FCCG-owned真源，不是只修一个生成工程。没有运行外部reference写操作。

## 真实C writer与Host模型结果

最终运行文件位于`tests/artifacts/startup22/final`；日志见`final-host.log`和`final-storage.log`。
实际LoggerBus → LoggerTask → LogSink → Storage → FatFs → diskio → 延迟DMA模型 → 文件读回 →
真实C codec与严格metadata审计；未用Python重写writer布局。后补的恢复断言要求step 1500后drop不再增长。

| 模型 | 写出records | overflow / gap IDs | gap段数 | normal/estimator HWM |
|---|---:|---:|---:|---:|
| 旧生产代码，同一200 Hz多流启动输入 | 291037 | 629 / 629 | 3 | 64 / 8 |
| 正常200 Hz多流启动与START | 291359 | 0 / 0 | 0 | 62 / 8 |
| 相同多流输入，START后有限过载 | 291367 | 517 / 517 | 2 | 64 / 26 |
| 原有100→500 records/s慢卡模型 | 40079 | 0 / 0 | 0 | 55 / 2 |
| 慢卡+有限过载 | 40121 | 558 / 558 | 保留真实缺口 | 64 / 32 |
| 满critical启动队列+有限过载 | 40188 | 692 / 692 | 保留真实缺口 | 64 / 32 |

所有模型存活记录的header/record CRC、length、framing、unknown和尾部未校验字节均0错误；
sequence reorder=0，匹配生成的decoder。每个文件仅一个decoder descriptor。没有resync取得通过。
正常/过载默认多流均保留1个Calibration、Alignment、Mission config和Initial State，2组SystemConfig
（bootstrap与START）；故意过载的drop与最终STATS严格对应，并恢复至结束不再增加。

默认多流模型：200 Hz IMU/BARO/HW quaternion、25 Hz GNSS、50 Hz Power；START前保留默认流策略，
START后加入IMU corrected、100 Hz INS相关记录、生成配置中的Estimator/KF抽取、GNSS/Baro量测和
STATS/Health/Telemetry诊断。自检报告延迟完成、session open注入300 ms停顿，运行40000个5 ms步，
约200秒。Device/Flight模拟工作计数各40000，普通生产路径无等待；IMU overflow fixture值为0。
这不是完整FreeRTOS调度器，也未执行真实传感器/Calibration/Alignment求解；真实FlightTask的NONE结果
映射由既有lifecycle Host测试另验，实际IMU总线overflow与任务执行时序仍须上板确认。

默认模型bootstrap suppression=351，绝不计作drop/sequence。session/open尝试=1/1，首个task delay=2 ticks，
没有成功open后的10 ms暂停。normal/overload的append/flush/serialize/close/storage错误及aggregate discard均0。
Storage最大write/sync=30000/8000 us；sink write平均正常14895 us、过载14893 us；最大Logger迭代316120 us
含300 ms开文件注入，不能独立当作CPU饥饿时间。模型ready绝对时刻1110520 us，包含测试准备时钟。
原有慢卡模型最大write/sync=90000/26000 us、最大迭代126260 us；bootstrap suppression=22。

## Queue与RAM/FLASH

队列深度 **64/32 → 64/32**，`sizeof(FlightLogRecord)=224` bytes；分别14336/7168 bytes，合计21504 bytes，
队列RAM增量0。aggregate仍4096 bytes、DMA bounce仍512 bytes。正常多流峰值62/8，对应空余2/24槽；
这仅覆盖本次延迟/负载模型，普通队列余量较小，实卡需测最大延迟与HWM，不能宣称任意卡均零丢弃。

| 构建 | FLASH基线→本轮（Δ） | main SRAM基线→本轮（Δ） | CCMRAM |
|---|---:|---:|---:|
| Release | 262112→261232（-880） | 77944→78032（+88） | 51064不变 |
| Debug | 278040→278808（+768） | 77960→78048（+88） | 51064不变 |

Release剩余FLASH263056、main SRAM53040、CCMRAM14472 bytes；Debug分别245480、53024、14472。
无heap符号。编译器Arm GNU 14.3.Rel1；Release/Debug全部8个静态task含Idle的`.su`+ELF预算通过。
Logger配置3072 bytes，最坏已知栈Release1376 / Debug1368，余量1696 / 1704；所有task均满足256-byte
最小静态余量。它们不是运行时HWM/MSP嵌套的实测值，assert/stack overflow/HardFault保护保持开启。

Release ELF SHA-256：`6baa96224d0fc008981e6c1723edc31a7ad3bc7db4f780a8d65a3feb858e1e7e`。
Debug ELF SHA-256：`2663072c207e6bbea45b3fa7eab2c60daf0f0fdd03b72d707d5ae2c8dd0661e3`。

## 执行门禁与交付状态

- fresh默认SS0.5 Generate：通过；产物位于本仓库tests下，不触碰外部参考工程。
- compileall `src main.py tools`：通过，cache重定向至tests内。
- 专项pytest（Storage/文档）：16 passed，57.17 s。
- 全量pytest：**334 passed、1 skipped，761.06 s**，退出码0；一次被中断的运行不计通过。
  跳过项为`tests/test_prompt_acceptance.py:287`的只读参考工程验收，触发条件是外部参考工作树不干净；
  该测试的“task is still active”提示不等于Codex任务状态查询，
  关机条件必须另用任务工具核对。其余门禁不依赖修改该外部参考工程。
- Release / Debug + Artifact + stack-report：均通过。
- Host：67 executables、14484 checks、0 failures；8 compile-pass、16 expected compile-failure。
  随后增加纯Host恢复断言并再次执行完整Storage runner：通过。
- Architecture：270 checks、0 failures。Power of Ten：5930 checks、94 first-party C、2223 functions，通过。
- Release `-fanalyzer`：完整独立目录编译/链接通过，未发现warning；退出码0。
- 源码确定性导出：两份ZIP逐字节一致，849个源文件；已检查build/acceptance/cache与编译产物排除，
  Host/Target真实源码及corruption fixture保留。最终文档收尾后重新导出，hash留在tests内export-result.json，
  避免把自身archive hash写回归档内容造成循环。
- `git diff --check`：通过。20个跟踪文件修改，均在FCCG内，修改保持未提交；未commit/push/tag/release。

仍需实机：SS0.5单IMU/GNSS/telemetry，NONE及所选procedure，反复preflight/alignment/START/正常收尾；
至少两次或两张卡，保留BIN、匹配decoder、独立审计、START前后及停止时诊断、任务HWM和最大存储延迟。
正常目标必须为logger/IMU overflow、gap、CRC/length/resync全0；故意过载仅允许真实drop且须恢复。
无真实硬件结果时不关闭该验收项；没有声称EIDE builder、烧录、飞行或其他MCU已通过。

# Validation — 2026-09-06 SSLOG storage integrity repair

本轮依据20号prompt实现并验证FCCG内部修复，基准HEAD：`346756111e6f6a9050dcfc7bb206117fae93b9e5`。
所有开发/测试写入均在FCCG内；生成、编译、日志、临时文件与源码包在`tests/artifacts/storage20/`
及仓库已有的tests临时目录。没有修改外部参考固件、FLP、GSHC，没有commit/push/Tag/Release。

## 根因与证据边界

- 可复现的底层缺陷：原SS0.5 `sd_diskio.c`禁用scratch，直接把任意FatFs byte pointer交给
  word-aligned SDIO DMA。FatFs跨partial/full sector后，即使应用buffer原先对齐，传递指针也可能偏移。
  原禁用的scratch-write分支还等待READ completion；原超时/错误completion和CTRL_SYNC的结果处理不可靠。
- 使用真实FatFs、原diskio与延迟到completion才消费buffer的word-DMA Host模型，完成10000次指定长度写入。
  以32-byte aligned buffer、512-byte读取隔离读侧影响，旧实现仍在offset **172032**（sector 336起点）
  字节不一致；完成写入时已提交5次未对齐DMA。该基线是期望失败，保留`baseline-integrity.log`。
- 独立的上层缺陷：partial write失败后Close再次尝试整个aggregate，可能重复已经写入的前缀。
  现已禁止错误关闭重放、禁止writer在不确定write/sync后重开疑似损坏文件，并区别fault与finalized。
- Queue增长与byte corruption分开处理：原关键记录逐条sync会放大等待，现合并排队中的critical批次，
  以queue空或首条20ms deadline触发；已有storage操作可延迟实际完成。普通/Estimator容量仍是64/32，
  aggregation仍是4096 bytes，任务优先级不变。增加HWM、accepted/dequeued、最大write/sync/迭代间隔诊断，
  writer按新观察到的累计overflow推进sequence，保留明确gap。
- 额外复现启动满队列停滞：SD打开后Required decoder descriptor入队失败会关闭session，唯一consumer
  因而始终无法排空queue。使用已修复diskio但保留旧Logger启动逻辑的独立基线，模型超过300秒完成期限
  并按预期失败（`baseline-startup-queue.log`）。现保持session打开，在dequeue后补入descriptor。
- **没有拿到SS0014.BIN及精确匹配decoder，也没有真实SDIO/TF卡上板。** Prompt中1152 CRC candidates、
  50 oversize、1222 gaps、overflow 110和START后3.318ms均为用户提供的历史事实，不能称为本轮重新测得。
  Host模型证明确定的软件契约缺陷，不单独证明SS0014所有损坏和溢出的硬件成因。

## 修复与所有权

`tools/reference_overlays/storage/`持有Board diskio/BSP覆盖；固定512-byte main-SRAM bounce每次传1 sector，
匹配completion且card-ready后才复用，等待有30秒整体边界。错误/超时锁存不可用直到reset，迟到IRQ不能解锁。
FatFs仍拥有partial sector与RMW，CPU源buffer不要求4/32-byte alignment，F407没有DCache处理。
Logger/Storage/LogSink C/H、Host/Target fixtures、离线audit均在importer的FCCG-owned/overlay映射中。
正常Apply仍保留project-owned源文件；老项目须新生成或明确移植这些修复。自定义CubeMX glue须独立移植和验证。

SSLOG payload/Record ID/version/framing/CRC、AIR M0、Maintenance 0.0、decoder 1.1、平台0.0.10均未变化。
MISSION_CONFIG仍是91-byte payload / 119-byte record，没有补齐。
共同Calibration契约与HEAD逐字节一致，SHA-256：`ffb8013cb9e1f254872255f8e4dc86abd374af5199ece39963fc90a0301f1f40`。

## 实际执行的质量门

| 项目 | 本轮结果 |
| --- | --- |
| 默认verified SS0.5 Generate | passed；最终输出`tests/artifacts/storage20/final`，只生成时不编译 |
| Release / Debug all + Artifact + stack-report | passed；两个配置均无heap symbols，所有静态task及Idle预算通过 |
| Host Tests | 67 executables、12423 checks、0 failures；8 compile-pass、16 expected compile rejection |
| Architecture | passed，270 checks；首次注释中的provider单词触发既有扫描，修正注释后通过 |
| Power of Ten | passed，5915 checks、94 first-party C files、2216 functions；拆分Logger诊断/周期flush保持函数行数限制 |
| `CONFIG=Release static-analysis` | passed，第一方严格warnings + `-fanalyzer`；最终Logger改动后增量重跑通过 |
| 额外ARM `-fanalyzer -Werror` | diskio、BSP callback glue、Target bench分别编译通过，补足vendor分类默认不加fanalyzer的边界 |
| 初次完整 `python -m pytest -q` | **333 passed, 1 skipped**，708.83 s |
| 启动queue修复后完整回归 | **333 passed, 1 skipped**，657.08 s，`pytest-full-final.log` |
| 启动queue修复定向回归 | **9 passed**，35.64 s |
| storage/docs/runtime定向 | **30 passed**，78.79 s；覆盖fixture/forensic audit及持久化修改 |
| `python -m compileall -q src main.py tools` | passed；缓存限定`tests/artifacts/storage20/pycache` |
| deterministic source export | 两次独立ZIP逐字节相同；保留真实unit/Host/Target/fixture源，排除build/tests临时与二进制产物 |
| `git diff --check` | passed |

唯一skip仍是`tests/test_prompt_acceptance.py:287`的只读外部reference工作树非clean，
提示`read-only reference firmware task is still active`。这是既有测试对外部工作树的保护，
不是对另一Codex任务是否完成的最终状态判断。没有为通过测试而改写外部reference。
首次完整pytest运行中调整了Logger函数组织及后续测试检查；启动queue修复后再次执行完整回归，
最终Host包含全部三个队列负载场景。

## Storage/Logger字节与队列结果

- 实际FatFs任意长度序列：1,2,3,4,7,31,60,88,91,119,127,255,256,257,511,512,513；
  源offset轮换1..31，跨512/4096，10000次小写与间歇sync，共**1668166 bytes**逐字节读回一致。
  无未对齐DMA提交。额外40000条真实C mixed records共**3850972 bytes**，header/记录逐字节重建、C CRC、
  sequence及EOF全部通过，不依赖resync。
- 读/写timeout、错误completion类型、提交失败以及CTRL_SYNC busy timeout共7种故障，每种单独进程，
  验证错误返回、initialize不能解锁、迟到callback不能复用scratch或发起新DMA。
- Target bench同样在Host实际FatFs模型中运行，返回Ok；此外完成ARM编译与fanalyzer。
  Target bench不在production SourceGraph，**尚未在真实硬件执行**。
- 真实LoggerBus→LoggerTask→LogSink→Storage→FatFs→diskio链路模拟START前约100 records/s、之后约500 records/s。
  正常模式accepted=40002、wire records=40004（含直接startup events），drop/gap=0；
  normal/estimator HWM=56/2，CRC全部正确、decoder三hash匹配、EOF无余字节。
- 故意向两个queue额外突发600条：accepted=40071，wire records=40073，**drop=531，gap records=531**，
  HWM=64/32；保留记录CRC全部正确、无sequence reorder，STATS计数精确对应gap。
  模型最大write=90000us、sync=26000us、Logger迭代=116060us，**这些是Host模型时间，不是实卡延迟**。
- lifecycle Host额外验证partial write只调用一次失败写，不在Close重放或重开；final sync失败不伪报finalized。
- 启动满队列加飞行中突发：accepted=40132、wire records=40134、drop/gap=671，
  Required decoder descriptor只出现一次且三hash精确匹配；全部记录CRC与EOF仍通过。
- synthetic fixtures覆盖512边界重复/缺1 byte、payload CRC翻转、oversized length、未解释sequence gap、extra tail，
  全部被严格审计拒绝；可选candidate scan只报告forensics，不改变pass/fail，也不修复输入文件。

## Release/Debug内存差值（bytes）

基线与修复使用相同默认Board/工程名/配置及Arm GNU 14.3.Rel1。

| 区域 | 基线 | 修复 | 差值 |
| --- | ---: | ---: | ---: |
| Release FLASH | 260864 | 262112 | +1248 |
| Release main SRAM | 77360 | 77944 | +584 |
| Release CCMRAM | 51064 | 51064 | +0 |
| Debug FLASH | 277192 | 278040 | +848 |
| Debug main SRAM | 77384 | 77960 | +576 |
| Debug CCMRAM | 51064 | 51064 | +0 |

main SRAM容量131072，CCMRAM容量65536，FLASH容量524288；均通过实际ELF/产物检查。
增加固定512-byte scratch、内部诊断和状态；queue/aggregate/task allocations不变。

| Task | 配置bytes | Release估计 / 余量 | Debug估计 / 余量 |
| --- | ---: | ---: | ---: |
| Device | 2048 | 1496 / 552 | 1320 / 728 |
| INS | 3072 | 2040 / 1032 | 1808 / 1264 |
| Estimator | 4096 | 1964 / 2132 | 1868 / 2228 |
| Flight | 4096 | 3428 / 668 | 2292 / 1804 |
| Logger | 3072 | 1376 / 1696 | 1344 / 1728 |
| Serial | 6144 | 4200 / 1944 | 2928 / 3216 |
| Telemetry | 4096 | 1980 / 2116 | 1660 / 2436 |
| Idle | 512 | 256 / 256 | 256 / 256 |

这是`.su`+linked ELF保守预算；不是实测HWM/MSP/IRQ nesting。最小要求256-byte余量继续满足。

## 仍需真实硬件与历史样本

按`docs/platform/details/STORAGE_AND_FLIGHT_LOG.md`执行verified SS0.5+已知良好卡：
preflight→NONE calibration→alignment→START→室内2–5分钟→正常停止，至少两次运行或两张卡，
保存前后诊断、HWM、BIN、精确decoder与独立audit JSON。对SS0014使用严格audit，必要时另加
`--scan-candidates`复核历史candidate统计。FLP能打开或GSHC正常不能替代TF文件CRC/字节验收。
本轮未flash、未执行EIDE、未上板/飞行；未声称其他MCU/自定义CubeMX的存储硬件支持。

下方保留历史验收快照，不将其测试数/硬件范围当作本轮新结果。

---

# Validation — 2026-09-05 final documentation alignment

本节是按19号prompt校对FCCG文档的实际验收快照。工作基准HEAD为
`5997babf0025a377f7bb9184da73a6da9e3f05c8`（修改栈大小，初始化灯等问题）。
采用用户替换后的docs作为基线，没有从Git恢复旧docs；没有commit、push、Tag或Release。

## 范围与结果

- FCCG应用规范入口：[docs/README.md](docs/README.md)；完整平台规范入口：
  [docs/platform/README.md](docs/platform/README.md)。平台当前为0.0.10，AIR M0、
  Maintenance/SSLOG 0.0、decoder package/project-semantics 1.1保持独立版本。
- 修正文档正文中的固定NOT_SELECTED/0x07、Reset后灯状态、仅instance 0、未来FCCG、
  Board通用storage/power/action归属、手工EIDE、默认Debug和旧构建路径等过期描述。
- 新增平台RUNTIME_SAFETY规范，根README/AGENTS/TARGETS链接统一入口；
  DOCUMENT_LIST包含详细规范与两组PDF/TEX。
- 代码仅修改`tools/import_reference_components.py`的包文档标注流程：通过WorkspacePolicy
  限定builtin根、拒绝文档越界、幂等标注package-local implementation note，指向当前平台规范。
  组件包文档不是第二套平台authority；Core包VALIDATION仅索引本根文件。
- 新增`tests/test_documentation.py`，检查内部相对链接、当前版本/Calibration旧说法、
  共同契约与索引、公式配对、包文档归属及重复标注不改时间戳。
- 没有修改固件C/H、AIR字段/命令/CRC、SSLOG Record或decoder schema。
  既有Calibration实现已经符合NONE常驻、四种mask、build门禁与真实事务语义，未做重构。

## 本轮实际执行

| 检查 | 实际结果 |
| --- | --- |
| `pytest tests/test_documentation.py tests/test_runtime_safety.py tests/test_stack_budget.py -q` | 26 passed，57.47 s |
| `pytest -q` | 324 passed，1 skipped，667.22 s |
| 最后文档/快照整理后，`pytest tests/test_documentation.py tests/test_runtime_safety.py::test_runtime_sources_survive_reference_import -q` | 7 passed，6.56 s |
| `compileall`：由`rg --files src tools tests -g '*.py'`列出受维护Python文件后逐文件编译 | passed，缓存仅在`tests/.pycache-docs19/` |
| `git diff --check` | passed |
| 文档链接、清单、公式检查 | passed；当前docs共52份Markdown，两组PDF/TEX；无网络依赖 |
| 共同Calibration契约 | 与GSHC同名文件逐字节一致 |
| 三份用户提供的历史文档 | SHA-256与本轮开始保存的基线一致，未改写历史版本 |

唯一skip为`test_reference_payload_sync_and_environment_templates_are_read_only`：
外部只读参考固件的working tree非clean，测试按现有规则报告
`read-only reference firmware task is still active`。本轮未修改、清理或重新导入该外部工作区。

完整pytest包含现有PySide6 offscreen GUI、生成/decoder、构建配置与安全回归。
定向runtime测试实际以Host GCC运行四种Calibration procedure mask及真实Telemetry命令路径，
并覆盖生产Indicator初始化与栈分析工具。没有单独重新运行生成固件的完整Host/SSLOG Golden、
ARM Release/Debug、EIDE构建、static-analysis/artifact或真实ELF stack-report门；
本轮没有运行时C变更，不能把下方历史结果当成本轮新执行结果。

日志保存在忽略的`tests/artifacts/docs19/pytest-full.log`及`pytest-final-docs.log`。
初次对整个tests树进行compileall遍历时遇到旧临时目录无法枚举提示，随后限定到
`rg --files`列出的受维护源码重新执行并通过；不将历史测试产物作为源码验收对象。

## 契约与保留证据

共同契约SHA-256：`ffb8013cb9e1f254872255f8e4dc86abd374af5199ece39963fc90a0301f1f40`。

| AIR calibration mask | 本次构建与运行行为 |
| --- | --- |
| 0x01 | 无采样procedure；boot/成功RESET自动NONE/Identity/READY，无需GSHC发送NONE |
| 0x03 | 默认NONE + OneFace；boot等待显式事务 |
| 0x05 | 默认NONE + SixFace；boot等待显式事务 |
| 0x07 | 默认NONE + OneFace + SixFace；boot等待显式事务 |

有采样procedure时，默认NONE通过真实CAL_START(NONE)选择/锁定active IMU、失效旧Alignment
并发布READY。非法mode为BAD_PARAM，合法但未编入为REJECTED，状态不允许为BAD_STATE，
互斥占用为BUSY，接受为OK；具体契约正文只由[共同文档](docs/AIR_CALIBRATION_CONTRACT.md)维护。

历史文件SHA-256：

- 0.0.7：`684a28da6d39b36f3aa5b660eca5cdb9e8b1ec91856b8d62545e1f3af57c4f02`
- 0.0.8：`96a45150466b79d9fd77d2df5045c736c7ea69b284f697145469c85164ec03d5`
- 0.0.9：`cf9d2a4df6e79a3ed9e644de2f594baef49e52fe6ea484e04c7eec968ae678a8`

## 仍待实机与Git状态

SS0.5冷启动/指示灯极性、反复AIR/Serial校准与对准/Reset、全部任务HWM、MSP与中断嵌套、
真实多设备失效切换、SD长写/掉电恢复、I2C/PWM电气路径和实际飞行验证仍待实测。
没有修改外部固件、GSHC或FLP，没有烧录或硬件结果声明。

变更保留在FCCG工作区：用户提供的新docs树、根文档、builtin文档备注、导入器及文档测试。
测试缓存/日志/编译产物均被忽略，未进入待提交文件。

---

以下保留此前runtime修复验收快照，执行范围和基准属于各自当时记录。

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

## 2026-09-12 shared algorithm-parameter closeout

Scope: generic `selection.ui_order` owner ordering, declarative `shared_key`, one shared GUI editor,
strict format-12 equality, and decoder required-FLP correction only. Platform 0.0.10, package and
project semantics 1.2, Record Catalog, AIR M0, Maintenance/SSLOG 0.0, firmware algorithm formulas
and timing remain unchanged. FLP was not modified.

Observed default generation resolves both `SYSTEM_INS_GRAVITY_MPS2` and
`SYSTEM_KF_GRAVITY_MPS2` to `9.779999733e+00f`; both decoder parameter sets contain binary32
`9.779999732971191`. Strict package verification reports package schema 1.2 and
`required_flp_minimum_version=0.0.2`.

| Check | Result |
|---|---|
| `python -m compileall -q src main.py tools` | PASS |
| builtin catalog scan and shared resolve/generate script | PASS (36 plugins; INS then KF6; equal gravity) |
| default SS0.5 assembler generation below `tests/.runtime-shared` and `.ssdecoder` strict verify | PASS |
| `python -m pytest -q tests/test_algorithm_parameters.py tests/test_gui_smoke.py` | ENVIRONMENT BLOCKED before collection: PySide6 loader requires unavailable `libGL.so.1` |
| Release / Debug / Host Tests / Architecture Check / Power of Ten / static analysis | ENVIRONMENT BLOCKED: generated Windows gates require unavailable `powershell` (and target toolchain) |
| frozen 52,045-float numerical trajectory | ENVIRONMENT BLOCKED: fixture requires `D:\\msys64\\ucrt64\\bin\\gcc.exe`; test remains present and now checks shared-only 9.81 change plus restored-default identity |

No GUI screenshot was captured because the same missing `libGL.so.1` prevents starting PySide6 in
this container. No hardware/toolchain/flight validation is claimed.
