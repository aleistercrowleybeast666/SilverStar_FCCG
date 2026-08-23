# SilverStar Flight Controller Code Generator

SilverStar_FCCG (FCCG) is a PySide6 flight-controller configurator, declarative component manager, safe project assembler, thin glue generator, STM32 hardware-import front end, and development-environment generator.

The current validated target is the real SilverStar 0.0.9 combination: STM32F407VET6, SilverStar 0.5, JY901B, NEO-M9N, SX1281, UART Console, FreeRTOS 11.3.0, the current Alignment/INS/KF6/Landing strategies, deployment/calibration modes, AIR, and SSLOG. The 23 builtin packages were imported read-only from reference commit `b8c90e997c3113dd23074302682c5560dae18926`.

## Run

Python 3.11 or newer and PySide6 6.8 or newer are required.

```powershell
python main.py
```

The main window has six pages: **Project**, **Devices**, **Board & Hardware**, **Flight Configuration**, **Build**, and **Plugins**. Simplified Chinese/English, Light/Dark themes, manifest-driven controls, repository-local settings, and shared background-task progress follow the copied GUI standard.

## Device-first workflow

1. Enter the project name, output directory, firmware version, and MCU. A sole Core, OS, Protocol Bundle, and Development Environment are selected automatically.
2. Select actual Devices by class. Their manifests declare resource requirements; users do not choose pins or DMA on this page.
3. Select a compatible Board. FCCG filters/sorts Boards by MCU and current Device requirements, auto-assigns defaults, and exposes only meaningful alternatives under **Advanced Resource Configuration**.
4. Select manifest-defined Strategies and Modes and adjust optional logging policy.
5. Choose **Generate Project** or **Apply Configuration**. FCCG runs Validate → Resolve → Plan → Apply directly. A diff confirmation appears only for dangerous replacement/removal/conflict cases.

For STM32 custom hardware, configure and generate a project in STM32CubeMX, then import its `.ioc` or complete generated directory. FCCG validates the MCU, layout, HAL/CMSIS, startup/linker presence, peripherals, and RTOS conflicts, then stores the snapshot only under `HardwareGenerated/STM32CubeMX/`. A validated mapping can be exported as a local `.ssplugin` Board for later reuse without CubeMX.

## Plugins and ownership

Supported declarative types are Core, MCU, Board, Device, Algorithm, FlightLogic, OS, ProtocolBundle, HardwareConfigurationProvider, and DevelopmentEnvironment. Installing `.ssplugin` data never executes package code or scripts.

Component payloads are copied only when first selected and then belong to the generated embedded project. Normal Apply does not overwrite them. FCCG replaces only its small `Generated/` glue surface and managed project/editor metadata. A new CubeMX snapshot is a special dangerous replacement and requires confirmation; ordinary component deactivation retains files and removes them only from the active source graph.

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
