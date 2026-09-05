# SilverStar Project Format

当前工程格式：**11**。

## 核心数据
- project identity：name、SilverStar firmware/platform version；
- MCU/Platform lock + `build.target_profile`派生锁；
- Board或Custom CubeMX hardware identity；
- Device instances；
- Strategies；
- Modes及参数；
- capability source overrides；
- three nullable protocol slots；
- logging policy；
- resource assignments；
- development environment；
- generation/readiness fingerprints。

## Calibration
`modes.calibration`合法：`[]`、`["OneFace"]`、`["SixFace"]`、`["OneFace","SixFace"]`。NONE不是GUI mode option，而是始终存在的SystemCalibration运行模式。空数组自动NONE/READY；非空build仍允许运行时选择NONE。

## Protocols
`telemetry/maintenance/logging`分别为协议锁对象或`null`。Device存在不强制启用协议。

## Target lock
`build.target_profile`必须与匹配MCU/Platform manifest完全一致；它是完整性锁，不是用户自由输入。

## Project Semantics
生成的Project Semantics记录physical devices、capability endpoints、initial canonical routes、protocol locks/bindings、algorithms/strategies/modes、logging和hardware identity。Runtime source change通过日志event表达。
