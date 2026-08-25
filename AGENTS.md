# SilverStar_FCCG agent guidance

SilverStar_FCCG is the SilverStar Flight Controller Code Generator: a graphical project
configurator, declarative component-plugin manager, project assembler, minimal glue generator,
and build/toolchain front end.

## Safety boundary

All writes made while developing or testing FCCG must remain below this repository root.
Codex or other automation working on FCCG may read, but must never modify, rename, delete,
format, commit, or otherwise write to the reference firmware, reference GUI, or any path outside
the FCCG workspace. Tests must place all temporary and generated outputs below `tests/`.
The installed product may write only to a project/output directory explicitly selected by the
user; that selected directory becomes a separate, exact authorization root and does not weaken
the internal workspace boundary.

Reference sources are always read-only:

- firmware: `C:\Users\chdxm\Desktop\stm32-1\Flight_Controller0.5`
- GUI: `D:\python_software\SilverStar_FLP`

Do not modify the system/user PATH, registry, global application settings, global Python
environment, or any other repository. Project-local settings and logs belong below `.fccg/`.

## Architecture and ownership

- Plugins are declarative source packages. Installing a plugin must never execute plugin code.
- Component payloads copied into an embedded project become ordinary project-owned source and
  normal Apply Configuration operations must not overwrite them.
- Only a deliberately small `Generated/` glue surface remains FCCG-owned and replaceable.
- `SilverStar.ssproject` is strict JSON and, together with installed manifests, is the single
  source of truth for Make, VS Code, and supported EIDE configuration.
- Protocol plugins own SSLOG record metadata and policy levels. FCCG must not duplicate a fixed
  record table in Python. Generated `.ssdecoder` bundles are declarative data and never code.
- For STM32 Boards, the bundled/imported `.ioc` is the physical truth. Board manifests retain
  semantic aliases, legal choices, verification state, services, and provenance rather than a
  second physical-resource database.
- GUI widgets call application/domain services; they do not copy files, parse plugin archives,
  modify build files, or run toolchains directly.
- All copy, extraction, replacement, and deletion operations pass through the workspace/path
  safety layer and use validation plus staging before apply.
- Configuration follows Device → Flight Configuration → Hardware Connection → Build. Device
  manifests declare capabilities and resource needs; Algorithm/Flight selections determine actual
  capability consumption before Board/imported hardware resolves physical mappings. The MCU plugin
  remains PCB-neutral.
- Physical `DeviceInstance` records provide capabilities. Selected Algorithm/Flight components
  require capabilities with a purpose, and the resolver stores a source override only when two or
  more physical instances can satisfy the same capability. Usage lifecycle stays in the consuming
  implementation; do not add a general PRE_START/ASCENT/RECOVERY phase policy.
- Raw/Data capabilities only assert that data exists. Qualified capabilities ending in
  `_qualified` assert suitability for a specific implementation contract. A Strategy must require
  every qualification it needs; never infer qualification from a device model or related raw data.
- Static preflight-alignment qualification is distinct from authoritative runtime-attitude
  qualification. Hardware-quaternion alignment selectors must require the former when they only
  sample attitude during initialization.
- User-facing sensors and actuators are declarative Device instances. ADC/GPIO resources remain
  Hardware Connection details; the input-voltage monitor and mission-action actuators bind to
  those resources without presenting the raw resources as devices.
- Protocol log availability uses Device-declared Recordable outputs independently from whether an
  Algorithm currently Consumes the same capability. Required streams remain forced on.
- Mission-action dependencies are one-way. A Mode may require the parachute output, but removing
  an actuator must never auto-add it again. Launch-output absence means external ignition; removing
  parachute output clears dependent deployment Modes.
- Mode parameters and telemetry/maintenance/logging profiles are manifest-owned generic data.
  Generated constants, summaries, and decoder profiles must all use the same project values.
- Board/imported `.ioc` facts must satisfy typed bus and GPIO electrical/safe-start constraints.
  Manual assignment confirmation is a fingerprint and must clear when a validity input changes.
- Strategy and Mode slots are generic manifest-declared dictionaries. Do not add hard-coded future
  Guidance/Control/Actuator choices without real plugins and source.
- Imported vendor configuration remains below `HardwareGenerated/STM32CubeMX/`. It is neither
  SilverStar Platform source nor FCCG-generated glue, and replacement always requires a dangerous
  plan confirmation.
- Make and native EIDE must be rendered from the same resolved source graph. VS Code tasks call the
  generated Make project; no environment renderer may independently discover sources.
- FCCG is generation-first: Generate/Apply materializes files without compiling or running quality
  gates, then the user opens the generated VS Code/EIDE project. Release is the default generated
  configuration while Debug remains selectable. Normal Apply preserves unchanged managed-file
  timestamps and build dependency files.
- GUI display functions are read-only. Configuration changes apply to a candidate model, run the
  shared reconcile pipeline, and replace the live model only after reconciliation succeeds.

## GUI standard

All PySide6 UI work follows `docs/GUI_STYLE_GUIDE.md` and the copied normative
`docs/CXYL_Python_GUI_STYLE_GUIDE.md`. Preserve the stable product title, deep-blue header and
left navigation, Light/Dark themes, Simplified Chinese/English catalogs, custom tab/table/control
styling, bottom task status/progress, and QRunnable/QThreadPool background work. Keep exactly the
four normal pages defined in the GUI guide and no standalone Project, Plugins, or Generate page.
Project operations belong in File; plugin management belongs in the Plugins menu. User-visible strings
use translation keys. Boolean/multiple selections use `StandardCheckBox`; progressive disclosure
uses `CollapsibleSection` and never disables its body. Logging remains directly visible.
Development settings remain repository-local.

## Code and tests

Keep modules focused and typed. Follow the project naming convention for callable interfaces:
noun followed by a capitalized verb phrase, for example `Project_Load` and `Theme_Apply`.
Run focused tests, then the complete suite. Do not claim toolchain, EIDE, flash, or hardware
support unless the corresponding validation actually passed.
