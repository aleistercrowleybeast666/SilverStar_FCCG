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
