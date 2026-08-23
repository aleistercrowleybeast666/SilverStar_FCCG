# SilverStar.ssproject format

`SilverStar.ssproject` is strict JSON with `format_version: 1`; the formal shape is `schemas/project.schema.json`. Format 0 projects are migrated in memory to the generic Strategy/Mode model and are saved as format 1.

## Sections

- `project`: name, firmware version, and embedded build target.
- `components`: exactly one Core, MCU, OS, and DevelopmentEnvironment; an optional Board while custom hardware is active; ordered Devices/base components/Protocol Bundles; and generic `strategies: {slot: component-id | null}`.
- `modes`: generic `{slot: [option, ...]}` selections. Slot rules and labels come from manifests.
- `hardware`: `board_plugin` or `custom`, source kind/provider, immutable import snapshot/provenance, detected MCU/capabilities/resources, trusted build contributions, and first-import risk acknowledgement.
- `resources`: `component-id:requirement-name` to provided physical/logical resource ID.
- `logging.streams`: official record, enable state, policy, decimation, and period.
- `build`: target/configuration, Make/toolchain/flash preferences, native EIDE mode, and project-local tool-path overrides.
- `generated_glue`: the reviewed FCCG-owned glue set.
- `component_provenance` and `reference_provenance`: audit information only.

Unknown/missing fields, wrong types, duplicate selections/records, invalid component IDs, unsafe target/path tokens, unsupported policies/configurations, invalid numeric ranges, malformed custom snapshot IDs, hardware paths outside `HardwareGenerated/STM32CubeMX/`, or a changed SSLOG record order are rejected.

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
    "calibration": ["Existing"],
    "deployment": ["ApogeeVerticalVelocity", "Delay"]
  }
}
```

No Python schema change is required when a real future plugin declares a new Strategy slot such as `guidance` or a Mode slot with new options.

## Custom hardware state

`hardware.mode = "custom"` requires the trusted provider ID, imported MCU, source digest/snapshot ID, risk acknowledgement, resources, and build paths below the dedicated hardware prefix. The generated project receives the snapshot as `HardwareGenerated/STM32CubeMX/`. The original external CubeMX directory is not referenced by the build.

After export/install as a Board plugin, a second project returns to `hardware.mode = "board_plugin"`; the Board payload supplies the same dedicated tree without another live import.

## Planning behavior

FCCG resolves intended files and `.fccg/ownership.json` into operations: `ADD`, `MODIFY`, `UNCHANGED`, `PRESERVE`, `DEACTIVATE`, `REPLACE_TREE`, or `CONFLICT`. Validation errors and conflicts prevent Apply. Dangerous operations require explicit confirmation. A missing or edited project-owned component file is never silently restored.

The JSON is machine state. `SilverStar_Configuration.md` is its generated human-readable review record, including MCU, Devices, Board/hardware source, mappings, Strategies, Modes, OS, environment/toolchain, and provenance.
