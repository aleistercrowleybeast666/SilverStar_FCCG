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

Resource kinds are open strings. Current manifests use UART, SPI, GPIO variants, ADC, SDIO, and Time; future real plugins may add I2C, PWM, CAN, timer, or servo PWM without changing a fixed enum.

## Common manifest blocks

The strict schema is `schemas/plugin.schema.json`. Version 0 includes identity/type/class/version, dependencies, required capabilities/resources, provided capabilities/resources, explicit build contributions, payload roots, localization/descriptor metadata, and optional type-specific blocks.

`build` may declare C/ASM sources, includes, defines, MCU flags, specs, libraries, forced includes, virtual sources, excluded sources, linker script, and toolchain prefix. Sources/linker/forced includes must exist in the declared payload; Make-unsafe tokens are rejected.

### Board

`resources.provides` declares physical/logical resources and metadata. `resources.roles` binds semantic requirement keys/classes to a kind, default, candidates, and `fixed` state. Provisions may be reserved; conflict groups reject illegal simultaneous use. `board` declares compatible MCUs, vendor/provider, verification/source kind, and hardware root.

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

A custom imported STM32 mapping can be exported as `.ssplugin` with Board manifest, resources/roles, hardware provenance, docs, and `payload/HardwareGenerated/STM32CubeMX/`. On installation it behaves as an ordinary reusable Board component; its `manual_import` status remains visible and is not upgraded to official validation.
