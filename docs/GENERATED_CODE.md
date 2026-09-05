# Generated code and imported hardware

FCCG intentionally generates a small surface:

```text
Generated/
├── Inc/project_capability_routes.h
├── Inc/project_device_instances.h
├── Inc/project_flight_config.h
├── Inc/project_log_config.h
├── Inc/project_log_decoder_profile.h
├── Inc/project_resources.h
├── Inc/project_storage_binding.h
├── Src/platform_resources.c
├── Src/project_capability_routes.c
├── Src/project_device_instances.c
├── Src/project_log_config.c
├── Src/project_log_decoder_profile.c
├── Src/project_metadata.c
├── module.mk
├── project_semantics.json
└── project_sources.mk
```

- `project_resources.h` binds semantic Device/Board requirements to resolved typed Platform IDs. For SS0.5 this includes logical input-voltage, launch-ignition, and parachute-pyro Device requirements mapped to ADC, P_CONTROL1, and P_CONTROL2; it never presents those physical IDs as user Devices.
- `project_storage_binding.h` binds the selected storage Device to the unique CubeMX FatFs object, path, and disk-driver symbols after SDIO/DMA/IRQ/App/Target/version checks. A non-storage Board cannot satisfy the logging sink merely by containing a codec.
- `platform_resources.c` binds those logical IDs to Board or imported hardware handles/GPIO metadata using the matched MCU/Platform manifest's header/table/getter/struct contract. For a verified Board its array designators come only from fixed Board `c_id` values; CubeMX inventory order cannot renumber them. Custom CubeMX retains imported numeric indices. Python validates tokens but does not contain F4 pin values or MCU-specific table code.
- `project_capability_routes.*` is a static, heap-free table of capability/provider-instance/provider-plugin/consumer/purpose hashes. A sole provider is marked automatic; unresolved ambiguity prevents generation.
- `project_flight_config.h` emits selected software-Indicator enable symbols, stable telemetry/maintenance/logging 0/1 macros, the 8-byte logging compatibility tag, plus the deployment trigger mask and validated thresholds. Time values such as Delay are scaled from manifest/UI seconds to a bounded `uint32` millisecond constant.
- `project_log_config.*` contains only logging enable/policy/decimation/period selection.
- `project_metadata.c` contains static component descriptors and the authoritative generation fingerprint digest.
- `project_sources.mk` is the explicit Make source/include/define/forced-include graph.
- `module.mk` lists the generated C sources for compatibility/review; the flight configuration is a forced-include header consumed by owning firmware and mission logging.

Generated C is static, heap-free connection/configuration data. It does not implement sensor drivers, MCU backends, INS/KF math, flight decisions, protocol codecs, or serialization. Function/type names and header guards follow the embedded reference convention.

The 0.0.10 release identity is derived from the one FCCG platform-version authority and appears in
the saved project, generated semantics/component locks, Core macros (`SILV0010`, revision-10 profile
ID), firmware metadata, and log header. AIR M0, maintenance/log format 0.0, decoder/project-semantics
1.1, FreeRTOS 11.3.0, SS0.5, and STM32F407VET6 remain independent identities. The generated target
directory and Make/EIDE/VS Code profile come from the selected MCU/Platform manifest lock.

Calibration procedure selection generates a mask for OneFace/SixFace. An empty list emits mask zero;
startup then calls the existing `SYSTEM_CALIBRATION_MODE_NONE` path to establish READY identity
correction before corrected IMU is consumed. It does not remove the calibration component. With
logging enabled, `CALIBRATION_RESULT` remains Required and describes the active NONE or measured
correction snapshot without changing Record ID, 72-byte layout, SSLOG 0.0, or CRC behavior.

Component payloads outside `Generated/` are project-owned source. Normal Save preserves them even when their original plugin changes or a component becomes inactive.

The SDIO/FatFs storage and file-log implementations are emitted under `Devices/Storage/SdSdioFatFs/` and owned by `silverstar.device.storage.sd_sdio_fatfs`. Legacy format-9 projects may retain the former Board-path copies as inactive project-owned files; applying the current format adds the Device-owned paths without overwriting or deleting those legacy files, and the resolved Source Graph compiles only the new owner. CubeMX App/Target glue, the controlled MCU FatFs core, and the storage consumer remain distinct providers.

CubeMX timer HAL timebase facts are parsed from the generated `stm32*_hal_timebase_tim.c` and rendered through the selected Platform contract. The generated resource table uses the discovered handle/instance and does not assume TIM1. SysTick timebase, missing or ambiguous initialization, non-1 MHz counter/non-1 kHz tick, disabled IRQ, source mismatch, and PWM reuse of the timebase timer fail before generation.

Managed output is rendered and staged as one plan. `Generated/`, Make/Target data, EIDE/VS Code metadata, the conditional `.ssdecoder`, configuration review, readiness markers, and ownership records are updated together; `SilverStar.ssproject` is published last. Readiness treats a missing or changed managed file as Dirty and Save regenerates it without overwriting project-owned component source. When logging is disabled, the plan transactionally removes only previously managed decoder/golden outputs and preserves manual logs. EIDE is the shared-ownership exception: readiness and planning compare the normalized FCCG-owned build subtree, not the whole YAML byte stream, so EIDE UI/order/uploader rewrites remain clean while real source/include/linker/toolchain changes are named explicitly.

The generation fingerprint comes from normalized portable generation state, not the complete descriptor dictionary. Local compiler/Make/Host-GCC paths and provenance do not invalidate generated code. Metadata rendering deep-copies the input model before inserting provenance, and successful materialization reloads the exact descriptor written to disk as the live model.

Apply compares bytes before replacement. An unchanged managed file is not rewritten, so its modification time remains stable. Apply does not clean `build/`, remove Make `.d` dependency files, compile firmware, or run quality targets. Component payloads are copied only when first materialized and are never overwritten by a normal Apply. This preserves useful incremental compilation after opening the generated VS Code/EIDE project.

Raw-log availability is resolved before rendering from Protocol `recordable_capabilities` and Device `recordable_outputs`; it is not inferred from generated capability routes. BARO_NATIVE therefore stays available without an Estimator while BARO_MEASUREMENT does not. MAG_NATIVE is generic to any compatible selected recordable magnetic source, not a JY901B-only record. A Record schema/codec describes a wire format, not proof that the selected component graph emits it. Optional Protocol `producer_components` metadata can therefore require a real selected producer in addition to normal capability availability; older metadata without that field retains its prior behavior.

Repeated context-safe Devices add typed arrays to `Generated/Inc/project_resources.h` and
`Generated/Src/project_resources.c`. Their manifest declares the C struct/accessor/count contract,
so rendering stays model-independent. The table length is the selected instance count, the compile
time maximum remains four, accessors reject out-of-range indices, and static assertions tie table
sizes to generated counts. Capability facade cases pass the physical source-instance index into
the driver adapter. One plugin's C sources still appear only once in `project_sources.mk`.

`Generated/project_semantics.json` and the deterministic `.ssdecoder` package enumerate every
physical Device, capability endpoint, resource assignment, native source identity, initial
Canonical route, and ordered AIR transport candidate. Runtime changes do not rewrite generated
state; the existing SSLOG EVENT records old/new instance and reason. Package schema and project
semantics remain 1.1, and the EVENT, AIR M0, maintenance 0.0, and SSLOG 0.0 binary layouts are
unchanged.

For the verified reference composition, imported Device/Telemetry tasks call the shared diagnostic
log implementation. The Core manifest contributes `silverstar.core.device_task` and
`silverstar.core.telemetry_task`; SSLOG metadata requires those identities for STATS and
TELEMETRY_DIAG. Both streams remain ordinary generated PERIODIC selections at 1000000 us and
200000 us in the default composition. The telemetry producer identity is active only with the
telemetry Protocol, so TELEMETRY_DIAG becomes unavailable under T=0 while STATS remains produced.

Cadence is Protocol-owned display metadata. Its optional kinds are periodic, source-driven, per-measurement, event-driven, one-shot, and algorithm-output. The project descriptor continues to persist only policy, decimation, and canonical `period_us`; a non-periodic `period_us = 0` means that no fixed period applies and never means continuous zero-period output. Cadence labels and unit choices are GUI concerns and do not alter generated firmware state.

## Decoder profile

Logging-enabled generation also creates `<ProjectName>.ssdecoder` under package schema 1.1. The deterministic ZIP contains only
`manifest.json`, `record_catalog.json`, `project_semantics.json`, `checksums.sha256`, and
`README.md`; entry timestamps/modes are fixed and no Python, PowerShell, shell, DLL, EXE, hook, or
other executable entry is present. `record_catalog.json` carries the selected Flight Log container
and record schema, while `project_semantics.json` records physical Device instances/descriptors,
resolved capability routes and resource assignments, selected Algorithms/Strategies/Modes, three
nullable protocol slots (with a required logging lock) and active physical bindings, detected MCU plus
Platform/Board/CubeMX identity, record availability, and active logging streams.

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
It is disabled when logging is None. In that state no package, descriptor source, golden expectation,
or golden Host task exists, while standalone `Generated/project_semantics.json` is still generated.

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

The `.ioc` inside a Board or imported snapshot is the physical source of truth. FCCG's persisted `HardwareInventory` records MCU/package/core, pins/AF/GPIO/EXTI, UART/SPI/I²C/ADC/Timer/PWM/Classic-CAN/FDCAN, DMA, NVIC and useful clocks. `connections.json` stores only semantic alias-to-physical-resource bindings; it is not a duplicate pin/peripheral database. Inventory presence alone is insufficient: an assigned resource must also be supported by the matched Platform contract, and only then does Source Graph add its conditional backend/provider sources.

For a verified Board, semantic ownership is strict: `connections.json` selects the logical table ID,
while the snapshot only resolves the declared alias to actual handle/port/pin/channel symbols. Before
rendering, Platform Resource Closure Check verifies every selected chain through the generated table.
SS0.5 emits `RADIO_NSS/RST/BUSY/DIO1` at `PLATFORM_GPIO_0..3`, P_CONTROL1/2 at 4/5,
IMU_CAL_LED at 6, and GNSS_RST/TIMEPULSE at 7/8, including matching validity-table entries. The
generated `.fccg` metadata records a binding fingerprint so mapping, snapshot, manifest, or renderer
drift cannot remain Ready silently.

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
