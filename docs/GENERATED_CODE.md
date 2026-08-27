# Generated code and imported hardware

FCCG intentionally generates a small surface:

```text
Generated/
├── Inc/project_capability_routes.h
├── Inc/project_flight_config.h
├── Inc/project_log_config.h
├── Inc/project_resources.h
├── Src/platform_resources.c
├── Src/project_capability_routes.c
├── Src/project_log_config.c
├── Src/project_metadata.c
├── module.mk
└── project_sources.mk
```

- `project_resources.h` binds semantic Device/Board requirements to resolved typed Platform IDs. For SS0.5 this includes logical input-voltage, launch-ignition, and parachute-pyro Device requirements mapped to ADC, P_CONTROL1, and P_CONTROL2; it never presents those physical IDs as user Devices.
- `platform_resources.c` binds those logical IDs to Board or imported hardware handles/GPIO metadata.
- `project_capability_routes.*` is a static, heap-free table of capability/provider-instance/provider-plugin/consumer/purpose hashes. A sole provider is marked automatic; unresolved ambiguity prevents generation.
- `project_flight_config.h` emits selected software-Indicator enable symbols plus the deployment trigger mask and validated thresholds. Time values such as Delay are scaled from manifest/UI seconds to a bounded `uint32` millisecond constant.
- `project_log_config.*` contains only logging enable/policy/decimation/period selection.
- `project_metadata.c` contains static component descriptors and the authoritative generation fingerprint digest.
- `project_sources.mk` is the explicit Make source/include/define/forced-include graph.
- `module.mk` lists the four generated C sources for compatibility/review; the flight configuration is a forced-include header consumed by owning firmware and mission logging.

Generated C is static, heap-free connection/configuration data. It does not implement sensor drivers, MCU backends, INS/KF math, flight decisions, protocol codecs, or serialization. Function/type names and header guards follow the embedded reference convention.

Component payloads outside `Generated/` are project-owned source. Normal Save preserves them even when their original plugin changes or a component becomes inactive.

Managed output is rendered and staged as one plan. `Generated/`, Make/Target data, EIDE/VS Code metadata, `.ssdecoder`, configuration review, readiness markers, and ownership records are updated together; `SilverStar.ssproject` is published last. Readiness treats a missing or changed managed file as Dirty and Save regenerates it without overwriting project-owned component source. EIDE is the shared-ownership exception: readiness and planning compare the normalized FCCG-owned build subtree, not the whole YAML byte stream, so EIDE UI/order/uploader rewrites remain clean while real source/include/linker/toolchain changes are named explicitly.

The generation fingerprint comes from normalized portable generation state, not the complete descriptor dictionary. Local compiler/Make/Host-GCC paths and provenance do not invalidate generated code. Metadata rendering deep-copies the input model before inserting provenance, and successful materialization reloads the exact descriptor written to disk as the live model.

Apply compares bytes before replacement. An unchanged managed file is not rewritten, so its modification time remains stable. Apply does not clean `build/`, remove Make `.d` dependency files, compile firmware, or run quality targets. Component payloads are copied only when first materialized and are never overwritten by a normal Apply. This preserves useful incremental compilation after opening the generated VS Code/EIDE project.

Raw-log availability is resolved before rendering from Protocol `recordable_capabilities` and Device `recordable_outputs`; it is not inferred from generated capability routes. BARO_NATIVE therefore stays available without an Estimator while BARO_MEASUREMENT does not. MAG_NATIVE is generic to any compatible selected recordable magnetic source, not a JY901B-only record. A Record schema/codec describes a wire format, not proof that the selected component graph emits it. Optional Protocol `producer_components` metadata can therefore require a real selected producer in addition to normal capability availability; older metadata without that field retains its prior behavior.

For the verified reference composition, imported Device/Telemetry tasks call the shared diagnostic
log implementation. The Core manifest contributes `silverstar.core.device_task` and
`silverstar.core.telemetry_task`; SSLOG metadata requires those identities for STATS and
TELEMETRY_DIAG. Both streams remain ordinary generated PERIODIC selections at 1000000 us and
200000 us, without changing the Flight Log Format 0.0 container or AIR M0 wire value.

Cadence is Protocol-owned display metadata. Its optional kinds are periodic, source-driven, per-measurement, event-driven, one-shot, and algorithm-output. The project descriptor continues to persist only policy, decimation, and canonical `period_us`; a non-periodic `period_us = 0` means that no fixed period applies and never means continuous zero-period output. Cadence labels and unit choices are GUI concerns and do not alter generated firmware state.

## Decoder profile

Generation also creates `<ProjectName>.ssdecoder`. The deterministic ZIP contains only
`manifest.json`, `record_catalog.json`, `project_semantics.json`, `checksums.sha256`, and
`README.md`; entry timestamps/modes are fixed and no Python, PowerShell, shell, DLL, EXE, hook, or
other executable entry is present. `record_catalog.json` carries the selected Flight Log container
and record schema, while `project_semantics.json` records physical Device instances/descriptors,
resolved capability routes, selected Strategies/Modes, protocol profiles, record availability, and
active logging streams.

Canonical JSON uses UTF-8 without BOM, sorted object keys, compact separators, stable arrays, and
one LF terminator. SHA-256 identifies the catalog and semantics; a generation-profile hash is
`SHA-256(package_schema_id + container_plugin_id + record_catalog_hash + project_semantics_hash)`.
The complete ZIP has a separate
package hash stored only in `SilverStar.ssproject`. Generated
`project_log_decoder_profile.h/.c` embed the first 16 bytes of the catalog, semantics, and
generation-profile hashes so firmware and decoder can reject a mismatched configuration.
The implementation source is explicitly present in `Generated/project_sources.mk`; Make and native
EIDE therefore compile the same descriptor implementation, while VS Code calls that Make graph.
The manifest creation time uses the reference commit timestamp, keeping identical project inputs
byte-for-byte deterministic across repeated imports of the same firmware commit.

Host Tests build `Tests/Host/generate_golden_sample.c` with the real `sslog_protocol.c`,
`sslog_records.c`, and generated descriptor source. The utility serializes and deserializes every
Golden record before publishing `Logs/Golden/<ProjectName>_golden.sslog`; Python does not duplicate
the wire layout. `Logs/Golden/expected.json` records the hashes, records, physical endpoints, and
canonical-channel expectations used by downstream validation.

The GUI action named **Export Log Decoder Profile** rebuilds this same canonical package, checks the
saved reference, generated package, and readiness state, then atomically writes the selected file.
It does not generate a parser, executable plugin, `.ssdecoder` variant, or version-dispatch layer,
and it does not make the project Dirty.

## HardwareGenerated

Custom vendor output is not FCCG glue:

```text
HardwareGenerated/
└── STM32CubeMX/
    ├── <project>.ioc
    ├── Core/
    ├── Drivers/
    ├── startup_*.s
    ├── *.ld
    └── README.md
```

The snapshot is copied, never referenced in place. It is classified as a controlled vendor/tool-generated Power-of-Ten deviation. SilverStar-written adapters, services, Devices, Algorithms, and generated glue remain strict.

The `.ioc` inside a Board or imported snapshot is the physical source of truth. FCCG's persisted `HardwareInventory` records MCU/package/core, pins/AF/GPIO/EXTI, UART/SPI/I2C/ADC/Timer/PWM/CAN, DMA, NVIC and useful clocks. `connections.json` stores only semantic alias-to-physical-resource bindings; it is not a duplicate pin/peripheral database.

Ordinary Save preserves this tree. Importing a different snapshot produces a dangerous `REPLACE_TREE` plan and requires explicit confirmation, including when the current tree was manually edited. The generated README warns that CubeMX regeneration may overwrite the tree and that clocks, DMA, interrupts, GPIO electrical levels, and power must be revalidated.

## Build artifacts and review packages

Generated firmware and analysis outputs are intentionally outside the managed source surface under
`build/FCCG/`; Host executables use `build/FCCG/Host/Tests`. Managed-file ownership never includes
objects, dependencies, maps, listings, or tool results, so incremental builds do not make the
project Dirty. Listing is disabled by default and enabled only through `LISTING=1`.

Source-package export is a separate deterministic ZIP operation. It preserves FCCG Python, formal
docs, schemas, direct unit-test sources, fixtures, plugin manifests/payloads, and embedded
`Tests/Host` sources. It excludes `.git`, installed-plugin state, generated projects, reference
copies, acceptance/pytest/cache trees, `main.zip`, and `.o/.d/.lst/.elf/.bin/.hex/.map/.exe/.pyc`.
Repository clean-all targets those excluded workspace artifacts with validated absolute paths and
never treats the workspace root or a reference repository as a deletion target.
