# SilverStar_FCCG architecture

FCCG is a component-based embedded-project assembler. It copies real implementations from declarative plugins, resolves one explicit build graph, generates a small connection surface, and never loads plugins inside the firmware.

## Application layers

```text
Six PySide6 pages / dialogs
          ↓
      FccgService
          ├── strict Project Model / validation
          ├── plugin catalog / safe installer
          ├── Board compatibility / resource resolver
          ├── trusted STM32CubeMX importer / Board exporter
          ├── source graph / renderers / staged assembler
          └── toolchain detector / guarded build runner
                         ↓
                  WorkspacePolicy
```

Widgets expose view state and signals. They do not parse archives, copy payloads, edit Make/EIDE/VS Code files, import CubeMX data, or run toolchains directly.

## Device, Board, and MCU responsibilities

```text
Device Plugin
  “I require UART ×1, Time, …”
          ↓ resource requirements

Board Plugin or imported Hardware
  defaults + candidates + fixed/reserved + conflicts
          ↓ resolved resource mapping

MCU Platform
  typed UART/SPI/GPIO/ADC/Time access and CPU/memory/toolchain contract
```

An MCU plugin describes chip-family capabilities, Platform backend, HAL/CMSIS dependencies, CPU/FPU flags, memory/CCMRAM contract, linker/startup support, and compatible environments/providers. It does not contain sensor selection or PCB pin meaning.

A Board plugin describes one PCB: compatible MCUs, concrete resources, semantic roles, legal alternatives, fixed/reserved resources, conflicts, Board services, hardware provenance, and `source_kind` (`verified_builtin`, `manual_import`, or `third_party`). The same MCU plugin is reused unchanged by multiple Boards.

A Hardware Configuration Provider is a trusted FCCG handler used to create a Board. The current provider imports STM32CubeMX output as data. Imported vendor code remains below `HardwareGenerated/STM32CubeMX/`; it never enters `Platform/`, `Devices/`, `System/`, `Algorithm/`, or `FlightLogic/`. After mapping and validation, the snapshot can be exported as a reusable Board plugin.

## Strategy and Mode model

```text
Algorithm / FlightLogic manifests
          ├── Strategy slot: one component or None
          └── Mode slot: zero/one/many declared options
                         ↓
                ProjectModel dictionaries
                         ↓
              Resolved source graph / glue
```

Slots are manifest strings, not permanent fields in Python. Current Strategy slots are Alignment, INS, Estimator, and Landing. Current Mode slots are Calibration and Deployment. `Estimator=None` contributes `SYSTEM_FUSION_NONE` definitions and excludes every KF6 source before Make/EIDE rendering. The model can accept future `guidance`, `control`, and `control_allocation` slots without showing fictional current plugins.

## One project and build truth

`SilverStar.ssproject` plus installed manifests are the configuration truth. `SourceGraph_Resolve()` combines explicit source, assembly, include, define, forced-include, linker, CPU, library, virtual-source, and exclusion contributions.

```text
Project Model + manifests
          ↓
Resolved Source Graph
          ├── Generated/project_sources.mk → Make
          ├── native .eide/eide.yml
          └── VS Code tasks → the generated Make project
```

EIDE has real `srcDirs`, explicit virtual files, includes, defines, exclusions, forced includes, CPU/FPU flags, linker, libraries, and toolchain. It does not use `srcDirs: []` and does not independently discover sources.

The selected DevelopmentEnvironment plugin chooses a trusted renderer. The current implementation is VS Code + EIDE + Arm GNU Toolchain. Arbitrary plugin code is never called.

## Ownership and Apply

New projects are assembled in workspace-local staging. Existing projects are validated and planned before writes.

- Component payloads become project-owned source and are preserved on ordinary Apply.
- Deactivated component files remain on disk but leave the source graph.
- `Generated/`, `SilverStar.ssproject`, `SilverStar_Configuration.md`, Make/target data, workspace files, `.vscode/`, and `.eide/` are FCCG-managed.
- A manually edited `.eide/eide.yml`, MCU/target change, collision, deactivation, or changed CubeMX snapshot marks the plan dangerous and requires confirmation.
- `HardwareGenerated/` is preserved normally. Reimport may replace its complete tree only after an explicit dangerous plan.
- `.fccg/ownership.json` records active components and hashes for comparison; hashes document provenance and never restore source automatically.

## Filesystem and process safety

All destinations pass through `WorkspacePolicy`, portable path validation, staging, and atomic replacement/rollback logic. Archive installation rejects traversal, absolute/drive paths, symlinks, special files, duplicate-case names, excessive size/count, managed-path claims, and executable-script package entries. Plugin data is never imported or executed.

Subprocesses use argument arrays and explicit project working directories. Tool detection runs version commands only. FCCG does not modify PATH, registry, global IDE settings, global Python state, or reference repositories.
