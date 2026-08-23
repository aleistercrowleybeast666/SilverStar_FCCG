# SilverStar_FCCG validation report

Validation date: 2026-08-23 (Asia/Shanghai)

## Result

The current FCCG upgrade is implemented and validated for the real SilverStar F407 reference combination. The six-page device-first GUI, format-1 generic model, 23 declarative builtins, Board/resource model, trusted STM32CubeMX import, custom Board export/reuse, thin generator, one Make/EIDE source graph, VS Code environment, staged ownership rules, and build front end are connected through `FccgService`.

No hardware was flashed and no electrical validation is claimed.

## Reference and provenance

- Read-only firmware: `C:\Users\chdxm\Desktop\stm32-1\Flight_Controller0.5`
- Commit: `b8c90e997c3113dd23074302682c5560dae18926`
- Branch: `codex/refactor-silverstar-0.0.9-platform`
- Working tree at final check: clean
- Snapshot digest: `67e89c36cf11bbe3538469a1461c48a87967691ffd556995c8b5fc6c4b1c4d54`
- Builtin catalog: 23 strict declarative packages
- Formal generated project: `tests/generated_projects/SilverStar_F407_Reference_Generated/`

The import script read and staged data only; the reference was not modified, built, formatted, committed, reset, cleaned, or otherwise written. The copied architecture/host-check scripts contain reviewed FCCG compatibility adaptations: `Generated/project_sources.mk` is allowed, the legacy Make-time Estimator override is skipped when the fixed FCCG graph exists, and host tests for absent unselected strategy payloads are explicitly skipped.

The reference repository's `main` remains at `9ca21c7`; the reference branch is a fast-forward descendant by three commits (`b1c13e2`, `9c7c01c`, `b8c90e9`). FCCG's mandatory read-only reference boundary prevented changing that external branch.

## FCCG automated verification

| Verification | Actual result |
|---|---|
| Python compile | `python -m compileall -q src tools` passed |
| FCCG regression suite | 32 passed, 0 failed |
| GUI | six pages, one-step wizard, zh_CN/en_US, Light/Dark, background progress passed |
| Plugin security | traversal/symlink/special/duplicate/dependency/capability/collision/managed-path cases passed |
| Project/model | strict load/save/migration, dependency/resource/log validation passed |
| Estimator=None | KF6 absent from resolved graph, Make, and EIDE; None defines present |
| Environment | workspace + `.vscode/` + native `.eide/eide.yml` + Make generated from one graph |
| Board variants | same F407 MCU/Platform reused; A maps USART1/2, B maps USART3/6; only mapping glue differs |
| Custom STM32 | import → validate → auto-map → generate → isolated HardwareGenerated passed |
| RTOS conflict | CubeMX FreeRTOS/CMSIS-RTOS2 fixture rejected |
| Board reuse | custom import → export `.ssplugin` → secure install → second project passed |

All pytest temporary/generated outputs are below `tests/`. The custom-hardware tests use a minimal mock CubeMX fixture, not the user's real CubeMX project.

## Formal generated firmware verification

The formal acceptance project resolves 133 C sources, one startup ASM source, 43 include directories, the selected strategies/modes, target forced memory include, explicit `Core/Src/sysmem.c` exclusion, and the reference linker/CPU/FPU/library contract.

| Verification | Actual result |
|---|---|
| Architecture check | 186 checks, 0 failures |
| Power of Ten | 5,252 checks; 85 first-party C files; 1,939 functions |
| Host tests | 50 executables; 8,221 checks; 0 failures |
| Compile contracts | 4 expected successes and 13 expected failures passed |
| Debug Arm build | passed; text 253,960, data 1,160, bss 114,152 bytes |
| Release Arm build | passed; text 241,416, data 1,160, bss 114,144 bytes |
| GCC static analysis | `-fanalyzer` build passed |
| Debug artifact | ELF 2,512,308 bytes; BIN/FLASH 255,120 bytes; heap symbols 0 |
| Release artifact | ELF 364,212 bytes; BIN/FLASH 242,576 bytes; heap symbols 0 |
| Debug memory | main SRAM 72,440 / 131,072; CCMRAM 42,872 / 65,536 bytes |
| Release memory | main SRAM 72,432 / 131,072; CCMRAM 42,872 / 65,536 bytes |

Detected tools used: Python 3.14.0, Arm GNU GCC 14.3.1, GNU Make 4.4.1, and MSYS2 Host GCC 16.1.0.

No callable EIDE CLI builder was found, so EIDE validation is limited to strict YAML parsing/source-graph equivalence and the firmware architecture check. An EIDE-native compile is not claimed.

## GUI and behavior

- Navigation is exactly Project, Devices, Board & Hardware, Flight Configuration, Build, Plugins.
- Device requirements are manifest-driven; Board mapping follows Device selection and auto-assigns first.
- Board manifests support provisions, semantic roles, defaults, candidates, fixed/reserved resources, and conflicts.
- Custom hardware is offered only for a compatible provider. First import carries an explicit unverified warning.
- Current Strategies are Alignment, INS, Estimator, Landing. Current Modes are Calibration and Deployment.
- Normal changes apply without mandatory Preview. Only dangerous plans show the diff/confirmation path.
- Component payloads are preserved; managed glue/editor data is replaceable; HardwareGenerated replacement is special and dangerous.
- User-visible page/action/status text is catalog-backed; key Chinese page coverage passed.

## Safety observations

All FCCG development/test writes remained below `D:\python_software\SilverStar_FCCG`. No PATH, registry, global IDE setting, global Python environment, external reference file, external GUI file, hardware, or unrelated repository was changed.

The obsolete formal acceptance directory was a generated output without ownership metadata. Its exact path was verified below `tests/generated_projects/`, removed, and completely regenerated; no user-authored source was removed.

## Remaining limitations

- Only STM32F407VET6/SilverStar 0.5 has complete firmware-build validation.
- Only STM32 has a manual HardwareConfigurationProvider.
- Custom/manual Boards remain explicitly unverified until their real hardware is tested.
- No Guidance, Control, Control Allocation, or actuator implementation exists.
- No alternate MCU, Keil/IAR/CMake renderer, EIDE CLI compile, hardware flash, or electrical test is claimed.
