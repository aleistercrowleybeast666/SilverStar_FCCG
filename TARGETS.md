# Development targets

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
- [x] Project format 6 with `DeviceInstance`, manifest-driven Mode parameters, independent protocol profiles, assignment confirmation fingerprint, and v0-v5 migration
- [x] Physical Device `provides` + consuming component `requires {capability,purpose}` + automatic/ambiguous provider resolution
- [x] current Device `instance_policy.project_max=1` without pretending that drivers support dual IMU/GNSS/link instances
- [x] `.ioc` physical truth for builtin/custom Boards plus semantic `connections.json`
- [x] UART/SPI/I2C/ADC/Timer/PWM/CAN/GPIO/EXTI/DMA/NVIC/clock inventory without parser count caps
- [x] separate FCCG-internal and explicitly authorized user-project roots
- [x] localized structured error dialogs, buttons, filters, build labels, and startup failure logging
- [x] latest-reference discovery/explicit selection and read-only provenance import
- [x] 29 real builtin components: 23 reference-derived packages, three Landing selectors, and three declarative voltage/mission-action Devices
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
- [x] generation-first workflow with Generate/Apply, Open VS Code Workspace, Open Project Folder, and no separate Build Release action
- [x] Release-default Make/VS Code/EIDE output with Debug retained, advanced Release Validation Build, dry-run planning, structured progress, and live logs
- [x] unchanged-file Apply semantics that preserve managed mtimes, project-owned payloads, build directories, and Make dependency files
- [x] normal toolchain UI limited to Arm GNU and Make, with derived objcopy/size and Host GCC under advanced quality checks
- [x] JY901B preflight 6-axis/9-axis quaternion qualifications separated from absent authoritative runtime qualifications
- [x] independently optional launch/parachute mission-action Power Outputs, external-ignition START behavior, and deployment-mode clearing/restoration without actuator auto-readd loops
- [x] Provided/Consumed/Recordable separation with POWER and HW_QUAT_NATIVE available and device-config-disabled MAG_NATIVE
- [x] deferred snapshot-based Mode/Logging transactions with rollback, traceback logging, incremental log widgets, and 50-change signal stress coverage
- [x] generated deployment trigger mask/threshold/delay header with seconds-to-milliseconds conversion and review/decoder propagation
- [x] typed UART/SPI/I2C/PWM and GPIO electrical/resource validation, physical-resource exclusivity, and invalidated manual-assignment fingerprints
- [x] independent AIR compact V0, maintenance 0.0, and SSLOG0 profile selectors
- [x] read-only reference EIDE/workspace templates and reliable `Code.exe --new-window` workspace launch with detailed failures

## Current validated scope

- STM32F407VET6 + SS0.5 is the only complete firmware-build-validated target.
- STM32 + STM32CubeMX is the only formally supported manual hardware-configuration path in v0.x.
- VS Code + EIDE + Arm GNU Toolchain is the only DevelopmentEnvironment renderer.
- Current selectable Strategies: Alignment (four choices), INS Coning2Sculling2, Estimator KF6/None, Landing Stillness/ImpactThenStillness/BarometerImuWindow. Landing selectors share the centralized reference implementation; they are not three independent duplicated C payloads.
- Current real Modes: Calibration and Deployment triggers.
- JY901B raw magnetic/external-attitude data does not grant absolute-vector or authoritative runtime quaternion qualification. Its explicit static preflight qualifications make HardwareQuat6AxisKnownYaw and HardwareQuat9Axis alignment available. GravityMagTriad and ImpactThenStillness remain unavailable; GravityKnownYaw, Stillness, and BarometerImuWindow are available.

## Deliberate limits / future work

- No Guidance, Control, Control Allocation, or continuous-control actuator implementation is supplied. The current launch-ignition and parachute-pyro Power Output plugins are declarative one-shot devices backed by existing Board services.
- No alternate MCU, non-STM manual provider, Keil, IAR, or fictional environment project is generated.
- FCCG inventories clocks, pin alternate functions, interrupts, and DMA, but does not solve or edit clocks, PLL, pinmux, alternate functions, or DMA streams.
- Custom hardware is generated with an explicit unverified warning; generation does not claim official Board validation.
- The current generated STM32 Platform binding surface has fixed reference-target enum sizes even though the IOC inventory parser itself is uncapped.
- FLP does not yet import `.ssdecoder`; this round defines and emits the safe profile contract without modifying FLP.
- Current drivers do not support multiple IMU, multiple GNSS, or multiple telemetry/maintenance endpoints; the format is ready but the GUI exposes add controls only when a real manifest raises `project_max`.
- Multi-EKF and sensor voting/failover are not implemented; they remain future explicit Strategies, never an automatic consequence of adding sensors.
- EIDE native metadata is generated and structurally/architecturally checked; an EIDE CLI builder is required before claiming an actual EIDE-native compile.
- No current Board/Environment pair declares validated flash capability, so FCCG emits no GUI, Make, VS Code, or EIDE upload action; no hardware flash or electrical test is claimed.
