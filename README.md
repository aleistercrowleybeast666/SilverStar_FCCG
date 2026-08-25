# SilverStar Flight Controller Code Generator

SilverStar_FCCG (FCCG) is a PySide6 flight-controller configurator, declarative component manager, safe project assembler, thin glue generator, STM32 hardware-import front end, and development-environment generator.

The current validated target is the real SilverStar 0.0.9 combination: STM32F407VET6, SS0.5, JY901B, NEO-M9N, E28-2G4M12SX with the existing SX1281 driver, Serial Maintenance Protocol 0.0, FreeRTOS 11.3.0, the current Alignment/INS/KF6/Landing strategies, deployment/calibration modes, AIR, and SSLOG. The 29 builtin packages retain read-only provenance from reference commit `e67529ef67f53049fa8d7a1d3eed314e11043d1a`; the added Landing selectors share the single reference implementation, while three declarative logical Devices expose input-voltage monitoring and the two SS0.5 mission-action outputs.

## Run

Python 3.11 or newer and PySide6 6.8 or newer are required.

```powershell
python main.py
```

The main window has exactly four pages: **Devices**, **Flight Configuration**, **Hardware Connection**, and **Code Generation & Build**. Project commands live in **File** and plugin management lives in the **Plugins** menu/dialog. Simplified Chinese/English, Light/Dark themes, manifest-driven controls, visible checkbox states, repository-local settings, and shared background-task progress follow the copied GUI standard. Advanced hardware/verification sections collapse by visibility only; Logging remains directly available.

## Device-first workflow

1. Enter only the project name and output directory. The sole current firmware/Core/OS/Protocol/Environment defaults are selected automatically.
2. Select the STM32 MCU and Device instances. **Other Sensors** contains the default-on input-voltage monitor; **Actuators** lists Launch Ignition Power Output first and Parachute Pyro Power Output second. These bind to SS0.5 ADC/GPIO resources on Hardware Connection; raw ADC/GPIO entries are never presented as Devices.
3. Open **Flight Configuration** to select manifest-defined Strategies and Modes, edit per-Mode parameters, choose independent telemetry/maintenance/logging protocol profiles, review derived capability consumers/sources, and adjust Protocol-owned Required/Recommended/Optional logging. Incompatible choices are disabled from Device capabilities alone, even before hardware is selected. A source override appears and is saved only for a genuinely ambiguous required capability.
4. Open **Hardware Connection**. A new STM32 draft starts on **Custom STM32 Hardware** for the manual CubeMX import flow; alternatively select a compatible Board. FCCG parses the Board/imported `.ioc`, validates typed UART/SPI/I2C/PWM and GPIO electrical contracts, preserves still-valid assignments, and auto-assigns new semantic connections. Use **Complete Manual Assignment and Check** to seal the current mapping fingerprint; any relevant Device/Mode/IOC/assignment change invalidates that confirmation. Only Board plugins expose the optional **Prepare Hardware Files** action.
5. Choose **Generate / Apply Project** (or **File → Save Project**). This validates, resolves, prepares hardware, incrementally updates the standalone source project, renders Make/EIDE/VS Code, verifies readiness, and publishes `SilverStar.ssproject` last. Unchanged managed and component files retain their timestamps; `build/` and dependency files are not cleaned.
6. From **Code Generation & Build**, choose **Open VS Code Workspace** or **Open Project Folder**, then build in VS Code/EIDE. Release is the default Make/EIDE/VS Code target and Debug remains available. **Open Firmware Output** stays disabled until an actual ELF/HEX/BIN/MAP artifact exists. FCCG's **Validation Build** is intentionally under advanced verification and also defaults to Release; generation itself never runs a full build or quality suite.

**Save Project As...** stages and copies the complete generated source tree—including project-owned Device, Algorithm, Platform, and FlightLogic edits—while excluding build output, caches, and intermediate artifacts. The copied descriptor is published last, so a failed operation is not presented as a ready project.

For STM32 custom hardware, configure and generate a project in STM32CubeMX, then import its `.ioc` or complete generated directory. FCCG inventories MCU/package/core, pins/AF/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC, and useful clocks; validates bus roles/rates/modes/DMA/IRQ plus GPIO pull/output type/speed/polarity/safe startup/EXTI constraints; then stores the snapshot only under `HardwareGenerated/STM32CubeMX/`. A validated mapping can be exported as a local `.ssplugin` Board for later reuse without CubeMX.

The output directory may be any user-selected writable project directory. FCCG treats that exact directory as a separate authorization root; generation/build cannot escape it, while plugins, settings, logs, and snapshots remain constrained to the FCCG workspace.

## Plugins and ownership

Supported declarative types are Core, MCU, Board, Device, Algorithm, FlightLogic, OS, ProtocolBundle, HardwareConfigurationProvider, and DevelopmentEnvironment. Installing `.ssplugin` data never executes package code or scripts.

Component payloads are copied only when first selected and then belong to the generated embedded project. Normal Save does not overwrite them. FCCG replaces only its small `Generated/` glue surface and managed project/editor metadata. A new CubeMX snapshot is a special dangerous replacement and requires confirmation; ordinary component deactivation retains files and removes them only from the active source graph.

Each generated project also receives `<ProjectName>.ssdecoder`, a deterministic ZIP containing JSON metadata only. It carries the SSLOG schema, selected devices/strategies/modes, Mode parameter values, independent protocol profiles, record availability, and active stream profile for a future generic SilverStar_FLP decoder engine; FCCG does not modify FLP or execute decoder code.

## Generated development environment

The default Environment plugin produces:

- `<ProjectName>.code-workspace`;
- project-local `.vscode/` tasks/settings/extensions;
- a native, non-empty `.eide/eide.yml`;
- `Makefile` and target metadata.

Make and EIDE are rendered from the same resolved source/include/define/linker graph. VS Code tasks call that Make project. Generated firmware builds do not require FCCG or Python.

The EIDE structure is copied from the read-only working firmware template, then only project/source/include/define/linker/output/target fields are rendered. It deliberately keeps `deviceName: null`, `packDir: null`, the reference target/upload structure, and OpenOCD rather than J-Link as the template default. This is structural compatibility, not a validated flash claim; FCCG emits no flash button or task. **Open VS Code Workspace** prefers the installed `Code.exe --new-window <absolute-workspace>`, then uses safe CLI/file-association fallbacks; a failed launch shows its exact reason.

Logging distinguishes **Provided**, **Consumed**, and **Recordable**. Native records depend on recordable Device outputs, not fusion selection: `BARO_NATIVE` remains available with Estimator=None while `BARO_MEASUREMENT` does not. The default project records Optional `HW_QUAT_NATIVE` even when the selected flight algorithm does not consume external attitude. `MAG_NATIVE` is a generic extensible magnetic-data record and becomes available whenever any compatible selected plugin enables recordable magnetic output; it is not tied to JY901B. POWER follows the optional input-voltage monitor.

```powershell
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Release all
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Debug all
mingw32-make host-tests
mingw32-make architecture-check
mingw32-make power10-check
mingw32-make static-analysis
mingw32-make artifact-check
```

The Power of Ten target is a real project-specific automatic compliance gate, not formal proof or safety certification. Static analysis is the real Arm GNU GCC `-fanalyzer` build over first-party sources with warnings treated as errors.

## FCCG tests

```powershell
python -m pytest
python -m compileall -q src tools
```

All automated outputs remain below `tests/`. FCCG does not alter PATH, registry, global IDE settings, another repository, or the read-only firmware/GUI references.

See [User Guide](docs/USER_GUIDE.md), [Architecture](docs/ARCHITECTURE.md), [Plugin Format](docs/PLUGIN_FORMAT.md), [Project Format](docs/PROJECT_FORMAT.md), [Generated Code](docs/GENERATED_CODE.md), [Build Integration](docs/BUILD.md), and [Validation](VALIDATION.md).
