# Build and development-environment integration

## Runtime safety contract — 2026-09-05

Every generated Arm GNU Make C compilation emits `-fstack-usage`; `.su` files stay beside objects
inside `build/FCCG/`. `make CONFIG=Release stack-report` and the Debug equivalent build normally,
then check every enabled static task against linked stack-symbol sizes. The report combines `.su`
frames with ELF calls/branches and conservative assembly-library stack decrements; unresolved
indirect calls, recursion and unbounded frames fail the gate. Verified SD_Driver callback edges
are explicit. Estimates include a 256-byte Cortex-M4F context reserve and require 256 bytes of
remaining task margin. `stack-budget.json` includes ELF SHA-256 and per-task paths. Root
`VALIDATION.md` records current Release/Debug results and RAM occupancy. Runtime HWM and nested
MSP/interrupt margins still require continuous SS0.5 testing. No EIDE-native compile or hardware
measurement is implied by a successful Make report.

## One resolved graph

The selected components and project model resolve to explicit C/ASM sources, includes, defines, forced includes, exclusions, linker script, CPU/FPU flags, specs, libraries, and toolchain prefix. No renderer scans the project with wildcards.

The matched MCU/Platform manifest also owns the build Target Profile. Reconciliation persists that
value as `build.target_profile`, and Make, EIDE, VS Code, static analysis, artifacts, and output paths
all consume the same lock. `SilverStar_F407` is the current verified plugin's declaration and an
example command value, not a Python default or a global MCU whitelist. A synthetic alternate-target
test validates generic routing only; production validation is still limited to F407/SS0.5.

The default reference graph has 138 C sources and one startup assembly source. The eight nullable-Protocol combinations resolve to 138, 128, 134, 124, 135, 125, 131, and 121 C sources for T1M1L1 through T0M0L0 respectively. Each graph contains only the selected Alignment/INS/Estimator/Landing strategies, active protocol tasks/services/codecs, the FreeRTOS static kernel subset/CM4F port, the bounded source selector, and applicable generated C files. A physical SX1281 or SD/TF Device may remain selected while its Protocol sources are absent. Repeated instances reuse the same component sources and add only generated descriptors/resources plus statically bounded selected-instance contexts. `Core/Src/sysmem.c` is excluded; both target memory and generated flight-configuration headers are forced includes, keeping deployment parameters identical across Make/EIDE.

Generated Protocol macros gate finite first-party call sites and static allocation. A disabled
TelemetryTask, SerialTask, or LoggerTask has no function, stack, or `StaticTask_t` symbol in the
linked ELF, while the task-report enum/index remains stable with allocation zero and no valid bit.
AIR M0 uses the unchanged `AIR-NCRC` logging tag; T=0/L=1 uses eight zero bytes.

Platform resource contributions are also resolved here. The MCU/Platform manifest declares a base graph, strict backend maturity, exact CubeMX/Firmware Package compatibility, one HAL/CMSIS source policy, and declarative module/provider sources. CubeMX init and FatFs App/Target providers are separate from the storage consumer wrapper. Under the current F407 `plugin_payload_authoritative` policy, HAL/CMSIS/startup/linker, controlled FatFs core, and optional backend support come from the MCU plugin exactly once; a custom CubeMX snapshot contributes only controlled `Core/Src` C and `Core/Inc`, never its `Drivers/`, CMSIS, startup or linker. A supported I²C/PWM backend enters the graph only when a selected Device has an actual matching assignment. Classic CAN remains `reserved` and blocks a consumer. Default SS0.5 has no such consumers, so no optional I²C/CAN/PWM Platform backend is emitted to Make, EIDE, or VS Code.

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

Targets include `all`, `clean`, `clean-all`, `host-tests`, `architecture-check`, `power10-check`, `static-analysis`, `artifact-check`, and `memory-report`. No flash target is generated because the current Board and Environment plugins do not jointly declare a validated flash capability.

## VS Code

`<ProjectName>.code-workspace` and project-local `.vscode/tasks.json`, `settings.json`, and `extensions.json` are generated. The Release task is the default `Ctrl+Shift+B` task; explicit Debug/Release Build, **Clean FCCG Build Outputs**, **Clean All Build Outputs**, Host Tests, Architecture Check, Power of Ten Check, Static Analysis, and Firmware Artifact Check remain available. They invoke the generated Make project and do not own another source list or modify global VS Code settings.

Before launch, the GUI requires an existing parseable workspace whose `folders[0].path` resolves to the project directory and whose `.eide/eide.yml` exists. Launcher order is `code.cmd`, `code.exe`, `code`, known installation paths, then the OS file association. CLI launchers always receive `--new-window` and the absolute workspace path. The process is observed briefly; an immediate nonzero exit is failure, while a still-running or zero-exit CLI means only that VS Code accepted the request. Technical command/cwd/return/stderr details are logged. The user sees one localized OK-only failure dialog with the workspace path for manual opening; a later EIDE extension/load error is classified separately from VS Code launch.

## EIDE native build

The Environment plugin stores verbatim copies of the read-only firmware's `.eide/eide.yml`, `.eide/files.options.yml`, root workspace, and VS Code task template. `.vscode/settings.json` and `extensions.json` were not standalone files in that reference, so FCCG derives them from the reference workspace and records that fact in the template inventory.

The rendered `.eide/eide.yml` keeps the reference schema/target/upload structure while replacing the resolved project graph: Release first/default and Debug retained, non-empty `srcDirs`, explicit virtual source files, include/define lists, excludes, forced includes, linker, CPU/FPU/toolchain flags, libraries, and `build\FCCG\SilverStar_F407\EIDE` output. Because no CMSIS Pack is bound, both `deviceName` and `packDir` are `null`. The retained template selects OpenOCD rather than J-Link, but FCCG does not expose a flash operation or claim that OpenOCD, J-Link, ST-Link, or hardware programming was validated.

`.eide/eide.yml` has shared ownership. FCCG parses YAML and fingerprints only the build-critical source graph, exclusions, includes, defines, CPU/FPU/ABI, linker/startup, selected toolchain configuration, Debug/Release flags, and output paths. EIDE-owned target selection, UI/uploader/debugger state, added compatibility fields, field order, and formatting are preserved and do not trigger a warning. Save reports a dangerous change only when an FCCG-owned field differs from its recorded normalized value, and the confirmation lists the exact field paths before FCCG merges its desired build fields into the current document.

The authoritative graph explicitly includes
`Generated/Src/project_log_decoder_profile.c`. Release, Debug, static analysis, native EIDE, and
VS Code therefore cannot disagree about the firmware-embedded decoder-profile identity.

## Tools and safety

The normal page has no duplicate tool-status pill or table; it shows only target and development environment. Advanced details separate **Firmware Build Environment** (Arm GNU Toolchain and GNU Make) from **Host Test Environment** (Host GCC). Arm GNU is the only supported firmware compiler. Selecting its compiler executable derives `arm-none-eabi-objcopy` and `arm-none-eabi-size` from the same `bin` directory. GNU Make is an orchestrator, not a compiler. Host GCC only builds/runs computer-side unit tests and cannot generate STM32 BIN/HEX. Browse choices stay in `build.tool_paths`; they do not enter the generation fingerprint or generated VS Code task command.

Missing Arm GNU disables FCCG firmware build and static analysis but never Generate Code. Missing Make disables Make-driven build/check actions. Missing Host GCC disables Host Tests only. A localized Installation Guide explains Arm GNU, GNU Make, and Host GCC, including the reference-validated Arm GNU 14.3.1 version, without claiming other versions are impossible. FCCG never downloads installers or changes PATH, registry, global IDE settings, or the global Python environment.

Build subprocesses receive argument arrays and an explicit project working directory that must resolve below the exact user-selected project root. The current GUI, Makefile, VS Code tasks, and EIDE metadata expose no upload action. A successful artifact check is not a hardware-flash or electrical-validation claim.

The **Code Generation & Build** workflow is Generate Code → Open VS Code Workspace/Project Folder → build in VS Code/EIDE. FCCG has no separate Build Release button. Advanced **Open Firmware Output** is gated by a real ELF/HEX/BIN/MAP artifact. **Build Firmware in FCCG** invokes Make with `CONFIG=Release`; Clean and quality checks remain explicit advanced actions. Generate Code never runs them.

Before an advanced validation build, `BuildRunner` invokes Make with `-n` and counts structured
compile/link/size/HEX/BIN markers. It also consumes the reusable
`FCCG_PROGRESS|<TASK>|PLAN|<total>` and paired BEGIN/DONE protocol emitted by Host tests and quality
scripts. BEGIN announces work but does not increase completion; DONE does. Architecture reports
source graph, directory boundaries, EIDE consistency, FreeRTOS, protocol, and summary. Power of Ten
reports each first-party C file plus function/build policy. Artifact checking reports ELF, MAP,
FLASH, main SRAM, CCMRAM, heap, BIN/HEX, and summary. Static analysis labels only first-party
`-fanalyzer` compilation as analysis and labels HAL/FatFs/FreeRTOS work as dependency compilation.
Output is delivered to the GUI one line at a time. Reapplying an unchanged FCCG model does not
rewrite equal managed files, remove `.d` files, or clean `build/`, so normal Make/EIDE incremental
compilation remains effective.

`power10-check` executes the project script and fails nonzero on violations; it is an automatic project compliance gate, not formal proof, NASA certification, or third-party safety certification. Its first-party conditional-compilation rule permits only the exact generated telemetry/maintenance/logging feature guards and continues to reject every unrelated conditional directive; preprocessor-only lines do not inflate executable function length. `static-analysis` performs a separate-output Arm GCC build with the real path-sensitive `-fanalyzer` and warnings-as-errors over first-party sources. Neither check is run automatically during generation.

The default Environment plugin is VS Code + EIDE + Arm GNU Toolchain. The manifest architecture can later add trusted Keil/IAR/CMake/pure-Make renderers, but no unvalidated project format is fabricated now.

## Output, feedback, and cleanup

Make writes firmware to `build/FCCG/<target>/<config>`, static analysis to
`build/FCCG/<target>/StaticAnalysis/<config>`, Host tests to `build/FCCG/Host/Tests`, and EIDE to
`build/FCCG/<target>/EIDE`. `LISTING ?= 0`; `.lst` files are emitted only with `LISTING=1`.
Normal `clean` removes the complete generated-project `build/FCCG` tree. Generated-project
`clean-all` removes `build/FCCG`, `.eide/build`, and `.eide/.cache`, while repository
`python tools/clean_all.py` validates the workspace boundary
before removing build, acceptance/reference-copy, pytest, temporary generation, and Python-cache
targets. Both generated-project cleanup targets use direct literal paths with no nested shell
variables, emit determinate PLAN/BEGIN/DONE progress, and never target source tests.

Only firmware Build shows a compile/link plan. Host, architecture, Power of Ten, static analysis,
and artifact checks use task-specific status. Static analysis performs an equivalent dry-run to
count stages and advances compile progress only on `COMPILE_DONE`; link/size/HEX/BIN occupy the
final progress bands. Success updates persistent green results without a modal dialog; failures
expand raw logs and show one localized summary with the complete Make output in dialog details.
Host GCC is validated with `--version` and `-dumpmachine`, passed as an explicit command-line
`HOST_CC` (configured absolute path or deterministic `gcc` fallback), and kept separate from Arm
GNU. On Windows the runner discards inherited `SHELL`/`MAKESHELL` values so a parent MSYS,
PowerShell, or Git Bash session cannot silently change `mingw32-make` recipe semantics. It also
places the resolved Host GCC directory first in the child `PATH` and clears inherited GCC search
overrides. The generated Host Test script repeats this isolation after resolving `HOST_CC`, so an
EIDE/Arm launcher cannot inject an incompatible MinGW runtime DLL into `cc1.exe` or the binutils.
The 2026-08-28 default-project validation completed 52 Host executables and 8,784 checks with this
isolation, including the C-codec Golden generator.

Host Test first collects runnable executables, expected-pass compile cases, and expected-rejection
cases, then emits actual totals. A configuration gate that rejects an illegal build is a neutral
success, not a red error. The normal log shows a localized summary; GCC diagnostics are retained in
the expandable detailed log and `build/FCCG/Host/Tests/host-tests-detail.log`. A missing expected
rejection, an unexpected non-gate compiler error, a failed expected-pass compile, or a nonzero test
executable is a real failure. Any failed/cancelled task retains its last completed progress rather
than being forced to 100%. Both cleanup actions use determinate progress rather than a cycling
indicator.
