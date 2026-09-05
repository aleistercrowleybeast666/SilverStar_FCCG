# User guide

## Create a project

Run `python main.py` and choose **File → New Project**. The compact one-step dialog uses the native title bar and asks only for project name and output directory. The sole current firmware/Core/OS/Environment defaults are automatic. The official SS0.5 reference draft starts with all three official protocols enabled, but each protocol can later be set to **None**. MCU is derived from the selected Board/imported CubeMX data and is never selected on Devices. Configuration continues through exactly four main pages:

```text
Devices → Flight Configuration → Hardware Connection → Code Generation & Build
```

When only one Core, OS, or Development Environment is installed, FCCG selects it automatically. Protocol candidates are never auto-selected merely because only one is installed; the official reference factory supplies its explicit defaults.

## Select physical Devices first

The page starts with user-selectable physical instances such as `imu0`/JY901B, `gnss0`/NEO-M9N, and `telemetry0`/E28-2G4M12SX (SX1281); there is no MCU control. Only `sensor.imu` and `sensor.gnss` appear under **Primary Sensors**. Every other valid `sensor.*` plugin enters **Other Sensors** automatically, while `link.*`, `storage.*`, `actuator.*`, and `indicator.*` remain separate. An invalid or misspelled category prevents plugin installation/scan instead of being silently displayed in the wrong group. The system-owned `maintenance0` transport is not duplicated as a user Device: selecting the Maintenance protocol profile declaratively creates and binds it, while selecting **None** removes it and releases its UART assignment and SerialTask contribution. Its concrete USART, pins, and baud rate remain visible as **Maintenance Console · UART** on Hardware Connection only while active. Pre-release project files that stored the endpoint continue to load without losing a still-enabled UART requirement. Add/Remove controls follow the class-wide `class_max`; the official JY901B, NEO-M9N, and E28-2G4M12SX/SX1281 plugins may each be repeated up to four times, while every other repeated model still requires its own `plugin_max`, `same_plugin_multiple`, and `multi_instance_ready` declarations. Instance order is the default backup order after the configured Canonical source, and Hardware Connection shows a separate resource request for every row.

One physical Device may provide several capabilities. The Devices page shows a concise capability summary but no capability enable/source controls. FCCG derives actual usage from selected Algorithm/Flight requirements on **Flight Configuration**. A sole provider is selected automatically; when several providers exist, capability instance 0 remains the Canonical default and the source selector stores only a non-default override. Unused physical outputs are read-only status, not project choices. The consumer implementation owns lifecycle; FCCG does not expose PRE_START/ASCENT/RECOVERY phase policy.

USART, SPI, GPIO, exclusive/shared ownership, DMA, and pinmux are internal contracts resolved on Hardware Connection, not editable controls on the normal Device page.

## Existing Board flow

```text
Select existing Board plugin
        → Board compatibility is checked against MCU + Devices
        → resource defaults are auto-assigned
        → inspect only if “Advanced Resource Configuration” is needed
        → optionally Prepare Hardware Files
        → Generate Code
        → Open VS Code Workspace
        → Build with VS Code / EIDE
```

The Board selector keeps incompatible entries identifiable and marks them in muted gray while explaining missing resource kinds. Fixed roles cannot be changed; selectable roles show only legal candidates. Reserved resources and declared conflict groups are enforced. **Prepare Hardware Files** is shown only for a Board plugin: it copies and checks the verified SS0.5 payload without invoking CubeMX, and repeating it with the same fingerprint is a no-op. Save performs the same preparation automatically, so this optional button is never a prerequisite.

The page is named **Hardware Connection** because it resolves Device needs against real hardware. For an STM32 Board, FCCG reads the Board `.ioc`, inventories pins/peripherals/DMA/IRQ/clocks, validates requirement constraints, and then applies the Board's semantic `connections.json`. A fixed connection is shown as text with its physical peripheral, pins, baud, DMA and IRQ details; only genuinely selectable roles use a dropdown. **Complete Manual Assignment and Check** performs strict resolution and stores a fingerprint; changing Devices, Modes, IOC content, or assignments clears the confirmation.

On an official verified Board, these fixed rows are not user-configurable and CubeMX discovery order
does not assign their Platform numbers. `connections.json` is authoritative; the `.ioc` and generated
headers only prove that each alias still resolves. Generation stops with a Platform Resource Closure
Check error naming the logical ID, expected alias, actual/missing symbol, and Board plugin if the
snapshot drifts. SS0.5's visible behavior is fixed: radio NSS/reset/busy/DIO1 use GPIO 0–3, launch
and parachute outputs use 4/5, the System Status Indicator uses 6/IMU_CAL_LED, and GNSS reset/
timepulse use 7/8. Re-save after a legitimate Board-plugin update to refresh the binding fingerprint.
The following custom CubeMX flow remains manually assignable and uses its imported inventory index.

## STM32 custom hardware flow

The current real custom-hardware provider is STM32CubeMX. A new project draft selects **Custom STM32 Hardware** by default, without asking the user to choose an MCU. This is a manual import workflow, so it does not show or run **Prepare Hardware Files**; Save/Build remains unavailable until a valid `.ioc` or generated CubeMX directory has been imported and its detected MCU has matched one installed Platform plugin.

```text
Configure the exact MCU and peripherals in CubeMX, then Generate Code
  → select Devices in FCCG
  → acknowledge the one-time custom-hardware risk warning
  → import the .ioc or complete generated directory
  → FCCG detects the MCU and matches one installed Platform plugin
  → FCCG validates layout/HAL/CMSIS/startup/linker/peripherals/RTOS
  → Device resources are auto-mapped, then reviewed
  → generate and run build/hardware validation
  → optionally Export Board Plugin
```

FCCG does not edit `.ioc`, solve PLL/pinmux/DMA, install CubeMX, or replace CubeMX. It reads exact MCU/family/package/core, CubeMX/Firmware Package, GPIO/AF/EXTI, UART, SPI, I²C, ADC, Timer/PWM, Classic CAN/FDCAN, DMA, NVIC, useful clocks, generated TIM HAL timebase, and FatFs App/Target/symbol facts without arbitrary peripheral-count limits. It then automatically matches an installed MCU/Platform plugin, showing compatibility facts, source policy, reason, specificity/priority, verification and provenance. Zero matches, tied best matches, or version/source-policy mismatches stop before generation; FCCG never silently falls back to F407 or mixes two HAL trees. It validates UART rate/frame/DMA/IRQ, SPI mode/order/rate, I²C Open Drain/rate/address/pull-up evidence/address conflicts/repeated-start capability, CAN inventory/backend maturity, PWM frequency/resolution/safe state/channel/shared-timer constraints, SDIO/FatFs/DMA/IRQ ownership, generated timebase frequency/IRQ/PWM exclusion, and GPIO electrical/safe-start/interrupt contracts. PWM mode and polarity come only from CubeMX, never from the Device. A project containing CubeMX FreeRTOS/CMSIS-RTOS2 is rejected because SilverStar supplies its own official FreeRTOS component.

The official F407 Platform currently provides software-tested blocking 7-bit I²C master transfers plus 8/16-bit memory-register access, and ordinary fixed-frequency non-complementary PWM1/PWM2 using logical permille duty. The public I²C ABI contains no HAL constants and does not claim DMA/IRQ or arbitrary repeated-start. Open Drain/NOPULL is valid only after the user confirms external pull-ups for that exact selected bus/snapshot; a digest change invalidates it. PWM accepts only channels proven by both CubeMX PWM Generation metadata and generated `HAL_TIM_PWM_ConfigChannel`; 0%/100% use exact forced states and Stop first drives logical inactive. Classic CAN/FDCAN remains visible in inventory, but the F407 bxCAN backend is `reserved` and cannot be assigned to a normal Device. The Platform does not claim CAN Filter/Router/Bus-Off recovery, dynamic timer-frequency changes, complementary/dead-time/center-aligned PWM, servo/control algorithms, electrical verification, or other STM32 families. Default SS0.5 uses none of these optional backends.

Custom hardware is a manual import workflow, so this mode does not show or run the separate **Prepare Hardware Files** action. Save/Build still validates and stages the imported snapshot as part of normal materialization. Selecting an existing Board plugin restores the optional preparation action.

Imported files are copied under `HardwareGenerated/STM32CubeMX/` with a warning README. They are not official SilverStar hardware validation. Confirm clocks, DMA, interrupts, GPIO electrical levels, and power behavior. Importing a changed snapshot later requires a dangerous diff confirmation.

**Export Board Plugin** creates local `.ssplugin` data containing the Board manifest, source `.ioc`, semantic `connections.json`, provenance/docs, and dedicated hardware payload. Install it normally; a later project selects that Board and no longer needs a CubeMX import.

## Flight Configuration

Strategy controls are created from installed manifests. Current slots are Alignment, INS, Estimator, and Landing. Estimator supports **No fusion**, which removes KF6 sources from both Make and EIDE.

The reference JY901B enables Gravity + Known Yaw, 6-axis Hardware Quaternion + Known Yaw, and 9-axis Hardware Quaternion Static Sample alignment. Those hardware choices require static preflight qualification, not absent authoritative runtime-attitude qualification. **Gravity Magnetic-Field Two-Vector Alignment** remains disabled because the current magnetic source lacks absolute-vector qualification. Stillness and Barometer + IMU Window Landing are available; Impact Then Stillness remains disabled. Availability is recalculated from the selected Device plugins. Disabled Alignment/Landing entries keep their normal names, use the theme's disabled text color, and explain missing capabilities in their tooltip rather than appending an “Unavailable” suffix. The three Landing selectors share one reference landing-math component and centralized recovery state machine.

Mode controls are also manifest-driven. Calibration shows only **One-face** and **Six-face** and new projects select neither. Empty selection means no sampling procedure: firmware starts `SYSTEM_CALIBRATION_MODE_NONE`, applies READY identity correction, and—when logging is enabled—still records the Required `CALIBRATION_RESULT` snapshot. OneFace, SixFace, and both together remain valid saved selections. Deployment supports any combination of Apogee/vertical-velocity, Tilt, and Delay, including none; new projects select Apogee and Tilt while Delay starts clear. The manifest also owns the vertical-velocity threshold (default -2 m/s), tilt threshold (default 45°), and delay (default 60 s, generated as `uint32` milliseconds). Per-option requirements disable unsupported choices before selection. Telemetry, maintenance, and logging profiles are independent model categories. Each combo always shows **None** first and currently has one real implementation: **AIR Telemetry Protocol M0**, **Serial Maintenance Protocol 0.0**, or **Flight Log Format 0.0**. Missing or ambiguous compatible transports leave the Profile visible but disabled with an explanatory tooltip. Removing the only telemetry or Log Sink Device clears the dependent slot in the same reconcile transaction; re-adding the Device leaves **None** selected until the user explicitly chooses a Profile. M0 names the low-resource AIR profile and does not change its numeric wire value.

Devices are grouped as Main Controller, Primary Devices, Other Sensors, and Actuators. **Input Voltage Monitor** is selected by default under Other Sensors and may be disabled; it is the logical sensor backed by the SS0.5 ADC/power service, not the ADC itself. The first two Actuator entries are **Launch Ignition Power Output** and **Parachute Pyro Power Output**, without parenthesized Required text. Both are independently optional. Removing launch ignition means external ignition: START remains legal and no GPIO is generated. Removing parachute pyro atomically clears/disables deployment Modes and never re-adds the actuator in a reconcile loop; explicitly enabling it again restores the manifest defaults. Internally both use the one-shot Mission Action Actuator class.

Log availability uses three meanings: a capability can be **Provided** by a Device, **Consumed** by a selected Algorithm, and independently **Recordable** as a raw stream. Native records follow Recordable outputs: BARO_NATIVE stays available with Estimator=None while BARO_MEASUREMENT becomes unavailable. POWER follows Input Voltage Monitor; Optional HW_QUAT_NATIVE is available even when Gravity + Known Yaw does not consume external attitude. MAG_NATIVE is generic and extensible to any compatible selected magnetometer plugin. Required streams are visibly locked and forced on by the model.

The Logging table labels its timing column **Cadence**. Protocol metadata declares whether a record is periodic, follows a source, occurs for each measurement, follows an event, or is one-shot. Periodic entries expose a unit-aware editor and continue to save the canonical value as microseconds; source/event/measurement/one-shot entries show their semantic cadence instead. A stored `period_us = 0` on a non-periodic policy means that the period field is not used—it is never displayed as a zero-period stream. Only `DECIMATION` exposes an editable decimation factor; all other policies show an em dash and retain their compatibility value internally. New projects and Device/Strategy/Mode/logging-profile availability changes select every currently available Record while still clearing unavailable Records. Manual Logging edits are preserved until the next such availability change. **Select All Available** restores every currently available Record after manual edits; **Keep Required Only** clears only optional and recommended Records without changing their policy, cadence, or decimation settings.

A schema or codec proves only that a Record format is known. New Protocol metadata may also declare producer components; when it does, FCCG requires both the normal capability conditions and a selected producer before enabling that Record. Older plugins without producer metadata keep their previous permissive behavior. The verified reference composition now has real Device-task and Telemetry-task producers: STATS and TELEMETRY_DIAG are available and enabled by default, displaying 1 s and 200 ms. The **Export Log Decoder Profile** button requires a saved, current logging-enabled project and writes a verified copy of its deterministic `.ssdecoder` package to the selected destination. It starts no background task, does not change the project or mark it Dirty, and still implements no executable log parser or parser-plugin generator. With logging set to **None**, the stream table, selection buttons, and export action are disabled with a clear status; stored stream preferences remain inactive rather than causing metadata errors.

## Save and project readiness

There is no standalone Generate page or mandatory Preview step. **Code Generation & Build** exposes **Generate Code**, **Open VS Code Workspace**, and **Open Project Folder**. Its advanced **Open Firmware Output** action is enabled only when an actual `.elf`, `.hex`, `.bin`, or `.map` exists. Generate Code reads the GUI model, validates and resolves it, prepares verified hardware, installs newly selected component payloads, updates only changed content, verifies the complete project, and publishes `SilverStar.ssproject` last. It does not build, clean, or run quality checks.

The Devices page has a separate **Indicators** group. **System Status Indicator** is selected by default and may be disabled without affecting flight logic. On SS0.5 it uses the active-low `IMU_CAL_LED` on PA1: calibration activity fast-blinks, calibration-ready/system-not-ready slow-blinks, and ready/mission states stay on. **GNSS Status Indicator** is optional, requires one GNSS Device and a second exclusive GPIO Output, and uses the canonical `position_usable` result: offline/no sample is off, online but unusable slow-blinks, and navigation-usable stays on. The verified SS0.5 profile has no second assignable indicator GPIO, but the checkbox remains enabled on Devices; Hardware Connection explains the missing output and strict generation rejects that unresolved selection. FCCG never reuses P_CONTROL1/P_CONTROL2 or presents a fixed hardware power lamp as a software Device.

The normal build summary contains only the target and development environment. The advanced section separates Arm GNU Toolchain and GNU Make from Host GCC, gives every build/check action a user-facing explanation, and shows **Installation Guide** when a tool is missing. Missing Arm GNU does not block code generation; missing Host GCC disables only Host Tests (assuming Make is present). The guide is informational and never installs software, changes PATH, or writes the registry.

**Open VS Code Workspace** validates the workspace JSON, first folder, and EIDE metadata before launch. It requests a new window even if VS Code already has another workspace open. If launch fails, one localized OK-only dialog gives the exact workspace path to open manually; launcher/exit/stderr diagnostics stay in the FCCG log and are not confused with later EIDE extension loading errors.

Component source copied from plugins is never overwritten by normal Save. FCCG-managed glue and environment metadata are regenerated. A concise diff confirmation appears for component deactivation, conflicts/local source concerns, MCU/target changes, actual changes to normalized FCCG-owned EIDE build fields, or HardwareGenerated replacement. EIDE UI state, target selection, formatting, and uploader/debugger metadata are preserved without a false manual-change warning. Open or drag `SilverStar.ssproject` to restore a project.

Build, Clean, and every advanced check use the same readiness boundary. Dirty models are saved automatically; missing/stale project material is regenerated; a Ready project proceeds directly to Make with the exact project root as `cwd`. A project is Ready only when the descriptor, Makefile/targets, selected payloads, verified hardware, EIDE, VS Code, workspace, and ownership hashes pass validation.

**File → Save Project As...** copies the complete source project to an empty destination, preserving manual changes to project-owned Device/Algorithm/Platform/FlightLogic files while excluding `build/`, temporary caches, and intermediate artifacts.

The output directory can be any explicitly selected writable project directory. That exact directory is the authorization root: FCCG may create/stage/build inside it but cannot reach its parent or siblings. Internal plugin/settings/log/import data remains under the FCCG workspace. Automated FCCG tests still generate only below `tests/`.

When Flight Log Format 0.0 is enabled, generation also emits `<ProjectName>.ssdecoder`. It is a deterministic JSON-only ZIP with the SSLOG schema, firmware, selected devices/strategies/modes, nullable telemetry/maintenance locks, record availability, and active stream policy. When logging is **None**, no package, decoder descriptor, `Logs/README.md`, golden expectation, or golden Host task is emitted; stale FCCG-managed versions are removed on apply while manual log files are preserved. `Generated/project_semantics.json` remains available in both states for project auditing. The downstream FLP discovery contract searches the current directory, child directories, and the parent for a matching profile; current FLP integration remains outside this FCCG task, and FCCG never modifies FLP.

For a logging-enabled project, running Host Tests also creates `Logs/Golden/<ProjectName>_golden.sslog` with the generated
project's real C SSLOG codec and verifies a deserialize round trip before publishing it.
`Logs/Golden/expected.json` provides the matching Record, hash, physical-endpoint, and Canonical
Channel expectations; it is a test fixture, not a second decoder-package format.

## Plugins and Build

Plugins are declarative data. Installation validates/stages an archive and never executes its contents. **Plugins → Plugin Manager...** exposes the useful ID/name/type/class/version/source/dependency/capability/status fields directly in its table; the redundant details popup was removed. **Install Plugin...** and **Refresh Plugins** are in the same menu. Normal configuration pages use localized physical names.

The normal page shows only the target and development environment, without a duplicate tool-status area. Advanced details separate Arm GNU Toolchain and GNU Make under the firmware build environment from Host GCC under the host-test environment. Objcopy and Size are derived from the selected Arm GNU `bin` directory, and static analysis reuses Arm GCC with `-fanalyzer`; Host GCC is not presented as a firmware compiler. The advanced firmware build defaults to Release. Debug (`-Og -g3 -gdwarf-2`) remains available in generated VS Code/EIDE tasks, while Release (`-O2 -g`) is the default and does not disable SilverStar assertions or safety gates. Power of Ten is a real project compliance gate, not formal verification or certification. Tool overrides remain project-local, and generated firmware builds independently with Make or native EIDE; no Python/FCCG runtime is required.

**Open VS Code Workspace** tries `code.cmd`, `code.exe`, `code`, known VS Code locations, and finally the system association. Every CLI route receives `--new-window <absolute-workspace>` so an existing unrelated window is not replaced. A still-running launcher or zero exit means only that VS Code accepted the request. If every route fails, technical reasons remain in the FCCG log while one localized OK-only dialog identifies the workspace to open manually. EIDE metadata starts from the read-only working firmware template and keeps its required target/upload structure with no Pack and no J-Link default. FCCG exposes no flash button; a missing EIDE/J-Link temporary XML remains an external extension problem, not evidence of a firmware compile failure.

## Current limits

Only the STM32F407VET6/SS0.5 single-device reference is fully firmware-build validated. FCCG v0.x formally supports STM32 + STM32CubeMX manual hardware configuration only. Software and Host tests cover repeated JY901B/NEO-M9N/SX1281 contexts and a synthetic multi-resource compile fixture, but real dual-sensor/dual-radio electrical, RF, HIL, and flight testing is still outstanding. IMU selection is allowed only before calibration/alignment and then locks. GNSS basic-liveness and AIR local-TX-timeout failover are one-way; there is no voting, cross-check, Multi-EKF, RF end-to-end health, or automatic failback. The Platform has a PWM resource backend but no concrete continuous-control actuator, Guidance, Control, or Control Allocation implementation. There is no complete clock solver, validated alternate MCU/provider, or Keil environment. No current Board/Environment pair declares a validated flash capability, so no GUI, Make, VS Code, or EIDE upload action is emitted; no electrical validation is implied by generation.

## Tool detection, results, and source export

The main tool area has only **Detect Toolchain** and **Installation Guide**. Detection checks saved
paths, PATH and common locations, then validates Arm GCC/objcopy/size, Make, and a Windows-capable
Host GCC. Nonstandard locations are selected inside the results dialog. The short guide opens only
the official [Arm GNU guide](https://learn.arm.com/install-guides/gcc/arm-gnu/) and
[MSYS2 site](https://www.msys2.org/); FCCG never downloads, installs, edits PATH, or writes the
registry. Missing Arm/Make disables only dependent Make tasks; missing Host GCC disables only Host
Tests. Generate Code, VS Code opening, and source export remain available.

Successful quality checks update persistent project-local result pills with time, duration, and
summary and do not open modal success dialogs. A failure opens one localized error, expands the
log, and preserves compiler/script output. Every long task reports real planned and completed
work through the shared progress protocol. `BEGIN` names the active subject without increasing
the completed count; only `DONE` advances it. Success reaches 100%, while failure or cancellation
keeps the last real position instead of presenting a false completion. **Clean FCCG Build
Outputs** reports one completed step; **Clean All Build Outputs** reports three completed steps for
`build/FCCG`, `.eide/build`, and `.eide/.cache`. Neither cleanup action uses a cycling indicator.

Host Tests count runnable tests, expected compile-pass gates, and expected compile-rejection gates
before execution. A correctly rejected illegal configuration is summarized neutrally as an
expected compile rejection, not as a product failure. The original GCC diagnostic remains in the
expandable detailed log and the project-local Host Test detail log. A gate is a real failure when
an expected rejection compiles, an expected pass fails, the diagnostic does not match the intended
compile-time gate, or a test executable returns nonzero.

Use **File → Export Source Package** for a deterministic
review ZIP containing FCCG/docs/test/plugin/schema sources but no build, pytest, reference-copy,
acceptance, binary, dependency, map, or listing artifacts.
