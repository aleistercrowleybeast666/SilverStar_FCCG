# User guide

## Create a project

Run `python main.py` and choose **File → New Project**. The compact one-step dialog uses the native title bar and asks only for project name and output directory. The sole current firmware/Core/OS/Protocol/Environment defaults are automatic; select the MCU on Devices. Configuration continues through exactly four main pages:

```text
Devices → Flight Configuration → Hardware Connection → Build
```

When only one Core, OS, Protocol Bundle, or Development Environment is installed, FCCG selects it automatically.

## Select physical Devices first

The page starts with the STM32 MCU, then physical instances such as `imu0`/JY901B, `gnss0`/NEO-M9N, `telemetry0`/E28-2G4M12SX (SX1281), and `maintenance0`/Serial Maintenance Protocol 0.0. **Maintenance Console** remains the stable system-function label. Current plugins set `project_max=1`, so no misleading Add control appears. The **Other Sensors** section remains visible with an install action even when empty.

One physical Device may provide several capabilities. The Devices page shows a concise capability summary but no capability enable/source controls. FCCG derives actual usage from selected Algorithm/Flight requirements on **Flight Configuration**. A sole required provider is selected automatically. Only an ambiguous case—such as JY901B and BMP280 both providing barometric altitude—shows a data-source selector and persists that override. Unused physical outputs are read-only status, not project choices. The consumer implementation owns lifecycle; FCCG does not expose PRE_START/ASCENT/RECOVERY phase policy.

USART, SPI, GPIO, exclusive/shared ownership, DMA, and pinmux are internal contracts resolved on Hardware Connection, not editable controls on the normal Device page.

## Existing Board flow

```text
Select existing Board plugin
        → Board compatibility is checked against MCU + Devices
        → resource defaults are auto-assigned
        → inspect only if “Advanced Resource Configuration” is needed
        → optionally Prepare Hardware Files
        → Save
        → Build
```

The Board selector keeps incompatible entries identifiable and explains missing resource kinds. Fixed roles cannot be changed; selectable roles show only legal candidates. Reserved resources and declared conflict groups are enforced. **Prepare Hardware Files** copies and checks the verified SilverStar 0.5 payload without invoking CubeMX; repeating it with the same fingerprint is a no-op. Save performs the same preparation automatically, so this optional button is never a prerequisite.

The page is named **Hardware Connection** because it resolves Device needs against real hardware. For an STM32 Board, FCCG reads the Board `.ioc`, inventories pins/peripherals/DMA/IRQ/clocks, validates requirement constraints, and then applies the Board's semantic `connections.json`. A fixed connection is shown as text with its physical peripheral, pins, baud, DMA and IRQ details; only genuinely selectable roles use a dropdown.

## STM32 custom hardware flow

Only an MCU with a compatible HardwareConfigurationProvider offers custom hardware. The current real implementation is STM32CubeMX for STM32. A new draft starts at **No hardware configuration selected**, which is allowed during editing but rejected by Save/Build until a Board or custom import is completed.

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

FCCG does not edit `.ioc`, solve PLL/pinmux/DMA, install CubeMX, or replace CubeMX. It reads MCU/package/core, GPIO/AF/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC and useful clock fields without arbitrary peripheral-count limits. A project containing CubeMX FreeRTOS/CMSIS-RTOS2 is rejected because SilverStar supplies its own official FreeRTOS component.

Custom hardware is a manual import workflow, so this mode does not show or run the separate **Prepare Hardware Files** action. Save/Build still validates and stages the imported snapshot as part of normal materialization. Selecting an existing Board plugin restores the optional preparation action.

Imported files are copied under `HardwareGenerated/STM32CubeMX/` with a warning README. They are not official SilverStar hardware validation. Confirm clocks, DMA, interrupts, GPIO electrical levels, and power behavior. Importing a changed snapshot later requires a dangerous diff confirmation.

**Export Board Plugin** creates local `.ssplugin` data containing the Board manifest, source `.ioc`, semantic `connections.json`, provenance/docs, and dedicated hardware payload. Install it normally; a later project selects that Board and no longer needs a CubeMX import.

## Flight Configuration

Strategy controls are created from installed manifests. Current slots are Alignment, INS, Estimator, and Landing. Estimator supports **No fusion**, which removes KF6 sources from both Make and EIDE.

Mode controls are also manifest-driven. Calibration offers Existing/OneFace/SixFace as a multi-select group and new projects select all three. Deployment supports any combination of Apogee/vertical-velocity, Tilt, and Delay, including none; new projects select all three. Per-option requirements disable unsupported choices before selection. The same page shows the read-only capability/consumer table and ambiguity-only source selectors. Logging is directly visible and is read from the selected Protocol plugin: record names are localized by Protocol metadata, Required records remain visibly checked and locked, every currently available record starts enabled, and unavailable records are disabled. Existing projects preserve their stored choices.

## Save and project readiness

There is no Generate page, separate normal Generate/Apply action, or mandatory Preview step. **Save** reads the GUI model, validates and resolves it, prepares verified hardware, installs newly selected component payloads, regenerates only FCCG-owned glue/editor/build metadata, verifies the complete project, and publishes `SilverStar.ssproject` last. The lifecycle is Draft/Dirty → Materializing → Ready, with Building/Error used while work runs or fails.

Component source copied from plugins is never overwritten by normal Save. FCCG-managed glue and environment metadata are regenerated. A concise diff confirmation appears for component deactivation, conflicts/local source concerns, MCU/target changes, manual EIDE overwrite, or HardwareGenerated replacement. Open or drag `SilverStar.ssproject` to restore a project.

Build, Clean, and every advanced check use the same readiness boundary. Dirty models are saved automatically; missing/stale project material is regenerated; a Ready project proceeds directly to Make with the exact project root as `cwd`. A project is Ready only when the descriptor, Makefile/targets, selected payloads, verified hardware, EIDE, VS Code, workspace, and ownership hashes pass validation.

**File → Save Project As...** copies the complete source project to an empty destination, preserving manual changes to project-owned Device/Algorithm/Platform/FlightLogic files while excluding `build/`, temporary caches, and intermediate artifacts.

The output directory can be any explicitly selected writable project directory. That exact directory is the authorization root: FCCG may create/stage/build inside it but cannot reach its parent or siblings. Internal plugin/settings/log/import data remains under the FCCG workspace. Automated FCCG tests still generate only below `tests/`.

Generation also emits `<ProjectName>.ssdecoder`. It is a deterministic JSON-only ZIP with the SSLOG schema, firmware, selected devices/strategies/modes, record availability and active stream policy. It is intended for a future generic SilverStar_FLP decoder engine; current FLP does not yet import it, and FCCG never modifies FLP.

## Plugins and Build

Plugins are declarative data. Installation validates/stages an archive and never executes its contents. **Plugins → Plugin Manager...** exposes the useful ID/name/type/class/version/source/dependency/capability/status fields directly in its table; the redundant details popup was removed. **Install Plugin...** and **Refresh Plugins** are in the same menu. Normal configuration pages use localized physical names.

Build exposes Build/Clean and tool status. The normal Build button always uses Debug. **Build Release**, tool paths, Host Tests, Architecture Check, Power of Ten, Static Analysis, and Artifact Check are in a responsive grid under Advanced Build Settings. Debug uses `-Og -g3 -gdwarf-2`; Release uses `-O2 -g` without disabling SilverStar assertions or safety gates. Build configuration is not saved in the project and never marks it dirty. Before an Arm build, FCCG runs Make in dry-run mode and counts the pending compile/link/SIZE/HEX/BIN markers; the real run streams each output line immediately and advances a determinate progress bar. Tool overrides remain project-local, and generated firmware builds independently with Make or native EIDE; no Python/FCCG runtime is required.

## Current limits

Only the STM32F407VET6/SilverStar 0.5 reference is fully firmware-build validated. FCCG v0.x formally supports STM32 + STM32CubeMX manual hardware configuration only. Current drivers do not yet support multiple IMU/GNSS/link/maintenance instances; sensor voting/failover and Multi-EKF are not implemented. There is no complete clock solver, real PWM actuator, alternate MCU/provider, Guidance, Control, Control Allocation, or Keil environment. No current Board/Environment pair declares a validated flash capability, so no GUI, Make, VS Code, or EIDE upload action is emitted; no electrical validation is implied by generation.
