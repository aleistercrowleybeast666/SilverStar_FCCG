# Plugin Format

插件是严格声明式manifest + payload，不执行安装包脚本。未知核心字段、非法路径、非法类别和ABI不匹配必须失败。

## Types
Core、MCU/Platform、Board、Device、Algorithm、FlightLogic、OS、Protocol、HardwareConfigurationProvider、DevelopmentEnvironment。

## Device category
合法命名空间：`sensor.*`、`link.*`、`storage.*`、`actuator.*`、`indicator.*`。`sensor.imu`和`sensor.gnss`进入Primary Sensors，其余合法`sensor.*`进入Other Sensors；未知顶层namespace拒绝。

## Instance policy
`plugin_max`控制同plugin最大实例，`class_max`控制类别总实例。重复同型号还要求`same_plugin_multiple=true`和`multi_instance_ready=true`。多实例驱动必须context-safe并使用instance-aware resource binding。

## MCU/Platform
声明part/family匹配、Target Profile、CPU/FPU、memory、HAL/CMSIS source policy、backend maturity、resource binding ABI和CubeMX兼容范围。Target不是GUI用户项。

## Board
Verified Board保存固定logical→physical mapping、兼容MCU、`.ioc` snapshot、roles/provenance。普通Generate不按CubeMX scan order重排logical ID。

## Protocol
每个Protocol插件只拥有一个category：telemetry/maintenance/logging。Project槽可为null。Profile声明transport selection：single或显式ordered failover等。AIR M0的多radio候选不改变wire。

## Security
ZIP traversal、绝对路径、symlink、special file、case collision、超限文件、managed-path claim均拒绝。所有C symbol/path/token做严格校验。
