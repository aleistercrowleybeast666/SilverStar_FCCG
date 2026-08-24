# Builtin reference components

The current catalog contains 23 declarative packages imported from clean reference commit `b8c90e997c3113dd23074302682c5560dae18926` on branch `codex/refactor-silverstar-0.0.9-platform`. `plugins/builtin/reference_provenance.json` records the read-only source path, commit, branch, status, digest, and import time.

| Type | Builtins |
|---|---|
| Core | SilverStar Core 0.0.9 |
| MCU | STM32F407VET6 / STM32F4 Platform / HAL/CMSIS / target memory contract |
| Board | SilverStar 0.5 verified `.ioc`, semantic connections, services, FatFs/SDIO, resource roles |
| Device | JY901B, NEO-M9N, physical E28-2G4M12SX (SX1281 Driver), Serial Maintenance Protocol 0.0; all current core classes have `project_max=1` |
| Algorithm base | Common math/geodesy, Alignment Common, Calibration component |
| Alignment Strategy | GravityKnownYaw, GravityMagTriad, HardwareQuat6AxisKnownYaw, HardwareQuat9Axis |
| INS Strategy | Coning2Sculling2 |
| Estimator Strategy | KF6; the slot also supports None |
| FlightLogic base | Flight Cycle/Recovery, Multi-trigger Deployment owner |
| Landing Strategy | BarometerImuWindow |
| OS | FreeRTOS Kernel 11.3.0 static subset and CM4F port |
| ProtocolBundle | Complete AIR V0 + SSLOG0 payload, parser metadata, policy levels, and docs |
| HardwareConfigurationProvider | Trusted STM32CubeMX importer declaration |
| DevelopmentEnvironment | VS Code + EIDE + Arm GNU Toolchain renderer declaration |

Calibration options remain `Existing`, `OneFace`, and `SixFace` in one multi-select Mode component; new projects select all three. Deployment options remain `ApogeeVerticalVelocity`, `Tilt`, and `Delay`, allow multiple selections, and allow none; new projects initially select all three. Declarative per-option requirements disable or remove unsupported options. Opening/reconciling an existing project otherwise retains its stored choices.

The reference has one JY901B physical instance (`imu0`). It provides `imu.acceleration`, `imu.angular_rate`, `attitude.external`, `magnetometer.field`, and `barometer.altitude`. With current GravityKnownYaw + Coning2Sculling2 + KF6 + BarometerImuWindow + Calibration selections, FCCG requires acceleration, angular rate, and barometric altitude. External attitude and magnetic field are optional user selections (enabled in the full reference profile) and may be disabled from Capability Usage. Selecting a HardwareQuaternion alignment strategy makes external attitude required and locked for initialization; that implementation—not an FCCG phase policy—owns its lifecycle.

Device manifests depend on Core and resource/capability contracts, not the concrete F407 MCU plugin. This permits a future supported MCU/Board to reuse the same physical Device package and driver.

The F407 MCU/target payload retains the reference `platform_memory` contract, `.ccmram_data`, `.ccmram_bss`, `.dma_bss`, startup initialization, linker placement, forced memory header, and DMA-access rules. FCCG does not recalculate object placement.

The SilverStar 0.5 Board parses `Flight_Controller0.5.ioc` at resolution time. `connections.json` binds its stable Platform aliases to USART/SPI/GPIO/ADC/SDIO/time inventory entries. The manifest keeps semantic roles and generated C interface IDs but does not repeat pin, baud, DMA, IRQ, or clock facts.

No ESKF15/24, Guidance, Control, Control Allocation, actuator, alternate MCU, Keil, or fictional Device plugin is supplied. The schema can represent future real implementations, but the GUI displays only installed manifests.
