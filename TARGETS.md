# Development targets

## Current FCCG upgrade

- [x] latest-reference discovery/explicit selection and read-only provenance import
- [x] 23 real builtin components, including four Alignment strategies, provider, and environment
- [x] strict Project format 1 migration plus generic Strategy/Mode dictionaries
- [x] Device-first six-page GUI and one-step project identity dialog
- [x] Board provides/defaults/candidates/fixed/reserved/conflicts and compatibility/auto-assignment
- [x] trusted STM32CubeMX `.ioc`/directory import with MCU/layout/peripheral/RTOS validation
- [x] isolated HardwareGenerated ownership, warning, Power-of-Ten boundary, and dangerous replacement
- [x] custom Board `.ssplugin` export, secure install, and second-project reuse
- [x] one resolved source graph for Make, native EIDE, and VS Code
- [x] Estimator=None excludes KF6 before build rendering
- [x] current Power of Ten, forced memory include, CCMRAM/DMA contract, Debug/Release/static/artifact tasks
- [x] F407 reference, same-MCU Board A/B, and custom hardware acceptance fixtures/tests
- [x] Simplified Chinese/English six-page coverage and updated architecture/user/plugin/build documentation

## Current validated scope

- STM32F407VET6 + SilverStar 0.5 is the only complete firmware-build-validated target.
- STM32CubeMX is the only manual HardwareConfigurationProvider.
- VS Code + EIDE + Arm GNU Toolchain is the only DevelopmentEnvironment renderer.
- Current real Strategies: Alignment (four choices), INS Coning2Sculling2, Estimator KF6/None, Landing BarometerImuWindow.
- Current real Modes: Calibration and Deployment triggers.

## Deliberate limits / future work

- No Guidance, Control, Control Allocation, or actuator implementation is supplied; their future slot/class shape is supported only by the generic schema.
- No alternate MCU, non-STM manual provider, Keil, IAR, or fictional environment project is generated.
- FCCG does not solve clocks, PLL, pinmux, alternate functions, or DMA streams and never edits `.ioc`.
- Custom hardware is generated with an explicit unverified warning; generation does not claim official Board validation.
- EIDE native metadata is generated and structurally/architecturally checked; an EIDE CLI builder is required before claiming an actual EIDE-native compile.
- Flash plumbing is guarded, but no hardware flash or electrical test is claimed.
