# SilverStar Flight Controller Code Generator

SilverStar_FCCG (FCCG) is a PySide6 flight-controller configurator, declarative component manager, safe project assembler, thin glue generator, STM32 hardware-import front end, and development-environment generator.

The current internal software release candidate validates the real SilverStar 0.0.9 combination: STM32F407VET6, SS0.5, JY901B, NEO-M9N, E28-2G4M12SX with the existing SX1281 driver, AIR Telemetry Protocol M0, Serial Maintenance Protocol 0.0, Flight Log Format 0.0, FreeRTOS 11.3.0, and the current Alignment/INS/KF6/Landing strategies and deployment/calibration modes. The 36 builtin packages retain read-only provenance from reference commit `cc0b377ded690556d037a412a55f87fe334c42d0` (`完善同能力多实例与日志配置契约`) while clearly identifying FCCG-owned overlays. This is a **Software Release Candidate / Pre-Hardware-Validation** milestone, not a public release or a claim of electrical, flight, flash, or alternate-MCU validation.

## Run

Python 3.11 or newer and PySide6 6.8 or newer are required.

```powershell
python main.py
```

The main window has exactly four pages: **Devices**, **Flight Configuration**, **Hardware Connection**, and **Code Generation & Build**. Project commands live in **File** and plugin management lives in the **Plugins** menu/dialog. Simplified Chinese/English, Light/Dark themes, manifest-driven controls, visible checkbox states, repository-local settings, and shared background-task progress follow the copied GUI standard. Advanced hardware/verification sections collapse by visibility only; Logging remains directly available.

## Device-first workflow

1. Enter only the project name and output directory. The sole current firmware/Core/OS/Environment defaults are selected automatically. The official SS0.5 reference draft also starts with all three official protocols enabled, while each protocol remains explicitly disableable later.
2. Select Device instances. MCU is not a Device-page choice: the selected Board snapshot or imported CubeMX `.ioc` supplies exact part/family/package/core facts, and FCCG deterministically matches the installed MCU/Platform plugin. **Primary Sensors** contains only `sensor.imu` and `sensor.gnss`; all other valid `sensor.*` plugins enter **Other Sensors** automatically. Links, storage, actuators, and indicators remain separate groups. SS0.5 maps the active-low system indicator to `IMU_CAL_LED` on PA1. Its verified hardware has no second assignable indicator GPIO, so strict generation reports the optional GNSS indicator as unresolved instead of reusing a mission output.
3. Open **Flight Configuration** to select manifest-defined Strategies and Modes, edit per-Mode parameters, choose AIR Telemetry Protocol M0 / Serial Maintenance Protocol 0.0 / Flight Log Format 0.0 or **None** independently, inspect derived capability consumers/sources, and adjust Protocol-owned Required/Recommended/Optional logging. M0 is the current low-resource/low-bandwidth AIR profile name, not a wire-version increment. Incompatible choices are disabled from Device capabilities alone, even before hardware is selected. A source override appears and is saved only for a genuinely ambiguous required capability.
4. Open **Hardware Connection**. A new STM32 draft starts on **Custom STM32 Hardware** for the manual CubeMX import flow; alternatively select a compatible Board. FCCG parses the Board/imported `.ioc`, displays the detected MCU, CubeMX/Firmware Package facts, HAL/CMSIS source policy, and matched Platform lock/reason/provenance, validates typed UART/SPI/I²C/CAN-inventory/PWM and GPIO electrical contracts, preserves still-valid assignments, and auto-assigns new semantic connections. A selected custom I²C bus with Open Drain/NOPULL exposes a bus-and-pin-specific **verified external pull-up** checkbox; its evidence is bound to the current snapshot and disappears for unrelated hardware. Use **Complete Manual Assignment and Check** to seal the current mapping fingerprint; any relevant Device/Mode/IOC/Platform/assignment change invalidates that confirmation. Only Board plugins expose the optional **Prepare Hardware Files** action.
5. Choose **Generate Code** (or **File → Save Project**). This validates, resolves, prepares hardware, incrementally updates the standalone source project, renders Make/EIDE/VS Code, verifies readiness, and publishes `SilverStar.ssproject` last. Unchanged managed and component files retain their timestamps; `build/` and dependency files are not cleaned.
6. From **Code Generation & Build**, choose **Open VS Code Workspace** or **Open Project Folder**, then build in VS Code/EIDE. Release is the default Make/EIDE/VS Code target and Debug remains available. **Open Firmware Output** stays disabled until an actual ELF/HEX/BIN/MAP artifact exists. FCCG's **Validation Build** is intentionally under advanced verification and also defaults to Release; generation itself never runs a full build or quality suite.

**Save Project As...** stages and copies the complete generated source tree—including project-owned Device, Algorithm, Platform, and FlightLogic edits—while excluding build output, caches, and intermediate artifacts. The copied descriptor is published last, so a failed operation is not presented as a ready project.

For STM32 custom hardware, configure and generate a project in STM32CubeMX, then import its complete generated directory. FCCG inventories MCU/package/core, CubeMX/Firmware Package, pins/AF/EXTI, UART, SPI, I²C, ADC, Timer/PWM, CAN/FDCAN, DMA, NVIC, and useful clocks; validates bus/electrical contracts; then stores the snapshot only under `HardwareGenerated/STM32CubeMX/`. The current F407 contract requires CubeMX 6.15.0 and `STM32Cube FW_F4 V1.28.3`. Its `plugin_payload_authoritative` policy keeps HAL, CMSIS, startup, linker, and Platform backend in the MCU plugin; imported `Drivers/`, CMSIS, startup, and linker artifacts never enter the Source Graph. A validated mapping can be exported as a local `.ssplugin` Board for later reuse without CubeMX.

The default physical storage is the single-instance `silverstar.device.storage.sd_sdio_fatfs`
Device. It owns the generic Storage and file Log Sink sources under
`Devices/Storage/SdSdioFatFs`; the Board owns only verified SDIO/Time mappings, CubeMX owns SDIO
and FatFs App/Target glue, and MCU/Platform owns the controlled FatFs core and HAL providers.
Import validates the unique FatFs object/path/driver, SDIO RX/TX DMA and IRQ, and the generated
TIM HAL timebase. The timebase handle and instance are discovered from generated code—TIM1 is not
hard-coded—and SysTick, frequency/IRQ mismatch, ambiguity, or PWM reuse fails before generation.

The output directory may be any user-selected writable project directory. FCCG treats that exact directory as a separate authorization root; generation/build cannot escape it, while plugins, settings, logs, and snapshots remain constrained to the FCCG workspace.

## Plugins and ownership

Supported declarative types are Core, MCU/Platform, Board, Device, Algorithm, FlightLogic, OS, Protocol, HardwareConfigurationProvider, and DevelopmentEnvironment. Installing `.ssplugin` data never executes package code or scripts. The legacy three-category `protocol_bundle` is accepted only as a project-format migration source and never enters a new Source Graph.

The old combined protocol package is split into three independently locked optional slots. An enabled slot locks `silverstar.protocol.telemetry.air_m0`, `silverstar.protocol.maintenance.serial_0_0`, or `silverstar.protocol.logging.sslog_0_0` by component/version/Profile/manifest SHA-256; a disabled slot is the project-model value `null`, not a fake plugin. Each plugin owns exactly one strict category and its complete Profile/build/transport/metadata contract. AIR M0, Serial Maintenance 0.0, and SSLOG 0.0 wire/file layouts are unchanged.

Physical Devices and protocol activation are independent. A selected SX1281 or SD/TF Device may remain present while its protocol is **None**. Removing the only compatible transport atomically clears the dependent protocol; restoring a Device never silently re-enables it. Maintenance uses a declaratively auto-managed internal UART Console endpoint, which is added only while the maintenance protocol is enabled and is removed together with its UART assignment and SerialTask sources when disabled.

Reference import uses a reproducible two-source pipeline: the external firmware snapshot is read-only, then official FCCG extensions from `tools/reference_overlays/` are replayed into builtin packages. The F407 Platform extension declares the resource-rendering ABI instead of hard-coding F4 headers/getters in Python. I²C provides blocking 7-bit master and 8/16-bit register access without HAL constants or generic repeated-start; PWM accepts only CubeMX-proven ordinary PWM1/PWM2 channels and uses exact forced endpoints. Both are software `supported`, not electrically `verified`. Classic CAN remains inventory-visible but its backend is `reserved` and cannot serve a normal consumer. Default SS0.5 therefore contains none of these optional backends or unrelated I²C/CAN/PWM code.

Component payloads are copied only when first selected and then belong to the generated embedded project. Normal Save does not overwrite them. FCCG replaces only its small `Generated/` glue surface and managed project/editor metadata. A new CubeMX snapshot is a special dangerous replacement and requires confirmation; ordinary component deactivation retains files and removes them only from the active source graph.

Each logging-enabled generated project also receives `<ProjectName>.ssdecoder`, a deterministic ZIP containing
only `manifest.json`, `record_catalog.json`, `project_semantics.json`, `checksums.sha256`, and
`README.md`. Canonical UTF-8 JSON and SHA-256 identities bind the Flight Log container/record
catalog to the three protocol locks and bindings, detected MCU/Platform/Board/CubeMX identity,
physical devices, resource assignments, capability routes, Algorithms, Strategies, Modes, and
stream policy. The first 16 bytes of the catalog, semantics, and generation-profile hashes are
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
`silverstar.ssdecoder.package-schema/1.1` and `silverstar.sslog.container/0.0`. Package schema 1.1
allows telemetry and maintenance locks to be `null` while requiring a real logging lock. The generated
descriptor source is part of the same authoritative Make/EIDE/VS Code Source Graph as the other
generated glue. Host Tests also compile a C utility against the real SSLOG codec to create and
round-trip-check `Logs/Golden/<ProjectName>_golden.sslog`.

When logging is **None**, the logging table and export action are disabled, LoggerTask/Log Sink/
SSLOG sources leave the active graph, and no `.ssdecoder`, decoder descriptor, golden expectation,
or golden task is generated. A later generation removes only stale FCCG-managed decoder artifacts;
manual flight-log files remain untouched. `Generated/project_semantics.json` is still emitted for
auditing and records all three protocol slots, including `null` values.

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
python -m compileall -q src main.py tools
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

Protocol selection is modeled as optional System Service → complete Protocol Profile → Transport
Binding → Physical Device/Storage. All three combo boxes always show **None** first and currently
expose one genuine implementation. Missing or ambiguous compatible transports disable the real
Profile with an explanation; no Profile is selected merely because it is installed.

See [User Guide](docs/USER_GUIDE.md), [Architecture](docs/ARCHITECTURE.md), [Plugin Format](docs/PLUGIN_FORMAT.md), [Project Format](docs/PROJECT_FORMAT.md), [Generated Code](docs/GENERATED_CODE.md), [Build Integration](docs/BUILD.md), and [Validation](VALIDATION.md).
