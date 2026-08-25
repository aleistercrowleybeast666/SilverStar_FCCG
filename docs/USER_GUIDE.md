# User guide

## Create a project

Run `python main.py` and choose **File → New Project**. The compact one-step dialog uses the native title bar and asks only for project name and output directory. The sole current firmware/Core/OS/Protocol/Environment defaults are automatic; select the MCU on Devices. Configuration continues through exactly four main pages:

```text
Devices → Flight Configuration → Hardware Connection → Code Generation & Build
```

When only one Core, OS, Protocol Bundle, or Development Environment is installed, FCCG selects it automatically.

## Select physical Devices first

The page starts with the STM32 MCU, then physical instances such as `imu0`/JY901B, `gnss0`/NEO-M9N, `telemetry0`/E28-2G4M12SX (SX1281), and `maintenance0`/Serial Maintenance Protocol 0.0. **Maintenance Console** remains the stable system-function label. Current plugins set `project_max=1`, so no misleading Add control appears. The **Other Sensors** section remains visible; **Install Plugin** appears there only while no Other Sensors plugin is installed.

One physical Device may provide several capabilities. The Devices page shows a concise capability summary but no capability enable/source controls. FCCG derives actual usage from selected Algorithm/Flight requirements on **Flight Configuration**. A sole required provider is selected automatically. Only an ambiguous case—such as JY901B and BMP280 both providing barometric altitude—shows a data-source selector and persists that override. Unused physical outputs are read-only status, not project choices. The consumer implementation owns lifecycle; FCCG does not expose PRE_START/ASCENT/RECOVERY phase policy.

USART, SPI, GPIO, exclusive/shared ownership, DMA, and pinmux are internal contracts resolved on Hardware Connection, not editable controls on the normal Device page.

## Existing Board flow

```text
Select existing Board plugin
        → Board compatibility is checked against MCU + Devices
        → resource defaults are auto-assigned
        → inspect only if “Advanced Resource Configuration” is needed
        → optionally Prepare Hardware Files
        → Generate / Apply Project
        → Open VS Code Workspace
        → Build with VS Code / EIDE
```

The Board selector keeps incompatible entries identifiable and marks them in muted gray while explaining missing resource kinds. Fixed roles cannot be changed; selectable roles show only legal candidates. Reserved resources and declared conflict groups are enforced. **Prepare Hardware Files** is shown only for a Board plugin: it copies and checks the verified SS0.5 payload without invoking CubeMX, and repeating it with the same fingerprint is a no-op. Save performs the same preparation automatically, so this optional button is never a prerequisite.

The page is named **Hardware Connection** because it resolves Device needs against real hardware. For an STM32 Board, FCCG reads the Board `.ioc`, inventories pins/peripherals/DMA/IRQ/clocks, validates requirement constraints, and then applies the Board's semantic `connections.json`. A fixed connection is shown as text with its physical peripheral, pins, baud, DMA and IRQ details; only genuinely selectable roles use a dropdown. **Complete Manual Assignment and Check** performs strict resolution and stores a fingerprint; changing Devices, Modes, IOC content, or assignments clears the confirmation.

## STM32 custom hardware flow

Only an MCU with a compatible HardwareConfigurationProvider offers custom hardware. The current real implementation is STM32CubeMX for STM32. A new STM32 draft selects **Custom STM32 Hardware** by default. This is a manual import workflow, so it does not show or run **Prepare Hardware Files**; Save/Build remains unavailable until a valid `.ioc` or generated CubeMX directory has been imported.

```text
Select STM32 MCU
  → select Devices
  → configure peripherals in CubeMX and Generate Code
  → acknowledge the one-time custom-hardware risk warning
  → import the .ioc or complete generated directory
  → FCCG validates MCU/layout/HAL/CMSIS/startup/linker/peripherals/RTOS
  → Device resources are auto-mapped, then reviewed
  → generate and run build/hardware validation
  → optionally Export Board Plugin
```

FCCG does not edit `.ioc`, solve PLL/pinmux/DMA, install CubeMX, or replace CubeMX. It reads MCU/package/core, GPIO/AF/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC and useful clock fields without arbitrary peripheral-count limits. It validates UART rate/frame/DMA/IRQ, SPI mode/order/rate, I2C rate/address/pull-up, PWM frequency/resolution/polarity, and GPIO electrical/safe-start/interrupt contracts. A project containing CubeMX FreeRTOS/CMSIS-RTOS2 is rejected because SilverStar supplies its own official FreeRTOS component.

Custom hardware is a manual import workflow, so this mode does not show or run the separate **Prepare Hardware Files** action. Save/Build still validates and stages the imported snapshot as part of normal materialization. Selecting an existing Board plugin restores the optional preparation action.

Imported files are copied under `HardwareGenerated/STM32CubeMX/` with a warning README. They are not official SilverStar hardware validation. Confirm clocks, DMA, interrupts, GPIO electrical levels, and power behavior. Importing a changed snapshot later requires a dangerous diff confirmation.

**Export Board Plugin** creates local `.ssplugin` data containing the Board manifest, source `.ioc`, semantic `connections.json`, provenance/docs, and dedicated hardware payload. Install it normally; a later project selects that Board and no longer needs a CubeMX import.

## Flight Configuration

Strategy controls are created from installed manifests. Current slots are Alignment, INS, Estimator, and Landing. Estimator supports **No fusion**, which removes KF6 sources from both Make and EIDE.

The reference JY901B enables Gravity + Known Yaw, 6-axis Hardware Quaternion + Known Yaw, and 9-axis Hardware Quaternion Static Sample alignment. Those hardware choices require static preflight qualification, not absent authoritative runtime-attitude qualification. **Gravity Magnetic-Field Two-Vector Alignment** remains disabled because the current magnetic source lacks absolute-vector qualification. Stillness and Barometer + IMU Window Landing are available; Impact Then Stillness remains disabled. Availability is recalculated from the selected Device plugins. Disabled Alignment/Landing entries keep their normal names, use the theme's disabled text color, and explain missing capabilities in their tooltip rather than appending an “Unavailable” suffix. The three Landing selectors share one reference landing-math component and centralized recovery state machine.

Mode controls are also manifest-driven. Calibration offers Existing/OneFace/SixFace as a multi-select group and new projects select all three. Deployment supports any combination of Apogee/vertical-velocity, Tilt, and Delay, including none; new projects select Apogee and Tilt while Delay starts clear. The manifest also owns the vertical-velocity threshold (default -2 m/s), tilt threshold (default 45°), and delay (default 60 s, generated as `uint32` milliseconds). Per-option requirements disable unsupported choices before selection. Telemetry, maintenance, and logging protocol profiles are independent categories; the current AIR compact V0, maintenance 0.0, and SSLOG0 choices remain visible but disabled because each category currently has one profile. Logging is directly visible and Protocol-owned; existing projects preserve stored choices.

Devices are grouped as Main Controller, Primary Devices, Other Sensors, and Actuators. **Input Voltage Monitor** is selected by default under Other Sensors and may be disabled; it is the logical sensor backed by the SS0.5 ADC/power service, not the ADC itself. The first two Actuator entries are **Launch Ignition Power Output** and **Parachute Pyro Power Output**, without parenthesized Required text. Both are independently optional. Removing launch ignition means external ignition: START remains legal and no GPIO is generated. Removing parachute pyro atomically clears/disables deployment Modes and never re-adds the actuator in a reconcile loop; explicitly enabling it again restores the manifest defaults. Internally both use the one-shot Mission Action Actuator class.

Log availability uses three meanings: a capability can be **Provided** by a Device, **Consumed** by a selected Algorithm, and independently **Recordable** as a raw stream. Native records follow Recordable outputs: BARO_NATIVE stays available with Estimator=None while BARO_MEASUREMENT becomes unavailable. POWER follows Input Voltage Monitor; Optional HW_QUAT_NATIVE is available even when Gravity + Known Yaw does not consume external attitude. MAG_NATIVE is generic and extensible to any compatible selected magnetometer plugin. Required streams are visibly locked and forced on by the model.

## Save and project readiness

There is no standalone Generate page or mandatory Preview step. **Code Generation & Build** exposes **Generate / Apply Project**, **Open VS Code Workspace**, and **Open Project Folder**. Its advanced **Open Firmware Output** action is enabled only when an actual `.elf`, `.hex`, `.bin`, or `.map` exists. Generate/Apply reads the GUI model, validates and resolves it, prepares verified hardware, installs newly selected component payloads, updates only changed content, verifies the complete project, and publishes `SilverStar.ssproject` last. It does not build, clean, or run quality checks.

Component source copied from plugins is never overwritten by normal Save. FCCG-managed glue and environment metadata are regenerated. A concise diff confirmation appears for component deactivation, conflicts/local source concerns, MCU/target changes, manual EIDE overwrite, or HardwareGenerated replacement. Open or drag `SilverStar.ssproject` to restore a project.

Build, Clean, and every advanced check use the same readiness boundary. Dirty models are saved automatically; missing/stale project material is regenerated; a Ready project proceeds directly to Make with the exact project root as `cwd`. A project is Ready only when the descriptor, Makefile/targets, selected payloads, verified hardware, EIDE, VS Code, workspace, and ownership hashes pass validation.

**File → Save Project As...** copies the complete source project to an empty destination, preserving manual changes to project-owned Device/Algorithm/Platform/FlightLogic files while excluding `build/`, temporary caches, and intermediate artifacts.

The output directory can be any explicitly selected writable project directory. That exact directory is the authorization root: FCCG may create/stage/build inside it but cannot reach its parent or siblings. Internal plugin/settings/log/import data remains under the FCCG workspace. Automated FCCG tests still generate only below `tests/`.

Generation also emits `<ProjectName>.ssdecoder`. It is a deterministic JSON-only ZIP with the SSLOG schema, firmware, selected devices/strategies/modes, record availability and active stream policy. It is intended for a future generic SilverStar_FLP decoder engine; current FLP does not yet import it, and FCCG never modifies FLP.

## Plugins and Build

Plugins are declarative data. Installation validates/stages an archive and never executes its contents. **Plugins → Plugin Manager...** exposes the useful ID/name/type/class/version/source/dependency/capability/status fields directly in its table; the redundant details popup was removed. **Install Plugin...** and **Refresh Plugins** are in the same menu. Normal configuration pages use localized physical names.

The normal page shows only Arm GNU Toolchain and Make status. Objcopy and Size are derived from the selected Arm GNU `bin` directory. Host GCC appears only with advanced quality checks, and static analysis reuses Arm GCC with `-fanalyzer`; it is not presented as another compiler. The advanced **Validation Build** defaults to Release. Debug (`-Og -g3 -gdwarf-2`) remains available in generated VS Code/EIDE tasks, while Release (`-O2 -g`) is the default and does not disable SilverStar assertions or safety gates. Power of Ten is a real project compliance gate, not formal verification or certification. Tool overrides remain project-local, and generated firmware builds independently with Make or native EIDE; no Python/FCCG runtime is required.

**Open VS Code Workspace** prefers the real `Code.exe --new-window <absolute-workspace>` executable so a visible window is created, derives it from discovered `code.cmd` installations, checks known VS Code locations, and finally tries the system association. If every route fails, a localized dialog includes the workspace path and exact launcher/association reason. EIDE metadata starts from the read-only working firmware template and keeps its required target/upload structure with no Pack and no J-Link default. FCCG exposes no flash button; a missing EIDE/J-Link temporary XML remains an external extension problem, not evidence of a firmware compile failure.

## Current limits

Only the STM32F407VET6/SS0.5 reference is fully firmware-build validated. FCCG v0.x formally supports STM32 + STM32CubeMX manual hardware configuration only. Current drivers do not yet support multiple IMU/GNSS/link/maintenance instances; sensor voting/failover and Multi-EKF are not implemented. There is no complete clock solver, real PWM actuator, alternate MCU/provider, Guidance, Control, Control Allocation, or Keil environment. No current Board/Environment pair declares a validated flash capability, so no GUI, Make, VS Code, or EIDE upload action is emitted; no electrical validation is implied by generation.
