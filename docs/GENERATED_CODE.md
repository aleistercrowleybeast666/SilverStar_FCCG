# Generated code and imported hardware

FCCG intentionally generates a small surface:

```text
Generated/
├── Inc/project_log_config.h
├── Inc/project_resources.h
├── Src/platform_resources.c
├── Src/project_log_config.c
├── Src/project_metadata.c
├── module.mk
└── project_sources.mk
```

- `project_resources.h` binds semantic Device/Board requirements to resolved typed Platform IDs.
- `platform_resources.c` binds those logical IDs to Board or imported hardware handles/GPIO metadata.
- `project_log_config.*` contains only logging enable/policy/decimation/period selection.
- `project_metadata.c` contains static component descriptors and a deterministic configuration digest.
- `project_sources.mk` is the explicit Make source/include/define/forced-include graph.
- `module.mk` lists the three generated C sources for compatibility/review.

Generated C is static, heap-free connection/configuration data. It does not implement sensor drivers, MCU backends, INS/KF math, flight decisions, protocol codecs, or serialization. Function/type names and header guards follow the embedded reference convention.

Component payloads outside `Generated/` are project-owned source. Normal Apply preserves them even when their original plugin changes or a component becomes inactive.

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

Ordinary Apply preserves this tree. Importing a different snapshot produces a dangerous `REPLACE_TREE` plan and requires explicit confirmation, including when the current tree was manually edited. The generated README warns that CubeMX regeneration may overwrite the tree and that clocks, DMA, interrupts, GPIO electrical levels, and power must be revalidated.
