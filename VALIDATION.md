# SilverStar_FCCG validation report

Validation date: 2026-08-28 (Asia/Shanghai)

## Result

This round completes the format-7 multi-instance Device model, generated direct bindings, 29-record SSLOG catalog, deterministic log-decoder profile, real C-codec Golden sample, and the Code Generation & Build workflow for SilverStar 0.0.9, STM32F407VET6, and SS0.5.

The reference firmware and reference GUI remained read-only. No firmware was flashed and no electrical, formal-safety, NASA, or third-party certification is claimed.

## Firmware sync and catalog

- Read-only firmware: `C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5`
- Imported source: branch `main`, commit `cc0b377ded690556d037a412a55f87fe334c42d0`, subject `完善同能力多实例与日志配置契约`, clean working tree and equal remote `main`
- Snapshot digest: `7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`
- Builtin catalog: 31 strict declarative packages: 23 reference-derived packages, three landing selector overlays, and five logical Device overlays
- Default acceptance project: `D:/stm32_project/SS_TEST_0/` (495 files on fresh generation)
- No-fusion/no-mission-output acceptance project: `tests/acceptance_optional_external_ignition_20260825_v5/` (475 generated files)

The importer copied the reference component roots and therefore kept the complete owning payloads synchronized. Files specifically relevant to this round include:

- `Devices/IMU/JY901B/Inc/jy901b_imu_build_capabilities.h`
- `Devices/IMU/JY901B/Adapter/Inc/jy901b_quaternion_build_capabilities.h`
- `Devices/IMU/JY901B/Adapter/Inc/jy901b_magnetometer_build_capabilities.h`
- `Devices/IMU/JY901B/Adapter/Inc/jy901b_barometer_build_capabilities.h`
- `Targets/SilverStar_F407/Inc/target_system_config.h`
- `System/User/system_user_capability_validation.h`
- `Tests/Host/test_build_capability_contract.c`
- `Tests/Host/test_alignment_strategy.c`
- the owning Alignment, JY901B, target, Host-Test, and capability-contract documentation roots
- `.eide/eide.yml`, `.eide/files.options.yml`, the root `.code-workspace`, `.vscode/extensions.json`, and `.vscode/settings.json` as Development Environment templates

Import is staged and followed by FCCG-only overlays; no third hand-maintained firmware copy is introduced. Firmware remains SilverStar 0.0.9. User-facing protocol names are AIR Telemetry Protocol M0, Serial Maintenance Protocol 0.0, and Flight Log Format 0.0; numeric AIR profile value 0 and internal `SSLOG0` magic remain unchanged.

## Capability and Strategy acceptance

JY901B raw capabilities are `imu.acceleration`, `imu.angular_rate`, `attitude.external`, `magnetometer.field`, and `barometer.altitude`. Its static/preflight qualifications are `attitude.external.preflight_alignment_6axis_qualified`, `attitude.external.preflight_alignment_9axis_qualified`, and `attitude.external.preflight_fallback_qualified`. It also provides software alignment, software propagation, landing stillness, and barometer landing-window qualifications.

It explicitly does not provide `magnetometer.absolute_vector_qualified`, either all-flight authoritative quaternion qualification, or `imu.landing_impact_qualified`. Static preflight suitability is therefore not confused with continuous authoritative attitude suitability.

| Strategy | JY901B result | Contract result |
|---|---|---|
| Gravity + Known Yaw | available | acceleration, angular rate, and software-alignment qualification present |
| Gravity/Magnetic Triad | unavailable, gray | absolute-vector magnetometer qualification absent |
| Hardware Quaternion 6-axis + Known Yaw | available | external attitude and 6-axis preflight qualification present |
| Hardware Quaternion 9-axis static sample | available | external attitude and 9-axis preflight qualification present |
| Landing Stillness | available | acceleration, angular rate, and stillness qualification present |
| Impact then Stillness | unavailable, gray | landing-impact qualification absent |
| Barometer + IMU Window | available | altitude, stillness, and barometer-window qualifications present |

Availability is resolved only from Device `provides` and Strategy `requires.capabilities`; there is no Python special case for JY901B. The unavailable entries remain visible, gray, and carry their localized reason. The three landing selectors share the single reference landing implementation rather than copying its state machine.

## Devices and logging

The Device page groups are Main Controller, Primary Devices, Other Sensors, and Actuators. Input Voltage Monitor is a default-selected logical sensor, not a raw ADC. Launch Ignition Power Output and Parachute Pyro Power Output are independently optional and mapped to P_CONTROL1/GPIO4 and P_CONTROL2/GPIO5. External ignition keeps START legal without a launch binding. Removing parachute clears dependent Modes; explicit re-enable restores its stable instance and default Modes. The Other Sensors Install Plugin action is hidden whenever a matching plugin exists.

When optional voltage/launch/parachute Devices are absent, generated resource macros use typed non-index sentinels (`PLATFORM_ADC_COUNT` / `PLATFORM_GPIO_COUNT`) and `0U` feature constants. Board services use ordinary control flow to avoid reading or driving those sentinels.

Logging now treats Provided, Consumed, and Recordable as independent facts. In the default project POWER and Optional HW_QUAT_NATIVE are available and enabled; HW_QUAT_NATIVE remains recordable even when the current flight algorithm does not consume external attitude. MAG_NATIVE uses a generic selected-plugin output reason and becomes available when another selected compatible plugin enables recordable `magnetometer.field`. Removing Input Voltage Monitor makes POWER unavailable. Required records are model-enforced, selected, and locked.

## Transaction and generation stability

The crash path combined reconciliation with synchronous Logging widget replacement inside the originating Qt callback. Logging now captures a complete immutable view snapshot during the signal, schedules one next-turn transaction, and updates existing controls incrementally when record IDs are unchanged. Mode parameters share the deferred candidate/reconcile pipeline. Tests cover rollback, one-reconcile behavior, and 50 consecutive logging changes followed by Strategy/Device refreshes without invalidating the original controls.

Deployment thresholds and trigger selections render to `Generated/Inc/project_flight_config.h`, the human configuration review, mission configuration logging, and the data-only decoder profile. The delay is range-checked in seconds and emitted as bounded `uint32` milliseconds. AIR M0, serial maintenance 0.0, and flight-log format 0.0 remain independent profile categories and are read-only while only one implementation exists.

System/GNSS Indicator manifests, the active-low SS0.5 PA1 mapping, `position_usable` GNSS mode resolver, missing-second-GPIO gate, resource collision detection, and generated enable symbols are covered by Python and generated-project Host tests. No hardware power lamp is modeled as software.

Readiness, project digest, decoder metadata, and ownership reuse one generation fingerprint. Regression tests generate to Ready, change only local tool paths without becoming Dirty, change a Mode and become Dirty, regenerate to Ready, and verify metadata rendering leaves the live model unchanged.

VS Code launcher tests validate JSON/folder/EIDE prerequisites, Windows-safe `code.cmd --new-window` quoting, short-window nonzero failure, the single OK-only localized manual-open dialog, and separation of launcher diagnostics from EIDE loading. On this desktop, the corrected `code.cmd` route accepted the request while other Code processes already existed and a new Code process appeared; window contents and EIDE extension loading remain manual checks.

The latest core uses one `APP/Src/estimator_task.c` facade for both estimator states. Selecting No fusion removes the KF6 implementation sources and emits `SYSTEM_FUSION_NONE` plus `SYSTEM_BUILD_ESTIMATOR_ENABLED=0U`; Make and native EIDE receive the same graph and defines. The obsolete `estimator_task_none.c` overlay is not generated or imported.

Hardware validation checks typed UART/SPI/I2C/PWM contracts and GPIO mode/output type/pull/speed/polarity/safe initial level/EXTI/IRQ/IOC-lock constraints. It rejects duplicate underlying physical resources. A successful manual assignment check stores a fingerprint that is invalidated by Device, Strategy, Mode, mapping, IOC, or hardware-source changes.

## Generated environment and workflow

- Normal workflow is FCCG **Generate Code**, then open the generated VS Code/EIDE workspace and build there. Generate Code does not compile or run quality gates.
- Advanced: Build and Validate in FCCG is a collapsed, optional area containing Release build, clean, Host tests, architecture, Power of Ten, GCC static analysis, artifact checks, and their log.
- Arm GNU is the only presented firmware compiler; Make orchestrates it and derives objcopy/size siblings. Host GCC appears only in advanced checks.
- Make defaults to Release; VS Code's default build task is Release; EIDE lists Release before Debug. Debug remains generated and selectable.
- EIDE uses the read-only reference templates and retains `targets`, `uploadConfigMap`, and `uploader`. `deviceName` and `packDir` are `null`. The preserved uploader is OpenOCD, not J-Link; no flash capability is claimed.
- VS Code 1.133.0 and EIDE 3.27.2 are installed. With existing Code processes present, the corrected first-choice `code.cmd --new-window <absolute-workspace>` launcher remained running through the observation window, FCCG returned “request accepted,” and a new Code process appeared. This does not claim that EIDE finished loading; exact technical failures remain in the log and the user dialog stays localized and minimal.

VS Code 1.133.0 exposes no command-line option for invoking an extension command, so an EIDE-native UI build was not automatically triggered or claimed. The same resolved source graph passed the generated Make Release build. Any missing J-Link temporary XML remains an external EIDE/J-Link environment issue and is irrelevant to the generated OpenOCD/no-flash validation.

## Executed verification

### Historical latest-reference round (2026-08-27)

| Verification | Actual result |
|---|---|
| FCCG regression suite after cleanup hardening | 128 passed in 243.51 s |
| Fresh default generation/readiness | 484 files added; Ready with no missing/stale files; one MCU persisted |
| GUI startup smoke | Simplified-Chinese Light window shown offscreen; exactly four pages; clean close |
| Tool detection | Arm GNU 14.3.1 (`arm-none-eabi`), GNU Make 4.4.1, Host GCC 16.1.0 (`x86_64-w64-mingw32`) all compatible |
| Host tests | 51 executables, 8,360 checks, 0 failures; absolute Host GCC path and target printed; 8 compile-pass and 16 expected compile-failure cases |
| Architecture / Power of Ten | 195 architecture checks, 0 failures; 5,382 checks over 88 first-party C files and 1,983 functions |
| Release Arm build | 137 compile steps / 141 total; text 245,688, data 1,160, bss 116,536 bytes; ELF/HEX/BIN/MAP produced |
| GCC static analysis | 137 `COMPILE_BEGIN` and 137 `COMPILE_DONE`; 141/141 stages; final 100%; separate StaticAnalysis tree |
| Release artifact check | FLASH/BIN 246,848 bytes; ELF 2,590,136 bytes; heap symbols 0; 16 configuration/generated files unchanged; project remained Ready |
| Listing/cleanup audit | Before cleanup: 4,289 historical `.lst` files / 979,093,000 bytes and 200 cleanup targets / 10,859,606,459 bytes. Normal permissions removed 196 targets and 10,424,512,167 file bytes; four abnormal-ACL directories totaling 435,094,292 bytes were reported and retained after elevated deletion was denied. Final accessible acceptance/build/Listing counts are zero. |

The generated architecture check validates generated source and build metadata. Installed-plugin
Markdown is not duplicated into every generated source project; the reference importer audits the
maintenance document and plugin management exposes the copied formal docs. The original reference
remained read-only and was neither built nor modified.

### Earlier baseline acceptance

| Verification | Actual result |
|---|---|
| Python compile | `python -m compileall -q src tools main.py` passed |
| JSON/catalog/reference sync | strict catalog loaded 31 packages; 33 i18n/manifest JSON files parsed; provenance and copied reference files matched |
| FCCG regression suite | 120 passed in 462.07 s |
| Default generation | 478 files; configuration valid; no implicit compile |
| Default Release Arm build | passed; text 241,560, data 1,160, bss 114,144 bytes; ELF/HEX/BIN/MAP produced |
| Default Debug Arm build | passed; text 254,152, data 1,160, bss 114,152 bytes; ELF/HEX/BIN/MAP produced |
| Default Host tests | 50 executables, 8,229 checks, 0 failures; 8 compile-pass and 16 expected compile-failure capability cases |
| Default architecture check | 187 checks, 0 failures |
| Default Power of Ten | 5,305 checks; 87 first-party C files; 1,956 functions; violation fixture failed nonzero |
| Default GCC static analysis | Arm GCC `-fanalyzer` completed and linked successfully |
| Default Release artifact check | FLASH/BIN 242,720 bytes; ELF 2,536,272 bytes; heap symbols 0 |
| Default Debug artifact check | FLASH/BIN 255,312 bytes; ELF 3,863,968 bytes; heap symbols 0 |
| No-fusion/no-mission-output Release build | passed without KF6; text 203,028, data 1,160, bss 96,104 bytes |
| No-fusion architecture / Power of Ten | 188 architecture checks, 0 failures; 5,124 checks over 86 first-party C files and 1,892 functions |
| No-fusion artifact check | FLASH/BIN 204,188 bytes; ELF 2,353,872 bytes; heap symbols 0 |
| VS Code workspace launch | generated project was Ready; with existing Code processes present, `code.cmd --new-window` was accepted and a new Code process appeared; workspace contents/EIDE load not automatically confirmed |

Power of Ten is a project-specific automated compliance gate, not formal verification. GCC `-fanalyzer` is path-sensitive compiler analysis and does not prove absence of defects.

## Logging cadence and progress acceptance

- Protocol metadata parsing accepts optional Cadence and producer declarations and derives safe
  defaults for older PERIODIC/DECIMATION/EVERY/EVENT/ONE_SHOT metadata.
- GUI acceptance checks the Cadence header, absence of meaningless `0 us`, editable PERIODIC units,
  semantic non-periodic text, DECIMATION-only extraction editing, and unchanged microsecond storage.
- Decoder-profile tests verify deterministic archive bytes, the five-entry data-only allowlist,
  canonical catalog/semantics hashes, per-entry checksums, model/package identities, generated C
  prefixes, saved/readiness gating, atomic export, no worker, and no model or Dirty-state change.
- Device-page acceptance requires the maintenance endpoint group to be absent while `maintenance0`
  still resolves Serial Maintenance Protocol 0.0, contributes its UART sources, and retains its
  Hardware Connection requirement.
- Structured progress tests require BEGIN to leave completion unchanged, DONE to advance it,
  success to reach 100%, and failure/cancel to retain the last real value. Generated Host,
  architecture, Power-of-Ten, and artifact scripts are also parsed by PowerShell after adaptation.
- Expected compile rejections require a static-assert or `#error` configuration gate. Their normal
  log line is neutral and localized; raw GCC diagnostics remain in detailed output and
  `build/FCCG/Host/Tests/host-tests-detail.log`.
- Producer-specific STATS/TELEMETRY_DIAG acceptance uses the verified clean read-only firmware
  commit `cc0b377ded690556d037a412a55f87fe334c42d0`; a non-mutating remote query confirmed the same
  GitHub main hash and the subject `完善同能力多实例与日志配置契约`. Tests require both producer identities,
  default enablement, availability, and periods of 1 s/200 ms.

### Historical progress/cleanup execution (2026-08-27)

| Verification | Actual result |
|---|---|
| Firmware dependency | superseded by the 2026-08-28 dependency gate recorded below |
| FCCG regression suite | `142 passed in 284.35s` |
| Python compilation | `python -m compileall -q src tests tools` exited 0; it reported two inaccessible historical test directories without a Python compilation failure |
| Fresh default generation/readiness | 486 files added through all seven PLAN/BEGIN/DONE phases; integrity check completed and project was Ready |
| Generated cleanup actions | `clean` returned 0, removed only `build/FCCG`, and completed 1/1; `clean-all` returned 0 and removed `build/FCCG`, `.eide/build`, and `.eide/.cache` through 1/3–3/3. A direct retry with inherited `SHELL=powershell` also returned 0. |
| Release Arm build | passed; text 246,568, data 1,160, bss 116,552 bytes; ELF/HEX/BIN/MAP produced |
| Debug Arm build | passed; text 259,208, data 1,160, bss 116,560 bytes; ELF/HEX/BIN/MAP produced |
| Host tests | 51 executables, 8,662 checks, 0 failures; 8 compile-pass and 16 expected compile-rejection cases. The FCCG runner also passed with deliberately invalid inherited `HOST_CC`, `SHELL=powershell`, and `MAKESHELL=sh.exe`, proving its command-line compiler override and Windows shell isolation. A follow-up reproduced the empty-diagnostic `interfaces` failure by putting EIDE's conflicting `libwinpthread-1.dll` directory before MSYS2 UCRT64; the isolated runner/script then passed the same complete 51/8,662 run with that hostile parent `PATH` unchanged. |
| Architecture check | 207 checks, 0 failures; UTF-8 SSLOG metadata parsed explicitly under Windows PowerShell 5 |
| Power of Ten | 5,404 checks over 89 first-party C files and 1,989 functions; passed |
| GCC static analysis | Arm GCC `-fanalyzer` compilation, link, SIZE, HEX, and BIN stages completed successfully |
| Release artifact check | FLASH/BIN 247,728 bytes; ELF 2,602,188 bytes; main SRAM 74,840 bytes; CCMRAM 42,872 bytes; heap symbols 0 |

Earlier execution tables are retained as historical records and are not substituted for the
current multi-instance results below.

### Multi-instance and decoder-profile final execution (2026-08-28)

The target was normalized to exactly `D:\stm32_project\SS_TEST_0`, its parent was exactly
`D:\stm32_project`, and both were verified as ordinary directories rather than symbolic links,
junctions, or other reparse points before only that exact project was removed and regenerated.

| Verification | Actual result |
|---|---|
| Firmware dependency | clean local/remote `main` at `cc0b377ded690556d037a412a55f87fe334c42d0`; subject `完善同能力多实例与日志配置契约` |
| FCCG regression suite | `146 passed in 262.36s` |
| Python compilation | `python -m compileall -q src main.py tools` exited 0 |
| Fresh generation | 495 files; one MCU; Ready; normal refresh changed only three FCCG-managed files |
| Generated cleanup | determinate PLAN/BEGIN/DONE 1/1; removed only `build/FCCG` |
| Release Arm build | passed; text 247,632, data 1,160, bss 116,688 bytes; ELF/HEX/BIN/MAP produced |
| Debug Arm build | passed; text 261,232, data 1,160, bss 116,696 bytes; ELF/HEX/BIN/MAP produced |
| Host Tests | 52 executables, 8,784 checks, 0 failures; 8 compile-pass and 16 expected-rejection cases; C Golden passed |
| Architecture check | 250 checks, 0 failures |
| Power of Ten | 5,516 checks over 90 first-party C files and 2,040 functions |
| GCC static analysis | Arm GCC `-fanalyzer` compile/link/SIZE/HEX/BIN completed in the separate StaticAnalysis tree |
| Release artifact check | FLASH/BIN 248,792 bytes; ELF 2,627,052 bytes; main SRAM 74,976 bytes; CCMRAM 42,872 bytes; heap symbols 0 |
| Authoritative source list | passed; includes `Generated/Src/project_log_decoder_profile.c` |

The verified `SS_TEST_0.ssdecoder` is an 89,797-byte five-entry data-only ZIP. Its Record Catalog,
project semantics, generation-profile, and complete package SHA-256 values are respectively
`962f9236529d2ff4375202cc2085ed5d89de03639429c368fbe87e760e5aa48f`,
`689c34354e7d274b2888bb45b382088e7da1f974de95785e1978f2abc0833554`,
`9b70cc2dff9bf752bc5f617d08ab78774802e0b4439dc419040eadfdbbd91b84`, and
`83326233420c7b13e69a2f225546deb3576559add115542e119ad4abe09ed453`.
`Logs/Golden/SS_TEST_0_golden.sslog` is 1,350 bytes and was serialized and deserialized by the real
C SSLOG codec before publication; `expected.json` records the matching hashes, records, endpoints,
and Canonical Channels. AIR M0 remains wire value 0 and heap remains zero.

## Remaining limitations

The 2026-08-28 round validates dynamic Device discovery, Hardware-page-only compatibility
gating, one-MCU persistence, normalized EIDE ownership, strict protocol transport resolution,
deterministic Host GCC forwarding, Make-shell isolation, UTF-8 diagnostics, task-local quality persistence, structured
static-analysis progress, `build/FCCG` paths, opt-in listing, safe cleanup, and deterministic
source export. The imported reference provenance is clean `main` commit
`cc0b377ded690556d037a412a55f87fe334c42d0` with snapshot digest
`7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`; the reference was read
and copied only, never built or modified. The final executed test counts are recorded above.

- EIDE-native UI compile and all upload/flash paths remain unvalidated; the generated Make project is the build result validated here.
- Only Arm GNU, Make, the current STM32CubeMX provider, and STM32F407VET6/SS0.5 have full generated-firmware validation.
- Landing selectors bind one shared reference state machine; they are not three independent implementations.
- No Sensor Voting/automatic Sensor Selection, multi-IMU runtime redundancy, Multi-EKF, vendor-specific maintenance command, Guidance, Control, Control Allocation, continuous-control actuator, or PWM actuator implementation is claimed.
- SilverStar_FLP does not yet import generated `.ssdecoder` files.
- No Keil, IAR, LLVM Embedded, CMake renderer, hardware flash, or electrical test is claimed.
