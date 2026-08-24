# Declarative plugin format

A `.ssplugin` is a ZIP data package:

```text
plugin.json
payload/
docs/
README.md
LICENSE
```

The manager parses and copies declared data only. It never imports or executes `plugin.py`, `install.py`, `setup.py`, EXE/DLL, BAT/CMD, PowerShell, or package hooks. The STM32CubeMX provider is a trusted FCCG implementation selected by a declarative handler name; third-party manifests cannot nominate arbitrary Python callables.

## Plugin types

| Type | Responsibility |
|---|---|
| `core` | Shared flight application, interfaces, system services, tests/tools |
| `mcu` | Chip/family Platform, HAL/CMSIS, CPU/memory/toolchain contract |
| `board` | PCB resources, mappings, services, hardware payload/provenance |
| `device` | Sensor, communication, or future `class=actuator` implementation |
| `algorithm` | Base algorithm code, Strategy, or Mode owner |
| `flight_logic` | Flight-cycle/mission behavior, Strategy, or Mode owner |
| `os` | RTOS kernel/port/configuration contribution |
| `protocol_bundle` | Complete compatible protocol set and documentation |
| `hardware_configuration_provider` | Declarative access to a trusted hardware-import handler |
| `development_environment` | Declarative access to a trusted project renderer |

Resource kinds are open strings. Current manifests use UART, SPI, GPIO variants, ADC, SDIO, and Time; the inventory already recognizes I2C, PWM, CAN and timer, and future real plugins may add those or `servo_pwm` without changing a fixed enum.

## Common manifest blocks

The strict schema is `schemas/plugin.schema.json`. Version 0 includes identity/type/class/version, Device `instance_policy` and `physical_device`, dependencies, typed capability/resource requirements, provided capabilities/resources, explicit build contributions, payload roots, localization/descriptor metadata, and optional type-specific blocks.

`build` may declare C/ASM sources, includes, defines, MCU flags, specs, libraries, forced includes, virtual sources, excluded sources, linker script, and toolchain prefix. Sources/linker/forced includes must exist in the declared payload; Make-unsafe tokens are rejected.

### Board

`resources.provides` declares stable semantic resource aliases and the small generated-interface metadata they need. `resources.roles` binds requirement keys/classes to a kind, default, candidates, and `fixed` state. Provisions may be reserved; conflict groups reject illegal simultaneous use. For STM32, `board.ioc_file` points to the physical truth and `board.connections_file` maps aliases to IOC resource IDs. The Board block also declares compatible MCUs, vendor/provider, verification/source kind, and hardware root.

Device requirements may constrain `baud_rate`, signal names, `mode`, RX/TX DMA, and IRQ availability. `instance_policy` contains `project_max` and `same_plugin_multiple`. Current IMU/GNSS/Telemetry/Maintenance plugins declare `{project_max: 1, same_plugin_multiple: false}`; only a real context-capable future driver may raise those limits.

`physical_device` distinguishes vendor/model/chipset from the reusable driver. For example, the current radio is physical model Ebyte E28-2G4M12SX, chipset SX1281, using the existing SX1281 Driver. A single Device can `provide` several capabilities; JY901B is one physical UART instance that provides acceleration, angular rate, external attitude, magnetic field, and barometric altitude.

Algorithm/Strategy/Flight manifests declare inputs as `{ "capability": "barometer.altitude", "purpose": "measurement_update" }`. Purpose describes the consumer contract; the implementation owns lifecycle. No generic phase policy is inferred or generated.

### Protocol bundle

`protocol.logging_metadata` points inside the package payload to `sslog_parser_metadata.json`. The block also explicitly declares `maintenance_protocol_version`, applicable `firmware_version`, and `documentation_version`; versions are never guessed from Markdown headings. Its `fccg.records` policy data assigns each record `required`, `recommended`, or `optional`, owns `display_names` for `zh_CN`/`en_US`, and can require capabilities, components, or selected strategy slots. Adding or translating a valid record in this metadata requires no FCCG Python record-table change.

### Strategy and Mode

`selection.kind = "strategy"` declares a slot, order, required/`allow_none`, and optional build definitions for None. Exactly the selected strategy payload enters the graph.

`selection.kind = "mode"` declares a slot, `allow_none`, `allow_multiple`, options, defaults, and localized labels. Modes remain options of their owner component rather than fake algorithm packages.

### Hardware provider

Declares vendor, accepted inputs, and one allowlisted handler such as `stm32_cubemx`. Installing a package cannot add handler code.

### Development environment

Declares renderer, toolchain, outputs/tasks, and native EIDE capability. The current allowlisted renderer is `vscode_eide_gcc`.

## Installation safety

Installation validates the entire archive in staging before one final move. It rejects invalid/unknown schema fields, traversal/absolute/drive/backslash/control/reserved paths, symlink/special-file entries, case-insensitive duplicates, excessive count/expanded size, duplicate IDs, unsatisfied dependencies/capabilities, payload collisions, unsafe build tokens, and claims on FCCG-managed `Generated/`, project metadata, `.vscode/`, or `.eide/` paths.

Builtins are read-only. Installed-package removal checks reverse dependencies and open-project selection. It never removes payload already copied into a generated project.

## Reference builtins and Board export

`tools/import_reference_components.py --reference <path>` reads a selected reference, records path/commit/branch/status/snapshot digest, stages 23 packages, strict-scans them, and atomically replaces only `plugins/builtin/`. The reference itself is never written or built.

A custom imported STM32 mapping can be exported as `.ssplugin` with Board manifest, semantic aliases/roles, `connections.json`, the source `.ioc`, hardware provenance/docs, and `payload/HardwareGenerated/STM32CubeMX/`. It does not serialize a second copy of parsed physical facts. On installation it behaves as an ordinary reusable Board component; its `manual_import` status remains visible and is not upgraded to official validation.
