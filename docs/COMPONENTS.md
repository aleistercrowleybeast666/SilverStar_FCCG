# Builtin reference components

The current catalog contains 31 strict declarative packages synchronized and adapted from the clean SilverStar 0.0.9 reference commit `cc0b377ded690556d037a412a55f87fe334c42d0` (`完善同能力多实例与日志配置契约`), together with FCCG's declarative selectors and logical Devices. `plugins/builtin/reference_provenance.json` records the read-only reference path, commit, branch, clean status, snapshot digest, import time, and audited source/schema/test/document groups. The synchronized SSLOG catalog contains 29 records, including the decoder-profile descriptor.

| Type | Builtins |
|---|---|
| Core | SilverStar Core 0.0.9 |
| MCU | STM32F407VET6 / STM32F4 Platform / HAL/CMSIS / target memory contract |
| Board | SS0.5 verified `.ioc`, semantic connections, services, FatFs/SDIO, resource roles |
| Device | JY901B, NEO-M9N, physical E28-2G4M12SX (SX1281 Driver), Serial Maintenance Protocol 0.0, input-voltage monitor, launch-ignition power output, parachute-pyro power output; instance policy separates per-model `plugin_max` from class-wide `class_max` and raises either only for a context-safe implementation |
| Algorithm base | Common math/geodesy, Alignment Common, Calibration component |
| Alignment Strategy | GravityKnownYaw, GravityMagTriad, HardwareQuat6AxisKnownYaw, HardwareQuat9Axis |
| INS Strategy | Coning2Sculling2 |
| Estimator Strategy | KF6; the slot also supports None |
| FlightLogic base | Flight Cycle/Recovery, Multi-trigger Deployment, Landing Detection Common |
| Landing Strategy | Stillness, ImpactThenStillness, BarometerImuWindow |
| OS | FreeRTOS Kernel 11.3.0 static subset and CM4F port |
| ProtocolBundle | AIR Telemetry Protocol M0, Serial Maintenance Protocol 0.0, Flight Log Format 0.0 payloads, parser metadata, policy levels, and docs |
| HardwareConfigurationProvider | Trusted STM32CubeMX importer declaration |
| DevelopmentEnvironment | VS Code + EIDE + Arm GNU Toolchain renderer declaration |

Calibration options remain `Existing`, `OneFace`, and `SixFace` in one multi-select Mode component; new projects select all three. Deployment options remain `ApogeeVerticalVelocity`, `Tilt`, and `Delay`; new projects select Apogee and Tilt while Delay starts clear. The same manifest owns -2 m/s, 45°, and 60 s defaults plus their validated generated symbols/scaling. Declarative per-option requirements disable unsupported options.

## Raw and qualified capabilities

Capabilities have two formal kinds. A Raw/Data capability means the device can output a value. A Qualified capability, identified by the `_qualified` suffix, means the value satisfies a concrete implementation contract. Strategy requirements name the exact kind they need; FCCG never infers qualification from a device model name or from the presence of related raw data.

The reference has one JY901B physical instance (`imu0`). Its raw data includes `imu.acceleration`, `imu.angular_rate`, `attitude.external`, `magnetometer.field`, and `barometer.altitude`. Reference compile-time evidence additionally qualifies software alignment, software propagation, preflight external-attitude fallback, static 6-axis and 9-axis preflight quaternion alignment, IMU stillness landing, and the barometer landing window. It explicitly does not qualify the magnetic field as an absolute vector, external attitude as authoritative 6-axis/9-axis runtime attitude, or acceleration as a landing-impact source.

Consequently, GravityKnownYaw, HardwareQuat6AxisKnownYaw, and HardwareQuat9Axis static alignment are available; GravityMagTriad is unavailable. Stillness and BarometerImuWindow landing are available; ImpactThenStillness is unavailable. The GUI reports the missing qualified-use contract rather than blaming the JY901B model.

The input-voltage monitor is a logical **Other Sensor**, not an ADC. Launch ignition and parachute pyro are independent optional one-shot **Power Output** Devices mapped to P_CONTROL1/P_CONTROL2. Cancelling launch means external ignition and emits no launch GPIO; cancelling parachute clears deployment Modes. The Board output service checks generated feature constants for each channel and never touches a disabled sentinel.

Device metadata also declares raw outputs that are **Recordable**. This is independent from the capability routes actually **Consumed** by Algorithms. JY901B external attitude is recordable even under GravityKnownYaw; magnetic field is Provided but explicitly not Recordable under the current return-frame configuration. Input voltage is Recordable only while its logical sensor is selected.

Protocol Record schema is distinct from runtime production. The current Core manifest declares the
real producer identities `silverstar.core.device_task` and `silverstar.core.telemetry_task`, backed
by the imported Device/Telemetry tasks plus `diagnostic_log.c`. SSLOG metadata binds STATS to the
former and TELEMETRY_DIAG to the latter. In the reference composition both are available, enabled
by default, and periodic at 1 s and 200 ms respectively.

Landing selectors contribute one compile-time mode definition. They all depend on the single shared `Landing Detection Common` payload. The current reference recovery state machine remains centralized and is not split into three duplicate C implementations; the selector packages do not claim otherwise.

Device manifests depend on Core and resource/capability contracts, not the concrete F407 MCU plugin. This permits a future supported MCU/Board to reuse the same physical Device package and driver.

The F407 MCU/target payload retains the reference `platform_memory` contract, `.ccmram_data`, `.ccmram_bss`, `.dma_bss`, startup initialization, linker placement, forced memory header, and DMA-access rules. FCCG does not recalculate object placement.

The SS0.5 Board parses `Flight_Controller0.5.ioc` at resolution time. `connections.json` binds stable Platform aliases to USART/SPI/GPIO/ADC/SDIO/time inventory entries. Device manifests impose typed bus/electrical contracts over those physical facts; strict pyro outputs require push-pull/no-pull/low-speed, inactive-low startup, and an IOC lock that prevents unsafe regeneration drift.

No ESKF15/24, Guidance, Control, Control Allocation, continuous-control actuator, alternate MCU, Keil, or fictional Device plugin is supplied. The schema can represent future real implementations, but the GUI displays only installed manifests.

## Current discovery boundary

Installed valid user-facing Device manifests automatically appear in manifest-declared groups such
as primary devices, other sensors, indicators, actuators, and telemetry links. The internal
`console` class is deliberately absent from Devices: `maintenance0` is automatically bound by the
selected maintenance profile and remains present in the source graph and Hardware Connection as
Maintenance Console · UART. The GUI does not special-case a concrete console component ID. A
selected GNSS indicator therefore remains selectable on
SS0.5 even though that Board has no second GPIO; the resource resolver reports the missing or
electrically invalid output on Hardware Connection and strict generation fails without silently
reusing the system LED or mission-action outputs.

Physical identity is independent from capability identity. One JY901B physical device can expose
IMU 0, BARO 0, ATTITUDE 0, and magnetic endpoints, each carrying descriptor/source/instance IDs
for maintenance and logs. This Device multiplicity never changes the single selected MCU/startup/
linker/memory-map contract.
