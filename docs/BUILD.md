# Build and development-environment integration

## One resolved graph

The selected components and project model resolve to explicit C/ASM sources, includes, defines, forced includes, exclusions, linker script, CPU/FPU flags, specs, libraries, and toolchain prefix. No renderer scans the project with wildcards.

The current reference graph has 134 C sources and one startup assembly source. It includes only the selected Alignment/INS/Estimator/Landing strategies, the FreeRTOS static kernel subset/CM4F port, and four FCCG-generated C files, including the static capability-route table. `Core/Src/sysmem.c` is explicitly excluded; the target memory forced include and CCMRAM/DMA linker contract remain active.

## Make

The root `Makefile` consumes `Generated/project_sources.mk`, preserves hierarchy in object paths, uses Debug `-Og -g3` / Release `-O2 -g`, section GC and nano specs, and emits ELF/HEX/BIN/MAP. Firmware compilation does not invoke Python or FCCG.

### Debug

Debug uses `-Og -g3 -gdwarf-2` for development, source-level diagnosis, and predictable stepping. It still enables the full first-party warning policy, Power-of-Ten gate, SilverStar runtime assertions, static allocation policy, linker map, and memory/artifact checks.

### Release

Release uses `-O2 -g` while retaining the same MCU/FPU ABI, section GC, nano specs, linker map, ELF/HEX/BIN outputs, static allocation, Power-of-Ten gate, and memory/artifact checks. Release does **not** define `NDEBUG` and does not disable SilverStar runtime assertions.

Warnings are classified:

- SilverStar first-party and Generated glue: strict `-Werror` policy;
- third-party/vendor/HAL and `HardwareGenerated`: controlled warning policy;
- static analysis: GCC `-fanalyzer` in a separate build tree.

Targets include `all`, `clean`, `host-tests`, `architecture-check`, `power10-check`, `static-analysis`, `artifact-check`, and `memory-report`. No flash target is generated because the current Board and Environment plugins do not jointly declare a validated flash capability.

## VS Code

`<ProjectName>.code-workspace` and project-local `.vscode/tasks.json`, `settings.json`, and `extensions.json` are generated. Tasks include explicit Debug/Release Build and Clean entries plus Host Tests, Architecture Check, Power of Ten Check, Static Analysis, and Artifact Check. They invoke the generated Make project and do not own another source list or modify global VS Code settings.

## EIDE native build

`.eide/eide.yml` is a real native graph with Debug and Release targets, non-empty `srcDirs`, explicit virtual source files, include/define lists, excludes, forced includes, linker, CPU/FPU/toolchain flags, libraries, and `build\EIDE\SilverStar_F407` output. It is rendered from the same `SourceGraph` object as Make.

`.eide/eide.yml` is FCCG-managed. If its previous generated hash no longer matches the file, Save marks replacement dangerous and asks the user to continue or cancel; no three-way merge is attempted.

## Tools and safety

The Build page detects Arm GNU GCC/binutils, GNU Make, and Host GCC. Advanced Browse choices are stored only in `build.tool_paths` inside the project. FCCG never changes PATH, registry, global IDE settings, or the global Python environment.

Build subprocesses receive argument arrays and an explicit project working directory that must resolve below the exact user-selected project root. The current GUI, Makefile, VS Code tasks, and EIDE metadata expose no upload action. A successful artifact check is not a hardware-flash or electrical-validation claim.

The Build page keeps only Build/Clean visible; Build always invokes `CONFIG=Debug`. Build Release, tool overrides, and Host/Architecture/Power-of-Ten/Static/Artifact checks live in a full-width, visibility-only collapsed section with a responsive button grid. Invoking Release does not change or dirty `SilverStar.ssproject`.

Before a Debug or Release Arm build, `BuildRunner` invokes Make with `-n` and counts structured `FCCG_PROGRESS` markers for pending compile, link, size, HEX, and BIN steps. The actual Make run emits the same dependency-free echo markers. Output is delivered to the GUI one line at a time; markers update a determinate progress bar and localized stage text while ordinary compiler output remains visible in the build log. Quality scripts that do not yet expose per-file markers report their known phase boundary rather than fabricating a compile count.

The default Environment plugin is VS Code + EIDE + Arm GNU Toolchain. The manifest architecture can later add trusted Keil/IAR/CMake/pure-Make renderers, but no unvalidated project format is fabricated now.
