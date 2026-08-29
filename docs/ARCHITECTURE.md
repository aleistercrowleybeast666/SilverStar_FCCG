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
        │ owns one or more
        ▼
Capability Endpoint Instance
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
        │ multiple providers: instance 0 default, optional saved override
        ▼
Static project_capability_routes.c
```

`DeviceInstance` identifies the physical module (`imu0`, `gnss0`, `telemetry0`, `maintenance0`) independently of its plugin implementation. Generated descriptors then assign contiguous capability-class endpoint indices: one JY901B physical instance can own IMU 0, BAROMETER 0, MAGNETOMETER 0, and ATTITUDE 0 without duplicating UART initialization or status objects. Canonical Source Selection is a third identity: each consumed capability defaults to endpoint instance 0 and stores only a non-default physical-source override. Instance policy distinguishes a per-model `plugin_max` from a whole-class `class_max`; legacy `project_max` data migrates conservatively. A class may contain two different singleton models when its class limit permits it, while repeating one model additionally requires `same_plugin_multiple` and a context-safe `multi_instance_ready` driver.

Strategy selection determines which implementation enters the source graph. Capability resolution determines which physical instance supplies each declared input. These are deliberately separate. The consuming implementation owns when and how it uses an input; FCCG has no general PRE_START/ASCENT/RECOVERY phase-policy layer. Future sensor selection/health and Multi-EKF behavior must be explicit Strategies, not automatic consequences of adding devices.

Capability state has three separate views: **Provided** means a Device can produce the datum, **Consumed** means a selected implementation has a routed requirement, and **Recordable** means Device/protocol metadata permits raw logging. Recordability never depends on a current Algorithm route. This allows JY901B hardware quaternions to be logged under software alignment while keeping magnetic frames disabled for the actual device return configuration.

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

An MCU/Platform plugin describes chip-family capabilities, Platform backend, one HAL/CMSIS source policy, exact CubeMX/Firmware Package compatibility, CPU/FPU flags, memory/CCMRAM contract, linker/startup support, compatible providers, and deterministic exact/family/package/core matching rules. Resource backends carry a strict `reserved`/`experimental`/`supported`/`verified` maturity. It does not contain sensor selection or PCB pin meaning. The user never selects it on Devices: Board/imported CubeMX facts are matched with exact-part precedence, and zero/tied candidates are explicit errors. The project persists the detected facts and component/version/manifest lock; a compatibility mismatch stops import/readiness rather than mixing vendor source and trying a build.

A Board plugin describes one PCB profile: compatible MCUs, an immutable `.ioc`/vendor snapshot, semantic aliases and connections, legal alternatives, fixed/reserved roles, provenance, verification state, and `source_kind` (`verified_builtin`, `manual_import`, or `third_party`). Physical pins, peripheral settings, DMA, IRQ, and clocks are parsed from `.ioc`; they are not duplicated in manifest metadata. A Board does not own generic storage, log-sink, mission-action, indicator, or voltage-monitor implementations. The same MCU plugin is reused unchanged by multiple Boards.

Logical Device plugins give user meaning to raw resources and explicit internal service components. The input-voltage monitor appears under Other Sensors and binds to an ADC-backed power service; launch ignition and parachute pyro appear as independently optional Power Outputs bound to P_CONTROL1/P_CONTROL2. Dependencies are one-way: a deployment Mode requires parachute output, but reconciliation never auto-adds a cancelled actuator. Removing parachute clears dependent Modes; removing launch selects external-ignition behavior and leaves START legal without a GPIO.

Physical storage is an ordinary single-instance Device, not a Board capability shortcut. The
`silverstar.device.storage.sd_sdio_fatfs` payload owns Storage and file Log Sink consumers under
`Devices/Storage/SdSdioFatFs`; the Board owns only fixed resource mappings, CubeMX owns SDIO plus
FatFs App/Target glue, and MCU/Platform owns the controlled FatFs core and HAL provider. Legacy
Board-path sources can remain project-owned after migration but are inactive in the resolved graph.

Software indicators use the same declarative Device/resource path. The System Status Indicator is selected by default and owns one GPIO Output; on SS0.5 its fixed role is active-low `IMU_CAL_LED`/PA1. The optional GNSS Status Indicator requires a GNSS Device capability and a distinct exclusive GPIO Output. SS0.5 explicitly declares that it has no second assignable indicator GPIO, so the resolver never reuses the system LED or P_CONTROL1/P_CONTROL2. A power-rail LED that cannot be controlled by the MCU is hardware metadata at most, never a software Device. Firmware reuses one `SystemIndicatorRole` state machine: GNSS mode resolves from online/sample availability and `SystemGnssSample.position_usable`, not `fix_type` alone.

A Hardware Configuration Provider is a trusted FCCG handler used to create a Board. The current provider imports STM32CubeMX output as data. Imported vendor code remains below `HardwareGenerated/STM32CubeMX/`; it never enters `Platform/`, `Devices/`, `System/`, `Algorithm/`, or `FlightLogic/`. After mapping and validation, the snapshot can be exported as a reusable Board plugin.

`HardwareInventory` retains every recognized peripheral without artificial count slicing. It models MCU/package/core plus CubeMX/Firmware Package, pins/AF/GPIO/EXTI, UART, SPI, I²C, ADC, Timer/PWM, Classic CAN versus FDCAN, DMA, NVIC, useful clocks, the generated HAL timebase, and FatFs App/Target/symbol facts. I²C requires Open Drain SCL/SDA; internal pull-ups, Board-declared verified external pull-ups, or a custom confirmation bound to `source_digest + snapshot_id + resource_id` are distinct auditable evidence paths. PWM exists only when `.ioc` declares PWM Generation and generated C contains the matching `HAL_TIM_PWM_ConfigChannel`; ordinary CH1..4, PWM1/PWM2, up-counter mode, polarity, prescaler, ARR, clock and safe-stop behavior are persisted as hardware facts. Input Capture, Output Compare, One Pulse, Encoder, complementary/dead-time, center-aligned, combined and asymmetric modes do not become PWM resources. The HAL timebase must be an unambiguous generated TIM source with a 1 MHz counter, 1 kHz interrupt tick and enabled matching IRQ; SysTick, source mismatch and PWM reuse fail. Requirements validate typed bus roles/rates/frame/mode/order/address/DMA/IRQ, Platform capabilities, PWM channel/shared-timer timing, and GPIO electrical/safe-start contracts. The resolver detects logical and underlying physical-resource collisions. A successful manual check stores a fingerprint over hardware truth, Platform lock, assignments, Devices, Strategies, and Modes; relevant changes invalidate it.

The renderer consumes the selected Platform manifest's resource binding contract: resource header, collection, vendor include, ID/table/getter/struct symbols, ABI, and conditional backend contributions. Python validates C identifiers and paths but contains no STM32F4 getter/header or MCU model table. Existing F4 symbol names remain in the F4 plugin. A virtual H7 test contract proves that a different header/getter can render without becoming a production-supported MCU.

Conditional backend selection is the intersection of actual inventory, an assigned Device resource, and an enabled backend maturity. Declarative module/provider mappings keep CubeMX init, middleware/HAL providers, and consumer wrappers separate. Active supported I²C/PWM assignments add the Platform backend and provider sources exactly once. The F407 Classic-CAN backend is `reserved`, so an inventory entry remains visible but a normal consumer receives an explicit error and no backend source. Under `plugin_payload_authoritative`, custom CubeMX contributes only controlled `Core/Src` C and `Core/Inc`; imported HAL/CMSIS, startup and linker never enter the graph. Default SS0.5 selects no I²C/CAN/PWM consumer, so all three optional backends remain absent.

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

Slots are manifest strings, not permanent fields in Python. Current Strategy slots are Alignment, INS, Estimator, and Landing. Current Mode slots are Calibration and Deployment. Mode manifests may own typed numeric parameters and generated symbols. Three independently selected Protocol plugins each own exactly one telemetry, maintenance, or logging category. `Estimator=None` contributes `SYSTEM_FUSION_NONE`, excludes KF6, keeps BARO_NATIVE recordable, and disables estimator-derived BARO_MEASUREMENT.

Capabilities have two explicit semantic kinds. Raw/Data capabilities (for example `magnetometer.field`) say that a physical Device can produce data. Qualified capabilities use the stable `_qualified` suffix (for example `magnetometer.absolute_vector_qualified`) and say that the current driver/hardware/system contract approves that data for a specific use. Device manifests provide both kinds; Strategy/Mode manifests require the qualified contract they actually need. The resolver contains no JY901B model-name special case.

Static preflight qualification and authoritative runtime attitude are different contracts. The JY901B evidence grants `attitude.external.preflight_alignment_6axis_qualified` and `_9axis_qualified`, so both hardware-quaternion static alignment Strategies are legal. It does not grant either authoritative 6-axis/9-axis runtime qualification. Gravity/Magnetometer TRIAD still requires the absent absolute-vector magnetic qualification.

The reference firmware currently centralizes three Landing modes in its recovery state machine and shares landing metrics/regression functions. FCCG therefore owns the shared payload once and uses three declarative compile-time selector components with different qualified requirements. It does not copy the same C code three times, and documentation does not claim that unselected mode functions already exist as fully separate reference source modules.

## One project and build truth

`SilverStar.ssproject` plus installed manifests are the configuration truth. `SourceGraph_Resolve()` combines explicit source, assembly, include, define, forced-include, linker, CPU, library, virtual-source, and exclusion contributions. A component may declare `strategy_sources` alternatives for one Strategy slot; the resolver selects exactly the `selected` or `none` branch and places the inactive branch in the environment exclusion graph. The core uses this for mutually exclusive KF6 and pure-INS estimator tasks, so Estimator=None contains neither KF6 source nor configuration-dependent branches in first-party C.

```text
Project Model + manifests
          ↓
Resolved Source Graph
          ├── Generated/project_sources.mk → Make
          ├── native .eide/eide.yml
          └── VS Code tasks → the generated Make project
```

EIDE starts from the read-only firmware's known-working `.eide/eide.yml`, `.eide/files.options.yml`, workspace, and task templates. FCCG replaces only project/source/include/define/linker/output/Debug/Release/workspace fields from the resolved graph. It retains required target and `uploadConfigMap`/`uploader` structure, keeps `deviceName: null` and `packDir: null`, and does not default to J-Link. Retaining the reference OpenOCD selection is not a flash-validation claim: FCCG emits no upload task/button and the current plugins declare no validated flash capability.

The selected DevelopmentEnvironment plugin chooses a trusted renderer. The current implementation is VS Code + EIDE + Arm GNU Toolchain. Arbitrary plugin code is never called.

## Lifecycle, ownership, and Save

New projects are assembled in workspace-local staging. Existing projects are validated and planned before writes. The public lifecycle is Draft/Dirty → Materializing → Ready, plus Building/Error while a long operation runs or fails. Save and every build/check entry re-plan current managed output, so an FCCG renderer upgrade cannot be hidden by hashes from an older installation.

A project is Ready only when its descriptor, Make targets, selected component/Board payloads, hardware-preparation fingerprint, Generated/Target trees, ownership hashes, EIDE, VS Code tasks, and workspace exist and agree with the in-memory model. Stale comparison, embedded project digest, decoder metadata, and ownership metadata share `ProjectGenerationState_Normalize()` / `ProjectGenerationFingerprint_Get()`. The normalized state includes MCU/Board/hardware source, Devices (including Indicators), Strategies, Modes/parameters, capability overrides, protocols, logging, resource assignments, environment, and source-graph configuration. It excludes Arm GNU/Make/Host GCC paths, tool-detection cache, provenance/display-only hardware fields, manual-confirmation state, and GUI preferences. Renderer functions deep-copy before adding provenance; after a successful apply the exact descriptor written to disk is reloaded and becomes the live model, so generation immediately reaches Ready.

New-project and Save-As publication order places `SilverStar.ssproject` last. Generate Code performs no compile or quality task. Advanced Build Firmware in FCCG, Clean, Host Tests, Architecture Check, Power of Ten, Static Analysis, and Firmware Artifact Check call `Project_EnsureBuildable`; dirty or incomplete material is saved before Make runs with the project root as explicit `cwd`.

GUI configuration edits are transactions: copy the live model, mutate the candidate, reconcile once, construct every view model, and render without mutating either model. Only a successful render publishes the candidate. Mode signals are coalesced through a zero-delay timer so a checkbox's parent is never deleted inside its own `toggled` stack. Rebuilds block signals; any exception logs a traceback, restores the previous view/model, and remains inside the Qt callback boundary.

- Component payloads become project-owned source and are preserved on ordinary Save.
- Managed files are replaced only when rendered bytes change; normal Apply preserves build outputs and Make dependency files.
- Save Project As copies the complete project-owned tree while excluding build/cache/intermediate output.
- Deactivated component files remain on disk but leave the source graph.
- `Generated/`, `SilverStar.ssproject`, `SilverStar_Configuration.md`, Make/target data, workspace files, `.vscode/`, and `.eide/` are FCCG-managed.
- A change to a normalized FCCG-owned `.eide/eide.yml` build field, MCU/target change, collision, deactivation, or changed CubeMX snapshot marks the plan dangerous and requires confirmation. EIDE-owned UI/order/target/uploader metadata does not.
- `HardwareGenerated/` is preserved normally. Reimport may replace its complete tree only after an explicit dangerous plan.
- `.fccg/ownership.json` records active components and hashes for comparison; hashes document provenance and never restore source automatically.
- `<ProjectName>.ssdecoder` is FCCG-managed declarative output. Canonical record-catalog and project-semantics JSON, a manifest, checksums, and a README form a deterministic data-only package; generated C embeds truncated catalog/semantics/generation identities. It contains no executable plugin.

## Filesystem and process safety

There are two non-overlapping authorization roots. The FCCG internal policy owns plugins, settings, logs and import snapshots below the repository. An output policy is created from the exact project directory explicitly selected by the user and owns only that generated project. Planning, staging, build working directories and every destination are checked against the applicable root; neither policy can escape into the other or a sibling path.

All destinations pass through `WorkspacePolicy`, portable path validation, staging, and atomic replacement/rollback logic. Archive installation rejects traversal, absolute/drive paths, symlinks, special files, duplicate-case names, excessive size/count, managed-path claims, and executable-script package entries. Plugin data is never imported or executed.

FCCG v0.x formally supports STM32 plus STM32CubeMX for manual Hardware Configuration. Plugin, Platform, Device, Strategy, Mode and provider interfaces remain generic so a future non-STM32 provider can be added without treating STM32 concepts as universal project fields.

Subprocesses use argument arrays and explicit project working directories. Tool detection runs version commands only. FCCG does not modify PATH, registry, global IDE settings, global Python state, or reference repositories.

## Device discovery and protocol composition

The Device page enumerates every valid installed `type = device` manifest and groups it from the
strict `metadata.device_category` namespace. `sensor.imu` and `sensor.gnss` are primary sensors;
other `sensor.*`, `link.*`, `storage.*`, `actuator.*`, and `indicator.*` remain separate dynamic
groups. Unknown namespaces fail plugin scan instead of falling into Other Sensors. It never uses
Board/IOC resource sufficiency as selection availability and contains no MCU selector.
Selected logical Devices feed capability and hardware requirements into the shared reconcile
pipeline; Hardware Connection alone resolves those requirements against Board or imported IOC
facts. The project owns one MCU, one target profile, and one hardware configuration, while
Device and capability endpoints may have instances.

Protocols use four explicit layers: a fixed System Service selects one complete Protocol Profile
from its independently locked single-category plugin;
the profile declares a Transport Binding and constraints; resolution chooses exactly one
compatible physical Device or storage provider. Profile source/include/define contributions enter
the one resolved graph only when selected. Decoder metadata records the same profile, binding,
provider instance, physical-device identity, source descriptor, and record instance data. The
current three profiles are real but are not advertised as freely interchangeable.

Formal component documentation stays in installed declarative plugin packages and is shown by
plugin management; it is not duplicated into each generated source project. Reference import
audits the maintenance instance-command document before publication. The generated architecture
gate therefore validates available generated source/build metadata and records a note when that
package-owned Markdown is intentionally absent.

## Logging semantics and task progress

The Protocol plugin owns both SSLOG wire/schema metadata and FCCG presentation policy. Optional
`cadence` metadata describes periodic, source-driven, measurement-driven, event, one-shot, or
algorithm-output timing without Record-ID branches in Python. Project state continues to store only
policy, `decimation`, and microsecond `period_us`; zero is an unused field for non-periodic policy,
not a continuous zero-period producer.

Availability is the intersection of schema presence, selected component/capability/Recordable
requirements, and—when declared—at least one selected producer component or producer identity.
Omitting producer metadata preserves pre-release behavior. This prevents a codec from being
mistaken for a runtime production path while keeping old protocol plugins loadable.

The synchronized reference commit `cc0b377ded690556d037a412a55f87fe334c42d0` declares
`silverstar.core.device_task` as the STATS producer and `silverstar.core.telemetry_task` as the
TELEMETRY_DIAG producer. Their shared `diagnostic_log.c` implementation is scheduled by the real
Device and Telemetry tasks; the protocol metadata therefore exposes STATS at 1 s and
TELEMETRY_DIAG at 200 ms only when the corresponding selected composition remains valid.

The serial maintenance Transport remains an internal physical `DeviceInstance` so protocol
resolution, source graph, and UART resources stay authoritative. The Devices page filters this
internal console class; Hardware Connection still owns its USART, pins, baud, and electrical facts.

Long operations report `FCCG_PROGRESS|TASK|PLAN|total`, `BEGIN|current|total|subject`, and
`DONE|current|total|subject`. BEGIN is observational and DONE alone advances completed work.
BuildRunner consumes the same protocol as TaskContext. Successful tasks finish at 100%; exceptions
and cooperative cancellation retain the last completed count. Expected host compile rejection is
a successful configuration gate only when the diagnostic matches static assertion/`#error`; its
raw compiler output is routed to detailed and file logs.

**Export Log Decoder Profile** is a synchronous, read-only project operation: it verifies that the
saved project and managed package are current, rebuilds the same canonical bytes, and atomically
writes only the user-selected destination. It never starts a task or mutates model, fingerprint,
ownership, or Dirty state.

## Shared EIDE ownership

FCCG fingerprints only normalized build-owned EIDE fields: sources/excludes, includes, defines,
CPU/FPU/ABI, linker/startup, toolchain, Debug/Release flags, libraries, and output directories.
EIDE-owned field order, selected target, UI state, uploader status, and compatible extension data
are preserved and ignored for stale detection. A dangerous plan names each genuinely changed
owned field instead of reporting a whole-file hash mismatch.
