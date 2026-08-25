# Build and development-environment integration

## One resolved graph

The selected components and project model resolve to explicit C/ASM sources, includes, defines, forced includes, exclusions, linker script, CPU/FPU flags, specs, libraries, and toolchain prefix. No renderer scans the project with wildcards.

The current reference graph has 134 C sources and one startup assembly source. It includes only the selected Alignment/INS/Estimator/Landing strategies, the FreeRTOS static kernel subset/CM4F port, and four FCCG-generated C files. `Core/Src/sysmem.c` is excluded; both target memory and generated flight-configuration headers are forced includes, keeping deployment parameters identical across Make/EIDE.

## Make

The root `Makefile` consumes `Generated/project_sources.mk`, preserves hierarchy in object paths, defaults to Release `-O2 -g`, retains Debug `-Og -g3`, uses section GC and nano specs, and emits ELF/HEX/BIN/MAP. Firmware compilation does not invoke Python or FCCG.

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

`<ProjectName>.code-workspace` and project-local `.vscode/tasks.json`, `settings.json`, and `extensions.json` are generated. The Release task is the default `Ctrl+Shift+B` task; explicit Debug/Release Build and Clean entries plus Host Tests, Architecture Check, Power of Ten Check, Static Analysis, and Artifact Check remain available. They invoke the generated Make project and do not own another source list or modify global VS Code settings.

The GUI prefers a discovered or known-installation `Code.exe` and invokes it with `--new-window` plus the absolute workspace path. A `code.cmd` discovery is also used to locate its sibling GUI executable before the batch launcher is attempted. The OS file association remains the final fallback. A process that fails immediately is not reported as opened; localized failure details include the absolute path and the exact launcher, exit-code, operating-system, or association reason.

## EIDE native build

The Environment plugin stores verbatim copies of the read-only firmware's `.eide/eide.yml`, `.eide/files.options.yml`, root workspace, and VS Code task template. `.vscode/settings.json` and `extensions.json` were not standalone files in that reference, so FCCG derives them from the reference workspace and records that fact in the template inventory.

The rendered `.eide/eide.yml` keeps the reference schema/target/upload structure while replacing the resolved project graph: Release first/default and Debug retained, non-empty `srcDirs`, explicit virtual source files, include/define lists, excludes, forced includes, linker, CPU/FPU/toolchain flags, libraries, and `build\EIDE\SilverStar_F407` output. Because no CMSIS Pack is bound, both `deviceName` and `packDir` are `null`. The retained template selects OpenOCD rather than J-Link, but FCCG does not expose a flash operation or claim that OpenOCD, J-Link, ST-Link, or hardware programming was validated.

`.eide/eide.yml` is FCCG-managed. If its previous generated hash no longer matches the file, Save marks replacement dangerous and asks the user to continue or cancel; no three-way merge is attempted.

## Tools and safety

The normal page displays only Arm GNU GCC and GNU Make. Selecting the compiler derives `arm-none-eabi-objcopy` and `arm-none-eabi-size` from the same `bin` directory. Host GCC appears only under advanced quality checks, and static analysis reuses Arm GCC rather than presenting a second analyzer compiler. Browse choices are stored only in `build.tool_paths` inside the project. FCCG never changes PATH, registry, global IDE settings, or the global Python environment.

Build subprocesses receive argument arrays and an explicit project working directory that must resolve below the exact user-selected project root. The current GUI, Makefile, VS Code tasks, and EIDE metadata expose no upload action. A successful artifact check is not a hardware-flash or electrical-validation claim.

The **Code Generation & Build** workflow is Generate/Apply → Open VS Code Workspace/Project Folder → build in VS Code/EIDE. FCCG has no separate Build Release button. Advanced **Open Firmware Output** is gated by a real ELF/HEX/BIN/MAP artifact. **Validation Build** invokes Make with `CONFIG=Release`; Clean and quality checks remain explicit advanced actions. Generate/Apply never runs them.

Before an advanced validation build, `BuildRunner` invokes Make with `-n` and counts structured `FCCG_PROGRESS` markers for pending compile, link, size, HEX, and BIN steps. Output is delivered to the GUI one line at a time. Reapplying an unchanged FCCG model does not rewrite equal managed files, remove `.d` files, or clean `build/`, so normal Make/EIDE incremental compilation remains effective.

`power10-check` executes the project script and fails nonzero on violations; it is an automatic project compliance gate, not formal proof, NASA certification, or third-party safety certification. `static-analysis` performs a separate-output Arm GCC build with the real path-sensitive `-fanalyzer` and warnings-as-errors over first-party sources. Neither check is run automatically during generation.

The default Environment plugin is VS Code + EIDE + Arm GNU Toolchain. The manifest architecture can later add trusted Keil/IAR/CMake/pure-Make renderers, but no unvalidated project format is fabricated now.
