# Development targets

## 2026-08-30 internal software release-candidate closeout

- [x] project format 10 with actual imported-MCU-first matching, strict Platform compatibility, declarative CubeMX module/provider activation, FatFs/timebase inventory, and deterministic format 0–9 migration
- [x] Device-owned single-instance `silverstar.device.storage.sd_sdio_fatfs`; Board supplies only verified physical mappings, MCU supplies controlled FatFs core/HAL providers, and CubeMX supplies SDIO plus App/Target glue
- [x] generated storage source moved to `Devices/Storage/SdSdioFatFs`, so format-9 projects retain legacy Board files without collision while the Source Graph compiles the new owner exactly once
- [x] dynamic CubeMX HAL timebase validation and rendering with no hidden TIM1 assumption; invalid SysTick, missing/mismatched init, frequency, IRQ, and PWM/timebase collisions are rejected
- [x] I²C/PWM provider boundaries, reserved Classic CAN consumer rejection, strict HAL/CMSIS single-source policy, and no default compile-all behavior
- [x] 36 strict builtin packages and 48 builtin/schema JSON documents
- [x] fresh default and custom-F407 generation/build/Host validation plus architecture, Power of Ten, static-analysis, artifact, GUI, migration, and schema regression coverage
- [x] status remains **Software Release Candidate / Pre-Hardware-Validation**; no tag, push, public release, flash, electrical, or flight claim

## 2026-08-28 internal firmware/plugin refactor

- [x] reproducible read-only reference snapshot plus FCCG-owned overlay provenance; external firmware remains unchanged
- [x] three mandatory single-category Protocol plugins with locked component/version/Profile/manifest hash and deterministic format-7 migration
- [x] at the 2026-08-28 checkpoint, project format 8 added explicit `protocols` slots and the detected MCU/Platform lock; format 0–7 files remained readable and saved as format 8 at that checkpoint
- [x] Board/imported CubeMX facts automatically match an installed MCU/Platform plugin; the Devices page no longer exposes an MCU selector
- [x] manifest-driven Platform resource renderer with no STM32F4 header/getter or MCU-model whitelist in Python
- [x] conditionally selected F407 I²C, Classic CAN, and PWM backends with static APIs, resolver constraints, Host mocks, and no default-SS0.5 inclusion
- [x] strict `sensor.*`, `link.*`, `storage.*`, `actuator.*`, and `indicator.*` categories plus dynamic Devices-page grouping
- [x] logging-plugin-owned Record Catalog and data-only `.ssdecoder` semantics covering three protocols, hardware, resources, devices, algorithms, and logging
- [x] 36 strict builtin packages: the former three-category bundle is replaced by three independent Protocol packages and hardware-facing services have explicit owners

## 2026-08-28 multi-instance/decoder-profile round

- [x] dynamic display of all valid installed Device manifests; Board/IOC incompatibility is deferred to Hardware Connection
- [x] one-MCU project model with multi-instance Device/capability identity and latest physical/source descriptor metadata
- [x] `build/FCCG/<target>/<config>`, StaticAnalysis, Host, EIDE, `clean-all`, and opt-in Listing layout
- [x] normalized shared EIDE ownership that ignores ordering/UI state but reports changed FCCG-owned fields
- [x] absolute Host GCC propagation, target validation, UTF-8 diagnostics, persistent nonmodal quality results, and real BEGIN/DONE progress
- [x] semantic logging Cadence with unit-aware periodic editing, source/event/measurement/one-shot text, and DECIMATION-only extraction editing
- [x] optional producer declarations that distinguish a known Record format from a producer in the selected component composition
- [x] verified **Export Log Decoder Profile** action plus deterministic canonical `.ssdecoder`; no executable decoder or multi-version parser is claimed
- [x] hidden Devices-page maintenance endpoint with the UART Transport retained in protocol binding, source graph, and Hardware Connection
- [x] reusable PLAN/BEGIN/DONE progress for generation, save, Save As, CubeMX, plugins, tools, Host tests, architecture, Power of Ten, and artifacts; failure/cancel never force 100%
- [x] strict Service → Profile → Transport Binding → Physical Device/Storage protocol resolution for the three real profiles
- [x] deterministic source-package export that preserves source tests and excludes generated/binary artifacts
- [x] retrying repository cleanup with read-only handling, per-target failure aggregation, and an explicit report for abnormal Windows ACL remnants

## Current FCCG upgrade

- [x] Draft/Dirty/Materializing/Ready/Building/Error lifecycle with staged complete Save and descriptor-last publication
- [x] one `Project_EnsureBuildable` path for Build/Clean and all five checks, including dirty auto-save, current renderer refresh, and explicit project `cwd`
- [x] idempotent verified-Board hardware preparation with automatic Save integration and no CubeMX call for SS0.5
- [x] Release-default `-O2 -g` / selectable Debug `-Og -g3 -gdwarf-2` policy with assertions retained and dual-configuration Make/VS Code/EIDE output
- [x] manifest-driven multi-select Mode/log defaults while preserving existing projects and locking Required logs
- [x] shared worker/progress/localized-error path, aligned bilingual wizard, and no unvalidated GUI/Make/VS Code/EIDE flash entry
- [x] non-blocking Board preparation planning plus completion-safe QRunnable ownership after 100% progress
- [x] Custom STM32 Hardware as the new-draft default, with no visible unselected entry or Board-only preparation action
- [x] fixed the three checkable-GroupBox interaction failures with visibility-only collapsible sections and visible cross-theme checkboxes
- [x] Protocol-owned SSLOG metadata, Required/Recommended/Optional policy, capability-aware availability, and deterministic data-only `.ssdecoder`
- [x] Project format 10 with `DeviceInstance`, manifest-driven Mode parameters, three explicit protocol locks, Platform lock, decoder-profile hashes, assignment confirmation fingerprint, FatFs/timebase facts, and v0-v9 migration
- [x] Physical Device `provides` + consuming component `requires {capability,purpose}` + automatic/ambiguous provider resolution
- [x] backward-compatible Device instance policy with independent `plugin_max` and `class_max`; repeating one model requires a context-safe driver, while different singleton models may share a class
- [x] `.ioc` physical truth for builtin/custom Boards plus semantic `connections.json`
- [x] UART/SPI/I2C/ADC/Timer/PWM/CAN/GPIO/EXTI/DMA/NVIC/clock inventory without parser count caps
- [x] separate FCCG-internal and explicitly authorized user-project roots
- [x] localized structured error dialogs, buttons, filters, build labels, and startup failure logging
- [x] latest-reference discovery/explicit selection and read-only provenance import
- [x] 36 real builtin components, including three independent Protocol plugins, a physical storage Device, internal mission-action/indicator services, and declarative voltage/mission-action/System/GNSS Indicator Devices
- [x] strict Project format migration plus generic Strategy/Mode dictionaries
- [x] four-page GUI; File owns New/Open/Save/Save As and Plugins owns manager/install/refresh dialogs
- [x] one-step New Project dialog with project name/output only and complete-source Save As
- [x] Board provides/defaults/candidates/fixed/reserved/conflicts and compatibility/auto-assignment
- [x] trusted STM32CubeMX `.ioc`/directory import with MCU/layout/peripheral/RTOS validation
- [x] isolated HardwareGenerated ownership, warning, Power-of-Ten boundary, and dangerous replacement
- [x] custom Board `.ssplugin` export, secure install, and second-project reuse
- [x] one resolved source graph for Make, native EIDE, and VS Code
- [x] Estimator=None excludes KF6 before build rendering
- [x] current Power of Ten, forced memory include, CCMRAM/DMA contract, Debug/Release/static/artifact tasks
- [x] F407 reference, same-MCU Board A/B, and custom hardware acceptance fixtures/tests
- [x] Locked required SSLOG checkboxes plus model enforcement and Protocol-owned metadata
- [x] Simplified Chinese/English four-page coverage and updated architecture/user/plugin/build documentation
- [x] Devices → Flight Configuration → Hardware Connection → Code Generation & Build flow with read-only derived capability usage on Flight Configuration
- [x] candidate/reconcile changes, edit-vs-strict validation, non-fatal unselected hardware, and assignment retention/cleanup/auto-map
- [x] formal Raw/Data versus Qualified capability model with JY901B evidence and localized unavailable-use reasons
- [x] generation-first workflow with Generate Code, Open VS Code Workspace, Open Project Folder, and no separate Build Release action
- [x] Release-default Make/VS Code/EIDE output with Debug retained, advanced Release Validation Build, dry-run planning, structured progress, and live logs
- [x] unchanged-file Apply semantics that preserve managed mtimes, project-owned payloads, build directories, and Make dependency files
- [x] normal build summary without duplicate tool status; advanced firmware/host environments separate Arm GNU, GNU Make, and Host GCC with derived objcopy/size and installation guidance
- [x] JY901B preflight 6-axis/9-axis quaternion qualifications separated from absent authoritative runtime qualifications
- [x] independently optional launch/parachute mission-action Power Outputs, external-ignition START behavior, and deployment-mode clearing/restoration without actuator auto-readd loops
- [x] Provided/Consumed/Recordable separation with POWER and HW_QUAT_NATIVE available and device-config-disabled MAG_NATIVE
- [x] deferred snapshot-based Mode/Logging transactions with rollback, traceback logging, incremental log widgets, and 50-change signal stress coverage
- [x] generated deployment trigger mask/threshold/delay header with seconds-to-milliseconds conversion and review/decoder propagation
- [x] typed UART/SPI/I2C/PWM and GPIO electrical/resource validation, physical-resource exclusivity, and invalidated manual-assignment fingerprints
- [x] read-only AIR M0, serial maintenance 0.0, and flight-log format 0.0 profile display with pre-release ID migration and unchanged wire formats
- [x] System Status Indicator on active-low SS0.5 PA1 plus optional GNSS Indicator using `position_usable` and an independent GPIO contract
- [x] unified generation fingerprint shared by digest/readiness/ownership, excluding host tool paths and provenance
- [x] validated reference EIDE/workspace templates and `code.cmd`/`code.exe`/`code --new-window` launch with one localized manual-open failure dialog

## Current validated scope

- STM32F407VET6 + SS0.5 is the only complete firmware-build-validated target.
- STM32 + STM32CubeMX is the only formally supported manual hardware-configuration path in v0.x.
- VS Code + EIDE + Arm GNU Toolchain is the only DevelopmentEnvironment renderer.
- Current selectable Strategies: Alignment (four choices), INS Coning2Sculling2, Estimator KF6/None, Landing Stillness/ImpactThenStillness/BarometerImuWindow. Landing selectors share the centralized reference implementation; they are not three independent duplicated C payloads.
- Current real Modes: Calibration and Deployment triggers.
- JY901B raw magnetic/external-attitude data does not grant absolute-vector or authoritative runtime quaternion qualification. Its explicit static preflight qualifications make HardwareQuat6AxisKnownYaw and HardwareQuat9Axis alignment available. GravityMagTriad and ImpactThenStillness remain unavailable; GravityKnownYaw, Stillness, and BarometerImuWindow are available.

## Deliberate limits / future work

- No Guidance, Control, Control Allocation, or continuous-control actuator implementation is supplied. The current launch-ignition and parachute-pyro Power Output plugins are declarative one-shot Devices backed by an explicit internal mission-action service, not by Board ownership.
- No alternate MCU, non-STM manual provider, Keil, IAR, or fictional environment project is generated.
- FCCG inventories clocks, pin alternate functions, interrupts, and DMA, but does not solve or edit clocks, PLL, pinmux, alternate functions, or DMA streams.
- Custom hardware is generated with an explicit unverified warning; generation does not claim official Board validation.
- The current production Platform package is verified only for STM32F407VET6/SS0.5. A virtual H7 contract fixture proves renderer portability but is deliberately not an installed/supported target.
- F407 I²C is blocking 7-bit master plus memory-register access and does not claim generic repeated-start; Classic CAN is bxCAN only and single-owner per peripheral; PWM is ordinary fixed-frequency, non-complementary output with CubeMX-owned timing.
- FLP does not yet import `.ssdecoder`; this round defines and emits the safe profile contract without modifying FLP.
- **Export Log Decoder Profile** writes a verified data-only package; this round still does not implement a log parser, executable decoder plugin, or version-plugin system.
- [x] Final multi-instance Facade, 29-record catalog, decoder descriptor, and STATS/TELEMETRY_DIAG producer declarations were imported only after clean reference HEAD `cc0b377ded690556d037a412a55f87fe334c42d0` matched GitHub main and named `完善同能力多实例与日志配置契约`; no older firmware was used to infer state.
- The GUI exposes add/remove controls when class capacity and another legal model/instance remain; same-model repetition still requires a context-safe manifest. Firmware-backed builtin limits are synchronized only after the specified reference commit passes the dependency gate.
- Multi-EKF and sensor voting/failover are not implemented; they remain future explicit Strategies, never an automatic consequence of adding sensors.
- EIDE native metadata is generated and structurally/architecturally checked; an EIDE CLI builder is required before claiming an actual EIDE-native compile.
- No current Board/Environment pair declares validated flash capability, so FCCG emits no GUI, Make, VS Code, or EIDE upload action; no hardware flash or electrical test is claimed.
