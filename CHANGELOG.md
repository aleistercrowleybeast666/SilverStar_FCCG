# Changelog

## Unreleased — 2026-08-25

- Upgraded the strict project/schema contract to format 6 with manifest-owned deployment parameters, independent AIR/maintenance/SSLOG protocol profiles, and hardware-assignment confirmation fingerprints. Generated flight constants, configuration review, and `.ssdecoder` now carry the same values.
- Made launch ignition and parachute pyro independently optional one-way dependencies. External ignition keeps START legal without a launch GPIO; removing parachute clears deployment Modes, while explicit re-enable restores the stable instance/default Modes without an auto-readd loop.
- Reworked Logging edits into signal-time snapshots and a deferred transaction, with incremental `Streams_Set` widget updates and 50-change stress coverage; strategy/device refreshes no longer delete the originating control inside its Qt signal stack.
- Added typed UART/SPI/I2C/PWM and GPIO electrical/safe-start validation, underlying physical-resource collision checks, balanced read-only hardware mapping presentation, and **Complete Manual Assignment and Check** fingerprint invalidation.
- Renamed the fourth page to **Code Generation & Build**, kept Arm GNU + Make as the normal tool surface, and gated **Open Firmware Output** on a real ELF/HEX/BIN/MAP artifact.
- Corrected Native/Measurement logging semantics: BARO_NATIVE follows a recordable barometer output and remains available with Estimator=None; BARO_MEASUREMENT remains estimator-derived. MAG_NATIVE remains generic and extensible to any compatible recordable magnetic source.
- Added manifest-declared `strategy_sources` alternatives so the core selects either the KF6 estimator task or a standalone pure-INS/no-fusion task in the resolved source graph. Estimator=None now compiles and links without KF6 source or first-party C conditional-compilation branches, while Make and EIDE explicitly exclude the inactive implementation.
- Fixed a Mode-manifest parser variable collision that replaced the selection default tuple with the last numeric parameter default, which had broken explicit parachute-output re-enable.
- Refined Device and Flight Configuration presentation: the Other Sensors install action now appears only when no matching plugin is installed; launch ignition/parachute entries are ordered and labeled as Power Outputs without parenthesized status suffixes; unavailable Alignment/Landing choices retain capability-driven disablement and use the theme's disabled text color.
- Updated localized Strategy and LOG metadata: GravityMagTriad and Coning2+Sculling2 use the requested names, Estimator None reads No Fusion, HW_QUAT_NATIVE is Optional, and the unavailable magnetometer-log explanation is plugin-generic and can be superseded by any compatible Device plugin with an enabled recordable magnetic output.
- Made VS Code opening prefer the real `Code.exe --new-window <absolute-workspace>` process, derive it from `code.cmd` installations, retain safe launcher/file-association fallbacks, and show the exact launcher or association failure reason in the localized error dialog.
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
- Changed the normal workflow to Generate/Apply → Open VS Code Workspace/Project Folder → build in VS Code/EIDE. Generation does not compile, clean, or run quality targets, and FCCG no longer exposes a separate Build Release action.
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
- Real STM32F407 acceptance passed Debug/Release builds, 8,221 Host Test checks, 186 architecture checks, 5,302 Power-of-Ten checks across 87 first-party C files, GCC static analysis, and artifact/memory validation. A separate Estimator=None/no-mission-output variant passed Release compilation, 188 architecture checks, 5,124 Power-of-Ten checks, and artifact validation without KF6.

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

- Reimported the latest clean SilverStar 0.0.9 reference at `e67529ef67f53049fa8d7a1d3eed314e11043d1a` into 23 reference-derived declarative builtins with path/commit/branch/status/digest provenance; three FCCG Landing selectors and three logical Device overlays bring the catalog to 29 packages.
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
