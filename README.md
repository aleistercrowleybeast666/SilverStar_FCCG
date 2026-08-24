# SilverStar Flight Controller Code Generator

SilverStar_FCCG (FCCG) is a PySide6 flight-controller configurator, declarative component manager, safe project assembler, thin glue generator, STM32 hardware-import front end, and development-environment generator.

The current validated target is the real SilverStar 0.0.9 combination: STM32F407VET6, SilverStar 0.5, JY901B, NEO-M9N, E28-2G4M12SX with the existing SX1281 driver, Serial Maintenance Protocol 0.0, FreeRTOS 11.3.0, the current Alignment/INS/KF6/Landing strategies, deployment/calibration modes, AIR, and SSLOG. The 23 builtin packages were imported read-only from reference commit `b8c90e997c3113dd23074302682c5560dae18926`.

## Run

Python 3.11 or newer and PySide6 6.8 or newer are required.

```powershell
python main.py
```

The main window has exactly four pages: **Devices**, **Flight Configuration**, **Hardware Connection**, and **Build**. Project commands live in **File** and plugin management lives in the **Plugins** menu/dialog. Simplified Chinese/English, Light/Dark themes, manifest-driven controls, visible checkbox states, repository-local settings, and shared background-task progress follow the copied GUI standard. Advanced hardware/build sections collapse by visibility only; Logging remains directly available.

## Device-first workflow

1. Enter only the project name and output directory. The sole current firmware/Core/OS/Protocol/Environment defaults are selected automatically.
2. Select the STM32 MCU and physical Device instances. Devices declare what they can provide; the page does not expose manual capability enable switches.
3. Open **Flight Configuration** to select manifest-defined Strategies and Modes, review the derived capability consumers/sources, and adjust Protocol-owned Required/Recommended/Optional logging. Incompatible choices are disabled from Device capabilities alone, even before hardware is selected. A source override appears and is saved only for a genuinely ambiguous required capability.
4. Open **Hardware Connection** and select a compatible Board or import STM32CubeMX data. A new draft remains in the non-fatal `unselected` state until this step. FCCG then parses the Board/imported `.ioc`, builds a physical inventory, validates Device contracts, preserves still-valid assignments, auto-assigns new semantic connections, and exposes meaningful alternatives under **Advanced Resource Configuration**.
5. Choose **File → Save Project**. Save means Validate → Resolve → prepare verified hardware → assemble/update sources → render Make/EIDE/VS Code → verify readiness → publish `SilverStar.ssproject` last. A diff confirmation appears only for dangerous replacement/removal/conflict cases.
6. Choose **Build** for a fixed Debug build, or **Build Release** under **Advanced Build Settings**. Running either configuration is not a project-model choice and does not mark the project dirty. If the model itself is dirty or incomplete, FCCG saves/applies it first and then invokes Make with the project root as its explicit working directory. A Make dry-run counts actual pending compile/link/conversion steps; live output and structured progress markers update the log and determinate progress bar as the build runs.

**Save Project As...** stages and copies the complete generated source tree—including project-owned Device, Algorithm, Platform, and FlightLogic edits—while excluding build output, caches, and intermediate artifacts. The copied descriptor is published last, so a failed operation is not presented as a ready project.

For STM32 custom hardware, configure and generate a project in STM32CubeMX, then import its `.ioc` or complete generated directory. FCCG inventories MCU/package/core, pins/AF/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC, and useful clocks; validates the MCU, layout, resources and RTOS conflicts; then stores the snapshot only under `HardwareGenerated/STM32CubeMX/`. A validated mapping can be exported as a local `.ssplugin` Board for later reuse without CubeMX.

The output directory may be any user-selected writable project directory. FCCG treats that exact directory as a separate authorization root; generation/build cannot escape it, while plugins, settings, logs, and snapshots remain constrained to the FCCG workspace.

## Plugins and ownership

Supported declarative types are Core, MCU, Board, Device, Algorithm, FlightLogic, OS, ProtocolBundle, HardwareConfigurationProvider, and DevelopmentEnvironment. Installing `.ssplugin` data never executes package code or scripts.

Component payloads are copied only when first selected and then belong to the generated embedded project. Normal Save does not overwrite them. FCCG replaces only its small `Generated/` glue surface and managed project/editor metadata. A new CubeMX snapshot is a special dangerous replacement and requires confirmation; ordinary component deactivation retains files and removes them only from the active source graph.

Each generated project also receives `<ProjectName>.ssdecoder`, a deterministic ZIP containing JSON metadata only. It carries the SSLOG schema, selected devices/strategies/modes, record availability, and active stream profile for a future generic SilverStar_FLP decoder engine; FCCG does not modify FLP or execute decoder code.

## Generated development environment

The default Environment plugin produces:

- `<ProjectName>.code-workspace`;
- project-local `.vscode/` tasks/settings/extensions;
- a native, non-empty `.eide/eide.yml`;
- `Makefile` and target metadata.

Make and EIDE are rendered from the same resolved source/include/define/linker graph. VS Code tasks call that Make project. Generated firmware builds do not require FCCG or Python.

```powershell
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Debug all
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Release all
mingw32-make host-tests
mingw32-make architecture-check
mingw32-make power10-check
mingw32-make static-analysis
mingw32-make artifact-check
```

## FCCG tests

```powershell
python -m pytest
python -m compileall -q src tools
```

All automated outputs remain below `tests/`. FCCG does not alter PATH, registry, global IDE settings, another repository, or the read-only firmware/GUI references.

See [User Guide](docs/USER_GUIDE.md), [Architecture](docs/ARCHITECTURE.md), [Plugin Format](docs/PLUGIN_FORMAT.md), [Project Format](docs/PROJECT_FORMAT.md), [Generated Code](docs/GENERATED_CODE.md), [Build Integration](docs/BUILD.md), and [Validation](VALIDATION.md).
