# FCCG User Guide

## 1. 新建工程
输入工程名和输出目录。默认Core/OS/Environment自动选择。

## 2. Devices
选择IMU、GNSS、其他传感器、通信链路、Storage、Actuator、Indicator。支持多实例的官方IMU/GNSS/Telemetry可使用“增加”按钮重复添加，同型号实例后续绑定不同硬件资源。

## 3. Flight Configuration
选择Alignment/INS/Estimator/Landing Strategy、Calibration/Deployment Mode、三种协议以及Logging。

Calibration采样procedure只有OneFace/SixFace，默认都不选；NONE始终是飞控可用模式。若一个或多个采样procedure被编入，GSHC运行时仍可选择默认NONE。

## 4. Hardware Connection
- Official Board：使用固定logical ID→alias映射，为设备分配兼容资源并验证闭合，不能按扫描顺序重排；
- Custom CubeMX：导入完整CubeMX generated project，由用户完成/确认资源分配。

I2C外部上拉、PWM模式/极性、timebase、SDIO/FatFs等根据hardware snapshot严格验证。

## 5. Generate
Generate验证并增量物化源码、Generated glue、Make/EIDE/VS Code和项目描述符。它不自动执行完整构建/质量门。

## 6. Build/Validation
使用EIDE/VS Code或FCCG高级操作执行支持的构建与验证。Stack Report通过生成工程的`mingw32-make CONFIG=Release stack-report`及Debug对应命令单独执行，详见[Build](BUILD.md)。

## 7. `.ssdecoder`
Logging启用时生成并可导出。它与对应日志精确匹配，供FLP后续解析；不要手工编辑包内容。
