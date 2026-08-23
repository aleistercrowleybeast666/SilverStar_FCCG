# Build and development-environment integration

## One resolved graph

The selected components and project model resolve to explicit C/ASM sources, includes, defines, forced includes, exclusions, linker script, CPU/FPU flags, specs, libraries, and toolchain prefix. No renderer scans the project with wildcards.

The current reference graph has 133 C sources and one startup assembly source. It includes only the selected Alignment/INS/Estimator/Landing strategies, the FreeRTOS static kernel subset/CM4F port, and three FCCG-generated C files. `Core/Src/sysmem.c` is explicitly excluded; the target memory forced include and CCMRAM/DMA linker contract remain active.

## Make

The root `Makefile` consumes `Generated/project_sources.mk`, preserves hierarchy in object paths, uses Debug `-Og` / Release `-O2`, section GC and nano specs, and emits ELF/HEX/BIN/MAP. Firmware compilation does not invoke Python or FCCG.

Warnings are classified:

- SilverStar first-party and Generated glue: strict `-Werror` policy;
- third-party/vendor/HAL and `HardwareGenerated`: controlled warning policy;
- static analysis: GCC `-fanalyzer` in a separate build tree.

Targets include `all`, `clean`, `host-tests`, `architecture-check`, `power10-check`, `static-analysis`, `artifact-check`, `memory-report`, and guarded `flash`.

## VS Code

`<ProjectName>.code-workspace` and project-local `.vscode/tasks.json`, `settings.json`, and `extensions.json` are generated. Tasks include Build, Clean, Flash, Host Tests, Architecture Check, Power of Ten Check, Static Analysis, and Artifact Check. They invoke the generated Make project and do not own another source list or modify global VS Code settings.

## EIDE native build

`.eide/eide.yml` is a real native graph with non-empty `srcDirs`, explicit virtual source files, include/define lists, excludes, forced includes, linker, CPU/FPU/toolchain flags, libraries, and `build\EIDE\SilverStar_F407` output. It is rendered from the same `SourceGraph` object as Make.

`.eide/eide.yml` is FCCG-managed. If its previous generated hash no longer matches the file, Apply marks replacement dangerous and asks the user to continue or cancel; no three-way merge is attempted.

## Tools and safety

The Build page detects Arm GNU GCC/binutils, GNU Make, Host GCC, OpenOCD, and optional static-analysis tools. Advanced Browse choices are stored only in `build.tool_paths` inside the project. FCCG never changes PATH, registry, global IDE settings, or the global Python environment.

Build subprocesses receive argument arrays and an explicit project working directory. Flash is exposed only when configured and always requires confirmation. A successful artifact check is not a hardware-flash or electrical-validation claim.

The default Environment plugin is VS Code + EIDE + Arm GNU Toolchain. The manifest architecture can later add trusted Keil/IAR/CMake/pure-Make renderers, but no unvalidated project format is fabricated now.
