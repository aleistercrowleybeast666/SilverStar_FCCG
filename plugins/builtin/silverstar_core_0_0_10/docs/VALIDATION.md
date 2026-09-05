# FCCG runtime safety validation — 2026-09-05

This is a software validation result for the SS0.5 default composition, not a hardware qualification.
The FCCG repository `VALIDATION.md` records complete commands, task budgets, ELF hashes and logs.

- Final Python suite: 318 passed; focused frozen-source validation: 21 passed.
- Real generated firmware Host suite: 67 executables, 12415 checks, 0 failures,
  8 compile-pass cases and 16 expected compile rejections.
- Arm GNU 14.3.Rel1 Release and Debug, architecture (270 checks), Power of Ten
  (6008 checks), first-party -fanalyzer, artifact and stack-report gates passed.
- Both ELF reports cover all 7 application tasks and Idle. Each build has 138 GCC .su files.
  Production init includes Indicator Init; communication tasks exclude the full Alignment Process;
  FlightTask includes it. Release Telemetry/Serial margins are 2116/1944 bytes after context reserve.
- Current mask values are 0x01/03/05/07; empty calibration initializes/resets to NONE identity READY.
  Required CALIBRATION_RESULT, protocol versions and wire layouts remain unchanged.
- Final reference import replay preserved all 629 file hashes; fresh generation and reload are Ready.
  No external firmware/GUI writes, commits, pushes, flashes or runtime HWM measurements were made.
- Continuous SS0.5 boot/indicator, command repetition, all-task HWM, MSP/interrupt nesting,
  source locking and effective calibration log snapshots remain hardware acceptance work.

The historical reference validation below is not the result of this FCCG repair.

---

# SilverStar Validation Record

正式验收要求见`docs/details/VALIDATION_REQUIREMENTS.md`，正式AIR协议见`docs/details/AIR_PROTOCOL.md`。本文保留已经完成的历史测试事实和后续上板记录；旧命令名与旧架构描述不再构成SilverStar正式接口。

## 2026-08-28 同能力多实例与日志配置契约验证

本轮将同能力多实例的正式边界从Generated静态门面扩展到实际Driver context。IMU、GNSS、BARO、MAG、ATTITUDE、TELEMETRY和POWER均提供有界`CountGet`及按`instance_id`访问descriptor、capabilities、health和适用sample/config/I/O的接口；实现使用生成期固定`switch`直接绑定，不含heap、函数指针、runtime registry、vtable或动态注册。JY901B、NEO-M9N和SX1281现明确声明最多4个context-safe同插件实例；每个实例使用独立Generated资源、parser/FIFO/config/status/radio context，同一源码只编译一次。真实双设备电气与飞行资格仍未验证。

最小Source Selector只实现pre-start IMU新鲜有效源选择并锁定、GNSS基础liveness单向切换，以及AIR单active transport在连续10次真实本地TX timeout后的单向切换。成功TX清零、BUSY不累计、无backup保留最后source并按正常周期继续有界尝试。不存在IMU飞行中切换、Voting、Multi-EKF、RF端到端健康或自动failback。真实切换复用既有SSLOG EVENT，`.ssdecoder`/project-semantics保持1.1且AIR M0、维护0.0、SSLOG 0.0 layout不变。

维护协议0.0继续按`<CAPABILITY> <INSTANCE> <COMMAND>`寻址实例化能力，越界实例明确返回`NOT_PRESENT`，不会回退到0。Host-only fixture生成IMU 0/1和GNSS 0/1两个逻辑实例，验证LIST、descriptor/physical identity、sample、health、配置与越界拒绝；fixture不进入firmware source graph。Canonical INS/KF仍固定使用当前项目语义选择的instance 0，本轮没有实现Sensor Selection、Voting、同型号Driver多实例或Multi-EKF。

Raw/Native日志生产者现在按Generated实例数量有界枚举IMU、GNSS、BARO、MAG、ATTITUDE和POWER；各能力的sequence与valid基线均为逐实例静态数组。Record继续携带`source_descriptor_id + instance_id`并链接`DEVICE_DESCRIPTOR`，相同sequence只抑制对应实例，单实例读取失败不阻塞其他实例。Canonical算法Record语义未变，AIR M0没有增加高频原始消息。

飞行日志格式0.0新增Record ID `0x1D`、v0、64-byte payload的`DECODER_PROFILE_DESCRIPTOR`，在每个日志session打开时一次性记录Record Catalog、project semantics和generation profile的截断SHA-256以及package/container版本；codec逐字段显式little-endian，不直接序列化C struct。正式Record Catalog现含29个Record，定义ID、version、payload size、字段类型/offset/size、单位、语义类别、默认可用性、模式/路由及decoder规则，并由离线validator与C enum、payload常量、codec、Generated配置和parser metadata交叉校验。完整hash为：

- Record Catalog：`962f9236529d2ff4375202cc2085ed5d89de03639429c368fbe87e760e5aa48f`；
- Project Semantics：`78e2a3a6ee9ab339c8090e5bf2dc270b1e74436624a52a7b95e1f850920720df`；
- Generation Profile：`3e53c8449ebeead0102d9b1106e3e75ab84c8d2fa81b2b3ce4c92e9eb1afc0ad`。

最终依次实际执行`mingw32-make clean`、SilverStar_F407 Release all、Debug all、显式`HOST_CC=D:/msys64/ucrt64/bin/gcc.exe`的Release host-tests、Release architecture-check、Release power10-check、Release static-analysis、Release artifact-check和`mingw32-make list-sources`，全部返回0：

- ARM Release：`text=247608 data=1160 bss=116688 dec=365456`；
- ARM Debug：`text=261128 data=1160 bss=116696 dec=378984`；
- Host：55个可执行测试，`checks=9730 failures=0 compile_pass_cases=8 expected_compile_failures=16`；Record Catalog离线校验为29 records/29 payloads；
- Architecture：`checks=253 failures=0`，包含6类Native日志逐实例sequence/valid基线检查；
- Power of Ten：93个第一方C文件、2078个函数，`checks=5625`，0失败；
- Arm GCC `-fanalyzer`严格warning-as-error Release构建通过；
- Artifact：FLASH 248768 B、主SRAM 74976 B、CCMRAM 42872 B，heap reserve与runtime allocator symbol均为0，ELF 375724 B、BIN 248768 B；
- `list-sources`包含Generated实例门面和Decoder Profile源码，不包含Host fixture；firmware Make仍不执行Python。

`Flight_Controller0.5.ioc`最终复核为零差异，USART1/2/3仍为230400/921600/230400 bit/s，P_CONTROL1/P_CONTROL2映射未变；固件版本继续为0.0.10。AIR M0 wire change为NONE，Flight Log Format 0.0容器、`SSLOG0` magic、Record header和CRC变化为NONE；新增Record只扩展Catalog，不提升容器版本。以上属于Host、静态分析、ARM编译与制品审计，不表示新增上板验证。

## 2026-08-27 STATS与TELEMETRY_DIAG生产路径验证

本轮为飞行日志格式0.0中已有的`STATS`（Record ID `0x03`、v0、16-byte payload）和`TELEMETRY_DIAG`（Record ID `0x0C`、v0、48-byte payload）补齐真实生产路径；未新增Record，也未修改ID、version、payload字段顺序、显式little-endian codec、Record header、`SSLOG0`容器或CRC。

`APP/Src/diagnostic_log.c`中的STATS周期生产者由Device Task现有POWER/HEALTH周期路径调用，仅在FLIGHT/RECOVERY、日志启用且1,000,000 us周期到达时读取并推送。四个字段分别来自`ImuSampleBus_StatsGet().overflow_count`、`LoggerBus_OverflowCountGet()`、`Ins_GetLatestSnapshot().update_seq`和`.health_flags`；无可用Canonical INS快照时，后两项明确写0。`TELEMETRY_DIAG`周期生产者由Telemetry Task在既有Telemetry Service处理周期后调用，仅在FLIGHT/RECOVERY、日志启用且200,000 us周期到达时读取通用`SystemTelemetryHealth`，逐字段映射Transport/Link健康并推送；`SystemTelemetry_HealthGet()`失败时不写伪造零记录、不推进周期基线，下次继续尝试。两条路径都只经Logger Bus写入，没有新增任务、AIR消息、射频私有统计依赖或动态状态注册。

Host Test覆盖两项v0 codec round-trip、payload size、Record ID/version、显式little-endian、所有字段映射、未到周期、到期单次推送、disabled与生命周期门禁、INS快照缺失、HealthGet失败后重试、RSSI/SNR/online以及`LoggerBus_Pop()`读回。Schema、parser metadata与Generated默认配置均启用STATS/1,000,000 us和TELEMETRY_DIAG/200,000 us，其他Record默认配置未改变；architecture-check验证真实producer不来自`logger_bus.c`定义、通用Transport Health依赖、无SX1281私有统计、schema/payload一致和authoritative Make source graph包含`diagnostic_log.c`。

最终依次实际执行`mingw32-make clean`、Release all、Debug all、显式`HOST_CC=D:/msys64/ucrt64/bin/gcc.exe`的host-tests、architecture-check、power10-check、Release static-analysis、Release artifact-check和list-sources，全部返回0：

- ARM Release：`text=246640 data=1160 bss=116552 dec=364352`；
- ARM Debug：`text=259120 data=1160 bss=116560 dec=376840`；
- Host：55个可执行测试，`checks=9609 failures=0 compile_pass_cases=8 expected_compile_failures=16`；logger套件两次配置各为723 checks、0 failures，AIR M0 golden tests通过；
- Architecture：`checks=210 failures=0`；
- Power of Ten：92个第一方C文件、2027个函数，`checks=5513`，0失败；
- Arm GCC `-fanalyzer`严格warning-as-error Release构建通过；
- Artifact：FLASH 247800 B、主SRAM 74840 B、CCMRAM 42872 B，heap reserve与runtime allocator symbol均为0，ELF 375244 B、BIN 247800 B；
- `list-sources`列出`APP/Src/diagnostic_log.c`，authoritative Make仍不执行Python。

`Flight_Controller0.5.ioc`最终复核为零差异；固件版本继续为0.0.10。AIR M0 wire change为NONE，Flight Log Format 0.0容器变化为NONE，串口维护协议0.0语法也未改变。以上属于Host、静态分析、ARM编译与制品审计，不表示新增上板验证。

## 2026-08-26 Capability Instance Addressing验证

本轮将Physical Device与Capability Endpoint正式分离。`SystemDeviceDescriptor`增加`physical_device_id`，descriptor支持按class统计和按`class + instance`查找；`Generated/project_device_instances`提供静态、无函数指针、无heap、无runtime registry的实例门面。当前JY901B physical 1映射到IMU 0、BARO 0和ATTITUDE 0，MAG 0仅在能力启用时生成；NEO-M9N physical 2映射GNSS 0，E28/SX1281 physical 3映射TELEMETRY 0，Power ADC physical 5映射POWER 0。当前门面只接受instance 0，不包含设备选择、投票或Multi-EKF。

串口维护协议0.0的设备能力命令统一为`<CAPABILITY> <INSTANCE> <COMMAND>`，System/Estimator/KF/INS/Calibration/Alignment/LOG/TIME仍不带实例；`LIST`返回生成的能力实例。旧无实例设备命令明确返回`INSTANCE_REQUIRED`，非法、越界和未生成实例分别返回可诊断错误。共享同一`physical_device_id`的JY901B端点共用物理IO统计和CLEAR基线，不再以BARO硬编码转发到IMU。

飞行日志格式0.0保持`SSLOG0`容器、Record ID、header、CRC和little-endian规则。DEVICE_DESCRIPTOR增加physical ID；POWER、IMU_NATIVE、GNSS_NATIVE、BARO_NATIVE、MAG_NATIVE和HW_QUAT_NATIVE增加`source_descriptor_id + instance_id + reserved`来源头，payload大小分别为48、80、84、48、60和48字节。来源切换复用既有12-byte EVENT payload；IMU_NATIVE已由DeviceTask真实生产。全部字段继续由显式endian-aware codec逐项编解码，未直接序列化C struct。AIR M0 wire修改为NONE；golden frame、消息ID、字段、长度、CRC和发送频率不变，Sensor Status仅改为descriptor驱动成员枚举。

最终实际执行`mingw32-make clean`、`mingw32-make -j4`、`mingw32-make "HOST_CC=D:\\msys64\\ucrt64\\bin\\gcc.exe" host-tests`、`mingw32-make list-sources`、`mingw32-make architecture-check`、`mingw32-make power10-check`、`mingw32-make static-analysis`和`mingw32-make artifact-check`，全部返回0：

- ARM Debug：`text=258304 data=1160 bss=116544 dec=376008`；
- Host：55个可执行测试，`checks=9307 failures=0 compile_pass_cases=8 expected_compile_failures=16`；
- Architecture：`checks=198 failures=0`；
- Power of Ten：91个第一方C文件、2021个函数，`checks=5491`，0失败；
- Arm GCC `-fanalyzer`严格warning-as-error构建通过；
- Artifact：FLASH 259464 B、主SRAM 74832 B、CCMRAM 42872 B，heap reserve与runtime allocator symbol均为0，ELF 2566944 B、BIN 259464 B；
- 两份SSLOG schema/parser metadata JSON解析通过，authoritative Make source graph列举通过。

`Flight_Controller0.5.ioc`最终复核为零差异，heap仍为0，USART1/2/3仍为230400/921600/230400 bit/s。固件版本继续为0.0.10，AIR遥测协议M0、串口维护协议0.0和飞行日志格式0.0均未升版。以上属于Host、静态分析、ARM编译与制品审计，不表示新增上板验证。

## 2026-08-26 GNSS Indicator、Host GCC与协议名称验证

本轮补齐通用GNSS Indicator：原实现已有`SYSTEM_INDICATOR_GNSS`角色和默认关闭开关，但没有`SystemIndicator_GnssModeResolve()`、周期GNSS健康/样本接入或行为测试。现在无GNSS设备、未初始化、离线或无有效样本为OFF；在线且样本有效但`position_usable=0`为慢闪；`position_usable!=0`为常亮。逻辑只使用System GNSS Interface，默认`SYSTEM_INDICATOR_GNSS_ENABLE=0U`；当前SilverStar 0.5仍只有SYSTEM灯Board资源，没有新增第二个GPIO，也没有复用P_CONTROL输出。

Host Test由Make的`HOST_CC`显式传入主机编译器。本轮实际使用`D:\msys64\ucrt64\bin\gcc.exe`，版本为GCC 16.1.0，`-dumpmachine`为`x86_64-w64-mingw32`。脚本在开始时输出并验证版本/target，统一PowerShell UTF-8输出；普通编译失败保留测试名、编译器信息、全部参数和GCC stdout/stderr，Expected Compile Failure保留真实首条GCC error。额外通过Make传入含空格的完整Arm GCC路径，负向检查按预期返回1，并明确报告`target=arm-none-eabi`不能在Windows运行Host Test EXE；同时验证了含空格路径的引用链。

面向用户的正式名称统一为AIR遥测协议M0、串口维护协议0.0和飞行日志格式0.0。技术兼容标识`AIR_PROFILE_COMPACT_V0`、wire numeric值0、`SSLOG0`文件magic及全部帧、Record、CRC、message ID和字段布局均未改变；`SilverStar.ssproject`未修改。

最终依次执行`mingw32-make clean`、`mingw32-make -j12`、`mingw32-make "HOST_CC=D:\msys64\ucrt64\bin\gcc.exe" host-tests`、`mingw32-make architecture-check`、`mingw32-make power10-check`、`mingw32-make static-analysis`和`mingw32-make artifact-check`，全部返回0：

- ARM Debug：`text=253952 data=1160 bss=114152 dec=369264`；
- Host：54个可执行测试，`checks=9180 failures=0 compile_pass_cases=8 expected_compile_failures=16`；其中System Indicator为34 checks、0 failures；
- Architecture：`checks=188 failures=0`；
- Power of Ten：89个第一方C文件、1982个函数，`checks=5380`，0失败；
- Arm GCC `-fanalyzer`严格warning-as-error构建通过；
- Artifact：FLASH 255112 B、主SRAM 72440 B、CCMRAM 42872 B，heap reserve与runtime allocator symbol均为0，ELF 2509144 B、BIN 255112 B。

`Flight_Controller0.5.ioc`最终复核为零差异，固件版本继续为0.0.10。本轮没有改动飞行算法、协议wire、硬件配置、传感器配置或Board资源。以上属于Host、静态分析、ARM编译和制品审计，不表示新增上板验证。

## 2026-08-25 JY901B静态初始对准与着陆资格门禁验证

本轮只固化JY901B能力合同与编译期门禁。硬件四元数的六轴已知航向角、九轴静态取样资格均为1；它们只允许在任务开始前采满静态窗口并形成一次冻结的初始`q_nb`。六轴、九轴飞行全程权威姿态资格继续为0，START后仍由软件四元数传播。JY901B绝对磁场矢量资格为0，不能选择重力/磁场双矢量对准。着陆静止判断资格为1，冲击检测资格继续为0。

Host能力矩阵已验证：JY901B的重力已知航向角、六轴硬件四元数已知航向角、九轴硬件四元数静态取样、静止着陆和气压计/IMU窗口着陆均编译通过；重力/磁场双矢量对准和冲击后静止着陆均按预期在编译期失败。对应资格被测试覆盖显式改为0时，六轴/九轴硬件四元数静态对准、静止着陆和气压计/IMU窗口着陆也均按预期编译失败。

最终依次执行`mingw32-make clean`、`mingw32-make -j12`、`mingw32-make host-tests`、`mingw32-make architecture-check`、`mingw32-make power10-check`、`mingw32-make static-analysis`和`mingw32-make artifact-check`，全部返回0：

- ARM Debug：`text=253952 data=1160 bss=114152 dec=369264`；
- Host：54个可执行测试，`checks=9168 failures=0 compile_pass_cases=8 expected_compile_failures=16`；
- Architecture：`checks=188 failures=0`；
- Power of Ten：89个第一方C文件、1980个函数，`checks=5375`，0失败；
- Arm GCC `-fanalyzer`严格warning-as-error构建通过；
- Artifact：FLASH 255112 B、主SRAM 72440 B、CCMRAM 42872 B，heap reserve与runtime allocator symbol均为0，ELF 2508168 B、BIN 255112 B。

`Flight_Controller0.5.ioc`最终复核为零差异；heap仍为0，USART1/2/3仍为230400/921600/230400 bit/s，TIM1仍为HAL时基。本轮没有改动算法数学、状态机、传感器配置、协议、构建架构、磁力回传/日志或飞行时姿态传播；固件、AIR、SSLOG和维护协议版本均保持0.0.10既有值。以上属于Host、静态分析、ARM编译和制品审计，不表示新增上板验证。

## 2026-08-23 Strict Power of Ten、CCMRAM与Strategy/Mode组件化验证

### 最终分类与source graph

| 功能 | 分类 | 当前F407选择 |
|---|---|---|
| Calibration | Mode | 空选=NONE/单位校正；OneFace、SixFace可独立或组合选择 |
| Alignment | Strategy | `GravityKnownYaw` |
| INS | Strategy | `Coning2Sculling2` |
| Estimator/Fusion | Strategy | `KF6`；`None`不编入KF6源码 |
| Landing | Strategy | `BarometerImuWindow` |
| Deployment | MultiTrigger Strategy + trigger Modes | Apogee/Tilt/Delay允许0..N组合，默认Apogee only |

重构前43个关键原文件保存于`backup/pre_strategy_componentization_20260821/`，该目录不进入Make、EIDE、Host或Power-of-Ten范围。当前正式source graph只包含Alignment Common+GravityKnownYaw、INS Coning2Sculling2、Estimator KF6、Landing BarometerImuWindow、Deployment MultiTrigger、Calibration与Algorithm Common。GravityMagTriad、HardwareQuat6AxisKnownYaw和HardwareQuat9Axis只参加独立Host测试；`ESTIMATOR_STRATEGY=None list-sources`已验证不含`navigation_kf.c`。

Deployment的NONE/APOGEE/TILT/DELAY及全部两两/三项组合均通过Host测试，保持任一条件满足、one-shot、reason/event与动作次数语义。硬件动作路径保持为`MultiTrigger decision -> FlightRecovery -> SystemMissionAction -> FlightLogic mission-action services -> PlatformGpio_Write -> Generated mapping -> P_CONTROL2 MOS`；FlightLogic不包含HAL、Platform GPIO或物理引脚知识。

### 自动检查与Host结果

- 最终依次执行`mingw32-make clean`、`mingw32-make -j12`、`mingw32-make host-tests`、`mingw32-make architecture-check`、`mingw32-make power10-check`、`mingw32-make static-analysis`和`mingw32-make artifact-check`，全部返回0；
- Host：54个可执行测试，`checks=9168 failures=0`，另有4个预期编译成功和13个预期编译失败能力契约；覆盖四种Alignment Strategy、三种Calibration Mode、八种Deployment mask组合、None/KF6语义、Device/Adapter、Lifecycle、Console、Telemetry、Logger、AIR和SSLOG；
- Architecture：`checks=188 failures=0`；Make/EIDE源、include、define，Strategy选择、FreeRTOS精简源集、层级边界、SSLOG schema/metadata/codec、`.ioc`关键资源与无Python authoritative build均通过；
- Power of Ten：89个第一方C文件、1980个函数、`checks=5375`，0失败；10条规则均为硬门禁。唯一明确的第一方API边界偏差是固定task entry直接传入FreeRTOS，以及Idle memory hook的固定双指针签名；未建立runtime function-pointer registry或strategy dispatch；
- Arm GCC 14.3 `-fanalyzer`在隔离的`build/FCCG/SilverStar_F407/StaticAnalysis/Debug/`图通过，第一方严格warnings-as-errors为0。

### ARM、EIDE与内存结果

| 构建 | text | data | bss | dec | ELF bytes | BIN bytes |
|---|---:|---:|---:|---:|---:|---:|
| Make Debug | 253952 | 1160 | 114152 | 369264 | 2508168 | 255112 |
| Make Release | 241424 | 1160 | 114144 | 356728 | 364212 | 242584 |
| EIDE native Debug | 254088 | 1160 | 114152 | 369400 | 2191744 | 255248 |

EIDE 3.27.2原生`unify_builder`使用Arm GNU Toolchain 14.3.1实际完成133个C文件和1个ASM文件的独立rebuild；`.eide/eide.yml`与Make选择由architecture-check逐项比对，EIDE产物隔离到`build/FCCG/SilverStar_F407/EIDE/`。

Debug artifact审计结果：FLASH使用255112 B；DMA可达主SRAM使用72440 B、剩余58632 B；CCMRAM使用42872 B、剩余22664 B；heap reserve与runtime allocator symbol均为0。Release主SRAM使用72432 B，CCMRAM同为42872 B。与迁移前Debug的`data+bss=121500 B`全部位于主SRAM相比，当前Debug主SRAM减少49060 B。GNU `size`的`bss`合并统计主SRAM与CCMRAM，不能把114152 B误写为当前主SRAM占用。

CCMRAM中的关键对象为`s_estimator` 17696 B、当前`s_alignment_strategy` 6232 B、七个静态任务栈和Idle栈；UART DMA/ring、HAL/DMA handle、Logger aggregate与logger storage均留在主SRAM。linker定义`.ccmram_bss`，startup在进入C之前有界清零；artifact检查按ELF/MAP验证实际地址而非只检查attribute源码。

### SSLOG与`.ioc`

本次2026-08-23历史验收的SSLOG基线为28个Record，其ID、version、payload size、metadata及显式逐字段little-endian serializer/deserializer位于`Protocol/SSLOG/Inc/sslog_records.h`和`Protocol/SSLOG/Src/sslog_records.c`。当时Host覆盖全部record的encode/decode/encode、长度、endian、CRC和错误路径，wire路径不复制或强制转换C payload struct；当前29类Record Catalog与Decoder Profile状态以本文2026-08-28条目为准，authoritative Make仍没有Python、generator或隐藏同步步骤。

输出前最终复核`Flight_Controller0.5.ioc`：本轮工作树对该文件无diff；heap为0，无FreeRTOS/CMSIS-RTOS2配置，TIM1仍为HAL tick；USART1/2/3为230400/921600/230400 bit/s且三路RX DMA均为circular；DMA/UART/EXTI中断优先级、SPI1/SDIO/ADC1_IN10及Radio/GNSS/P_CONTROL引脚与CubeMX源码、Generated资源映射和Target契约一致。

以上结论属于Host、静态分析、EIDE/ARM编译与ELF/MAP审计，不表示GNSS模块配置持久化、SDIO断电恢复、SX1281双机、P_CONTROL执行器安全链或整机飞行已经新增上板验证。

## 2026-08-20 SilverStar 0.0.10平台化重构验证

### 已实现与静态检查

- 当前分支为`codex/refactor-silverstar-0.0.10-platform`；以`9ca21c7`为重构前基线，并先以`b1c13e2`建立0.0.10平台化checkpoint，未创建兼容工程副本、未reset/clean或覆盖既有成果；
- 当前依赖为`System -> Interfaces -> Device Adapter / Device-owned service / internal hardware service -> Device -> Platform -> STM32F4 backend`。JY901B/M9N/SX1281/UART集成归各Device组件，Power/Storage归各自Device，Mission Output与Indicator归内部FlightLogic服务组件，资源/日志选择/metadata归薄`Generated/`；旧Provider/VTable/Registry、`Bindings/`、sensor×STM32 port、CMSIS-RTOS2、defaultTask、旧Cube FreeRTOS与Semtech Radio callback/vtable路径已删除；
- `mingw32-make architecture-check`通过：`checks=109 failures=0`；显式manifest、Device Adapter/Board/Platform/FlightLogic/Generated边界、FreeRTOS V11.3.0精简源集、无第一方动态分配/libc printf、无Python authoritative build、SSLOG双向endian codec、`.ioc`关键资源和旧架构残留均通过；
- 本次历史验收时SSLOG基线为28类Record，其ID、metadata和逐字段little-endian serializer/deserializer已是`Protocol/SSLOG/Inc/sslog_records.h`与`Protocol/SSLOG/Src/sslog_records.c`普通源码，schema/parser metadata当时仅作离线参考；当前29类Record Catalog与Decoder Profile状态以本文2026-08-28条目为准。工程仍禁止按C struct布局直接读写wire；
- `mingw32-make list-sources`通过，列出的当前图包含F407、JY901B、M9N、SX1281、UART Adapter、SilverStar 0.5 Board、FlightLogic和受控Generated glue，不包含旧Provider、Binding、sensor STM32 port、CMSIS、heap或SSLOG生成器；
- `git diff --check`通过；当前正式文档已同步FCCG-ready reference firmware结构，历史0.0.7/0.0.8规范保留为快照。

### Host执行

- `Tests/Host/run_tests.ps1`使用C11、`-Wall -Wextra -Werror -pedantic`完成48个独立可执行测试：`checks=9050 failures=0`，另有4个预期编译成功和13个预期编译失败能力契约；
- 覆盖Interfaces/Platform mock/Device Driver+Adapter、Device-owned/internal services、Alignment/Calibration/INS/KF6/Lifecycle/FlightRecovery、AIR、Console、Telemetry、Logger及SSLOG；新增JY901B和NEO-M9N native-to-System转换测试；
- SSLOG覆盖全部28个payload的`encode -> decode -> encode`字节一致性、完整Record endian/sync/version/size/CRC及buffer-small/unknown-type错误路径；Common有界格式器覆盖整数、定点小数、general float、截断与NULL边界。

### ARM GCC clean build与产物

工具链为`arm-none-eabi-gcc 14.3.1 20250623`、GNU Make 4.4.1。Debug与Release均从各自目标目录clean后构建，并在最终源码上分别执行`artifact-check`；构建日志没有Python调用：

| 配置 | text | data | bss | dec | object数 | ELF bytes | BIN bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| Debug | 218132 | 1188 | 120312 | 339632 | 131 | 2171976 | 219324 |
| Release | 217428 | 1188 | 120312 | 338928 | 131 | 337732 | 218620 |

两套目标均生成`SilverStar_0_0_10.elf/.map/.hex/.bin`，对象保留源码目录层级。ELF符号和map检查确认：无`malloc/calloc/realloc/free/_sbrk`运行期heap路径，无`heap_*.o`、`sysmem.o`、`cmsis_os2.o`或defaultTask；只选择官方FreeRTOS V11.3.0的`list.c/queue.c/tasks.c/ARM_CM4F port.c`。

### `.ioc`复核

输出前已对`Flight_Controller0.5.ioc`执行差异与字段检查；工作树及相对本轮checkpoint `b1c13e2`的diff均为空，本轮没有改动硬件配置：

- 当前`Mcu.IP0..10`仅含ADC1、DMA、FATFS、NVIC、RCC、SDIO、SPI1、SYS、USART1/2/3，`Mcu.IPNb=11`；不存在`FREERTOS.*`、`VP_FREERTOS_VS_CMSIS_V2`、`rtos.0.ip`或Cube任务表，不再由CubeMX生成CMSIS-RTOS2/defaultTask；
- `ProjectManager.HeapSize=0x0`，并与链接脚本`_Min_Heap_Size=0x0`一致；
- `NVIC.TimeBaseIP=TIM1`，TIM1 IRQ优先级15；SysTick优先级15并由Target转入`xPortSysTickHandler`；
- USART1/2/3仍分别为230400/921600/230400 bit/s，三路RX DMA仍为circular；DMA、USART和EXTI业务IRQ优先级仍为5，与`configLIBRARY_MAX_SYSCALL_INTERRUPT_PRIORITY=5`一致；
- IMU UART1、GNSS UART2、Console UART3、SPI1 Radio、ADC1_IN10、SDIO、RADIO DIO1/RESET/BUSY/NSS、GNSS TIMEPULSE/RESET和两路P_CONTROL的引脚映射未改变。

### 未完成的硬件验收

以上结论属于静态、Host和ARM编译验证，不是上板验证。NEO-M9N模块端921600/ACK/持久化、JY901B动态性能、SX1281双机与链路预算、SDIO长时间写入/断电恢复、P_CONTROL执行器安全链路和整机飞行仍需按正式验收文档取得实测证据。

## Historical local ASCII debug protocol check

The pre-SilverStar USART3 request/response modules were `SYSTEM`, `AIR`, `LINK`, `IMU`, `GNSS`, `PWROUT`, `ADC`, and `TF`. These names are retained below only as historical validation evidence. The SilverStar formal modules and response rules are defined by `docs/details/MAINTENANCE_PROTOCOL.md`.

Before START, verify all current commands reach their existing owner paths. Do not issue dangerous hardware writes during automated checks. After START, the following remain available:

- `SYSTEM HELP/PING/STATS`;
- `AIR PING/STATUS/CONFIG`;
- `LINK PING/STATUS/CONFIG/IRQ/RSSI/DIAG`;
- `IMU PING/DATA`;
- `GNSS PING/STATUS/FIX/PVT`;
- `PWROUT PING/STATUS`;
- `ADC PING/STATUS/SAMPLE/CONFIG`;
- `TF STATUS`.

After START, `SYSTEM CLEAR_STATS`, active IMU/GNSS hardware readbacks, device writes, AIR test-mode changes, LINK state changes/raw TX, and PWROUT writes must return `BAD_STATE` with `detail=MISSION_RUNNING` from the command owner path. With `FC_SERIAL_PWROUT_WRITE_ENABLE=0`, pre-START `PWROUT SET/ALL_OFF` must return `UNSUPPORTED` with `detail=PWROUT_WRITE_DISABLED`; with the macro set to 1, those commands may use the existing write path only before START. Restore the final configuration to 0.

GNSS hardware acceptance starts with `GNSS PING/STATUS/FIX/PVT` at the current UART settings. Record real UART/UBX NAV-PVT flow, online state, fix type and validity, satellite count, position, NED velocity, ground speed, heading, and freshness before testing `GNSS CONFIG/SET/SAVE` before START.

### 2026-08-03 GNSS measurement availability result

- UBX statistics now use checksum terminology for the existing CK_A/CK_B calculation. `GNSS CONFIG` identifies the fixed VALGET source as `read_layer=RAM`; write responses retain `persisted=...` only for their write target.
- `GnssNeoM9nData` publishes independent `positionUsable`, `velocityUsable`, and `courseUsable` flags on every process cycle. PDOP remains diagnostic only and is not a gate.
- A host test extracted the actual `Gnss_UpdateStatus()` implementation and passed all eight cases:
  1. static good fix: `has=1 position=1 velocity=1 course=0`;
  2. bad position accuracy with good velocity/course: `has=1 position=0 velocity=1 course=1`;
  3. good position with bad speed accuracy: `has=1 position=1 velocity=0 course=0`;
  4. good velocity with low ground speed: `has=1 position=1 velocity=1 course=0`;
  5. high ground speed with bad heading accuracy: `has=1 position=1 velocity=1 course=0`;
  6. all criteria good: `has=1 position=1 velocity=1 course=1`;
  7. age 501 ms: `has=1 position=0 velocity=0 course=0`;
  8. valid 2D fix: `has=1 position=0 velocity=0 course=0`.
- Worst-case GNSS field lengths are PING 247, STATUS 797, FIX 427, PVT 535, and CONFIG 250 bytes including the terminator, all within the 896-byte response field buffer.
- A clean ARM GCC build passed: `text=123260`, `data=152`, `bss=103824`. These are static/compiled results, not GNSS hardware validation.
- AIR protocol/layout and TF binary log format were not changed by this GNSS update.

### 2026-08-03 static and build result

- Static routing checks passed for `GNSS/PWROUT/ADC/TF`; `LORA` has no parser route and still falls through to `BAD_MODULE`.
- Static owner-path permission checks passed for the documented pre-START and post-START command matrix, including `BAD_STATE/MISSION_RUNNING` before any protected mutation.
- `FC_SERIAL_PWROUT_WRITE_ENABLE=1U` and the final default `0U` both completed clean ARM GCC builds. The final `0U` image size is `text=122380`, `data=152`, `bss=103824`.
- No AIR protocol, device driver, LoRa state-machine, quaternion telemetry, or TF log-format file was modified by this change.
- No dangerous configuration or GPIO write was executed during automated checks. Live USART3 responses, PWROUT GPIO behavior, and GNSS UART/search/fix behavior remain hardware validation items.

## Phase 4 first 6-state position/velocity KF

### State, covariance, and noise baseline

- State order is `[p_E, p_N, p_U, v_E, v_N, v_U]`; START initializes all six states to zero.
- `P0=diag(4,4,9,0.25,0.25,0.25)` in position/velocity SI units.
- SilverStar重构前的KF曾消费Pure INS生成的`delta_velocity_n_corrected`。0.0.5正式边界改为共享机体系`SystemInertialIncrement`：Pure INS和KF导航支路分别维护姿态并各自生成ENU增量。等效加速度标准差仍为E/N `1.5 m/s²`、U `2.0 m/s²`；KF数学核心继续使用`Q_dv=diag((sigma_a*dt)²)`和`G=[0.5*dt*I; I]`。
- GNSS uses `1.25*hAcc/vAcc/sAcc`, with lower standard-deviation limits of `1.5 m` horizontal, `2.5 m` Up, and `0.15 m/s` velocity. Variances are rebuilt from each accepted NAV-PVT.
- Barometer altitude standard deviation starts at `5.0 m` (`R=25 m²`) and may not be set below `1.5 m`.
- Three-dimensional GNSS soft/hard NIS thresholds are `11.345/16.266`; one-dimensional barometer thresholds are `6.635/10.828`. Soft weighting scales R by `NIS/soft`, clamped to 10; hard rejection leaves x and P unchanged.
- Updates use Joseph form, covariance symmetrization, `P` diagonal floor `1e-8`, and matrix epsilon `1e-9`. NaN, Inf, illegal dt, or non-SPD innovation covariance sets health/counters and restores the initial covariance without passing invalid values onward.

### Origin and freshness conditions

- GNSS origin is collected only before START from 50 consecutive new `pvtSequence` samples with `positionUsable=1`; maximum sample gap is 200 ms. Latitude, wrapped longitude, and WGS84 ellipsoid height are averaged in integer/double precision and frozen at START.
- If no GNSS origin exists at START, GNSS position stays disabled for that mission. GNSS velocity remains independently usable and is converted NED→ENU as `[velE, velN, -velD]*0.001`.
- Barometer origin is the mean of at least 50 new `pressure_frame_count` heights within a 2000 ms pre-START window and is frozen at START. If absent, only barometer updates are disabled.
- GNSS and barometer measurement timestamps and ages are recorded. Both current delay-reservation macros are 0; no fictitious history rewind or replay is performed. Default maximum measurement age is 500 ms.
- A repeated `pvtSequence` or `pressure_frame_count` must not increment the corresponding KF update counter. Position-unusable/velocity-usable NAV-PVT must still update velocity without requiring a GNSS origin.

### Host and static validation

- Host tests use origin `22.5892690°, 113.9670092°, 209 m`: `+0.00001°` latitude gives about `+1.107 m` North and `+0.00001°` longitude gives about `+1.028 m` East. Zero delta, positive Up, and ±180° longitude wrapping are also checked.
- Prediction checks cover zero delta-v, covariance growth/symmetry/non-negative diagonals, and `delta_v=[1,0,0] m/s, dt=0.01 s` producing approximately `v_E=1.0 m/s, p_E=0.005 m`.
- Separate tests cover GNSS position only, GNSS velocity only, barometer Up update and velocity cross-covariance, accepted/soft/hard NIS, NaN/Inf/illegal dt, and non-SPD recovery. Legacy SAMPLE/EVENT/STATS payload constants remain `196/12/16` bytes; ESTIMATOR is `136` bytes.
- Static integration checks must confirm sequence-based deduplication, permanent per-mission origin failure behavior, GNSS position-before-velocity ordering, pressure-after-GNSS ordering, and that KF results never write into `InsMechanizationContext`.

### Hardware stationary test

1. Keep the vehicle stationary before START until at least 50 usable GNSS PVT frames and 50 new pressure frames have accumulated; record fix, hAcc/vAcc/sAcc, origin flags, sample gaps, and pressure stability.
2. Send START and confirm the KF state begins at zero, both origins remain frozen, Pure INS continues its original independent output, and prediction queue overflow remains zero.
3. Hold stationary for at least five minutes. Record KF position/velocity, all six P diagonals, three NIS values, accepted/soft/rejected counts, measurement ages, health flags, queue overflow, GNSS checksum errors, and TF logger overflow/errors.
4. Repeat with GNSS position intentionally unusable while velocity remains usable; then repeat with no GNSS origin and with no barometer origin. Confirm only the dependent measurement path is disabled.
5. Power-cycle and verify AIR/LINK/IMU/GNSS local commands, LoRa, GNSS stream/rate, and original log record parsing have no regression. Compilation/static checks are not hardware validation.

Parameters still requiring real-data tuning are the three process acceleration standard deviations, GNSS accuracy scale and floors, barometer standard deviation, NIS thresholds/max R scale, origin sample/window conditions, and measurement-age limits. Preserve the logged acceptance/rejection counts, NIS distributions, P diagonals, measurement ages, origin flags, queue overflows, and GNSS accuracy fields for each tuning run.

## LoRa physical configuration check

- Preamble is 16 symbols.
- SX1280/SX1281 encoded `PreambleLength` is `0x18`.
- Do not configure `LORA_CFG_PREAMBLE_LEN` as direct decimal `16U`.

## Historical radio phase check

1. Power on without sending START.
   - No `AIR_TYPE_FLIGHT_STATE` (`0x10`, 50 bytes) may be transmitted.
   - With `FC_RADIO_PRESTART_QUAT_TELEM_ENABLE=1`, expect `AIR_TYPE_QUAT_STATE` (`0x11`, 14 bytes) every 200 ms when the link is idle.
2. Send PING, LOCK and UNLOCK with their required tokens; each command must receive ACK.
3. Send an unknown command; expect `AIR_ACK_RESULT_BAD_CMD`.
4. Send a command with an invalid token; expect `AIR_ACK_RESULT_BAD_TOKEN`.
5. Send START with token `0xA55A3CC3`.
   - Expect `AIR_ACK_RESULT_OK`.
   - Expect `AIR_STATUS_MISSION_START` three times at 50 ms intervals.
   - Expect `AIR_TYPE_FLIGHT_STATE` (`0x10`, 50 bytes) at 5 Hz.
   - No further `AIR_TYPE_QUAT_STATE` packets may be transmitted.

## Mission-relative time check

1. Power on and wait at least 10 seconds before sending START.
2. Verify `AIR_STATUS_MISSION_START.time_ms` is 0.
3. Verify the first `AIR_TYPE_FLIGHT_STATE.time_ms` is close to 0 rather than the system uptime near 10000 ms.
4. Verify later FLIGHT_STATE timestamps advance with real mission time at approximately 200 ms intervals.
5. If one telemetry period is skipped because the radio is busy, verify the next timestamp reflects elapsed mission time, for example 400 ms to 800 ms, without a fabricated intermediate timestamp.
6. Repeat the identical START command and verify the mission time is not reset.
7. Verify START-before `AIR_TYPE_QUAT_STATE.time_ms` and ACK timestamps retain their existing system-time semantics.

Hardware results must be recorded from serial logs, a logic analyzer, or a two-node radio test; static checks and compilation are not hardware validation.

## JY901B ORIENT=1 九轴惯导验证

实物已确认 JY901B `ORIENT=1` 原始 WXYZ 能正确驱动地面站三轴姿态，且与逻辑加速度/角速度 XYZ 使用同一机体系。当前九轴惯导必须满足 `q_nb=normalize(q_raw)`，不取共轭、不做固定安装旋转。

### 配置确认

1. 上电并确认诊断快照显示 boot config 已启用、期望算法正确、期望 orientation 为 1。
2. 用串口日志或逻辑分析仪确认 ORIENT 写命令为 `FF AA 23 01 00`。
3. 确认总体配置完成并出现 `IMU_CONFIG_ORIENT_VERTICAL_OK`；若出现 `IMU_CONFIG_ORIENT_FAILED`，停止后续姿态验收。
4. 配置完成后等待至少 1 秒，不立即使用模块尚未稳定的输出判断方向。
5. 确认 IMU online，`QuaternionFrameCount` 持续增加，并持续收到 `0x59` 四元数帧。

### 标准安装

JY901B Y 轴箭头竖直向上；该方向沿火箭纵轴并指向箭头。保持静止后记录原始 Q0/Q1/Q2/Q3、原始陀螺 XYZ、上位机锥体和 R/P/Y。

### 单轴旋转

保持双矢量校准关闭，分别绕 JY901B X、Y、Z 正方向缓慢旋转。每次记录原始 Q0/Q1/Q2/Q3、上位机锥体动作、R/P/Y 和原始陀螺 XYZ。重点确认绕 JY901B Y 轴时，上位机锥体是否绕模型 Z 轴/火箭纵轴自转。

### 加速度和角速度轴

分别沿三个物理轴晃动或转动，确认 LoRa `ax/ay/az`、`gx/gy/gz` 保持 JY901B 逻辑 X/Y/Z 顺序，不出现软件轴交换。上电零偏完成后，数值应为补偿后物理量按当前量程重新量化的 `int16_t`；字段长度和顺序不变。

### 测试 A：JY 姿态模式

设置 `INS_ATTITUDE_SOURCE=INS_ATTITUDE_SOURCE_JY901B_RAW`，依次执行 15 秒静止和 15 秒剧烈运动：

1. START 前确认上位机姿态正常，速度和位置不积分；
2. START 瞬间确认速度、位置清零且姿态无跳变；
3. START 后确认短四元数包停止，完整遥测四元数仍为 JY 原始 Q15；
4. 对比 BIN `q_raw/q_nb`，二者应表示同一姿态，允许归一化和 `q/-q` 连续性造成整体变号；
5. 记录最终速度、位置、导航系加速度和 JY 四元数。

### 测试 B：软件传播模式

设置 `INS_ATTITUDE_SOURCE=INS_ATTITUDE_SOURCE_SOFTWARE_PROPAGATION`，用完全相同的安装和动作重复测试 A：

1. START 前姿态必须仍来自 JY 九轴四元数，速度和位置不积分；
2. START 瞬间以最新 JY `q_nb` 初始化软件姿态，清零速度、位置和机械化历史，地面站姿态无明显跳变；
3. START 后软件 `q_nb` 只跟随原始陀螺传播，不被加速度、磁场或后续 JY 四元数拉回；
4. BIN 中 `q_raw` 继续记录实时 JY 姿态，`q_nb` 记录软件传播姿态；完整遥测使用软件 `q_nb` 量化值；
5. 分别绕逻辑 X/Y/Z 正转，确认传播方向正确；快速多轴摆动时检查二阶锥运动补偿；
6. 记录最终速度、位置和姿态，并重点比较两种模式剧烈运动 15 秒后的速度、位置误差。

两种模式都应在 identity 和多个倾斜静止姿态下满足 `rotate(q_nb, specific_force_b)≈[0,0,+g]`，重力补偿后的导航系加速度接近零。

### 样本间隔异常

在软件传播模式制造一次超出 `INS_SAMPLE_DT_MIN_S..INS_SAMPLE_DT_MAX_S` 的间隔，确认置位 `INS_HEALTH_SAMPLE_GAP`、清空并重建两子区间历史，同时保持最后有效软件姿态；不得跳回当前 JY 四元数。

### Host 与静态检查

Host 测试必须位于工程目录外，执行后删除，且不得写入 `.eide/eide.yml` 或 `Makefile`。至少覆盖：

- 两个姿态来源宏均可编译，非法值触发编译错误；
- 旋转向量零值、小角度和正常角度分支；机体系增量必须右乘；
- 二阶锥运动项的叉乘符号和精确 `2/3` 系数；恒定角速度、10000 次传播后单位模长；
- START 初值复制、JY/软件来源切换、软件模式忽略后续 JY 四元数、样本间隔保持传播姿态；
- identity/倾斜静止重力补偿、无加速度/磁场姿态修正；
- START 前短包始终使用 JY 原始 Q15，START 后完整包按来源宏选择，软件浮点四元数先整体归一化再四舍五入并饱和到 Q15；
- AIR 类型、固定长度、字段顺序和偏移全部不变。

## 六轴逻辑机体系与 TRIAD 验收

以下项目仅在六轴构建并将 `INS_SIX_AXIS_ALIGNMENT_ENABLE` 设为 1 后执行；九轴主路径不运行 TRIAD。若默认算法配置为六轴且对准宏为 0，编译必须失败。

### Host 数学检查

Host 测试源不得放入飞控工程目录或加入 EIDE/Makefile。测试应在工程外临时创建，单独链接 `attitude_frame.c`、`attitude_triad.c` 和 `ins_mechanization.c`，执行后删除。

必须覆盖：JY901B 原始四元数归一化与 `q_rs` 求解、`q_rb=q_rs`、旋转矩阵转四元数各数值分支、标准摆放 TRIAD 单位姿态、0°/东偏 10°磁偏角、六轴 `q_nr` 组合、逻辑 X/Y/Z 直接作为机体系，以及静止比力/重力抵消。

### 上板方向与命令检查

标准安装：JY901B 使用 `ORIENT=1`，Y 轴箭头沿火箭纵轴并指向箭头；JY901B 逻辑 X/Y/Z 就是飞控机体系 X/Y/Z。

1. 确认 BIN 原始 `acc_raw/gyro_raw/mag_raw/q_raw` 仍来自 JY901B 原始逻辑轴；浮点 `accel_b/gyro_b/mag_b` 与逻辑轴同向，其中加速度和角速度已应用上电零偏，磁场已应用 MCU 端偏置与比例校准。
2. 六轴模式先在无候选时发送 UNLOCK，预期 BUSY 且保持 LOCKED；静止等待 `ALIGNMENT_CANDIDATE_READY` 后以新 seq 发送 UNLOCK，预期 OK 和 UNLOCKED。
3. UNLOCK 后立即发送 START 时，若候选尚未被 `InsTask` 应用，预期 BUSY；出现 `ALIGNMENT_APPLIED` 后 START 才允许 OK。
4. 对准后确认 `q_nr×q_rb_alignment≈q_nb_absolute`；静止时 `specific_force_enu≈[0,0,+g]`，加入 ENU 重力后线加速度接近零。
5. 分别绕逻辑 X/Y/Z 正方向转动，确认角速度、六轴姿态和 AIR 字段均保持同轴，不发生软件置换。
6. 重复相同 seq 的 UNLOCK 不重复应用；新 seq UNLOCK 使用当时最新候选重新对准。
7. 配置缓存算法值与 `IMU_DEFAULT_ALGORITHM_VALUE` 不同应置 mismatch 健康位、记录事件并使 UNLOCK/START BUSY；缓存无效应置 unverified 健康位。

## Phase 3 第一版纯惯导基础设施（历史实现基线，代码保留）

日期：2026-07-13

### 已实现

- 固定元素 SPSC 队列，满时只丢弃完整 item；
- 基于 HAL 现有 1MHz TIM1 timebase 的单调微秒时间；
- JY901B 各类型独立帧计数、时间戳和 DeviceTask 上下文回调；
- 保存 JY901B 原始逻辑轴、机体系物理量及各字段时间戳的完整 IMU 样本队列；
- JY901B `ORIENT=1` 逻辑轴与飞控机体系一致，九轴和六轴均不执行额外安装轴置换；六轴 TRIAD 代码保留；
- START 原始四元数就绪门控、二阶划桨补偿、速度和位置积分保留；新增姿态来源宏、START 姿态初始化、二阶锥运动补偿和原始陀螺软件传播；
- `InsOutputSnapshot` 双缓冲只读发布与 START 请求；
- LoRa 保留最新快照与 50ms stale 统计；短包始终取 JY 原始 Q15，完整包在 RAW 模式取原始 Q15、在软件模式取传播快照，raw acc/gyro 继续取 JY901B 原生 XYZ；
- Logger 单 BIN 文件、逐字段 little-endian 序列化、4KB 缓存和周期同步。

### 已静态检查

- 重构前的`Radio_QuatStateProcess()`始终读取`QuaternionRawQ15[0..3]`，`Radio_Stage2FlightStateBuild()`由当时的姿态来源配置选择原始Q15或归一化软件快照；该事实仅作为历史验证记录；
- 重构前`RadioTask`未调用任何惯导SPSC Pop接口；SilverStar对应约束由`TelemetryService`继续保持；
- FatFs 业务写入只位于`LoggerTask`；
- UART DMA 字节环形缓冲区文件未修改；
- AIR 类型值、固定长度和字段偏移未修改。

四元数方向修正后的静态检查还必须确认：

- JY901B 原始 `q_raw_sr` 在驱动、样本队列和 BIN 日志中原样保留；
- 六轴 `q_rb=q_rs`；九轴 `AttitudeFrame_NineAxisTransform()` 直接归一化原始 WXYZ；
- `InsTask` 在机械化成功后统一发布和记录 `state.q_nb`；软件模式的 START 后 LoRa 从 `InsOutputSnapshot.q_nb` 生成四元数；
- 重构前`INS_SIX_AXIS_ALIGNMENT_ENABLE=0`时，Radio的UNLOCK不调用对准请求且START不读取`alignment_valid`；SilverStar的START统一由Lifecycle事务处理；
- `.eide/eide.yml` 与 `Makefile` 均不包含 Host tests；工程目录内不保留测试源或 `tests` 目录。

### 已编译

```text
工程外姿态传播 Host 测试：RAW 127 checks、SOFTWARE 137 checks、来源/遥测/布局静态检查 39 checks；非法来源宏编译失败符合预期（临时文件执行后删除）

PowerShell 原生删除 build 目录后执行 mingw32-make -j
text=108484, data=152, bss=105640
```

两个来源宏的 ARM 语法检查、旋转向量、右乘传播、二阶锥运动、恒定角速度、长期单位模长、来源切换、JY 跳变隔离、样本间隔保持、identity/倾斜重力补偿、Q15 量化和 AIR 固定布局检查通过；ARM GCC clean build、链接、HEX/BIN 生成通过。

### 后续非阻塞回归验证

当前纯惯导软件链路和台架开发目标已完成，允许进入 Phase 4。以下飞行数据与长时间硬件项目继续用于回归验证和误差分析，但不再阻塞 GNSS 验收与 EKF 开发：

- RAW 与 SOFTWARE 两种模式各 15 秒静止和 15 秒同动作剧烈运动后的姿态、导航系加速度、速度和位置对比；
- 数个倾斜静止姿态下重力是否泄漏到 East/North；
- 100 个静止加速度/磁场样本能否稳定形成候选，以及磁场过期、移动和突变拒绝；
- 六轴 UNLOCK/START BUSY 门控、重复 seq 去重、新 seq 重新对准；
- 软件传播的三轴正转方向、快速多轴摆动时锥运动补偿，以及 START 后与 JY `q_raw` 的差异；
- 静止速度/位置漂移量；
- 已知方向平移和转动的轴、符号和单位；
- 200Hz 输入下约 100Hz 惯导更新是否持续无积压；
- LoRa 5Hz 遥测的内部 `update_seq` 推进、暂停 InsTask 后 stale 计数及堵塞恢复；
- TF 卡长时间单文件写入、拔卡恢复和错误计数。

静态检查与编译结果不能替代上述硬件验收。


## SilverStar 0.0.5新增验证

- SSLOG0文件头和逐记录CRC32；
- 4 KB聚合写与随机断电恢复；
- Provider Native样本完整率和sequence连续性；
- Pure INS/KF6各日志独立开关；
- System/User注册与配置唯一性；
- Host离线重放与在线结果一致性。
