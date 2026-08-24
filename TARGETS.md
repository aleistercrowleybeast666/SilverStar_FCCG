# Development targets

## Current FCCG upgrade

- [x] Draft/Dirty/Materializing/Ready/Building/Error lifecycle with staged complete Save and descriptor-last publication
- [x] one `Project_EnsureBuildable` path for Build/Clean and all five checks, including dirty auto-save, current renderer refresh, and explicit project `cwd`
- [x] idempotent verified-Board hardware preparation with automatic Save integration and no CubeMX call for SilverStar 0.5
- [x] Debug `-Og -g3` / Release `-O2 -g` policy with assertions retained and dual-configuration Make/VS Code/EIDE output
- [x] manifest-driven multi-select Mode/log defaults while preserving existing projects and locking Required logs
- [x] shared worker/progress/localized-error path, aligned bilingual wizard, and no unvalidated GUI/Make/VS Code/EIDE flash entry
- [x] fixed the three checkable-GroupBox interaction failures with visibility-only collapsible sections and visible cross-theme checkboxes
- [x] Protocol-owned SSLOG metadata, Required/Recommended/Optional policy, capability-aware availability, and deterministic data-only `.ssdecoder`
- [x] Project format 5 `DeviceInstance` model, ambiguity-only capability overrides, v0-v4 migration, and no persisted capability/build-configuration switches
- [x] Physical Device `provides` + consuming component `requires {capability,purpose}` + automatic/ambiguous provider resolution
- [x] current Device `instance_policy.project_max=1` without pretending that drivers support dual IMU/GNSS/link instances
- [x] `.ioc` physical truth for builtin/custom Boards plus semantic `connections.json`
- [x] UART/SPI/I2C/ADC/Timer/PWM/CAN/GPIO/EXTI/DMA/NVIC/clock inventory without parser count caps
- [x] separate FCCG-internal and explicitly authorized user-project roots
- [x] localized structured error dialogs, buttons, filters, build labels, and startup failure logging
- [x] latest-reference discovery/explicit selection and read-only provenance import
- [x] 23 real builtin components, including four Alignment strategies, provider, and environment
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
- [x] Devices → Flight Configuration → Hardware Connection → Build flow with read-only derived capability usage on Flight Configuration
- [x] candidate/reconcile changes, edit-vs-strict validation, non-fatal unselected hardware, and assignment retention/cleanup/auto-map
- [x] fixed Debug main build, advanced Release build, responsive advanced grid, dry-run step planning, structured Make progress, and live logs

## Current validated scope

- STM32F407VET6 + SilverStar 0.5 is the only complete firmware-build-validated target.
- STM32 + STM32CubeMX is the only formally supported manual hardware-configuration path in v0.x.
- VS Code + EIDE + Arm GNU Toolchain is the only DevelopmentEnvironment renderer.
- Current real Strategies: Alignment (four choices), INS Coning2Sculling2, Estimator KF6/None, Landing BarometerImuWindow.
- Current real Modes: Calibration and Deployment triggers.
- Current JY901B project consumption is acceleration, angular rate, and barometric altitude. Magnetic field and external attitude are available from the physical instance but unused by the selected GravityKnownYaw strategy.

## Deliberate limits / future work

- No Guidance, Control, Control Allocation, or actuator implementation is supplied; their future slot/class shape is supported only by the generic schema.
- No alternate MCU, non-STM manual provider, Keil, IAR, or fictional environment project is generated.
- FCCG inventories clocks, pin alternate functions, interrupts, and DMA, but does not solve or edit clocks, PLL, pinmux, alternate functions, or DMA streams.
- Custom hardware is generated with an explicit unverified warning; generation does not claim official Board validation.
- The current generated STM32 Platform binding surface has fixed reference-target enum sizes even though the IOC inventory parser itself is uncapped.
- FLP does not yet import `.ssdecoder`; this round defines and emits the safe profile contract without modifying FLP.
- Current drivers do not support multiple IMU, multiple GNSS, or multiple telemetry/maintenance endpoints; the format is ready but the GUI exposes add controls only when a real manifest raises `project_max`.
- Multi-EKF and sensor voting/failover are not implemented; they remain future explicit Strategies, never an automatic consequence of adding sensors.
- EIDE native metadata is generated and structurally/architecturally checked; an EIDE CLI builder is required before claiming an actual EIDE-native compile.
- No current Board/Environment pair declares validated flash capability, so FCCG emits no GUI, Make, VS Code, or EIDE upload action; no hardware flash or electrical test is claimed.
