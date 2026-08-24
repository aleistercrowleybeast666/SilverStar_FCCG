# SilverStar_FCCG architecture

FCCG is a component-based embedded-project assembler. It copies real implementations from declarative plugins, resolves one explicit build graph, generates a small connection surface, and never loads plugins inside the firmware.

## Application layers

```text
Four PySide6 pages + project/plugin dialogs
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

## Physical Device capability architecture

```text
Physical Device Instance
        │ provides
        ▼
    Capabilities
        ▲ requires {capability, purpose}
        │
Algorithm / Strategy / Flight component
        │
        ▼
 Capability Resolver
        │ sole provider: automatic
        │ multiple providers: saved user override
        ▼
Static project_capability_routes.c
```

`DeviceInstance` separates a physical endpoint (`imu0`, `gnss0`, `telemetry0`, `maintenance0`) from its plugin implementation. One JY901B instance therefore provides acceleration, angular rate, external attitude, magnetic field, and barometric altitude without creating duplicate UART initialization or status objects. Current real drivers declare `project_max=1`; the model can represent additional instances, but the GUI exposes Add only after a real plugin declares support.

Strategy selection determines which implementation enters the source graph. Capability resolution determines which physical instance supplies each declared input. These are deliberately separate. The consuming implementation owns when and how it uses an input; FCCG has no general PRE_START/ASCENT/RECOVERY phase-policy layer. Future sensor selection/health and Multi-EKF behavior must be explicit Strategies, not automatic consequences of adding devices.

## Device, Hardware Connection, Board, and MCU responsibilities

```text
Device Instance + Device Plugin
     │
     │ requires
     ▼
Hardware Connection
     │
     ├── reads .ioc
     ▼
Hardware Inventory
     │
     ▼
Semantic Connection
     │
     ▼
SilverStar Generated Glue
     │
     ▼
STM32 Platform
```

An MCU plugin describes chip-family capabilities, Platform backend, HAL/CMSIS dependencies, CPU/FPU flags, memory/CCMRAM contract, linker/startup support, and compatible environments/providers. It does not contain sensor selection or PCB pin meaning.

A Board plugin describes one PCB profile: compatible MCUs, an immutable `.ioc`/vendor snapshot, semantic aliases and connections, legal alternatives, fixed/reserved roles, Board services, provenance, verification state, and `source_kind` (`verified_builtin`, `manual_import`, or `third_party`). Physical pins, peripheral settings, DMA, IRQ, and clocks are parsed from `.ioc`; they are not duplicated in manifest metadata. The same MCU plugin is reused unchanged by multiple Boards.

A Hardware Configuration Provider is a trusted FCCG handler used to create a Board. The current provider imports STM32CubeMX output as data. Imported vendor code remains below `HardwareGenerated/STM32CubeMX/`; it never enters `Platform/`, `Devices/`, `System/`, `Algorithm/`, or `FlightLogic/`. After mapping and validation, the snapshot can be exported as a reusable Board plugin.

`HardwareInventory` retains every recognized peripheral without artificial count slicing. It currently models MCU/package/core, pins/AF/GPIO/EXTI, UART, SPI, I2C, ADC, Timer/PWM, CAN, DMA, NVIC and useful clock facts. Requirements can constrain baud, signal sets, master/slave mode, DMA RX/TX, and enabled IRQs; the resolver also detects exclusive-resource and DMA-stream collisions. Full clock solving and automatic CubeMX editing are deliberately outside FCCG.

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

EIDE has real `srcDirs`, explicit virtual files, includes, defines, exclusions, forced includes, CPU/FPU flags, linker, libraries, and toolchain. It does not use `srcDirs: []` and does not independently discover sources. Because the current plugins declare no validated flash capability, the renderer emits no uploader or probe configuration.

The selected DevelopmentEnvironment plugin chooses a trusted renderer. The current implementation is VS Code + EIDE + Arm GNU Toolchain. Arbitrary plugin code is never called.

## Lifecycle, ownership, and Save

New projects are assembled in workspace-local staging. Existing projects are validated and planned before writes. The public lifecycle is Draft/Dirty → Materializing → Ready, plus Building/Error while a long operation runs or fails. Save and every build/check entry re-plan current managed output, so an FCCG renderer upgrade cannot be hidden by hashes from an older installation.

A project is Ready only when its descriptor, Make targets, selected component/Board payloads, hardware-preparation fingerprint, Generated/Target trees, ownership hashes, EIDE, VS Code tasks, and workspace exist and agree with the in-memory model. New-project and Save-As publication order places `SilverStar.ssproject` last. Build, Clean, Host Tests, Architecture Check, Power of Ten, Static Analysis, and Artifact Check all call `Project_EnsureBuildable`; dirty or incomplete material is saved before Make runs with the project root as explicit `cwd`.

- Component payloads become project-owned source and are preserved on ordinary Save.
- Save Project As copies the complete project-owned tree while excluding build/cache/intermediate output.
- Deactivated component files remain on disk but leave the source graph.
- `Generated/`, `SilverStar.ssproject`, `SilverStar_Configuration.md`, Make/target data, workspace files, `.vscode/`, and `.eide/` are FCCG-managed.
- A manually edited `.eide/eide.yml`, MCU/target change, collision, deactivation, or changed CubeMX snapshot marks the plan dangerous and requires confirmation.
- `HardwareGenerated/` is preserved normally. Reimport may replace its complete tree only after an explicit dangerous plan.
- `.fccg/ownership.json` records active components and hashes for comparison; hashes document provenance and never restore source automatically.
- `<ProjectName>.ssdecoder` is FCCG-managed declarative output. It contains the Protocol schema plus project/device/strategy/mode/record availability and stream selections for a future generic FLP decoder; it contains no executable plugin.

## Filesystem and process safety

There are two non-overlapping authorization roots. The FCCG internal policy owns plugins, settings, logs and import snapshots below the repository. An output policy is created from the exact project directory explicitly selected by the user and owns only that generated project. Planning, staging, build working directories and every destination are checked against the applicable root; neither policy can escape into the other or a sibling path.

All destinations pass through `WorkspacePolicy`, portable path validation, staging, and atomic replacement/rollback logic. Archive installation rejects traversal, absolute/drive paths, symlinks, special files, duplicate-case names, excessive size/count, managed-path claims, and executable-script package entries. Plugin data is never imported or executed.

FCCG v0.x formally supports STM32 plus STM32CubeMX for manual Hardware Configuration. Plugin, Platform, Device, Strategy, Mode and provider interfaces remain generic so a future non-STM32 provider can be added without treating STM32 concepts as universal project fields.

Subprocesses use argument arrays and explicit project working directories. Tool detection runs version commands only. FCCG does not modify PATH, registry, global IDE settings, global Python state, or reference repositories.
