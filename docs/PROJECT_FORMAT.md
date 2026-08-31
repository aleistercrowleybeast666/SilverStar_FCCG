# SilverStar.ssproject format

`SilverStar.ssproject` is strict JSON with `format_version: 11`; the formal shape is `schemas/project.schema.json`. Formats 0–10 migrate through Strategy/Mode, Hardware Inventory, Device-instance, capability, Mode-parameter, protocol-profile, assignment-confirmation, decoder-profile, independent-Protocol, Platform-lock, CubeMX/HAL compatibility, I²C evidence, storage-Device ownership, FatFs, timebase facts, and nullable Protocol slots. Format 10 selections migrate unchanged as enabled locks; all supported older files are saved only as format 11.

## Sections

- `project`: name, SilverStar firmware/platform version, and release identity. New 0.0.10 projects use `firmware_version: "0.0.10"` and `build_target: "SilverStar_0_0_10"`; this release identity is distinct from the MCU Target Profile.
- `components`: exactly one Core, automatically matched MCU/Platform, OS, and DevelopmentEnvironment; an optional Board while custom hardware is active; ordered `devices: [{instance_id, plugin}]`, base components, and generic `strategies: {slot: component-id | null}`. Protocol components no longer live in this block.
- `modes`: generic `{slot: [option, ...]}` selections. Slot rules and labels come from manifests.
- `mode_parameters`: generic `{slot: {option: {parameter: number}}}` values. Types, units, ranges, defaults, generated symbols, and scaling come from the owning Mode manifest.
- `protocols`: exactly `telemetry`, `maintenance`, and `logging`; each value is either `null` or a lock containing component ID, plugin version, Profile ID, and manifest SHA-256. The three keys are mandatory and unknown categories are rejected. Format-7 `protocol_bundles`/`protocol_profiles` and pre-release IDs migrate deterministically to the three official plugins.
- `hardware`: `unselected`, `board_plugin`, or `custom`, plus source kind/provider, immutable import snapshot/provenance, detected MCU/capabilities/resources, persisted `inventory`, trusted build contributions, matched `platform_component`/`platform_version`/`platform_manifest_sha256`, exact `cubemx_version`/`firmware_package`, `hal_cmsis_source_policy`, per-resource `i2c_external_pullup_confirmations`, first-import risk acknowledgement, and `assignment_fingerprint`. Pull-up evidence maps a resource ID to the exact source digest and snapshot ID; reconcile removes stale bindings. The Platform lock and fingerprint are refreshed by reconcile and retained only while their validity inputs are unchanged.
- `resources`: `device-instance-id:requirement-name` (or non-Device component ID) to provided physical/logical resource ID.
- `capability_sources`: only non-default user decisions for a required capability with several providers, mapping capability to the selected physical Device instance; absent values bind Canonical Source to capability instance 0.
- `logging.streams`: the selected Protocol metadata order plus enable state, policy, decimation, and period. Record definitions and Required/Recommended/Optional levels do not live in the project file. The values remain user preferences but are inactive when `protocols.logging` is `null`.
- `log_decoder_profile`: generated relative `.ssdecoder` path, package-schema version, container-plugin ID, generation-profile SHA-256, and complete package SHA-256. These are derived verification data, not editable generation inputs; all five strings use the existing empty-reference state while logging is disabled.
- `build`: the MCU/Platform-derived `target_profile` integrity lock, Make/toolchain preferences, native EIDE mode, and project-local tool-path overrides. The lock must exactly match the selected MCU manifest (`SilverStar_F407` for the current verified plugin); it is reconciled, not user-selected, and a mismatch blocks strict generation. Release is the generated default and Debug remains an invocation choice; neither is persisted as mutable project configuration. `flash_command` is currently an empty reserved field; it creates no GUI, Make, VS Code, or EIDE upload action without a future validated capability contract.
- `generated_glue`: the reviewed FCCG-owned glue set.
- `component_provenance` and `reference_provenance`: audit information only.

The persisted Device record identifies one physical module. Capability Endpoint Instances are derived from that module's declarative descriptor contributions and receive contiguous indices within each capability class during generation. Canonical Source Selection is separate again: current single-estimator algorithms consume one endpoint per capability and default to class instance 0; no Sensor Voting or Multi-EKF state is implied by adding another physical Device.

Readiness never compares the complete JSON dictionary. `ProjectGenerationState_Normalize()` retains fields that can change generated code or structure (matched Platform, CubeMX/Firmware Package/source policy, hardware source/inventory, Device instances including Indicators, Strategies, Modes/parameters, capability sources, three protocol locks, logging, resource assignments, environment, and source-graph configuration). It removes host tool paths/detection data, provenance/display fields, assignment confirmation, external-pull-up evidence, GUI preferences, and derived decoder hashes, then normalizes tuples/lists through strict JSON so a save/load round trip cannot create a false stale result. Pull-up evidence gates readiness but cannot change generated bytes; version/source facts do participate in the generation fingerprint. The same normalized state feeds `ProjectGenerationFingerprint_Get()`, embedded metadata, stale detection, decoder semantics, and ownership metadata.

Unknown/missing fields, wrong types, duplicate instance IDs/selections/records, instance-policy violations, invalid or unnecessary capability-source overrides, invalid component IDs, unsafe target/path tokens, unsupported policies, invalid numeric ranges, malformed custom snapshot IDs, hardware paths outside `HardwareGenerated/STM32CubeMX/`, a changed Protocol record order, disabled available Required records, or enabled unavailable records are rejected.

## Device instance and capability example

```json
{
  "components": {
    "devices": [
      {"instance_id": "imu0", "plugin": "silverstar.device.imu.jy901b"},
      {"instance_id": "gnss0", "plugin": "silverstar.device.gnss.neo_m9n"},
      {"instance_id": "telemetry0", "plugin": "silverstar.device.telemetry.sx1281"},
      {"instance_id": "maintenance0", "plugin": "silverstar.device.console.uart"}
    ]
  },
  "capability_sources": {}
}
```

Raw/Data capabilities state that a provider emits data. Qualified capabilities ending in `_qualified` state that the data meets a named implementation contract. The selected components derive that the reference consumes JY901B acceleration, angular rate, software-alignment qualification, IMU-stillness qualification, barometric altitude, and barometer-window qualification while external attitude and magnetic field remain unused. If a future BMP280 and JY901B both provide required `barometer.altitude`, the only additional persisted decision is `"barometer.altitude": "barometer0"`. Requirement purposes and lifecycle remain in Algorithm/Strategy manifests and implementations; no flight-phase policy is stored.

Device instances also include source-less logical sensors, actuators, and indicators. The reference uses stable IDs `voltage_monitor0`, `launch_ignition0`, `parachute_pyro0`, and `system_indicator0`; their resource keys bind to ADC/P_CONTROL1/P_CONTROL2/IMU_CAL_LED through the Board. They are ordinary independent singleton Device plugins, not multiple instances of one unverified generic driver. Optional `gnss_indicator0` requires `device.gnss` plus a separate GPIO Output and is unavailable on SS0.5.

Logging does not persist a second capability database. Protocol metadata names Recordable requirements, Device metadata states which raw outputs are enabled, and the saved stream retains only the user's stream settings. Existing project choices are preserved; defaults are applied only when a record is first introduced, while Required records are always forced enabled.

## Generic selection examples

```json
{
  "components": {
    "strategies": {
      "alignment": "silverstar.algorithm.alignment.gravity_known_yaw",
      "estimator": null,
      "ins": "silverstar.algorithm.ins.coning2_sculling2",
      "landing": "silverstar.flight_logic.landing.baro_imu_window_strategy"
    }
  },
  "modes": {
    "calibration": [],
    "deployment": ["ApogeeVerticalVelocity", "Tilt"]
  },
  "mode_parameters": {
    "deployment": {
      "ApogeeVerticalVelocity": {"vertical_velocity_threshold": -2.0},
      "Tilt": {"tilt_threshold": 45.0},
      "Delay": {"delay": 60.0}
    }
  },
  "protocols": {
    "telemetry": {
      "component": "silverstar.protocol.telemetry.air_m0",
      "version": "0.0",
      "profile": "air.m0",
      "manifest_sha256": "<64 lowercase hex digits>"
    },
    "maintenance": {
      "component": "silverstar.protocol.maintenance.serial_0_0",
      "version": "0.0",
      "profile": "maintenance.serial.0_0",
      "manifest_sha256": "<64 lowercase hex digits>"
    },
    "logging": {
      "component": "silverstar.protocol.logging.sslog_0_0",
      "version": "0.0",
      "profile": "flight_log.0_0",
      "manifest_sha256": "<64 lowercase hex digits>"
    }
  }
}
```

`modes.calibration` may be `[]`, `["OneFace"]`, `["SixFace"]`, or both options. Empty means
NONE/READY identity correction, not an absent calibration subsystem or raw-data bypass. The exact
official 0.0.9 pre-release `Existing` combinations migrate once by removing `Existing`, updating
the 0.0.10 Core/platform locks, and requiring regeneration in a new output directory; unknown
third-party selections are not silently upgraded.

No Python schema change is required when a real future plugin declares a new Strategy slot such as `guidance` or a Mode slot with new options.

Each Protocol value may instead be disabled explicitly without omitting its category:

```json
"protocols": {
  "telemetry": null,
  "maintenance": null,
  "logging": null
}
```

`null` is part of canonical serialization and the generation fingerprint. It contributes no
component ID, component/protocol lock, provenance entry, Profile, transport binding, or Source
Graph contribution. Reconciliation clears a non-null telemetry/logging selection when its sole
compatible transport disappears and does not restore it when the Device returns.

## Custom hardware state

`hardware.mode = "custom"` requires the trusted provider ID, imported MCU, source digest/snapshot ID, risk acknowledgement, resources, hardware inventory, compatibility facts, source policy, and build paths below the dedicated hardware prefix. The inventory is a data snapshot of the imported `.ioc` plus controlled generated source: MCU/name/family/package/core, CubeMX/Firmware Package, pins, peripherals, DMA, NVIC, clocks, generated TIM HAL timebase, FatFs App/Target/symbol facts, and parser issues. With `plugin_payload_authoritative`, only imported controlled `Core/Src` C, `Core/Inc`, and manifest-selected CubeMX glue are build contributions; imported HAL/CMSIS Drivers, startup and linker remain in the auditable snapshot but are not source-graph inputs. The generated project receives the vendor snapshot as `HardwareGenerated/STM32CubeMX/`; the original external CubeMX directory is not referenced by the build.

After export/install as a Board plugin, a second project returns to `hardware.mode = "board_plugin"`; the Board payload supplies the same dedicated tree without another live import.

## Logging stream state and metadata

Each `logging_streams` entry remains project-owned configuration: `record`, `enabled`, `policy`,
`decimation`, and integer microsecond `period_us`. Display units are never serialized. For EVENT,
ONE_SHOT, EVERY, and DECIMATION policies, `period_us=0` means the period field is unused and must
not be interpreted as an infinitely fast stream. Only DECIMATION gives `decimation` user-editable
meaning; other policies preserve their compatible stored default without exposing an editor.
The GUI names this DECIMATION value the **extraction factor** and presents it as “record once per
N related data updates”; the persisted field remains `decimation` for compatibility.

The generated `log_decoder_profile` reference is populated only while rendering a saved,
logging-enabled project. The current firmware-owned package/container IDs are
`silverstar.ssdecoder.package-schema/1.1` and `silverstar.sslog.container/0.0`. Schema 1.1 permits
nullable telemetry and maintenance locks but requires a real logging lock. `generation_profile_sha256` is SHA-256 over UTF-8 package
schema ID, one LF, UTF-8 container ID, one LF, the raw 32-byte record-catalog digest, and the raw
32-byte project-semantics digest in that exact order. `package_sha256` identifies the complete
deterministic ZIP. Export rebuilds those bytes and refuses a missing, stale, or mismatched project.

Cadence text and optional producer requirements are Protocol metadata extensions, not duplicated
project fields. Older metadata without either extension remains loadable: PERIODIC maps to periodic,
DECIMATION to related-source cadence, EVERY to related measurement, EVENT to related event, and
ONE_SHOT to one time. Producer omission retains old availability behavior.

The synchronized reference metadata uses producer identities rather than adding project-format
fields: STATS requires `silverstar.core.device_task` and TELEMETRY_DIAG requires
`silverstar.core.telemetry_task`. Their project stream values remain ordinary `PERIODIC` entries
with `period_us` 1000000 and 200000, so wire/container/project compatibility is unchanged.

Legacy pre-release descriptors may still contain the `maintenance0` UART Device instance. Loading
retains and normalizes that internal Transport and its resource owner while maintenance remains
enabled. Reconciliation removes an endpoint declared with
`auto_managed_protocol_category = maintenance` when the slot is `null`, and re-creates a stable
`maintenance0` endpoint when the user explicitly re-enables a compatible Profile.

## Planning behavior

FCCG resolves intended files and `.fccg/ownership.json` into operations: `ADD`, `MODIFY`, `UNCHANGED`, `PRESERVE`, `DEACTIVATE`, `REPLACE_TREE`, or `CONFLICT`. Validation errors and conflicts prevent Save from applying the plan. Dangerous operations require explicit confirmation. A missing or edited project-owned component file is never silently restored.

The JSON is machine state. `SilverStar_Configuration.md` is its generated human-readable review record, including MCU, Devices, Board/hardware source, mappings, Strategies, Modes, active/inactive retained Mode parameters, protocol profiles, OS, environment/toolchain, and provenance.

## Protocol, local-tool, and quality state

`protocols` stores one nullable, independently locked plugin/Profile slot for each of `telemetry`,
`maintenance`, and `logging`; a plugin is allowed to own only its declared strict category. Installed manifests—not
a Python record table—supply full profile sources, binding, transport requirements, decoder data,
docs, and tests. Duplicate `(category, profile)` providers are rejected rather than selected by scan
order. A non-null selection resolves exactly one transport from manifest capability/kind/mode/MTU/
ordering/reliability/directionality contracts. Zero providers forces the slot to `null`; multiple
providers remain an explicit ambiguity. Selecting a Device does not enable a Protocol, and restoring
a transport does not auto-select the first installed Profile. Active bindings are emitted into the
generated decoder/configuration review.

`build.tool_paths` contains project-local host preferences and never enters the normalized
generation fingerprint. Likewise `.fccg/quality-results.json` stores task/result/timestamp/
duration/summary outside `SilverStar.ssproject`; updating it cannot make generated code stale.
Reference provenance and GUI preferences are display/diagnostic state, not firmware semantics.
