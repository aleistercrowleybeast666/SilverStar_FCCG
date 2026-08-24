# Generated code and imported hardware

FCCG intentionally generates a small surface:

```text
Generated/
├── Inc/project_capability_routes.h
├── Inc/project_log_config.h
├── Inc/project_resources.h
├── Src/platform_resources.c
├── Src/project_capability_routes.c
├── Src/project_log_config.c
├── Src/project_metadata.c
├── module.mk
└── project_sources.mk
```

- `project_resources.h` binds semantic Device/Board requirements to resolved typed Platform IDs.
- `platform_resources.c` binds those logical IDs to Board or imported hardware handles/GPIO metadata.
- `project_capability_routes.*` is a static, heap-free table of capability/provider-instance/provider-plugin/consumer/purpose hashes. A sole provider is marked automatic; unresolved ambiguity prevents generation.
- `project_log_config.*` contains only logging enable/policy/decimation/period selection.
- `project_metadata.c` contains static component descriptors and a deterministic configuration digest.
- `project_sources.mk` is the explicit Make source/include/define/forced-include graph.
- `module.mk` lists the four generated C sources for compatibility/review.

Generated C is static, heap-free connection/configuration data. It does not implement sensor drivers, MCU backends, INS/KF math, flight decisions, protocol codecs, or serialization. Function/type names and header guards follow the embedded reference convention.

Component payloads outside `Generated/` are project-owned source. Normal Save preserves them even when their original plugin changes or a component becomes inactive.

Managed output is rendered and staged as one plan. `Generated/`, Make/Target data, EIDE/VS Code metadata, `.ssdecoder`, configuration review, readiness markers, and ownership hashes are updated together; `SilverStar.ssproject` is published last. Readiness treats a missing or hash-mismatched managed file as Dirty and Save regenerates it without overwriting project-owned component source.

## Decoder profile

Generation also creates `<ProjectName>.ssdecoder`. The deterministic ZIP contains only `manifest.json`, `project_profile.json`, `sslog_parser_metadata.json`, and `README.md`; timestamps are fixed and no Python, DLL, EXE, hook, or other executable entry is present. The profile records firmware/protocol identity, physical Device instances, resolved capability routes, selected Strategies/Modes, record availability and the active logging streams, while the copied Protocol metadata supplies field layouts, units and semantic names.

The intended design is a generic SilverStar_FLP SSLOG decoder engine plus this data profile. Unknown records remain safely skippable through record type/version/payload length. FLP import is future work; FCCG does not inspect or modify the FLP source tree.

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
