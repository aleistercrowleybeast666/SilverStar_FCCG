# FCCG组件边界

本文定义SilverStar 0.0.9 reference firmware未来拆入独立`SilverStar_FCCG`工程时的payload边界。本仓库没有实现GUI、插件管理器、`.ssplugin`、JSON驱动构建或代码生成器。

## Ownership原则

FCCG创建工程时复制的Component Source归目标工程所有，之后允许用户或Codex修改；普通Apply Configuration不得覆盖这些源码。只有`Generated/`内明确列出的薄连接文件可由未来FCCG重写。`SilverStar.ssproject`记录组合，但不是源码hash或完整性锁。

| 组件类别 | 当前目录/文件 | 责任与可移植边界 |
| --- | --- | --- |
| Core | `APP/`、`System/`、`Interfaces/`、`Common/`、`Modules/` | 任务编排、系统行为、跨组件契约和通用容器；不认识具体Sensor、HAL或STM32 |
| MCU | `Platform/Inc/`、`Platform/STM32F4/`、`Core/`中的CubeMX外设初始化、`Drivers/`、`startup_stm32f407xx.s`、linker script | UART/SPI/GPIO/ADC/Time/Critical后端与STM32F407启动；generic Platform不包含板级资源意义 |
| Board | `Board/SilverStar_0_5/` | SilverStar PCB 0.5的indicator、output、mission action、power、storage和log sink服务 |
| Device | `Devices/IMU/JY901B/`、`Devices/GNSS/NEO_M9N/`、`Devices/Telemetry/SX1281/`、`Devices/Console/UART/` | 每个目录同时携带native Driver和`Adapter/`；Adapter只依赖公共Interface、Device和Platform API，不依赖HAL、concrete Board或Target |
| Algorithm | `Algorithm/Common/`、`Algorithm/Calibration/`、`Algorithm/Alignment/<Strategy>/`、`Algorithm/INS/<Strategy>/`、`Algorithm/Estimator/<Strategy>/` | Common与Calibration全量组件进入正式图；互斥Strategy仅选中实现进入图；无Device/Board/STM32/FreeRTOS依赖 |
| FlightLogic | `FlightLogic/FlightCycle/`、`FlightLogic/Deployment/<Strategy>/`、`FlightLogic/Landing/<Strategy>/` | 生命周期组合、deploy判定和landing判定；当前Deployment=MultiTrigger、Landing=BarometerImuWindow；`APP/Src/flight_task.c`只负责周期编排和系统动作连接 |
| OS | `OS/FreeRTOS/`、`ThirdParty/FreeRTOS-Kernel/`、`Targets/SilverStar_F407/Src/freertos_target_irq.c` | 官方11.3.0 kernel、SilverStar静态配置/Hook和F407 IRQ连接；不包含heap backend或CMSIS-RTOS2 |
| Protocol | `Protocol/Src/air_protocol.c`、`Protocol/SSLOG/` | AIR纯字节协议与SSLOG0正常源码；SSLOG逐字段little-endian codec是Protocol组件，不由FCCG生成 |
| Generated Glue | `Generated/` | 仅project resource mapping、project log selection和project metadata；当前手工维护，未来可由FCCG重写 |
| Target | `Targets/SilverStar_F407/` | 选择STM32F4、SilverStar 0.5、JY901B、M9N、SX1281、FreeRTOS port、F407 flags/linker/HAL/FatFs source set |

## 连接关系

```text
System / APP
    |
Interfaces
    |
Device Adapter 或 Board Service
    |
Device native driver
    |
Platform API
    |
STM32F4 backend

Generated/project_resources + platform_resources
    └─ 只把当前工程选择映射到Platform ID、CubeMX句柄和GPIO pin
```

`Platform/STM32F4`只通过`platform_stm32f4_resources.h`取得opaque handle或GPIO资源；`huart1`、`RADIO_NSS`等当前工程映射集中在`Generated/Src/platform_resources.c`。

## 替换场景

- JY901B换BMI088：复制新的Device Driver+Adapter，修改Target选择、Generated resource mapping和capability aggregation；System、KF6和FlightLogic不修改。
- STM32F407换H743：替换MCU backend、CubeMX/startup/linker/RTOS port及Generated physical mapping；JY901B、M9N、SX1281、Algorithm和FlightLogic不修改。
- Deployment算法替换：保留`FlightDeployment*`显式输入/输出契约或提供等价适配，只替换`FlightLogic/Deployment`；`flight_task.c`不承载阈值数学。

## Strategy与Mode

Strategy是build-time selected的互斥Component；未选择实现不编译、不依赖linker GC、也不通过大段`#if`隐藏。当前分类：

| 功能 | 分类 | 当前reference选择 |
| --- | --- | --- |
| Calibration | Mode/operation | Existing、OneFace、SixFace均保留 |
| Alignment | Strategy | GravityKnownYaw |
| INS | Strategy | Coning2Sculling2 |
| Estimator/Fusion | Strategy | KF6；None不编译KF6 |
| Landing | Strategy | BarometerImuWindow |
| Deployment | Strategy + Modes | MultiTrigger；Apogee/Tilt/Delay为可组合trigger Modes |

Mode由已编入Component的runtime/project配置选择。Mode Set可以按contract允许0..N项；Deployment `selection: []`/mask=0合法且不自动部署。Calibration的`NONE`是“使用已有校准”业务模式，不等同于通用empty set。FCCG负责选择Strategy并生成source graph，runtime只选择Mode；不得生成runtime registry、vtable或函数指针dispatch。

`SilverStar.ssproject`只保存上述human/FCCG reference metadata，不参与Make解析。当前构建truth是Target与module manifests；配置头只保存已编入Component的Mode/参数。

## Deployment硬件动作边界

```text
MultiTrigger decision
 -> FlightRecovery
 -> System Mission Action Interface
 -> Board/SilverStar_0_5 mission_action_service
 -> output_service
 -> PlatformGpio_Write
 -> Generated P_CONTROL2 mapping / physical MOS
```

Deployment Strategy不得包含HAL、Platform GPIO、GPIO port/pin、MOS或PWROUT物理知识。active level、pulse/latched、one-shot、START/PWROUT1与Deploy/PWROUT2语义由既有Board动作链保持，必须另做台架验收。

## Target Memory组件职责

FCCG的MCU/Target插件应携带memory capability、vendor-neutral placement映射、linker、startup初始化、DMA/cache规则、Make/EIDE forced include和artifact预算。Component Source只表达CPU-fast/DMA-accessible意图。F407当前把CPU-only大对象与静态栈置于CCMRAM，DMA对象留主SRAM；这不是可复制到其他MCU的固定地址算法。

## FCCG阶段仍需实现

当前未提供plugin manifest、插件依赖/版本解析、资源冲突检查、toolchain管理、组件升级合并或自动配置摘要生成。当前EIDE native source graph只是手工reference镜像，未来FCCG仍需按选择生成/覆盖；这些能力属于独立FCCG工程，不是0.0.9 firmware运行依赖。
