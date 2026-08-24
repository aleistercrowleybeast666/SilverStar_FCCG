# SilverStar.ssproject format

`SilverStar.ssproject` is strict JSON with `format_version: 5`; the formal shape is `schemas/project.schema.json`. Formats 0 and 1 migrate through the Strategy/Mode and Hardware Inventory changes; format 2 string Device selections migrate to physical Device instances and instance-owned resource keys; legacy format 4 capability selections and build configuration are discarded because both are now derived actions rather than project state. All supported older files are saved as format 5.

## Sections

- `project`: name, firmware version, and embedded build target.
- `components`: exactly one Core, MCU, OS, and DevelopmentEnvironment; an optional Board while custom hardware is active; ordered `devices: [{instance_id, plugin}]`, base components/Protocol Bundles; and generic `strategies: {slot: component-id | null}`.
- `modes`: generic `{slot: [option, ...]}` selections. Slot rules and labels come from manifests.
- `hardware`: `unselected`, `board_plugin`, or `custom`, plus source kind/provider, immutable import snapshot/provenance, detected MCU/capabilities/resources, persisted `inventory`, trusted build contributions, and first-import risk acknowledgement. `unselected` is valid while editing but not for Save/Build.
- `resources`: `device-instance-id:requirement-name` (or non-Device component ID) to provided physical/logical resource ID.
- `capability_sources`: only user decisions needed to resolve an ambiguous required capability, mapping capability to the selected Device instance.
- `logging.streams`: the selected Protocol metadata order plus enable state, policy, decimation, and period. Record definitions and Required/Recommended/Optional levels do not live in the project file.
- `build`: target, Make/toolchain preferences, native EIDE mode, and project-local tool-path overrides. Debug/Release is an invocation choice and is not persisted. `flash_command` is currently an empty reserved field; it creates no GUI, Make, VS Code, or EIDE upload action without a future validated capability contract.
- `generated_glue`: the reviewed FCCG-owned glue set.
- `component_provenance` and `reference_provenance`: audit information only.

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

The selected components derive that the reference consumes JY901B acceleration, angular rate, and barometric altitude while external attitude and magnetic field remain unused. If a future BMP280 and JY901B both provide required `barometer.altitude`, the only additional persisted decision is `"barometer.altitude": "barometer0"`. Requirement purposes and lifecycle remain in Algorithm/Strategy manifests and implementations; no flight-phase policy is stored.

## Generic selection examples

```json
{
  "components": {
    "strategies": {
      "alignment": "silverstar.algorithm.alignment.gravity_known_yaw",
      "estimator": null,
      "ins": "silverstar.algorithm.ins.coning2_sculling2",
      "landing": "silverstar.flight_logic.landing.baro_imu_window"
    }
  },
  "modes": {
    "calibration": ["Existing", "OneFace", "SixFace"],
    "deployment": ["ApogeeVerticalVelocity", "Tilt", "Delay"]
  }
}
```

No Python schema change is required when a real future plugin declares a new Strategy slot such as `guidance` or a Mode slot with new options.

## Custom hardware state

`hardware.mode = "custom"` requires the trusted provider ID, imported MCU, source digest/snapshot ID, risk acknowledgement, resources, hardware inventory, and build paths below the dedicated hardware prefix. The inventory is a data snapshot of the imported `.ioc`: MCU/family/package/core, pins, peripherals, DMA, NVIC, clocks and parser issues. The generated project receives the vendor snapshot as `HardwareGenerated/STM32CubeMX/`; the original external CubeMX directory is not referenced by the build.

After export/install as a Board plugin, a second project returns to `hardware.mode = "board_plugin"`; the Board payload supplies the same dedicated tree without another live import.

## Planning behavior

FCCG resolves intended files and `.fccg/ownership.json` into operations: `ADD`, `MODIFY`, `UNCHANGED`, `PRESERVE`, `DEACTIVATE`, `REPLACE_TREE`, or `CONFLICT`. Validation errors and conflicts prevent Save from applying the plan. Dangerous operations require explicit confirmation. A missing or edited project-owned component file is never silently restored.

The JSON is machine state. `SilverStar_Configuration.md` is its generated human-readable review record, including MCU, Devices, Board/hardware source, mappings, Strategies, Modes, OS, environment/toolchain, and provenance.
