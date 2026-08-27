# SilverStar Flight Controller Code Generator

SilverStar_FCCG (FCCG) is a PySide6 flight-controller configurator, declarative component manager, safe project assembler, thin glue generator, STM32 hardware-import front end, and development-environment generator.

The current validated target is the real SilverStar 0.0.9 combination: STM32F407VET6, SS0.5, JY901B, NEO-M9N, E28-2G4M12SX with the existing SX1281 driver, AIR Telemetry Protocol M0, Serial Maintenance Protocol 0.0, Flight Log Format 0.0, FreeRTOS 11.3.0, and the current Alignment/INS/KF6/Landing strategies and deployment/calibration modes. The 31 builtin packages retain read-only provenance from reference commit `cc0b377ded690556d037a412a55f87fe334c42d0` (`完善同能力多实例与日志配置契约`); five declarative logical Devices expose input-voltage monitoring, two mission-action outputs, and two software indicator roles.

## Run

Python 3.11 or newer and PySide6 6.8 or newer are required.

```powershell
python main.py
```

The main window has exactly four pages: **Devices**, **Flight Configuration**, **Hardware Connection**, and **Code Generation & Build**. Project commands live in **File** and plugin management lives in the **Plugins** menu/dialog. Simplified Chinese/English, Light/Dark themes, manifest-driven controls, visible checkbox states, repository-local settings, and shared background-task progress follow the copied GUI standard. Advanced hardware/verification sections collapse by visibility only; Logging remains directly available.

## Device-first workflow

1. Enter only the project name and output directory. The sole current firmware/Core/OS/Protocol/Environment defaults are selected automatically.
2. Select the STM32 MCU and Device instances. **Other Sensors** contains the default-on input-voltage monitor; **Indicators** contains the default-on System Status Indicator and optional GNSS Status Indicator; **Actuators** lists Launch Ignition Power Output first and Parachute Pyro Power Output second. SS0.5 maps the active-low system indicator to `IMU_CAL_LED` on PA1. Its verified hardware has no second assignable indicator GPIO, but the GNSS indicator remains visible and selectable here; Hardware Connection reports the unresolved GPIO and strict generation blocks it instead of reusing a pyrotechnic output. A hardware power LED, if one exists, is not a software Device.
3. Open **Flight Configuration** to select manifest-defined Strategies and Modes, edit per-Mode parameters, review the read-only AIR Telemetry Protocol M0 / Serial Maintenance Protocol 0.0 / Flight Log Format 0.0 profiles, inspect derived capability consumers/sources, and adjust Protocol-owned Required/Recommended/Optional logging. M0 is the current low-resource/low-bandwidth AIR profile name, not a wire-version increment. Incompatible choices are disabled from Device capabilities alone, even before hardware is selected. A source override appears and is saved only for a genuinely ambiguous required capability.
4. Open **Hardware Connection**. A new STM32 draft starts on **Custom STM32 Hardware** for the manual CubeMX import flow; alternatively select a compatible Board. FCCG parses the Board/imported `.ioc`, validates typed UART/SPI/I2C/PWM and GPIO electrical contracts, preserves still-valid assignments, and auto-assigns new semantic connections. Use **Complete Manual Assignment and Check** to seal the current mapping fingerprint; any relevant Device/Mode/IOC/assignment change invalidates that confirmation. Only Board plugins expose the optional **Prepare Hardware Files** action.
5. Choose **Generate Code** (or **File → Save Project**). This validates, resolves, prepares hardware, incrementally updates the standalone source project, renders Make/EIDE/VS Code, verifies readiness, and publishes `SilverStar.ssproject` last. Unchanged managed and component files retain their timestamps; `build/` and dependency files are not cleaned.
6. From **Code Generation & Build**, choose **Open VS Code Workspace** or **Open Project Folder**, then build in VS Code/EIDE. Release is the default Make/EIDE/VS Code target and Debug remains available. **Open Firmware Output** stays disabled until an actual ELF/HEX/BIN/MAP artifact exists. FCCG's **Validation Build** is intentionally under advanced verification and also defaults to Release; generation itself never runs a full build or quality suite.

**Save Project As...** stages and copies the complete generated source tree—including project-owned Device, Algorithm, Platform, and FlightLogic edits—while excluding build output, caches, and intermediate artifacts. The copied descriptor is published last, so a failed operation is not presented as a ready project.

For STM32 custom hardware, configure and generate a project in STM32CubeMX, then import its `.ioc` or complete generated directory. FCCG inventories MCU/package/core, pins/AF/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC, and useful clocks; validates bus roles/rates/modes/DMA/IRQ plus GPIO pull/output type/speed/polarity/safe startup/EXTI constraints; then stores the snapshot only under `HardwareGenerated/STM32CubeMX/`. A validated mapping can be exported as a local `.ssplugin` Board for later reuse without CubeMX.

The output directory may be any user-selected writable project directory. FCCG treats that exact directory as a separate authorization root; generation/build cannot escape it, while plugins, settings, logs, and snapshots remain constrained to the FCCG workspace.

## Plugins and ownership

Supported declarative types are Core, MCU, Board, Device, Algorithm, FlightLogic, OS, ProtocolBundle, HardwareConfigurationProvider, and DevelopmentEnvironment. Installing `.ssplugin` data never executes package code or scripts.

Component payloads are copied only when first selected and then belong to the generated embedded project. Normal Save does not overwrite them. FCCG replaces only its small `Generated/` glue surface and managed project/editor metadata. A new CubeMX snapshot is a special dangerous replacement and requires confirmation; ordinary component deactivation retains files and removes them only from the active source graph.

Each generated project also receives `<ProjectName>.ssdecoder`, a deterministic ZIP containing
only `manifest.json`, `record_catalog.json`, `project_semantics.json`, `checksums.sha256`, and
`README.md`. Canonical UTF-8 JSON and SHA-256 identities bind the Flight Log container/record
catalog to the selected physical devices, capability routes, Strategies, Modes, protocol profiles,
and stream policy. The first 16 bytes of the catalog, semantics, and generation-profile hashes are
also embedded in generated C; FCCG does not modify FLP or execute decoder code.

## Logging cadence and task progress

The Logging table calls its timing column **Cadence**. PERIODIC records edit a microsecond-backed
period with an automatically suitable `us`, `ms`, or `s` display. DECIMATION records show their
declared data-source cadence and alone expose an extraction factor; EVERY, EVENT, and ONE_SHOT
show measurement, event, and one-time semantics. A stored `period_us` of zero for those policies
means “not used,” never a zero-period continuous stream. Protocol metadata owns these meanings;
the GUI contains no Record-ID timing table.

Record availability may additionally require a declared producer in the selected component set.
Metadata without producer declarations retains the pre-release permissive behavior. After the
read-only firmware reference was verified clean at pushed commit
`cc0b377ded690556d037a412a55f87fe334c42d0` (`完善同能力多实例与日志配置契约`), FCCG synchronized the real
STATS producer (`silverstar.core.device_task`) and TELEMETRY_DIAG producer
(`silverstar.core.telemetry_task`). Both are available and enabled by default in the reference
composition, with Cadence values of 1 s and 200 ms respectively.

**Export Log Decoder Profile** first requires a saved, non-stale generated project, rebuilds and
verifies its canonical hashes, then writes the selected `.ssdecoder` destination atomically. It
starts no worker and does not alter the project or Dirty state. FCCG still does not implement a log
parser, executable decoder plugin, or multi-version decoder engine in this release.

The current package contract uses firmware-owned IDs
`silverstar.ssdecoder.package-schema/1.0` and `silverstar.sslog.container/0.0`. The generated
descriptor source is part of the same authoritative Make/EIDE/VS Code Source Graph as the other
generated glue. Host Tests also compile a C utility against the real SSLOG codec to create and
round-trip-check `Logs/Golden/<ProjectName>_golden.sslog`.

Long operations emit structured PLAN/BEGIN/DONE progress. BEGIN announces the active subject;
only DONE advances the completed count. Successful work ends at 100%, while failure or cancellation
keeps its last real position. Expected Host compile rejection is presented as a neutral successful
gate summary; the original GCC output stays in the expandable detailed log and full log file.

## Generated development environment

The default Environment plugin produces:

- `<ProjectName>.code-workspace`;
- project-local `.vscode/` tasks/settings/extensions;
- a native, non-empty `.eide/eide.yml`;
- `Makefile` and target metadata.

Make and EIDE are rendered from the same resolved source/include/define/linker graph. VS Code tasks call that Make project. Generated firmware builds do not require FCCG or Python.

The EIDE structure is copied from the read-only working firmware template, then only project/source/include/define/linker/output/target fields are rendered. It deliberately keeps `deviceName: null`, `packDir: null`, the reference target/upload structure, and OpenOCD rather than J-Link as the template default. This is structural compatibility, not a validated flash claim; FCCG emits no flash button or task. **Open VS Code Workspace** validates the workspace JSON, `folders[0].path`, and `.eide/eide.yml`, then tries `code.cmd`, `code.exe`, `code`, known installations, and finally file association. Every CLI path uses `--new-window`; failures are logged technically while the single localized dialog tells the user which workspace to open manually.

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

The normal build page shows only the target and selected development environment. Advanced tool configuration separates **Arm GNU Toolchain** and **GNU Make** (firmware build environment) from **Host GCC** (host-test environment). Missing tools disable only dependent advanced actions and reveal a localized installation guide; code generation remains available and FCCG never installs software or changes PATH.

## FCCG tests

```powershell
python -m pytest
python -m compileall -q src tools
```

All automated outputs remain below `tests/`. FCCG does not alter PATH, registry, global IDE settings, another repository, or the read-only firmware/GUI references.

## Current build and protocol behavior

Every valid installed Device manifest is discoverable on the Device page, including a GNSS
status indicator that SS0.5 cannot currently wire. Selection remains legal there; resource and
electrical incompatibility is reported on Hardware Connection and blocks strict generation. A
project still owns exactly one MCU/target/hardware configuration.

Generated outputs use `build/FCCG/<target>/<Debug|Release>`,
`build/FCCG/<target>/StaticAnalysis/<config>`, and `build/FCCG/Host/Tests`.
`LISTING=0` is the default. File → Export Source Package creates a deterministic review archive,
while `python tools/clean_all.py` removes repository-local generated/test artifacts only.

Protocol selection is modeled as System Service → complete Protocol Profile → Transport Binding
→ Physical Device/Storage. The GUI currently exposes one genuine implementation in each of the
three combo boxes; this is an extensible contract, not a claim that arbitrary protocol swapping
already works.

See [User Guide](docs/USER_GUIDE.md), [Architecture](docs/ARCHITECTURE.md), [Plugin Format](docs/PLUGIN_FORMAT.md), [Project Format](docs/PROJECT_FORMAT.md), [Generated Code](docs/GENERATED_CODE.md), [Build Integration](docs/BUILD.md), and [Validation](VALIDATION.md).
