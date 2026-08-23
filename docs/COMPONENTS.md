# Builtin reference components

The current catalog contains 23 declarative packages imported from clean reference commit `b8c90e997c3113dd23074302682c5560dae18926` on branch `codex/refactor-silverstar-0.0.9-platform`. `plugins/builtin/reference_provenance.json` records the read-only source path, commit, branch, status, digest, and import time.

| Type | Builtins |
|---|---|
| Core | SilverStar Core 0.0.9 |
| MCU | STM32F407VET6 / STM32F4 Platform / HAL/CMSIS / target memory contract |
| Board | SilverStar 0.5 verified hardware, services, FatFs/SDIO, resource roles |
| Device | JY901B, NEO-M9N, SX1281, UART Console |
| Algorithm base | Common math/geodesy, Alignment Common, Calibration component |
| Alignment Strategy | GravityKnownYaw, GravityMagTriad, HardwareQuat6AxisKnownYaw, HardwareQuat9Axis |
| INS Strategy | Coning2Sculling2 |
| Estimator Strategy | KF6; the slot also supports None |
| FlightLogic base | Flight Cycle/Recovery, Multi-trigger Deployment owner |
| Landing Strategy | BarometerImuWindow |
| OS | FreeRTOS Kernel 11.3.0 static subset and CM4F port |
| ProtocolBundle | Complete AIR V0 + SSLOG0 payload and docs |
| HardwareConfigurationProvider | Trusted STM32CubeMX importer declaration |
| DevelopmentEnvironment | VS Code + EIDE + Arm GNU Toolchain renderer declaration |

Calibration options remain `Existing`, `OneFace`, and `SixFace` in one Mode component. Deployment options remain `ApogeeVerticalVelocity`, `Tilt`, and `Delay`, allow multiple selections, and allow none.

The F407 MCU/target payload retains the reference `platform_memory` contract, `.ccmram_data`, `.ccmram_bss`, `.dma_bss`, startup initialization, linker placement, forced memory header, and DMA-access rules. FCCG does not recalculate object placement.

No ESKF15/24, Guidance, Control, Control Allocation, actuator, alternate MCU, Keil, or fictional Device plugin is supplied. The schema can represent future real implementations, but the GUI displays only installed manifests.
