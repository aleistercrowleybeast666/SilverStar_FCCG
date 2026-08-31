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
| `mcu` | Chip/family Platform, automatic match rules, resource ABI/backends, HAL/CMSIS, CPU/memory/toolchain contract |
| `board` | PCB resources, mappings, services, hardware payload/provenance |
| `device` | Sensor, communication, or future `class=actuator` implementation |
| `algorithm` | Base algorithm code, Strategy, or Mode owner |
| `flight_logic` | Flight-cycle/mission behavior, Strategy, or Mode owner |
| `os` | RTOS kernel/port/configuration contribution |
| `protocol` | Exactly one strict telemetry, maintenance, or logging category with one or more complete Profiles |
| `hardware_configuration_provider` | Declarative access to a trusted hardware-import handler |
| `development_environment` | Declarative access to a trusted project renderer |

Resource kinds are schema-controlled strings. Current contracts support typed UART (rate/frame/DMA/IRQ), SPI (mode/phase/order/rate/DMA/IRQ), I²C (rate/address/address-mode/pull-up/DMA/IRQ/repeated-start requirement), PWM (frequency/resolution/safe state/channel), GPIO electrical/safe-start/EXTI constraints, plus ADC, SDIO, Time, Classic CAN, FDCAN inventory separation, and timer facts. PWM polarity is deliberately not a Device constraint: mode, polarity, counter, ARR/prescaler and frequency are immutable CubeMX/Board hardware facts.

## Common manifest blocks

The strict schema is `schemas/plugin.schema.json`. Version 0 includes identity/type/class/version, Device `instance_policy` and `physical_device`, dependencies, typed capability/resource requirements, provided capabilities/resources, explicit build contributions, payload roots, localization/descriptor metadata, and optional type-specific blocks.

`build` may declare C/ASM sources, includes, defines, MCU flags, specs, libraries, forced includes, virtual sources, excluded sources, linker script, and toolchain prefix. `strategy_sources` can additionally contribute a `selected` or `none` C-source set for a manifest-named Strategy slot. `protocol_sources` maps telemetry/maintenance/logging to finite Core/Service sources that enter the graph only while that Protocol slot is non-null. Sources/linker/forced includes must exist in the declared payload; Make-unsafe tokens are rejected.

### MCU/Platform

Every MCU manifest owns `platform.build_target.profile`, a strict non-empty safe token such as
`SilverStar_F407`. It names the generated Target Profile and output subtree; it is not a GUI option
and does not imply hardware verification. Reconciliation derives the project lock from the matched
MCU/Platform, while strict validation rejects a missing, unsafe, or mismatched lock. Non-MCU
manifests cannot declare `platform`. The official SilverStar builtin manifest `version` follows the
0.0.10 platform release train, while MCU part/Board revision, CubeMX/Firmware Package, protocol
Profile, schema, RTOS, and third-party upstream versions retain their own namespaces.

### Board

`resources.provides` declares stable semantic resource aliases and the small generated-interface metadata they need. `resources.roles` binds requirement keys/classes to a kind, default, candidates, and `fixed` state. Provisions may be reserved; conflict groups reject illegal simultaneous use. For STM32, `board.ioc_file` points to the physical truth and `board.connections_file` maps aliases to IOC resource IDs. The Board block also declares compatible MCUs, vendor/provider, verification/source kind, and hardware root.

`metadata.optional_resource_bindings` declares hardware-service resource macros whose logical Device may be absent. Each entry names the normal `binding_macro`, an `enabled_macro`, a typed platform sentinel used as the disabled `fallback`, and the platform header that defines that sentinel. The generated resource header emits a real assignment plus `1U` only when the role is resolved, otherwise the non-index sentinel plus `0U`. Device-owned or internal service C implementations test the generated feature constant with ordinary control flow; they do not duplicate the Board's physical mapping or add configuration-dependent preprocessor branches.

Device requirements may use legacy simple constraints or one typed UART/SPI/I²C/Classic-CAN/PWM contract plus independent GPIO electrical constraints and required Platform capabilities. Typed I²C, Classic-CAN, and PWM requirements must name at least one `platform_capabilities` entry; seeing a matching peripheral in an inventory is not evidence that the selected Platform implements its backend. A backend also declares `maturity` as `reserved`, `experimental`, `supported`, or `verified`; normal projects reject reserved and experimental entries. I²C requirements may declare a `composite_device` identity. Two endpoints may share one bus/address only when they belong to the same physical Device instance and explicitly use the same non-empty composite identity; otherwise the duplicate address is rejected. `required_pullup` accepts internal pin pull-ups, Board resource metadata `external_pullup_verified=true`/`pullup_source=external_verified`, or an exact custom-snapshot confirmation; NOPULL alone is never evidence. New `instance_policy` data separates `plugin_max` (instances of one model) from `class_max` (all physical Devices in that class), plus `same_plugin_multiple` and `multi_instance_ready`. Legacy `project_max` manifests remain loadable and map safely to those two limits. Raising `plugin_max` above one requires a real context-capable driver; a class limit above one may instead permit two different singleton models. Declaring multiple physical instances never duplicates shared source paths in the resolved graph.

`physical_device` distinguishes vendor/model/chipset from the reusable driver. For example, the current radio is physical model Ebyte E28-2G4M12SX, chipset SX1281, using the existing SX1281 Driver. A single Device can `provide` several capabilities; JY901B is one physical UART instance that provides acceleration, angular rate, external attitude, magnetic field, and barometric altitude.

`metadata.device_instance_bindings` may map a capability class to a C function prefix and declare
whether the implementation receives an instance context. FCCG uses this generic metadata to emit
bounded `CountGet` functions and direct `switch(instance_id)` calls; the generator does not branch
on JY901B, NEO-M9N, or another vendor/model name.

Declarative logical Devices may omit payload roots when an explicit internal service component owns the implementation. Board plugins own PCB facts and verified semantic mappings, not generic storage, mission-action, indicator, or voltage-monitor services. `metadata.logical_device`, `device_category`, and `independent_class_member` identify UI grouping and independent singleton members. `device_category` must match `sensor.*`, `link.*`, `storage.*`, `actuator.*`, or `indicator.*`; unknown/misspelled namespaces fail at scan/install time. `default_instance_id` restores a stable ID when the user explicitly re-enables a singleton. An internal endpoint may declare `auto_managed_protocol_category` as exactly `telemetry`, `maintenance`, or `logging`; reconciliation then adds/removes it generically with that slot and never removes a user-owned Device lacking this declaration. `auto_select_when_required` is deliberately false for the two mission-action outputs: downstream Modes may depend on an actuator, but reconciliation never overrides the user's actuator cancellation. Current actuator classes distinguish `mission_action_actuator` from the reserved future `continuous_control_actuator`.

`metadata.recordable_outputs` declares raw outputs that can be written to protocol logs and optional device-configuration reason codes for outputs that exist but are not currently returned. It is intentionally separate from Algorithm capability consumption. Protocol record policies use `requires.recordable_capabilities`; they must not infer recordability from a capability route.

Algorithm/Strategy/Flight manifests declare inputs as `{ "capability": "barometer.altitude", "purpose": "measurement_update" }`. Raw/Data capabilities state only that data exists; qualified-use capabilities end in `_qualified` and state that the provider meets a concrete implementation contract. Strategies explicitly require both the raw inputs and every qualification they need. Purpose describes the consumer contract; the implementation owns lifecycle. No generic phase policy is inferred or generated.

### Protocol

`protocol.category` is the strict enum `telemetry`, `maintenance`, or `logging`; one plugin cannot cross categories. Each Profile declares service/slot, codec and parser sources, includes/defines, typed transport binding, decoder metadata, documentation, Host tests, and golden tests. Referenced assets must exist in the plugin dependency closure. Duplicate `(category, profile_id)` providers are rejected. An enabled project slot locks component ID, plugin version, Profile ID, and raw manifest SHA-256; `null` is an explicit project state and never a plugin. The old `protocol_bundle` shape exists only in the format-7 migration path and is not accepted as a new production plugin.

For the logging category, `protocol.logging_metadata` points inside the package payload to `sslog_parser_metadata.json`. Its `fccg.records` policy data assigns each record `required`, `recommended`, or `optional`, owns bilingual names, and can require capabilities, Recordable outputs, components, or selected strategy slots. Adding or translating a valid record requires no FCCG Python record-table change.

Each FCCG record policy may also declare optional timing and production semantics:

```json
{
  "cadence": {
    "kind": "source",
    "source": "imu",
    "display_names": {
      "zh_CN": "取决于IMU数据更新",
      "en_US": "Follows IMU updates"
    }
  },
  "producer_components": ["silverstar.core.device_task"]
}
```

Supported Cadence kinds are `periodic`, `source`, `measurement`, `event`, `one_shot`, and
`algorithm_output`. Display names and source IDs are declarative; GUI code must not branch on Record
enum names. `producer_components` is an any-of producer identity constraint applied after schema,
capability, Recordable, component, and Strategy checks. Selected manifests may contribute aliases
through `metadata.log_producers`. Omitting these fields preserves compatibility with old plugins.
The presence of a schema/codec never substitutes for an explicitly declared producer.

The selected logging profile's parser metadata references the authoritative record schema used to
build `record_catalog.json`. FCCG preserves that declarative schema rather than hard-coding record
layouts in Python. Generated `.ssdecoder` packages add project semantics and hashes around this
data; they contain no parser source, script, shared library, or executable hook.
The current firmware-owned package and container IDs are
`silverstar.ssdecoder.package-schema/1.1` and `silverstar.sslog.container/0.0`; package schema 1.1
allows nullable telemetry/maintenance locks while requiring logging to be selected. A prompt or plugin
may not silently substitute another container identity for the selected real codec.

### Strategy and Mode

`selection.kind = "strategy"` declares a slot, order, required/`allow_none`, and optional build definitions for None. Exactly the selected strategy payload enters the graph.

`selection.kind = "mode"` declares a slot, `allow_none`, `allow_multiple`, options, defaults, localized labels, per-option requirements, optional numeric `parameters`, generated symbols/scales, per-option trigger symbols, and an aggregate mask symbol. Modes remain options of their owner component rather than fake algorithm packages.

The calibration component uses `allow_none: true`, `allow_multiple: true`, options OneFace/SixFace,
and an empty default. That empty list is the declared NONE/identity-correction state; no fake None or
Existing option is installed. The component remains in the Source Graph and its Required
`CALIBRATION_RESULT` producer remains active whenever logging is selected.

### Hardware provider

Declares vendor, accepted inputs, and one allowlisted handler such as `stm32_cubemx`. Installing a package cannot add handler code.

### Development environment

Declares renderer, toolchain, outputs/tasks, and native EIDE capability. The current allowlisted renderer is `vscode_eide_gcc`, and the only supported firmware compiler is Arm GNU `arm-none-eabi-gcc`. Make orchestrates builds; objcopy/size are derived sibling tools; Host GCC is only for host tests.

## Installation safety

Installation validates the entire archive in staging before one final move. It rejects invalid/unknown schema fields, traversal/absolute/drive/backslash/control/reserved paths, symlink/special-file entries, case-insensitive duplicates, excessive count/expanded size, duplicate IDs, unsatisfied dependencies/capabilities, payload collisions, unsafe build tokens, and claims on FCCG-managed `Generated/`, project metadata, `.vscode/`, or `.eide/` paths.

Install/remove progress follows validate → copy/delete → register/unregister → Catalog refresh.
Removal first moves the package into a repository-local staging tombstone and restores it if a later
phase fails or is cancelled; plugin code is never executed during any phase.

Builtins are read-only. Installed-package removal checks reverse dependencies and open-project selection. It never removes payload already copied into a generated project.

## Reference builtins and Board export

`tools/import_reference_components.py --reference <path>` reads a selected reference, records path/commit/branch/status/snapshot digest/protocol-source hashes, stages the reference-derived components, replaces the old combined protocol package with three independent Protocol packages, relocates generic services to their declared Device/internal-service owners, replays FCCG-owned Platform/protocol/logging/landing overlays, strict-scans all 36 packages, and atomically replaces only `plugins/builtin/`. The reference itself is never written or built. Each manifest's `metadata.reference` contains only stable source kind, commit, and snapshot digest, so a later import timestamp, local path, branch display, or audit note cannot make otherwise identical packages stale. Dynamic import/audit details remain in catalog-level `reference_provenance.json`. `metadata.source_origins` identifies `reference_base` separately from FCCG-owned optional-protocol gating and other extensions; the importer's `fccg_owned_files` mapping replays those exact workspace sources so a later reference import cannot erase the task/codec gating.

`build.module_providers` declares CubeMX-owned initialization/middleware modules separately from consumer wrappers. A provider may contribute exact sources/includes/defines only when its inventory predicate and selected component composition require it. HAL/CMSIS ownership remains a separate Platform source policy; source presence alone never activates every optional provider. The current F407 Platform keeps Classic CAN `reserved`, so its provider can be audited without permitting a normal CAN consumer.

### MCU/Platform contract

An MCU manifest can declare `platform`: ABI ID/major/minor, CubeMX provider, exact/family/package/core match rules with priority/specificity/verification, exact compatibility/source policy, the resource binding header, per-kind collection/include/table/getter/struct contracts, conditionally activated backends with maturity, Platform capabilities, plugin provider sources, ownership rules, support level, and limitations. C identifiers, headers, paths, handles, channel tokens, versions, policies, and referenced assets are strictly validated. Renderer input is only the validated inventory and assignments; no plugin code or general-purpose template expression is evaluated.

An MCU/Platform `compatibility` block strictly declares accepted `cubemx_versions`, `firmware_packages`, and either `plugin_payload_authoritative` or `imported_tree_authoritative`. The current F407 implementation accepts only CubeMX 6.15.0 plus `STM32Cube FW_F4 V1.28.3` and uses plugin-owned HAL/CMSIS/startup/linker. Backend activation requires an assigned resource whose inventory kind matches a non-reserved backend. Source Graph then includes its declared plugin provider sources; imported CubeMX `Drivers/`, CMSIS, startup and linker are rejected under this policy. The F407 contract advertises no generic repeated-start, separates `can_classic` from `can_fd`, marks bxCAN reserved, and enforces PWM channel exclusivity/shared-timer frequency equality.

Indicator Device manifests own their GPIO Output requirement and generated enable symbol. A Board may fix the System Indicator to a verified LED or declare an optional indicator unsupported; that declaration prevents fallback onto unrelated exclusive outputs. Hardware-fixed power lamps have no Device manifest because firmware cannot control them.

A custom imported STM32 mapping can be exported as `.ssplugin` with Board manifest, semantic aliases/roles, `connections.json`, the source `.ioc`, hardware provenance/docs, and `payload/HardwareGenerated/STM32CubeMX/`. It does not serialize a second copy of parsed physical facts. On installation it behaves as an ordinary reusable Board component; its `manual_import` status remains visible and is not upgraded to official validation.

## Complete protocol profiles and transports

A profile is catalog-visible only when it declares a valid service, profile ID/display names,
slot, codec and parser sources, includes/defines/source graph, binding, typed transport constraint,
decoder metadata, protocol docs, and Host/golden tests, and every referenced asset exists in its
dependency closure. A name-only manifest is rejected.

Physical Device and Board/storage manifests may declare `transports` with capability, kind, mode,
MTU, ordering, directionality, and reliability. Resolution requires exact capability/kind/mode,
sufficient MTU, and every requested boolean property, and rejects both missing and ambiguous
providers. These declarations model current AIR packet, maintenance byte-stream, and sequential
flight-log sink bindings; they do not claim future profiles work without their complete sources.
