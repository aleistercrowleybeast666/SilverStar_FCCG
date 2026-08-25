# SilverStar_FCCG validation report

Validation date: 2026-08-26 (Asia/Shanghai)

## Result

This round implements the format-6 generation contract for SilverStar 0.0.9, STM32F407VET6, and SS0.5: one-way optional mission-action outputs, manifest-owned deployment parameters, independent protocol profiles, deferred Logging transactions, typed hardware/electrical validation, manual-assignment fingerprints, and the Code Generation & Build workflow.

The reference firmware and reference GUI remained read-only. No firmware was flashed and no electrical, formal-safety, NASA, or third-party certification is claimed.

## Firmware sync and catalog

- Read-only firmware: `C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5`
- Imported source: branch `main`, commit `e67529ef67f53049fa8d7a1d3eed314e11043d1a`, clean working tree
- Snapshot digest: `0f2388a98e33076b9a6454a8d370190dd339556527071b683a1bc10a2add2686`
- Builtin catalog: 29 strict declarative packages: 23 reference-derived packages, three landing selector overlays, and three logical Device overlays
- Default acceptance project: `tests/acceptance_generation_code_complete_20260825_v4/` (478 generated files)
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

Import is staged and followed by FCCG-only overlays; no third hand-maintained firmware copy is introduced. Firmware and protocol versions remain SilverStar 0.0.9, AIR V0, SSLOG0, and maintenance protocol 0.0.

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

Deployment thresholds and trigger selections render to `Generated/Inc/project_flight_config.h`, the human configuration review, mission configuration logging, and the data-only decoder profile. The delay is range-checked in seconds and emitted as bounded `uint32` milliseconds. AIR compact V0, maintenance 0.0, and SSLOG0 remain independent profile categories.

The core manifest uses `build.strategy_sources` to select either `APP/Src/estimator_task.c` or `APP/Src/estimator_task_none.c`. The no-fusion graph excludes the full estimator and KF6 source, while Make and native EIDE receive the same selected/excluded paths. This avoids configuration-dependent compilation in first-party C and lets the pure-INS variant compile as a real project.

Hardware validation checks typed UART/SPI/I2C/PWM contracts and GPIO mode/output type/pull/speed/polarity/safe initial level/EXTI/IRQ/IOC-lock constraints. It rejects duplicate underlying physical resources. A successful manual assignment check stores a fingerprint that is invalidated by Device, Strategy, Mode, mapping, IOC, or hardware-source changes.

## Generated environment and workflow

- Normal workflow is FCCG Generate/Apply, then open the generated VS Code/EIDE workspace and build there. Generate/Apply does not compile or run quality gates.
- Advanced: Build and Validate in FCCG is a collapsed, optional area containing Release build, clean, Host tests, architecture, Power of Ten, GCC static analysis, artifact checks, and their log.
- Arm GNU is the only presented firmware compiler; Make orchestrates it and derives objcopy/size siblings. Host GCC appears only in advanced checks.
- Make defaults to Release; VS Code's default build task is Release; EIDE lists Release before Debug. Debug remains generated and selectable.
- EIDE uses the read-only reference templates and retains `targets`, `uploadConfigMap`, and `uploader`. `deviceName` and `packDir` are `null`. The preserved uploader is OpenOCD, not J-Link; no flash capability is claimed.
- VS Code 1.133.0 and EIDE 3.27.2 are installed. A newly generated Ready flight-controller project was opened through the current launcher; it selected `Code.exe --new-window <absolute-workspace>`, returned success, and produced the visible window `欢迎 - VSCode_Launch_Acceptance (工作区) - Visual Studio Code`. Exact fallback failures are localized.

VS Code 1.133.0 exposes no command-line option for invoking an extension command, so an EIDE-native UI build was not automatically triggered or claimed. The same resolved source graph passed the generated Make Release build. Any missing J-Link temporary XML remains an external EIDE/J-Link environment issue and is irrelevant to the generated OpenOCD/no-flash validation.

## Executed verification

| Verification | Actual result |
|---|---|
| Python compile | `python -m compileall -q src tools main.py` passed |
| JSON/catalog/reference sync | strict catalog loaded 29 packages; provenance and copied reference files matched |
| FCCG regression suite | 111 passed in 419.12 s; focused generation/variant/acceptance set: 31 passed |
| Default generation | 478 files; configuration valid; no implicit compile |
| Default Release Arm build | passed; text 241,584, data 1,160, bss 114,144 bytes; ELF/HEX/BIN/MAP produced |
| Default Debug Arm build | passed; text 254,064, data 1,160, bss 114,152 bytes; ELF/HEX/BIN/MAP produced |
| Default Host tests | 50 executables, 8,221 checks, 0 failures; 8 compile-pass and 16 expected compile-failure capability cases |
| Default architecture check | 186 checks, 0 failures |
| Default Power of Ten | 5,302 checks; 87 first-party C files; 1,955 functions |
| Default GCC static analysis | Arm GCC `-fanalyzer` completed and linked successfully |
| Default Release artifact check | FLASH/BIN 242,744 bytes; ELF 2,535,504 bytes; heap symbols 0 |
| Default Debug artifact check | FLASH/BIN 255,224 bytes; ELF 3,862,348 bytes; heap symbols 0 |
| No-fusion/no-mission-output Release build | passed without KF6; text 203,028, data 1,160, bss 96,104 bytes |
| No-fusion architecture / Power of Ten | 188 architecture checks, 0 failures; 5,124 checks over 86 first-party C files and 1,892 functions |
| No-fusion artifact check | FLASH/BIN 204,188 bytes; ELF 2,353,872 bytes; heap symbols 0 |
| VS Code workspace launch | newly generated project was Ready; `Code.exe --new-window` succeeded; a visible `VSCode_Launch_Acceptance (工作区)` window was observed |

Power of Ten is a project-specific automated compliance gate, not formal verification. GCC `-fanalyzer` is path-sensitive compiler analysis and does not prove absence of defects.

## Remaining limitations

- EIDE-native UI compile and all upload/flash paths remain unvalidated; the generated Make project is the build result validated here.
- Only Arm GNU, Make, the current STM32CubeMX provider, and STM32F407VET6/SS0.5 have full generated-firmware validation.
- Landing selectors bind one shared reference state machine; they are not three independent implementations.
- No multi-IMU runtime redundancy, multi-EKF, Guidance, Control, Control Allocation, continuous-control actuator, or PWM actuator implementation is claimed.
- SilverStar_FLP does not yet import generated `.ssdecoder` files.
- No Keil, IAR, LLVM Embedded, CMake renderer, hardware flash, or electrical test is claimed.
