# Changelog

## Unreleased — 2026-08-28

- Upgraded project format 7 with a derived log-decoder-profile reference, canonical record catalog
  and project semantics, SHA-256 generation/package identities, generated C hash prefixes, and a
  deterministic data-only `.ssdecoder` checksum manifest.
- Replaced the log-decoder placeholder with **Export Log Decoder Profile**. It verifies saved
  readiness and generated hashes, writes atomically, starts no background task, and preserves the
  model and Dirty state; no executable parser/plugin or multi-version engine is implemented.
- Added backward-compatible `plugin_max`/`class_max` Device policy, explicit instance-row Remove,
  and model-limit-aware disabled choices while retaining legacy `project_max` plugin loading.

- Replaced the ambiguous logging Rate/Period column with declarative Cadence. Periodic values use
  unit-aware editing while source, measurement, event, one-shot, and algorithm-output records show
  semantic text; non-periodic `period_us=0` is no longer rendered as `0 us`.
- Renamed the extraction multiplier to extraction factor, restricted editing to DECIMATION, and extended the logging view model and
  protocol metadata with backward-compatible Cadence and optional producer declarations.
- Added **Select All Available** and **Keep Required Only** Logging actions. New projects and
  capability-affecting Device/Strategy/Mode/logging-profile changes now enable every currently
  available Record while preserving explicit manual Logging edits until the next such change.
- Removed the duplicate Maintenance Endpoint group from Devices while retaining the automatic UART
  maintenance Transport, generated source, protocol binding, and Hardware Connection requirement.
- Unified task PLAN/BEGIN/DONE progress, fixed failure/cancel completion retention, added real Host
  test counts and phase progress for architecture/Power-of-Ten/artifact checks, and separated
  expected configuration-gate rejections from raw GCC detail.
- Added actual service-boundary progress for generation, hardware preparation, Save/Save As,
  CubeMX import, plugin transactions, tool detection, and source export. Plugin removal now stages
  a recoverable move until Catalog refresh succeeds.
- Hardened atomic staging publication against transient Windows file locks with bounded, validated
  replacement retries across generation, reference import, CubeMX/Board preparation, and plugin
  installation. Generated architecture checks now read localized SSLOG JSON explicitly as UTF-8
  under Windows PowerShell 5.
- Synchronized multi-instance/decoder and STATS/TELEMETRY_DIAG state only after the clean read-only
  reference HEAD and GitHub main both resolved to
  `cc0b377ded690556d037a412a55f87fe334c42d0` with subject
  `完善同能力多实例与日志配置契约`. The real Device/Telemetry task producer identities now make the streams
  available and enabled by default at 1 s and 200 ms; no old-firmware producer state was inferred.

- Added declarative System/GNSS Indicator Devices. SS0.5 maps the default System Indicator to active-low `IMU_CAL_LED`/PA1; the optional GNSS Indicator remains visible and selectable on the Device page, while its missing second GPIO is reported only on Hardware Connection and blocks strict generation. GNSS firmware mode uses online/sample state plus `position_usable`.
- Synchronized the clean read-only `cc0b377ded690556d037a412a55f87fe334c42d0` firmware snapshot, including the generated direct instance facade, physical/source descriptor identity, decoder-profile descriptor, native and periodic diagnostic producers, 29-record SSLOG metadata, Host tests, architecture checks, AIR M0 metadata, and formal reference docs.
- Added a real C-codec Golden generator/round-trip check and included generated
  `project_log_decoder_profile.c` in the authoritative Make/EIDE/VS Code Source Graph.
- Moved all generated outputs below `build/FCCG`, made listing opt-in, added safe `clean-all` plus deterministic source export, and excluded persistent test/build artifacts without excluding source tests.
- Normalized FCCG-owned EIDE build fields so target/UI/order/uploader rewrites do not cause false manual-edit warnings; genuine source/include/linker/toolchain changes list their field paths.
- Added strict Service/Profile/Transport/Physical-provider protocol composition, simplified toolchain detection/install guidance, absolute Host GCC propagation, persistent quality results, and BEGIN/DONE static-analysis progress.
- Scoped the copied architecture gate correctly for generated projects: formal maintenance Markdown remains audited and displayed from installed plugin metadata, while a source-only generated project no longer fails merely because it does not duplicate plugin documentation.
- Hardened repository cleanup for Windows with short filesystem-race retries, read-only attribute handling, continued cleanup after an individual failure, and a final exact list of ACL-protected remnants.
- Fixed generated-project cleanup under PowerShell/MSYS Make shells by replacing the nested
  `$paths`/`$path` loop with literal-path operations. **Clean FCCG Build Outputs** now removes the
  whole `build/FCCG` tree with 1/1 progress; **Clean All Build Outputs** reports 1/3 through 3/3
  while additionally removing EIDE build/cache output.
- Made Host Tests immune to inherited `HOST_CC`, `SHELL`, and `MAKESHELL` values. The selected Host
  GCC (or deterministic `gcc` fallback) is a Make command-line override, and failed quality dialogs
  retain the full process output instead of exposing only Make's generic return code 2. The runner
  and generated Host Test script now also put that GCC's runtime directory first and discard GCC
  search-path overrides, preventing EIDE's incompatible `libwinpthread-1.dll` from making `cc1.exe`
  exit with code 1 and no diagnostic.
- Renamed the pre-release protocol profiles to AIR Telemetry Protocol M0 (`air.m0`), Serial Maintenance Protocol 0.0 (`maintenance.serial.0_0`), and Flight Log Format 0.0 (`flight_log.0_0`), with direct old-ID migration. AIR numeric profile 0, frames, messages, CRC/endian/MTU, and internal `SSLOG0` magic are unchanged.
- Unified embedded digest, stale/readiness, decoder, and ownership state through one generation fingerprint. Tool paths/provenance no longer produce false stale reports; metadata rendering now uses a deep copy and successful generation reloads the descriptor written to disk.
- Renamed the primary action to **Generate Code**, removed duplicate normal-page tool status, separated Arm GNU/GNU Make from Host GCC in Advanced, added localized purpose/tooltips and a manual Installation Guide, and gated only actions that actually require missing tools.
- Hardened VS Code launch with workspace JSON/folder/EIDE validation, Windows-safe `code.cmd` quoting, `code.cmd` → `code.exe` → `code` new-window ordering, a short exit-status window, detailed internal diagnostics, and one localized OK-only manual-open failure dialog.
- Kept the real project Power of Ten script and Arm GNU GCC `-fanalyzer` paths intact and documented their non-certification boundaries.
- Upgraded the strict project/schema contract to format 6 with manifest-owned deployment parameters, independent AIR/maintenance/SSLOG protocol profiles, and hardware-assignment confirmation fingerprints. Generated flight constants, configuration review, and `.ssdecoder` now carry the same values.
- Made launch ignition and parachute pyro independently optional one-way dependencies. External ignition keeps START legal without a launch GPIO; removing parachute clears deployment Modes, while explicit re-enable restores the stable instance/default Modes without an auto-readd loop.
- Reworked Logging edits into signal-time snapshots and a deferred transaction, with incremental `Streams_Set` widget updates and 50-change stress coverage; strategy/device refreshes no longer delete the originating control inside its Qt signal stack.
- Added typed UART/SPI/I2C/PWM and GPIO electrical/safe-start validation, underlying physical-resource collision checks, balanced read-only hardware mapping presentation, and **Complete Manual Assignment and Check** fingerprint invalidation.
- Renamed the fourth page to **Code Generation & Build**, reduced its normal summary to target and development environment, moved Arm GNU/Make/Host GCC details into Advanced, and gated **Open Firmware Output** on a real ELF/HEX/BIN/MAP artifact.
- Corrected Native/Measurement logging semantics: BARO_NATIVE follows a recordable barometer output and remains available with Estimator=None; BARO_MEASUREMENT remains estimator-derived. MAG_NATIVE remains generic and extensible to any compatible recordable magnetic source.
- Updated Estimator=None for the latest unified `APP/Src/estimator_task.c` facade: KF6 implementation sources are removed while Make/EIDE receive `SYSTEM_FUSION_NONE` and `SYSTEM_BUILD_ESTIMATOR_ENABLED=0U`; the obsolete standalone `estimator_task_none.c` is gone.
- Fixed a Mode-manifest parser variable collision that replaced the selection default tuple with the last numeric parameter default, which had broken explicit parachute-output re-enable.
- Refined Device and Flight Configuration presentation: the Other Sensors install action now appears only when no matching plugin is installed; launch ignition/parachute entries are ordered and labeled as Power Outputs without parenthesized status suffixes; unavailable Alignment/Landing choices retain capability-driven disablement and use the theme's disabled text color.
- Updated localized Strategy and LOG metadata: GravityMagTriad and Coning2+Sculling2 use the requested names, Estimator None reads No Fusion, HW_QUAT_NATIVE is Optional, and the unavailable magnetometer-log explanation is plugin-generic and can be superseded by any compatible Device plugin with an enabled recordable magnetic output.
- Made VS Code opening prefer `code.cmd --new-window <absolute-workspace>`, then try `Code.exe`/`code`/known installations and file association; technical failures are logged while the localized dialog remains an OK-only manual-open instruction.
- Fixed Windows startup failures after staged imports created a protected `plugins/builtin` ACL. Every Windows staging root now restores parent-directory permission inheritance before atomic publication, covering reference import, plugin installation, CubeMX preparation, and project generation.
- Synchronized the clean read-only firmware reference at `e67529ef67f53049fa8d7a1d3eed314e11043d1a`, including JY901B capability headers, target/user capability contracts, Host tests, documentation bundles, and the known-working EIDE/workspace templates. The catalog now contains 29 strict builtins.
- Added explicit JY901B static preflight 6-axis/9-axis quaternion qualifications. HardwareQuat6AxisKnownYaw and HardwareQuat9Axis are available without falsely granting authoritative runtime attitude; GravityMagTriad remains unavailable.
- Added the default-on Other Sensors input-voltage monitor and independent launch-ignition/parachute-pyro power-output logical Devices, backed by the existing SS0.5 ADC/P_CONTROL1/P_CONTROL2 services. This was subsequently refined to fully optional one-way actuator dependencies above.
- Separated Provided, Consumed, and Recordable state. POWER follows `power.voltage`, HW_QUAT_NATIVE is recordable independently of Algorithm consumption, and MAG_NATIVE reports the selected plugins' recordable magnetic-output configuration as its disable reason.
- Made Mode changes deferred single-Reconcile transactions with signal blocking, candidate-view construction, render rollback, and traceback logging. A removed auto-selectable actuator no longer makes the Mode that can restore it unreachable.
- Rendered EIDE from verbatim read-only reference templates while preserving required target/upload structure, no-Pack fields, and a non-J-Link default.
- Removed the synthetic "Select a strategy" entry from required Strategy dropdowns, retained the genuine optional None choice, and rendered unavailable Strategy/Board entries in muted gray.
- Made Custom STM32 Hardware the default for new drafts and removed the visible unselected-hardware entry. The manual custom workflow does not expose Prepare Hardware Files.
- Moved hardware planning off the GUI thread and made QRunnable completion ownership explicit, preventing the startup pause and the native-lifetime race after progress reaches 100%.
- Added formal Raw/Data and Qualified capability kinds. JY901B qualification evidence now comes from the reference compile-time contracts, and unavailable Strategy choices report the exact missing qualified use.
- Corrected Alignment availability: GravityKnownYaw and static preflight hardware-quaternion 6-axis/9-axis alignment are available, while GravityMagTriad and authoritative runtime attitude qualifications remain unavailable for the current JY901B.
- Added Stillness, ImpactThenStillness, and BarometerImuWindow Landing selectors over one shared Landing Detection Common payload. Current JY901B enables Stillness and BarometerImuWindow and disables ImpactThenStillness.
- Renamed the verified Board everywhere user-visible to **SS0.5** while retaining the stable plugin ID and `SILVERSTAR_0_5` firmware symbol.
- Aligned native EIDE metadata with the working reference: no-Pack projects emit `deviceName: null`/`packDir: null`, a deterministic 32-hex UID, validated GCC/linker fields, and Release before Debug. The root `.code-workspace` points at `.` and Make/EIDE share one source graph.
- Changed the normal workflow to Generate Code → Open VS Code Workspace/Project Folder → build in VS Code/EIDE. Generation does not compile, clean, or run quality targets, and FCCG no longer exposes a separate Build Release action.
- Made Release the Make, default VS Code task, EIDE-target, advanced Validation Build, static-analysis, and artifact-check default; Debug remains available with `-Og -g3 -gdwarf-2` while Release remains `-O2 -g`.
- Simplified toolchain status to Arm GNU + Make, derives objcopy/size from the compiler directory, and places Host GCC under advanced quality checks. Static analysis reuses Arm GCC `-fanalyzer`.
- Preserved incremental builds by avoiding byte-identical managed-file rewrites, component-payload overwrites, automatic cleans, and deletion of Make dependency files.
- Documented Power of Ten as a real project compliance gate rather than formal verification or certification, and retained real warnings-as-errors GCC `-fanalyzer` execution.

- Reordered the four pages to Devices → Flight Configuration → Hardware Connection → Code Generation & Build. Devices selects physical and logical instances; derived capability usage, consumers, and ambiguity-only source choices live on Flight Configuration.
- Upgraded `SilverStar.ssproject` to format 5, removed persisted optional-capability switches and build configuration, added `hardware.mode=unselected`, and retained only genuine multi-provider source overrides.
- Added one candidate/reconcile pipeline for Device/Strategy/Mode/capability-source/hardware changes, availability-based disabled choices, declarative per-Mode-option requirements, safe strategy replacement/clearing, and edit-vs-strict validation.
- Made Calibration select all three options for a new project. Deployment defaults to Apogee and Tilt while Delay starts clear. All currently available SSLOG records start enabled; unavailable records are closed and Required records remain locked.
- Added semantic hardware requirement labels, separate recommended/actual mappings, legal assignment retention, invalid assignment cleanup, automatic new mapping, and pending-state summaries.
- Removed the Debug/Release combo and later replaced the fixed-build surface with the generation-first actions documented above. Advanced Validation Build retains Make dry-run planning, structured compile/link/SIZE/HEX/BIN markers, live log callbacks, and determinate progress.
- Kept the compact native-title-bar new-project dialog, aligned form controls across languages/themes, localized builtin plugin names/descriptions and remaining Chinese UI prose, and retained only intended model/tool/protocol abbreviations.
- Added Draft/Dirty/Materializing/Ready/Building/Error lifecycle validation. Save now stages a complete buildable project, prepares verified Board hardware, verifies ownership/targets/editor metadata, and publishes `SilverStar.ssproject` last.
- Added one `Project_EnsureBuildable` entry for Build, Clean, Host Tests, Architecture Check, Power of Ten, Static Analysis, and Artifact Check. Dirty/incomplete projects auto-save before Make runs with an explicit project-root `cwd`.
- Added idempotent **Prepare Hardware Files** for the verified SS0.5 Board; bundled `.ioc`, Core, Drivers, FATFS, startup, linker, services, and connections require no CubeMX invocation.
- Added manifest-driven per-capability device status, instance-aware provider/resource routing, singleton enforcement, and mock multi-IMU/multi-GNSS model coverage without claiming current driver support or creating multiple estimators.
- New projects use manifest defaults for multi-select Calibration/Deployment modes and all available SSLOG records while keeping Required logs visibly checked/locked; existing selections are preserved.
- Standardized Debug as `-Og -g3 -gdwarf-2` and Release as `-O2 -g`, with assertions/safety gates retained, and removed unvalidated flash/upload actions from the GUI, Make, and VS Code. EIDE retains the working reference's required uploader structure without exposing or claiming a validated flash operation.
- Aligned the new-project form across Chinese/English and Light/Dark, added shared bottom progress for all long operations, and routed localized error summaries separately from raw tool logs.
- Real STM32F407 acceptance passed Debug/Release builds, 8,229 Host Test checks, 187 architecture checks, 5,305 Power-of-Ten checks across 87 first-party C files, GCC static analysis, and artifact/memory validation. A separate Estimator=None/no-mission-output variant passed Release compilation, 188 architecture checks, 5,124 Power-of-Ten checks, and artifact validation without KF6.

- Fixed `Translator.Text_Get()` so formatting values such as `{code}` cannot collide with its translation-key parameter.
- Reduced normal navigation to four pages, moved project commands to File, and moved plugin management to a dedicated dialog under Plugins; the final page order is the device-first order recorded above.
- Added complete-source **Save Project As**, excluding build/cache/intermediate output while preserving project-owned manual source changes.
- Upgraded `SilverStar.ssproject` to format 3 with physical `DeviceInstance` records and v2 migration of device/resource owners (now migrated onward to format 5).
- Added manifest `instance_policy`, physical-device/driver metadata, typed capability requirements with purpose, automatic provider resolution, ambiguity-only overrides, and static heap-free capability route glue.
- Corrected E28 display/physical metadata to `E28-2G4M12SX（SX1281）`, retained the SX1281 driver, and kept the GUI system term **Maintenance Console** with option **Serial Maintenance Protocol 0.0** and independent firmware/protocol/document versions.
- Added active-looking immutable `LockedCheckBox` controls for required SSLOG records while retaining domain reconciliation and validation enforcement.
- Replaced the broken checkable advanced/logging groups with visibility-only `CollapsibleSection` controls; Logging is directly visible and `StandardCheckBox` now provides a clear Light/Dark indicator for modes, logs, and dynamic multi-select Devices.
- Moved the SSLOG record table and Required/Recommended/Optional policy into Protocol metadata, added capability/component/strategy-conditioned availability, enforced required streams, and generated deterministic data-only `.ssdecoder` profiles.
- Added the initial Device cardinality experiment; format 3 superseded it with explicit instance policies and physical instances. The later optional-capability experiment was removed again in format 5 in favor of fully derived usage.
- Renamed Board & Hardware to Hardware Connection and made STM32CubeMX `.ioc` the physical source of truth for builtin and custom Boards; Board data now keeps semantic `connections.json` mappings and verification/provenance.
- Added uncapped Hardware Inventory parsing for MCU/package/core, pins/AF/GPIO/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC, and useful clocks, plus Device resource-contract and DMA/exclusive-conflict checks.
- Upgraded `SilverStar.ssproject` to format 2 with persisted hardware inventory and format-1 migration (now migrated onward to format 5).
- Separated repository-internal safety from the exact user-authorized project root, allowing generation in any selected writable project directory without permitting path escape.
- Added structured error data, localized message-box buttons/filters/tool labels, a styled header-combo popup, and startup exception logging/dialog handling.
- Expanded acceptance coverage for capability routing, multi-instance representation, four-page GUI, locked logging, Save As, EIDE overwrite detection, and physical/protocol metadata.

- Reimported the latest clean SilverStar 0.0.9 reference at `e67529ef67f53049fa8d7a1d3eed314e11043d1a` into 23 reference-derived declarative builtins with path/commit/branch/status/digest provenance; three FCCG Landing selectors and five logical Device overlays bring the catalog to 31 packages.
- Replaced fixed Algorithm/Flight lists with generic manifest-driven Strategy and Mode slots; added four Alignment strategies and real Estimator=None source exclusion.
- Added formal MCU/Board/Device resource responsibilities, Board defaults/candidates/fixed/reserved/conflicts, compatibility filtering, and device-first auto-assignment.
- Added the trusted STM32CubeMX hardware provider: `.ioc`/directory validation, MCU/RTOS/layout/peripheral checks, isolated `HardwareGenerated/STM32CubeMX/` snapshots, risk state, dangerous reimport, and local Board `.ssplugin` export/reuse.
- Added the DevelopmentEnvironment plugin and one resolved source graph for Make, native non-empty EIDE, and VS Code workspace/tasks.
- Reduced the earlier ten-page GUI through an intermediate six-page layout to the current four-page navigation; retained the one-step identity dialog and removed the standalone Generate page/mandatory Preview workflow.
- Expanded Simplified Chinese/English catalogs and updated GUI coverage for the current four-page layout.
- Updated generated Make with forced includes, source exclusions, first-party/vendor warning boundaries, Power of Ten, static analysis, and artifact tasks.
- Added acceptance fixtures/tests for two Boards on one MCU, Estimator=None, environment graph equivalence, CubeMX import/RTOS rejection, custom project generation, and Board export/install/reuse.

## 0.0.1 — 2026-08-21

- Created the independent PySide6 FCCG application, strict project/plugin models, secure installer, staged assembler, project-owned component preservation, thin generated glue, editor metadata, toolchain front end, and initial F407 acceptance project.
