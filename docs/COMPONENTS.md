# Builtin reference components

The current catalog contains 36 strict declarative packages synchronized and adapted from the clean SilverStar 0.0.9 reference commit `cc0b377ded690556d037a412a55f87fe334c42d0` (`完善同能力多实例与日志配置契约`), together with FCCG's declarative selectors, physical and logical Devices, internal service owners, three independent Protocol packages, and official Platform overlays. `plugins/builtin/reference_provenance.json` records the read-only reference path, commit, branch, clean status, snapshot digest, import time, audited groups, and protocol-source hashes. Per-manifest `source_origins` distinguishes the reference base from FCCG extensions replayed by the importer. The synchronized SSLOG catalog contains 29 records, including the decoder-profile descriptor.

| Type | Builtins |
|---|---|
| Core | SilverStar Core 0.0.9 |
| MCU/Platform | STM32F407VET6 exact/family matching, declarative resource ABI, STM32F4 Platform, conditionally selected I²C/Classic-CAN/PWM backends, HAL/CMSIS, and target memory contract |
| Board | SS0.5 verified `.ioc`, semantic connections, fixed resource roles, and provenance; no generic storage/log/mission/indicator service ownership |
| Device | JY901B, NEO-M9N, physical E28-2G4M12SX (SX1281 Driver), internal maintenance UART, SD/TF Card · SDIO + FatFs, input-voltage monitor, two mission-action power outputs, and software indicators; instance policy separates per-model `plugin_max` from class-wide `class_max` |
| Algorithm base | Common math/geodesy, Alignment Common, Calibration component |
| Alignment Strategy | GravityKnownYaw, GravityMagTriad, HardwareQuat6AxisKnownYaw, HardwareQuat9Axis |
| INS Strategy | Coning2Sculling2 |
| Estimator Strategy | KF6; the slot also supports None |
| FlightLogic base | Flight Cycle/Recovery, Multi-trigger Deployment, Landing Detection Common |
| Landing Strategy | Stillness, ImpactThenStillness, BarometerImuWindow |
| OS | FreeRTOS Kernel 11.3.0 static subset and CM4F port |
| Protocol | Three mandatory single-category packages: AIR Telemetry Protocol M0, Serial Maintenance Protocol 0.0, and Flight Log Format 0.0, each with an independent component/version/Profile/manifest lock |
| HardwareConfigurationProvider | Trusted STM32CubeMX importer declaration |
| DevelopmentEnvironment | VS Code + EIDE + Arm GNU Toolchain renderer declaration |

Calibration options remain `Existing`, `OneFace`, and `SixFace` in one multi-select Mode component; new projects select all three. Deployment options remain `ApogeeVerticalVelocity`, `Tilt`, and `Delay`; new projects select Apogee and Tilt while Delay starts clear. The same manifest owns -2 m/s, 45°, and 60 s defaults plus their validated generated symbols/scaling. Declarative per-option requirements disable unsupported options.

## Raw and qualified capabilities

Capabilities have two formal kinds. A Raw/Data capability means the device can output a value. A Qualified capability, identified by the `_qualified` suffix, means the value satisfies a concrete implementation contract. Strategy requirements name the exact kind they need; FCCG never infers qualification from a device model name or from the presence of related raw data.

The reference has one JY901B physical instance (`imu0`). Its raw data includes `imu.acceleration`, `imu.angular_rate`, `attitude.external`, `magnetometer.field`, and `barometer.altitude`. Reference compile-time evidence additionally qualifies software alignment, software propagation, preflight external-attitude fallback, static 6-axis and 9-axis preflight quaternion alignment, IMU stillness landing, and the barometer landing window. It explicitly does not qualify the magnetic field as an absolute vector, external attitude as authoritative 6-axis/9-axis runtime attitude, or acceleration as a landing-impact source.

Consequently, GravityKnownYaw, HardwareQuat6AxisKnownYaw, and HardwareQuat9Axis static alignment are available; GravityMagTriad is unavailable. Stillness and BarometerImuWindow landing are available; ImpactThenStillness is unavailable. The GUI reports the missing qualified-use contract rather than blaming the JY901B model.

The input-voltage monitor is a logical **Other Sensor**, not an ADC. Launch ignition and parachute pyro are independent optional one-shot **Power Output** Devices mapped to P_CONTROL1/P_CONTROL2. Cancelling launch means external ignition and emits no launch GPIO; cancelling parachute clears deployment Modes. Their internal mission-action service checks generated feature constants for each channel and never touches a disabled sentinel.

The physical storage Device is selected once by default and owns both the generic Storage interface
adapter and sequential file Log Sink at `Devices/Storage/SdSdioFatFs`. SS0.5 owns only fixed SDIO
and Time mappings; CubeMX contributes SDIO and FatFs App/Target glue; MCU/Platform contributes the
controlled FatFs core and HAL providers. The resolver requires the unique FatFs object/path/driver,
SDIO RX/TX DMA and IRQ, and a valid generated timer HAL timebase before the Device is available.

Device metadata also declares raw outputs that are **Recordable**. This is independent from the capability routes actually **Consumed** by Algorithms. JY901B external attitude is recordable even under GravityKnownYaw; magnetic field is Provided but explicitly not Recordable under the current return-frame configuration. Input voltage is Recordable only while its logical sensor is selected.

Protocol Record schema is distinct from runtime production. The current Core manifest declares the
real producer identities `silverstar.core.device_task` and `silverstar.core.telemetry_task`, backed
by the imported Device/Telemetry tasks plus `diagnostic_log.c`. SSLOG metadata binds STATS to the
former and TELEMETRY_DIAG to the latter. In the reference composition both are available, enabled
by default, and periodic at 1 s and 200 ms respectively.

Landing selectors contribute one compile-time mode definition. They all depend on the single shared `Landing Detection Common` payload. The current reference recovery state machine remains centralized and is not split into three duplicate C implementations; the selector packages do not claim otherwise.

Device manifests depend on Core and resource/capability contracts, not the concrete F407 MCU plugin. This permits a future supported MCU/Board to reuse the same physical Device package and driver.

Device grouping is driven by strict `metadata.device_category`: only `sensor.*`, `link.*`, `storage.*`, `actuator.*`, and `indicator.*` are accepted. `sensor.imu` and `sensor.gnss` are primary sensors; all other valid sensors enter Other Sensors without a Python model branch. Misspellings or unknown top-level namespaces fail plugin scan rather than being silently reclassified.

The F407 MCU/target payload retains the reference `platform_memory` contract, `.ccmram_data`, `.ccmram_bss`, `.dma_bss`, startup initialization, linker placement, forced memory header, and DMA-access rules. FCCG does not recalculate object placement.

The F407 Platform contract owns the existing F4 resource getter symbols but exposes their header, tables, getters, ABI, match rules, compatibility/source policy, backend maturity, capabilities, conditional sources, and ownership rules declaratively. I²C supports blocking 7-bit master plus 8/16-bit memory-register operations but not DMA/IRQ or generic repeated-start; external pull-ups require Board evidence or a snapshot-bound confirmation. Classic CAN/FDCAN remains inventory-visible while the bxCAN backend is reserved and unavailable to a normal consumer. PWM uses CubeMX-proven ordinary PWM1/PWM2 channel/mode/polarity/timing, logical integer duty, exact forced endpoints, and forced-inactive-before-stop behavior. The default SS0.5 inventory/assignments activate none of these optional backends.

The SS0.5 Board parses `Flight_Controller0.5.ioc` at resolution time. `connections.json` binds stable Platform aliases to USART/SPI/GPIO/ADC/SDIO/time inventory entries. Device manifests impose typed bus/electrical contracts over those physical facts; strict pyro outputs require push-pull/no-pull/low-speed, inactive-low startup, and an IOC lock that prevents unsafe regeneration drift. Timer timebase identity is dynamic inventory data rather than an assumed TIM1 constant.

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
