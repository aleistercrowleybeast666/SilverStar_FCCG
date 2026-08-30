# Validation — 2026-08-30 optional protocols and firmware task gating

This file records only validation actually performed against the current FCCG source tree for
project-format 11, independently optional telemetry/maintenance/logging protocols, and generated
firmware task/source gating. The result remains an internal software validation result; it is not
a hardware-flash, electrical, or flight qualification.

## Environment

- Windows PowerShell 7.6.4
- Python 3.14.0
- PySide6 6.10.1
- Arm GNU Toolchain 14.3.Rel1, GCC 14.3.1
- GNU Make 4.4.1 (`mingw32-make`)
- MSYS2 UCRT64 Host GCC 16.1.0, target `x86_64-w64-mingw32`
- Builtin catalog: 36 strict packages

## Read-only reference and wire evidence

- Path: `C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5`
- Branch: `main`
- Commit: `cc0b377ded690556d037a412a55f87fe334c42d0`
- Subject: `完善同能力多实例与日志配置契约`
- Recorded working tree: clean
- Snapshot digest: `7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`

The external reference was not modified, formatted, built, committed, or pushed. Tests compared
the current builtin wire sources with the SHA-256 values recorded by the read-only reference
import, and all four matched exactly:

- `Protocol/Src/air_protocol.c`:
  `4537b3588b65baa051c13605eed5715a42f530abe5a0bdfad11a4925a2a0b418`
- `System/Src/system_console.c`:
  `c1efc4849c33c9fca361015ec6068d027eeac95bd275f56d139146ea3c781d99`
- `Protocol/SSLOG/Src/sslog_protocol.c`:
  `b065b6733fe87dea5e220e8eaed4ef61569fff831e3dd3d14f1c218fc6aaa3bc`
- `Protocol/SSLOG/Src/sslog_records.c`:
  `871b73bd1cecf9a39a2b95006f34bb32d303a5cba23d55aa02aedb934fe03d30`

The default generated compatibility tag remains the eight bytes for `AIR-NCRC`:
`41 49 52 2D 4E 43 52 43`. The T=0/L=1 build uses the documented fixed no-telemetry tag:
`00 00 00 00 00 00 00 00`. The default Host golden sample round-trip passed; its generated
artifact was 1350 bytes with SHA-256
`91683b4a466d80402b512ed00d5508d25e0bc85f455fd8f02ee1cbcc609f2302`.
The decoder-profile descriptor's schema minor is intentionally 1 for the declared 1.1 contract;
record IDs, field layouts, AIR/maintenance/SSLOG codec sources, CRC behavior, and container layout
were not changed.

## Python, schema, model, and GUI regression

- `python -m pytest -q`: **225 passed in 368.11 s**
- `python -m compileall -q src main.py tools`: passed
- The suite covers format 10 to 11 migration, exact nullable protocol keys, canonical digest and
  serialization, component/lock/provenance/source-graph omission, strict enabled-profile locks,
  zero/one/multiple transport availability, atomic protocol clearing when a device disappears,
  no automatic protocol restoration, and the maintenance endpoint lifecycle.
- Headless GUI tests cover all three persistent `None` entries, disabled unavailable profiles,
  localized tooltips, language rebuilds, stable signals, logging-table/button disabling, and the
  localized log-decoder export error when logging is disabled.
- Logging-disabled generation tests cover stale managed decoder/golden/descriptor removal while
  preserving user-owned log files and retained inactive logging preferences.

## Eight-combination Source Graph and builds

`tools/check_optional_protocol_combinations.py` generated all combinations below
`tests/acceptance_optional_protocols_final/` and built every one with both configurations. Each
row has one assembly source in addition to the listed C-source count.

| Telemetry | Maintenance | Logging | C sources | Release | Debug | task function/stack/TCB audit |
| --- | --- | --- | ---: | --- | --- | --- |
| 1 | 1 | 1 | 136 | passed | passed | passed |
| 1 | 1 | 0 | 126 | passed | passed | passed |
| 1 | 0 | 1 | 132 | passed | passed | passed |
| 1 | 0 | 0 | 122 | passed | passed | passed |
| 0 | 1 | 1 | 133 | passed | passed | passed |
| 0 | 1 | 0 | 123 | passed | passed | passed |
| 0 | 0 | 1 | 129 | passed | passed | passed |
| 0 | 0 | 0 | 119 | passed | passed | passed |

All 16 build processes returned 0. `arm-none-eabi-nm` confirmed that each disabled protocol omits
its task entry point, stack object, and `StaticTask_t` control object, while enabled protocols
contain all three. The generated model checks additionally retain the telemetry device under T=0
and the SD/TF storage device under L=0; M=0 removes the auto-managed Console device, UART
assignment, SerialTask sources, stack, and TCB.

For T=M=L=1, the regular builds reported:

- Release: `text=248664`, `data=1072`, `bss=118976`
- Debug: `text=262456`, `data=1072`, `bss=118992`

## Decoder and project-semantics contract

- T1/M1/L1 generated `T1_M1_L1.ssdecoder`: 101973 bytes, SHA-256
  `0a54c7679aab4b3f6c1fceecaa5984e41bdf16bddd3d489fcc14f6799b3a034e`.
- T0/M1/L1 generated `T0_M1_L1.ssdecoder`: 101186 bytes, SHA-256
  `01b44ebcd300d0a7c46c142214ee3f3fca84f257c8258fbe96d658fc6197b323`;
  its telemetry selection is JSON `null` while maintenance and logging remain locked objects.
- Both packages use `silverstar.ssdecoder.package-schema/1.1` and embed
  `silverstar.project-semantics/1.1`. Their deterministic entry set is `README.md`,
  `checksums.sha256`, `manifest.json`, `project_semantics.json`, and `record_catalog.json`.
- T1/M1/L0 generated no `.ssdecoder` and no `Logs/Golden` directory, but did generate the
  standalone `Generated/project_semantics.json` audit document.
- Logging remains mandatory inside a package that exists; telemetry and maintenance are nullable.

## Generated firmware quality gates

All commands ran from the freshly generated final T1/M1/L1 project and returned 0.

- Host Tests: 50 executables, 8756 checks, 0 failures, 8 compile-pass cases, and 16 expected
  compile rejections. Expected rejections retained raw GCC diagnostics and counted as successful
  gates.
- Architecture Check: 250 checks, 0 failures.
- Power of Ten: 5601 checks over 92 first-party C files and 2074 functions; passed.
- Static Analysis: complete Arm GCC `-fanalyzer` build with strict warnings as errors; passed and
  linked ELF/HEX/BIN artifacts.
- Artifact Check: passed with ELF 2630100 bytes and BIN 249736 bytes; FLASH 249736/524288,
  main SRAM 77176/131072, CCMRAM 42872/65536, heap reserved 0, runtime allocator symbols 0.

## Conclusions and remaining hardware work

1. Project format 11 preserves enabled v10 selections and represents each explicit disabled
   protocol as JSON `null`; the official SS0.5 project still defaults to all three protocols.
2. Physical device selection and protocol enablement are independent. Lost transports clear their
   dependent protocol atomically, and restored devices do not silently re-enable it.
3. Disabled telemetry, maintenance, and logging protocols are removed from the resolved Source
   Graph and from static FreeRTOS task resources; stable task-status slots report them as disabled.
4. Logging-disabled projects leave no managed decoder/golden artifacts, while project semantics
   remains available for audit.
5. Flash/upload, physical UART/radio/storage behavior, and flight operation still require hardware
   validation.
