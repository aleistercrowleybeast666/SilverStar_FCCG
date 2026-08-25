# SilverStar 0.0.9 验收要求

> 文档版本：0.0.9
> 适用范围：SilverStar 0.0.9

验收结论必须标明层级：静态检查、Host执行、ARM编译、HIL/台架、上板或飞行。较低层级不能替代较高层级。

## 1. 必跑入口

```powershell
mingw32-make host-tests
mingw32-make architecture-check
mingw32-make power10-check
mingw32-make static-analysis
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Debug clean all
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Release clean all
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Debug artifact-check
mingw32-make TARGET_PROFILE=SilverStar_F407 CONFIG=Release artifact-check
```

发布报告记录命令、退出码、测试数、编译器版本、ELF size和产物路径。没有执行的项目不得写“通过”。

## 2. 架构检查

`Tools/check_architecture.ps1`至少验证：

- System/Algorithm/Protocol/Interfaces/Modules/Common/FlightLogic、Device core、Device Adapter、Platform public无HAL、STM32 handle、GPIO port、CMSIS泄漏；
- System-facing层无JY901B、NEO-M9N、SX1281具体依赖；Platform无具体设备名；
- Device core无System Interface和FreeRTOS依赖；Device Adapter可见native与公共Interface，但不包含HAL、具体Board或Target；
- 旧Provider Ops/VTable/Registry、Device callback registry、sensor×STM32 port、Semtech Radio vtable已删除；
- 第一方runtime无malloc/free、libc snprintf/vsnprintf和FreeRTOS动态创建；
- CMSIS-RTOS2、defaultTask、旧Cube FreeRTOS、`heap_*.c`与`Core/Src/sysmem.c`不在构建图，`.ioc`和链接脚本的heap reserve为0；
- manifest不使用wildcard或`notdir`压平，源文件存在、无重复，只选择当前backend；Target拥有MCU flags、linker script和vendor source manifest；
- FreeRTOS为V11.3.0，只选择list/queue/tasks/ARM_CM4F port，static allocation配置正确；
- EIDE拥有可直接构建但非权威的F407镜像图；其实际C/S集合、include、define、CPU/FPU、linker、forced include和输出隔离必须与Make/Target契约一致；
- SilverStar 0.0.9、AIR Profile 0和SSLOG0版本边界正确；
- `Generated/`只含评审允许的项目资源、日志配置、metadata和manifest薄胶水，不含算法或飞行判定；
- SSLOG普通源码包含显式little-endian serializer/deserializer与三类descriptor，wire路径无struct直写；authoritative Make/manifest不调用Python或生成器；
- 旧`Bindings/`、`Board/SilverStar_F407`、`Protocol/SSLOG/generated`和SSLOG generator不存在。

脚本通过后仍需人工复核例外：CubeMX `Core`、STM32 HAL/Drivers、FATFS Target和Target port中的vendor依赖合理存在。

## 3. Host总回归

`Tests/Host/run_tests.ps1`必须以C11、`-Wall -Wextra -Werror -pedantic`编译独立可执行测试并输出汇总。至少覆盖：

- Interfaces参数/返回值；
- System Time、Mission Time和UTC mapping；
- System/Navigation/Estimator Profile默认与override；
- Attitude、Alignment、Calibration、Pure Inertial；
- AIR和KF6；
- JY901B、NEO-M9N、SX1281 native Device；
- JY901B与NEO-M9N native-to-common Adapter、Power与Mission Action Board Service；
- GNSS/Barometer质量、pending与Sensor Status；
- Lifecycle、FlightRecovery各trigger/Landing组合；
- Lifecycle日志；
- Startup默认、write+verify和no-write策略；
- Health、Console、Telemetry；
- SSLOG/Logger默认与Estimator override、28类payload双向字节往返及完整Record错误解码；
- 编译期能力成功/预期失败矩阵；
- 周期路径不复制大型Alignment status的静态栈审计。
- 四种仓库Alignment Strategy各自独立Host入口；正式F407只编GravityKnownYaw；
- Calibration Existing/default、OneFace和SixFace全部路径；
- Deployment mask NONE、三个单项、三个两两组合和ALL，验证任一满足、reason/mask、one-shot动作与事件序列；
- Estimator None源图不含KF6的构建级检查。

Host输出只写`build/Host/Tests`，不得进入目标manifest。测试mock实现Platform和直接Interface，不恢复HAL/CMSIS或运行期注册表。

## 4. Build与FreeRTOS

Debug和Release均从目标输出目录clean后构建。验收：

1. 生成`SilverStar_0_0_9.elf/.map/.hex/.bin`；
2. 对象路径保留源码层级，无同名压平和duplicate source；
3. map/ELF中不存在`cmsis_os2`、旧Kernel、`heap_1..5`、defaultTask、`malloc/free/realloc`或`_sbrk`；
4. 只出现官方V11.3.0的`list.o/queue.o/tasks.o/ARM_CM4F port.o`；
5. 七个APP任务由`xTaskCreateStatic`创建，Idle storage hook存在；
6. `configSUPPORT_STATIC_ALLOCATION=1`、`configSUPPORT_DYNAMIC_ALLOCATION=0`、priority count=8；
7. SysTick进入FreeRTOS port，HAL tick仍为TIM1；
8. 当前Target只包含STM32F4 backend、JY901B、NEO-M9N、SX1281、UART Console及对应Adapter、SilverStar 0.5 Board Service和受控Generated glue；
9. warning按Makefile策略为0，关键未检查返回/隐式声明/类型不兼容/return error为构建失败；
10. 记录Flash、data和bss；与基线异常变化时分析静态stack/buffer贡献。

还必须运行`artifact-check`/`memory-report`验证：`.ccmram_bss`位于0x10000000..0x1000FFFF且不超过64 KiB；Estimator、当前Alignment storage、七个APP任务栈及Idle栈确实在CCMRAM；UART DMA/rings、Logger aggregation和其他列名的DMA对象在主SRAM；主SRAM使用不超过96 KiB。GNU `size`的总bss跨内存域，不能替代map分域统计。

## 5. Platform与Board

Host mock验证UART读写/分片、SPI/GPIO/ADC/Time/Critical的Device可测试性。STM32F407 backend至少完成ARM编译。

上板必须分别验证：

- UART1/2/3 DMA Receive-to-Idle连续接收、环形buffer wrap、overflow/discontinuity和restart；
- Console异步normal/priority TX顺序与长期不阻塞；
- SPI1时序、NSS/BUSY/RESET/DIO1逻辑和IRQ event累计；
- ADC raw与电压比例；
- Output/Indicator极性、安全上电状态和超时deactivate；
- `PlatformCritical_Exit`恢复原PRIMASK，不误开嵌套临界区；
- microsecond monotonic time跨32-bit tick边界；
- Board逻辑资源与`.ioc`/原理图一致。
- 发布前确认本轮架构修改没有无意改动`Flight_Controller0.5.ioc`；若确需改动，必须同时复核CubeMX生成区和文档。

## 6. Device与Adapter

### JY901B

- parser覆盖0x51/52/53/54/56/59、任意分片、粘包、checksum错误和resync；
- raw/物理量、timestamp、sequence、valid mask和overflow正确；
- baud/rate/bandwidth/6轴9轴/filter/range/RSW/readback/Z-zero配置映射正确；
- Device仅使用Platform，不包含HAL/RTOS；
- IMU Adapter是唯一UART/parser owner，其余逻辑Adapter只读共享native snapshot；
- owner激活后破坏stream的配置返回BUSY，不Abort/DeInit UART；
- 默认Mag关闭、RSW与逻辑enable一致；Mag raw/µT不伪造calibrated/absolute资格。

### NEO-M9N

- UBX NAV-PVT解析、checksum、分片、未知/NMEA流和resync；
- position/velocity/time/accuracy/validity单位映射；
- 非阻塞VALSET/VALGET、ACK/NAK、timeout、bad version/layer/key/length和RX discontinuity；
- NAV-SAT/MON-RF诊断长度、计数上限、C/N0、quality、天线/jamming/cw/noise/AGC；
- 默认不自动写Flash，921600模块端一致性和恢复速率必须上板确认。

### SX1281

- command、register、packet、IRQ、TX/RX queue、timeout、CRC/error状态；
- Semtech调用是直接静态函数，无`Radio.`对象、function-pointer callback和DIO handler registry；
- DIO1通过Platform事件消费，BUSY deadline有界；
- 2473 MHz、12 dBm、SF10、800 kHz、CR4/5、16-symbol preamble、variable length、hardware CRC保持；
- AIR MTU 50 <= transport MTU 64编译/Host断言。

### Adapter通用

- native-to-common逐字段、单位、坐标、valid mask、timestamp、sequence和error mapping；
- NULL、not-ready、unsupported、stale、offline路径；
- 配置report阶段掩码与shared physical delegated语义；
- disabled capability不Init/Start/Process/Health；
- descriptor count/flags/rate/hash与当前Target一致且不越公共上界。

## 7. Startup、Health与Console

- Startup只调用enabled Interface；Required失败fatal，Optional失败degraded；
- 禁用Mag等能力不接触共享逻辑Adapter；
- 正常启动不运行维护self-test，不默认写/保存传感器配置；
- write/apply/persist/verify分别记录，真实回读不以cache冒充；
- 输出在任何失败路径保持safe；普通设备失败仍尽力建立Console/Logger诊断；
- System Time平台初始化失败明确阻止时间服务ready；成功后Mission/UTC API正常；
- Health融合Profile/Startup/IMU/Calibration/Alignment/Output/Estimator状态，不赋予构建资格；
- Maintenance command token、生命周期权限、`SHOW/READ/VERIFY/APPLY`和`IO CLEAR`语义保持；
- `IO CLEAR`只改显示基线，不清底层统计/parser/ring/health。

## 8. Calibration、Alignment与Inertial

- NONE/ONE_FACE/SIX_FACE状态、face检测、样本/方差/静止门、retry/failure和Correction；
- Calibration变化立即使Alignment失效；未READY阻止START；
- Gravity + Known ENU Yaw窗口、known yaw axis、q_nb body-to-ENU和符号约定；
- JY901B GravityKnownYaw、六轴known-yaw和九轴hardware quaternion静态Initial Alignment组合编译通过；TRIAD因absolute magnetic vector资格为0而编译拒绝；两种hardware quaternion任务期authoritative资格保持0；
- READY后运动触发STALE，不自动恢复；
- SystemInertial逐字段保持primary IMU输入，未来source扩展不改变下游Virtual IMU；
- 二子样圆锥/划桨补偿、dt/gap、软件四元数传播和ENU增量数值回归；
- 周期Telemetry/Health/Lifecycle只读紧凑Alignment snapshot，不在任务栈复制完整窗口。

## 9. KF6与量测

- P0、Q、R、对称性、有限值和non-negative covariance；
- GNSS EN/U分组门控、soft/hard NIS、rejection、reacquisition和origin；
- hAcc/vAcc/sAcc动态方差不被较小静态floor覆盖；
- Baro pending顺序、relative origin、variance、stale和gating；
- Fusion NONE与KF6构建/运行路径分别验证；
- Estimator noise recommendation/override compile-contract完整；
- 架构迁移前后的确定输入结果一致，不无理由改变算法阈值。

## 10. Lifecycle与FlightRecovery

- `Calibration -> Alignment -> START`原子提交，拒绝原因稳定；
- START first-wins、Mission Time从0开始、配置冻结与失败rollback；
- NONE/TILT/APOGEE_VZ/DELAY及OR mask、new sequence评价、confirm span和one-shot锁存；
- TILT参考START冻结axis，APOGEE阈值为ENU负向下降速度，DELAY相对START；
- Mission Action逻辑口0/1到Output通道1/2，未知动作/未就绪/失败明确返回；
- 动作成功才记录Deploy并进入RECOVERY，重试不重复执行已锁存动作；
- STILLNESS、IMPACT_THEN_STILLNESS和BARO_IMU_WINDOW各模式；默认direct Baro回归与同窗corrected IMU覆盖率/样本/freshness；
- Landing事件先入队，post-landing grace、Bus拒绝新记录、排空/flush/finalize/retry；
- current JY901B STILLNESS与BARO_IMU_WINDOW作为expected compile success，impact模式作为expected compile failure；Host通过不等于真实静止/冲击捕获或执行器验证。

## 11. AIR Profile 0

逐offset测试：

- type、固定长度、little-endian、token和无application CRC；
- Capability/PREFLIGHT_STATUS/PREFLIGHT_STATE/FLIGHT_STATE/SENSOR_STATUS/CMD/ACK；
- sensor ID registry、snapshot ordering、unknown sensor安全处理；
- Calibration/Alignment/START命令权限、pending/ACK抢占和任务期关闭策略；
- IMU量化使用Calibration后物理量与标准重力9.80665 m/s²；
- 5 Hz飞行遥测、sequence、freshness和saturation诊断；
- 架构重构前后Profile 0 golden frame一致。

固件0.0.9不得把AIR profile改为1。

## 12. SSLOG0

- Record ID、version、payload size、metadata和codec由`sslog_records.*`普通源码拥有；schema/parser metadata仅为离线参考；
- 64-byte file header、24-byte Record header、little-endian、sync、payload length和CRC；
- Record `0x01..0x19` ID/version保持，descriptor `0x1A..0x1C` version 0；
- 每种payload由普通源码实现显式little-endian serializer/deserializer，encode-decode-encode字节一致，长度等于静态metadata；buffer-small和unknown-type安全失败；
- 完整Record deserializer校验sync、version、payload size和CRC；C payload struct不得通过`memcpy`、cast或`sizeof`直接作为wire layout；
- MISSION_CONFIG无payload内部冗余version；
- per-record stream config取代32-bit mask，freeze/rollback/decimation；
- Device/Algorithm/Log Stream descriptor逐实例写出，无固定metadata payload数组；
- LoggerBus normal/estimator queue、overflow、event retry、finalization和BAD_STATE行为；
- 文件截断、尾部半Record、CRC错误与unknown Record离线恢复；
- map/source graph没有runtime JSON、serializer registry或heap。
- firmware build日志没有Python或生成器调用，且不存在`sslog-generate`、`sslog-check`等隐藏前置步骤。

## 13. 文档与版本一致性

- `AGENTS.md`读取0.0.9规范；
- README、CHANGELOG、TARGETS、VALIDATION、System/User README与details当前事实一致；
- `DEVICE_PROVIDER_INTERFACE.md`已由`DEVICE_INTERFACE.md`取代，旧路径无当前引用；
- AIR/SSLOG/Maintenance文档明确区分firmware与wire version；
- 历史`SilverStar_0_0_7.md`、`SilverStar_0_0_8.md`和历史patch note保持历史语义；仅允许标注0.0.9已删除的失效文档链接；
- 所有硬件声明有证据，不把Host/ARM编译写成上板通过。

## 14. 当前未由静态/Host/ARM构建证明的项目

至少包括：

- NEO-M9N模块端921600一致性、配置ACK和持久化；
- SDIO/TF长时间吞吐、突然断电和文件恢复；
- SX1281双机距离、法规、天线和链路预算；
- JY901B动态姿态、时延、安装方向和现场噪声；
- P_CONTROL执行器、点火/开伞负载、互锁和故障安全；
- Landing冲击/静止/气压窗口的真实飞行阈值；
- 整机EMI、电源、振动、温度、HIL和飞行验证。

这些项目在获得实际记录前必须继续列为未验证，不得以0.0.9架构完成为由关闭。

## 15. Power of Ten、Strategy与EIDE追加门禁

`power10-check`必须扫描全部第一方运行时C源码并排除`backup/`及第三方；Rule 1..10任一失败即阻止发布。`static-analysis`在隔离输出目录启用Arm GCC `-fanalyzer`，不能通过关闭整个warning类别处理诊断。FreeRTOS任务入口、Idle hook双指针、调度循环和deterministic fail-stop是明确OS/safety边界，除此之外不允许新增偏差。

默认`make list-sources`必须包含Calibration、Alignment Common + GravityKnownYaw、Coning2Sculling2、KF6、BarometerImuWindow和MultiTrigger，且不包含其余Alignment策略或`backup/`。`ESTIMATOR_STRATEGY=None list-sources`必须移除`navigation_kf.c`。EIDE镜像只能包含默认正式选择；实际EIDE builder未执行时只能报告“配置静态一致”，不得报告“EIDE build通过”。

最终发布前人工核对`Flight_Controller0.5.ioc`的heap/FreeRTOS、TIM1 HAL tick、USART1/2/3 baud、RX DMA circular、NVIC priority、radio/GNSS/output/ADC/SDIO GPIO资源，并与CubeMX生成代码和Target资源映射对照。静态一致性不是上板结论。
