# Changelog

## Unreleased — 2026-08-24

- Reordered the four pages to Devices → Flight Configuration → Hardware Connection → Build. Devices now selects physical instances only; derived capability usage, consumers, and ambiguity-only source choices live on Flight Configuration.
- Upgraded `SilverStar.ssproject` to format 5, removed persisted optional-capability switches and build configuration, added `hardware.mode=unselected`, and retained only genuine multi-provider source overrides.
- Added one candidate/reconcile pipeline for Device/Strategy/Mode/capability-source/hardware changes, availability-based disabled choices, declarative per-Mode-option requirements, safe strategy replacement/clearing, and edit-vs-strict validation.
- Made Calibration and Deployment select all three options for a new project. All currently available SSLOG records start enabled; unavailable records are closed and Required records remain locked.
- Added semantic hardware requirement labels, separate recommended/actual mappings, legal assignment retention, invalid assignment cleanup, automatic new mapping, and pending-state summaries.
- Removed the Debug/Release combo. Normal Build is fixed Debug; Build Release is in the responsive advanced grid and does not dirty the project. Make dry-run planning, structured compile/link/SIZE/HEX/BIN markers, live log callbacks, and determinate progress are now implemented.
- Kept the compact native-title-bar new-project dialog, aligned form controls across languages/themes, localized builtin plugin names/descriptions and remaining Chinese UI prose, and retained only intended model/tool/protocol abbreviations.
- Added Draft/Dirty/Materializing/Ready/Building/Error lifecycle validation. Save now stages a complete buildable project, prepares verified Board hardware, verifies ownership/targets/editor metadata, and publishes `SilverStar.ssproject` last.
- Added one `Project_EnsureBuildable` entry for Build, Clean, Host Tests, Architecture Check, Power of Ten, Static Analysis, and Artifact Check. Dirty/incomplete projects auto-save before Make runs with an explicit project-root `cwd`.
- Added idempotent **Prepare Hardware Files** for the verified SilverStar 0.5 Board; bundled `.ioc`, Core, Drivers, FATFS, startup, linker, services, and connections require no CubeMX invocation.
- Added manifest-driven per-capability device status, instance-aware provider/resource routing, singleton enforcement, and mock multi-IMU/multi-GNSS model coverage without claiming current driver support or creating multiple estimators.
- New projects use manifest defaults for multi-select Calibration/Deployment modes and all available SSLOG records while keeping Required logs visibly checked/locked; existing selections are preserved.
- Standardized Debug as `-Og -g3 -gdwarf-2` and Release as `-O2 -g`, with assertions/safety gates retained, and removed unvalidated flash/upload actions from the GUI, Make, VS Code, and EIDE metadata.
- Aligned the new-project form across Chinese/English and Light/Dark, added shared bottom progress for all long operations, and routed localized error summaries separately from raw tool logs.
- Real STM32F407 acceptance passed Debug/Release builds, 8,221 Host Test checks, 186 architecture checks, 5,263 Power-of-Ten checks, GCC static analysis, and artifact/memory validation.

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

- Reimported the latest clean SilverStar 0.0.9 reference at `b8c90e997c3113dd23074302682c5560dae18926` into 23 declarative builtins with path/commit/branch/status/digest provenance.
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
