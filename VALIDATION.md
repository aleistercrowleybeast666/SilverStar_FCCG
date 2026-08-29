# Validation — 2026-08-30 internal software release candidate

This file records only the validation performed for the current source tree in this closeout.
The resulting status is **Software Release Candidate / Pre-Hardware-Validation**. It is not a
public release, tag, hardware-flash result, electrical qualification, or flight qualification.

## Environment

- Windows PowerShell 7.6.4
- Python 3.14.0
- PySide6 6.10.1
- Arm GNU Toolchain 14.3.Rel1, GCC 14.3.1
- GNU Make 4.4.1 (`mingw32-make`)
- MSYS2 UCRT64 Host GCC 16.1.0, target `x86_64-w64-mingw32`
- Builtin catalog: 36 strict packages; builtin plus schema JSON documents: 48

## Read-only reference

- Path: `C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5`
- Branch: `main`
- Commit: `cc0b377ded690556d037a412a55f87fe334c42d0`
- Subject: `完善同能力多实例与日志配置契约`
- Working tree before and after import: clean
- Snapshot digest: `7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`

The importer read the reference and copied data into staged builtin payloads. It did not modify,
format, build, commit, or push the firmware repository. FCCG-owned Platform and ownership overlays
remain under `tools/reference_overlays/` and are identified separately from reference-derived data.

## Python and GUI regression

- `python -m pytest -q`: **208 passed in 356.93 s**
- `python -m compileall -q src tools main.py`: passed
- The suite includes both locales, four-page GUI smoke tests, Hardware Connection summaries,
  storage grouping, Platform matching, format migration, generation idempotency, source ownership,
  decoder determinism, task progress, and failure/cancellation behavior.
- Focused storage/RC run after relocating storage ownership: **10 passed**.

## Fresh verified-Board project

Generated below `tests/.rc-final2-20260830` and removed during final cleanup.

- Initial materialization: 503 files added, 0 modified.
- Reload readiness: Ready.
- Second generation plan: 471 `PRESERVE`, 32 `UNCHANGED`; 0 add/modify/delete and not dangerous.
- Resolved Source Graph: 136 C sources; no optional I²C, CAN, or PWM backend/provider source was
  activated by the default SS0.5 composition.
- `.ssdecoder`: 102035 bytes, package SHA-256
  `67f2eb4f5c96ec28dcbe4ef2d0b22fbcb1c731a88163a596812c6dc92b7cb6cc`.
- Decoder entries were exactly `README.md`, `checksums.sha256`, `manifest.json`,
  `project_semantics.json`, and `record_catalog.json`.
- Record Catalog SHA-256:
  `962f9236529d2ff4375202cc2085ed5d89de03639429c368fbe87e760e5aa48f`.
- Project semantics SHA-256:
  `a308626cb7898faf701903e342d7ccd4d08ac125c837457c5cf19f8a33ad9204`.
- Generation profile SHA-256:
  `50a72839454d854ce0972e62f7ae3a6f46a30bc654dac3537adb80dda832a9e8`.

## Generated firmware gates

All commands ran from the fresh verified-Board project and returned 0.

- Release build: `text=248648`, `data=1604`, `bss=118440`; ELF, MAP, HEX, and BIN produced.
- Debug build: `text=262416`, `data=1604`, `bss=118456`; ELF, MAP, HEX, and BIN produced.
- Host Tests: 50 executables, 8754 checks, 0 failures, 8 compile-pass cases, and 16 expected
  compile rejections. Expected rejections retained raw GCC diagnostics but counted as successful
  gates.
- Architecture Check: 250 checks, 0 failures. The first run found an MCU name in a generic
  Platform-header comment; the comment was made vendor-neutral, the builtin was deterministically
  reimported, and this final run passed.
- Power of Ten: 5603 checks over 92 first-party C files and 2074 functions; passed.
- Static Analysis: complete Arm GCC `-fanalyzer` build with warnings as errors; passed.
- Artifact Check: passed with ELF 2629884 bytes and BIN 250252 bytes; FLASH 250252/524288,
  main SRAM 77172/131072, CCMRAM 42872/65536, heap reserved 0, runtime allocator symbols 0.
- `list-sources`: passed and showed the Device-owned storage sources exactly once at
  `Devices/Storage/SdSdioFatFs/Src/`; inactive I²C/CAN/PWM providers were absent.

## Custom CubeMX F407 and migration

The custom project used snapshot
`fb3c835918a2bbe0b285128b901c6f1fa10d2932d5ef81f8630f888e288d2dac` and was generated only
below `tests/`. FCCG detected STM32F407VET6 before matching
`silverstar.mcu.stm32f407vet6` 0.0.9. Compatibility facts were CubeMX 6.15.0,
`STM32Cube FW_F4 V1.28.3`, and `plugin_payload_authoritative`.

- Timebase: generated TIM HAL source, `htim1`/TIM1, 1 MHz counter, 1 kHz tick, enabled
  `TIM1_UP_TIM10_IRQn`.
- FatFs: `SDFatFS`, `SDPath`, `SD_Driver`, `hsd`/SDIO, PC7 detect, and the three Target sources.
- Updating the pre-relocation generated project added the two new Device-owned storage files and
  modified 11 managed files, with no conflict or dangerous operation. Legacy Board-path files were
  retained and inactive. The next plan was 1760 `PRESERVE` plus 32 `UNCHANGED`, and Ready.
- Final custom Release build passed: `text=248656`, `data=1604`, `bss=118448`.
- Final custom Host Tests passed with the same 50/8754/0, 8 compile-pass, and 16 expected-rejection
  totals.

Unit tests also cover accepted F407 matching, unsupported H7, zero and tied Platform candidates,
Board/MCU mismatch, missing or ambiguous FatFs symbols/glue, SDIO DMA/IRQ violations, SysTick or
invalid TIM timebase, PWM/timebase collision, I²C electrical evidence, reserved CAN consumers, and
provider/source uniqueness.

## Conclusions and remaining hardware work

1. Default SS0.5 and imported custom F407 projects generate deterministically and pass the current
   software gates.
2. Storage, CubeMX glue, Platform providers, and Board mappings have distinct single owners; old
   generated projects migrate without source overwrite or duplicate compilation.
3. The current Platform contract is validated only for STM32F407VET6/SS0.5. H7/G4 and other MCUs
   remain unsupported until real plugins and validation exist.
4. Board electrical behavior, external I²C pull-ups, PWM waveforms/safe states, SD-card behavior,
   flash/upload, and flight operation still require physical hardware validation.
