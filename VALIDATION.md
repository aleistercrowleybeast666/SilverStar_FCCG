# SilverStar_FCCG validation report

Validation date: 2026-08-24 (Asia/Shanghai)

## Result

The current FCCG upgrade is implemented and validated for the real SilverStar F407 reference combination. The four-page device-first GUI, format-5 physical Device Instance model, candidate-based configuration reconciliation, capability resolver, 23 declarative builtins, Protocol-owned logging/decoder profile, IOC-backed Hardware Inventory, semantic Board connections, verified-Board preparation, explicit Draft/Dirty/Ready lifecycle, exact user-project authorization root, thin generator, one Make/EIDE source graph, VS Code environment, staged ownership rules, and live-progress build front end are connected through `FccgService`.

No hardware was flashed and no electrical validation is claimed.

## Reference and provenance

- Read-only firmware: `C:\Users\chdxm\Desktop\stm32-1\Flight_Controller0.5`
- Commit: `b8c90e997c3113dd23074302682c5560dae18926`
- Branch at final read-only check: `main`
- Working tree at final check: clean
- Snapshot digest: `fda74af625c0330ba9f619b02cd44e7df66d476c5fb3291c074ab2301bf3ee5c`
- Builtin catalog: 23 strict declarative packages
- Formal generated project: `tests/reference_copy/acceptance_format5_20260824/`

The import script read and staged data only; the reference was not modified, built, formatted, committed, reset, cleaned, or otherwise written. The copied architecture/host-check scripts contain reviewed FCCG compatibility adaptations: `Generated/project_sources.mk` and the two capability-route glue files are allowed, the legacy Make-time Estimator override is skipped when the fixed FCCG graph exists, and host tests for absent unselected strategy payloads are explicitly skipped.

At the final read-only check, local `main`, `GitHub_Flight_Controller0.5/main`, and `codex/refactor-silverstar-0.0.9-platform` all pointed to `b8c90e9`. The requested reference branch integration had therefore already been completed by the external firmware task; FCCG did not write or run a build in that repository.

## FCCG automated verification

| Verification | Actual result |
|---|---|
| Python compile | `python -m compileall -q src tools` passed |
| FCCG regression suite | 83 passed, 0 failed in 145.17 s |
| Lifecycle | first Save produced a Ready 476-file project; missing/stale managed files and renderer revisions refresh; descriptor publication is last; Build/advanced actions share EnsureBuildable |
| Application startup | real `main.py` entry path constructed/shown under an offscreen Qt event loop and exited 0 |
| GUI | exactly four pages in Devices → Flight Configuration → Hardware Connection → Build order; physical-only Devices, availability-aware Flight Configuration, compact native new-project dialog screenshots, Light/Dark states, locked required logs, localized dialogs/buttons, and determinate background build progress passed |
| Plugin security | traversal/symlink/special/duplicate/dependency/capability/collision/managed-path cases passed |
| Read-only builtin re-import preview | 23 manifests; file sets equal; 0 semantic differences; FCCG SSLOG policy overlay restored all 28 records |
| Project/model | strict load/save/format 0/1/2/3/4 → 5 migration, Device instances, no persisted capability toggles/build configuration, instance policies, edit/strict dependency/resource/log validation passed |
| Capability resolver | single-provider auto routing, unused capabilities, ambiguity/override validation, purposes, stale override reconciliation, and future multi-instance fixtures passed |
| Logging/decoder | Protocol metadata, Required enforcement, capability availability, new-record loading, defaults, deterministic data-only `.ssdecoder` passed |
| IOC inventory | MCU/package/core, pin/AF/GPIO/EXTI, UART/SPI/I2C/ADC/Timer/PWM/CAN, DMA/NVIC/clocks and no artificial UART count cap passed |
| Path policy | sibling mock user project root accepted; internal policy and project-root escape rejected |
| Estimator=None | KF6 absent from resolved graph, Make, and EIDE; None defines present |
| Environment | workspace + `.vscode/` + native `.eide/eide.yml` + Make generated from one graph |
| Board variants | same F407 MCU/Platform reused; A maps USART1/2, B maps USART3/6; only mapping glue differs |
| Custom STM32 | import → validate → auto-map → generate → isolated HardwareGenerated passed |
| RTOS conflict | CubeMX FreeRTOS/CMSIS-RTOS2 fixture rejected |
| Board reuse | custom import → export `.ssplugin` with `.ioc`/`connections.json` → secure install → second project passed |

All pytest temporary/generated outputs are below `tests/`. The custom-hardware tests use a minimal mock CubeMX fixture, not the user's real CubeMX project.

## Formal generated firmware verification

The formal acceptance project resolves 134 C sources, one startup ASM source, 43 include directories, the selected strategies/modes, target forced memory include, explicit `Core/Src/sysmem.c` exclusion, and the reference linker/CPU/FPU/library contract. Its small generated surface includes static capability routes and no heap allocation.

| Verification | Actual result |
|---|---|
| Architecture check | 186 checks, 0 failures |
| Power of Ten | 5,263 checks; 86 first-party C files; 1,941 functions |
| Host tests | 50 executables; 8,221 checks; 0 failures |
| Compile contracts | 4 expected successes and 13 expected failures passed |
| Debug Arm build | passed; text 253,960, data 1,160, bss 114,152 bytes |
| Release Arm build | passed; text 241,416, data 1,160, bss 114,144 bytes |
| GCC static analysis | `-fanalyzer` build passed |
| Debug artifact | ELF 3,854,172 bytes; BIN/FLASH 255,120 bytes; heap symbols 0 |
| Release artifact | ELF 2,534,596 bytes (debug symbols retained); BIN/FLASH 242,576 bytes; heap symbols 0 |
| Debug memory | main SRAM 72,440 / 131,072; CCMRAM 42,872 / 65,536 bytes |
| Release memory | main SRAM 72,432 / 131,072; CCMRAM 42,872 / 65,536 bytes |
| Read-only reference comparison | compatible; 453 copied files checked, 0 semantic mismatches, all 133 reference C sources retained, only capability-route C added |

Detected tools used: Python 3.14.0, Arm GNU GCC 14.3.1, GNU Make 4.4.1, and MSYS2 Host GCC 16.1.0.

No callable EIDE CLI builder was found, so EIDE validation is limited to strict YAML parsing/source-graph equivalence and the firmware architecture check. An EIDE-native compile is not claimed.

## GUI and behavior

- Navigation is exactly Devices, Flight Configuration, Hardware Connection, Build. Project operations are in File; plugin management is a dialog opened from Plugins.
- Device instances and `instance_policy.project_max` are manifest-driven; current IMU, GNSS, Telemetry, and Maintenance plugins are singletons. Format 5 can represent future multiple instances, but capability usage is derived and only true source ambiguity is persisted as an override.
- Physical Device plugins provide capabilities; selected Algorithm/Flight plugins declare typed requirements and purposes. A single provider is selected automatically, and only a real ambiguity exposes a source choice.
- Advanced resources/build sections toggle visibility without disabling children. Logging is directly visible and uses real checkbox cell widgets. The shared status bar shows determinate or busy progress, briefly reaches 100%, then resets.
- Protocol metadata owns all 28 SSLOG records and their Required/Recommended/Optional/availability policy. New projects enable every currently available record; Required records are visibly checked and cannot be disabled, while existing projects preserve their choices.
- The Build page exposes only fixed-Debug Build/Clean on its normal surface; advanced settings contain Build Release and five quality checks in a responsive grid. Current Make, VS Code, and EIDE output contains no unvalidated flash/upload entry.
- Board manifests support semantic aliases/roles, defaults, candidates, fixed/reserved resources, and conflicts; physical facts come from `.ioc`.
- Custom hardware is offered only for a compatible provider. First import carries an explicit unverified warning.
- Current Strategies are Alignment, INS, Estimator, Landing. Current Modes are Calibration and Deployment.
- Normal changes apply without mandatory Preview. Only dangerous plans show the diff/confirmation path.
- Component payloads are preserved; managed glue/editor data is replaceable; HardwareGenerated replacement is special and dangerous.
- Generated `.ssdecoder` archives are deterministic JSON-only data for a future generic FLP decoder and contain no executable plugin.
- User-visible page/action/status/filter/tool text and standard message buttons are catalog-backed; Chinese and English coverage passed.

## Device and capability truth

- `imu0` (JY901B) provides acceleration, angular rate, external attitude, magnetic field, and barometric altitude as one physical device instance.
- The current `GravityKnownYaw` + Coning2/Sculling2 INS + KF6 + barometer/IMU landing combination consumes acceleration, angular rate, and barometric altitude.
- External attitude and magnetic field are unused by the current selected combination. This differs from the prompt's expectation because the real selected `GravityKnownYaw` alignment initializes from acceleration/gyro, while the selected INS propagates from acceleration/gyro. The HardwareQuat alignment alternatives declare external attitude with `initialization` purpose.
- FCCG introduces no editable `PRE_START`/`ASCENT`/`RECOVERY` phase policy; input lifecycle remains the selected algorithm implementation's responsibility.
- The telemetry UI identifies the physical module as `E28-2G4M12SX (SX1281)` and retains the shared SX1281 driver component. The maintenance UI remains `Maintenance Console` / `Serial Maintenance Protocol 0.0`, with firmware `0.0.9`, protocol `0.0`, and documentation `0.0.9` shown separately.

## Safety observations

All FCCG development/test writes remained below `D:\python_software\SilverStar_FCCG`; external-output behavior was simulated with sibling roots below `tests/`. Product generation creates an exact authorization policy for the user-selected project directory and rejects parent/sibling escape. No PATH, registry, global IDE setting, global Python environment, external reference file, external GUI file, hardware, or unrelated repository was changed.

The current acceptance directory was verified absent before creation and generated entirely below `tests/reference_copy/`; no user-authored source was removed.

## Remaining limitations

- Only STM32F407VET6/SilverStar 0.5 has complete firmware-build validation.
- FCCG v0.x formally supports STM32 + STM32CubeMX manual hardware configuration only; no NXP or other provider is implemented.
- Hardware Inventory reads useful clock facts but does not implement a complete clock/PLL solver or rewrite `.ioc`.
- The IOC parser has no artificial resource-count cap, but the current F407 generated Platform interface still has reference-target enum bounds.
- Custom/manual Boards remain explicitly unverified until their real hardware is tested.
- No Guidance, Control, Control Allocation, or real PWM actuator implementation exists.
- Current drivers do not implement multiple IMU/GNSS instances; model support does not claim runtime redundancy.
- Multi-EKF and sensor selection/failover strategies are not implemented.
- SilverStar_FLP does not yet import `.ssdecoder`; FLP was intentionally not modified in this round.
- No alternate MCU, Keil/IAR/CMake renderer, EIDE CLI compile, hardware flash, or electrical test is claimed.
