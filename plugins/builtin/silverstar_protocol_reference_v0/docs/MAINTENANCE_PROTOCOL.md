# SilverStar 0.0.9 本机维护协议

> **项目：SilverStar**
> **文档版本：0.0.9**
> **状态：Draft / 未发布**

## 1. 边界

本协议是System Console处理的ASCII行协议，与AIR二进制协议互不复用。Console Interface只负责非阻塞字节输入、输出和链路健康；SerialTask形成完整行并调用System Console，不直接访问设备寄存器，也不推进GNSS、IMU或Telemetry解析器。

关键词使用本文给出的ASCII大写形式，token以空格或制表符分隔，CR、LF或CRLF结束。通常最多接受三个token；`SYSTEM CONSOLE IO CLEAR`是唯一合法的四token命令。任何其他多余token均返回`BAD_FORMAT/TOKEN_COUNT`。`STATUS`、`INFO`和`CAPABILITIES`不接受第三token。

成功与失败格式为：

```text
OK <MODULE> <COMMAND> key=value ...
ERR <MODULE> <COMMAND> code=<ERROR> reason=<TEXT>
```

## 2. 正式模块

正式模块为：

```text
SYSTEM IMU GNSS BARO MAG ATTITUDE ESTIMATOR KF INS CAL ALIGN
TELEMETRY POWER OUTPUT LOG TIME
```

0.0.9尚未发布，不保留旧维护命令兼容层。`TF STATUS`、`TF HEALTH`、`TF TEST`和`TF SYNC`均不是正式命令；`TF`作为未知模块返回`BAD_MODULE/UNKNOWN`。日志系统只使用与介质无关的`LOG`模块名。

当前实现没有`HELP`命令或帮助文本，不得文档化并不存在的`SYSTEM HELP`。

## 3. 公共命令语义

| 命令 | 语义 | I/O | 不支持时 |
|---|---|---|---|
| `<MODULE> INFO` | Device、model、driver等静态信息 | 不主动读取设备 | `UNSUPPORTED/DEVICE` |
| `<MODULE> STATUS` | 初始化、启动、在线、当前健康、样本及错误摘要 | 快照读取 | `UNSUPPORTED/DEVICE` |
| `<MODULE> CAPABILITIES` | 公共capability mask | 快照读取 | `UNSUPPORTED/DEVICE` |
| `<MODULE> SAMPLE` | 兼容简略样本 | 快照读取 | `UNSUPPORTED/DEVICE` |
| `<MODULE> SAMPLE DETAIL` | 支持性、有效性、质量和拒绝原因 | 快照读取 | 当前仅GNSS和BARO支持 |
| `<MODULE> IO` | 物理Transport、DMA、Parser、完整性和错误累计计数 | 快照读取 | `UNSUPPORTED/DEVICE` |
| `<MODULE> IO CLEAR` | 把当前累计快照设为新的维护显示基线 | 只更新System Console基线 | `UNSUPPORTED/DEVICE` |
| `<MODULE> CONFIG SHOW` | 软件侧有效、缓存或目标配置 | 不主动读取硬件 | `UNSUPPORTED/DEVICE` |
| `<MODULE> CONFIG READ` | 主动从真实硬件回读配置 | 设备事务 | 当前仅GNSS支持 |
| `<MODULE> CONFIG VERIFY` | 真实硬件配置与System/User当前目标配置比较 | 设备事务 | 无所有者安全实现时`UNSUPPORTED/DEVICE_OPERATION` |
| `<MODULE> CONFIG APPLY` | 应用System/User当前目标配置 | 写事务 | 无所有者安全实现时`UNSUPPORTED/DEVICE_OPERATION` |

`CONFIG SHOW`不得主动访问硬件；Device不维护软件侧有效配置时返回`UNSUPPORTED`，不得伪造。`CONFIG READ`不得退化成`CONFIG SHOW`，非GNSS模块执行`CONFIG READ`返回`UNSUPPORTED/HARDWARE_READ`。`CONFIG VERIFY`和`CONFIG APPLY`是正式、可识别的统一语义，但当前Device没有相应运行期所有者事务时返回`UNSUPPORTED/DEVICE_OPERATION`。`CONFIG APPLY`属于写操作，FLIGHT/RECOVERY首先返回`LOCKED/FLIGHT`。

## 4. 当前实际命令表

| 模块 | 当前正式可识别命令 |
|---|---|
| SYSTEM | `INFO`、`STATUS`、`CAPABILITIES`、`PROFILE`、`READY`、`START`、`START RESULT`、`STARTUP`、`STARTUP IMU`、`STARTUP GNSS`、`STARTUP TELEMETRY`、`CONSOLE IO`、`CONSOLE IO CLEAR` |
| IMU | `INFO`、`STATUS`、`CAPABILITIES`、`SAMPLE`、`IO`、`IO CLEAR`、`CONFIG SHOW` |
| GNSS | `INFO`、`STATUS`、`CAPABILITIES`、`SAMPLE`、`SAMPLE DETAIL`、`IO`、`IO CLEAR`、`CONFIG SHOW`、`CONFIG READ`、`CONFIG VERIFY`、`CONFIG APPLY`、`NAV SAT`、`MON RF` |
| BARO | `INFO`、`STATUS`、`CAPABILITIES`、`SAMPLE`、`SAMPLE DETAIL`、`IO`、`IO CLEAR`、`CONFIG SHOW` |
| MAG | `INFO`、`STATUS`、`CAPABILITIES`、`SAMPLE`、`IO`、`IO CLEAR`、`CONFIG SHOW` |
| ATTITUDE | `INFO`、`STATUS`、`CAPABILITIES`、`SAMPLE`、`IO`、`IO CLEAR`、`CONFIG SHOW` |
| ESTIMATOR | `STATUS`、`GNSS`、`BARO` |
| KF | `STATUS` |
| INS | `STATUS` |
| CAL | `STATUS`、`DETAIL`、`START NONE`、`START ONE_FACE`、`START SIX_FACE`、`FACE X+`、`FACE X-`、`FACE Y+`、`FACE Y-`、`FACE Z+`、`FACE Z-`、`STOP`、`RESET` |
| ALIGN | `STATUS`、`DETAIL`、`START`、`STOP`、`RESET` |
| TELEMETRY | `INFO`、`STATUS`、`CAPABILITIES`、`IO`、`IO CLEAR` |
| POWER | `INFO`、`STATUS`、`CAPABILITIES`、`SAMPLE`、`CONFIG SHOW` |
| OUTPUT | `STATUS` |
| LOG | `INFO`、`STATUS` |
| TIME | `STATUS` |

表中`CONFIG VERIFY/APPLY`表示命令语义已被Parser识别，不表示当前每个Device均实现相应硬件事务；能力缺失时按第3节返回`UNSUPPORTED`。`SYSTEM SELFTEST`、`SYSTEM PARAM ...`、`<DEVICE> SELFTEST`和`<DEVICE> PARAM ...`保留明确拒绝路径并返回`UNSUPPORTED`，不是0.0.9已实现功能。未知命令返回`BAD_COMMAND`，未知模块返回`BAD_MODULE`。

## 5. 生命周期权限

PREFLIGHT/READY允许上述读取命令、`IO CLEAR`、全部`CAL`命令、`ALIGN START`、`ALIGN STOP`、`ALIGN RESET`以及`SYSTEM START`。FLIGHT/RECOVERY继续允许INFO、STATUS、CAPABILITIES、SAMPLE、SAMPLE DETAIL、IO、IO CLEAR、CONFIG SHOW、CONFIG READ、CONFIG VERIFY、SYSTEM STARTUP/PROFILE/READY、GNSS NAV SAT、GNSS MON RF、ESTIMATOR STATUS、ESTIMATOR GNSS、ESTIMATOR BARO、KF STATUS、INS STATUS、CAL STATUS、CAL DETAIL、ALIGN STATUS、ALIGN DETAIL和TIME STATUS。`CAL START/FACE/STOP/RESET`及`ALIGN START/STOP/RESET`在FLIGHT/RECOVERY返回锁定错误。`IO CLEAR`只更新维护显示基线，不是设备写入。配置写入或未列入的操作返回：

```text
ERR SYSTEM <COMMAND> code=LOCKED reason=FLIGHT
```

只读许可不表示模块必须支持该能力；能力缺失仍返回`UNSUPPORTED`。

## 6. GNSS运行期事务

`GNSS CONFIG READ`、`GNSS NAV SAT`和`GNSS MON RF`在启动完成后只向NEO-M9N Device的单槽事务提交请求。SerialTask可以有限等待完整响应，但不得调用`SystemGnss_Process()`。DeviceTask每周期先照常处理IMU，再消费GNSS RX并推进事务一个有限步骤；不得在DeviceTask内使用等待循环或延时。

CONFIG READ依次读取UART、协议、NAV-PVT、rate、dynamic model和signals六组。组读取失败后逐key回退也跨DeviceTask周期推进。事务具有唯一`transaction_id`；第二个请求返回`BUSY`；NAK、checksum、畸形响应、超时或RX discontinuity结束当前事务并允许后续请求复用slot。无关NAV-PVT不能完成VALGET、NAV-SAT或MON-RF事务。

典型硬件回读响应包含：

```text
OK GNSS CONFIG READ source=HARDWARE read_result=<result> valid_mask=<mask> ... transaction_id=<id> detailed_result=<detail>
```

`CONFIG SHOW`固定标记`source=CACHE`。部分读取成功只由`valid_mask`声明，禁止用缓存补齐失败字段。

## 7. SAMPLE DETAIL

`GNSS SAMPLE DETAIL`输出device/model、`supported_mask`、`valid_mask`、fix字段、位置/高度/精度字段、`age_ms`、`position_usable`、速度mask、位置/速度拒绝mask和`quality_degraded`。不支持显示`UNSUPPORTED`，支持但当前无效显示`INVALID`，不得用0冒充缺失值。

`BARO SAMPLE DETAIL`输出device/model、支持/存在/配置状态、字段mask、样本新鲜度、压力、温度、高度和`status`。`status`区分`UNSUPPORTED`、`NOT_PRESENT`、`NOT_CONFIGURED`、`NOT_READY`、`STALE`、`INVALID`、`FAILED`和`OK`。

`ESTIMATOR BARO`输出原点采集/冻结、相对高度、量测方差、innovation、NIS、接受/软化/拒绝/跳过计数及最近跳过原因。

`ESTIMATOR STATUS`输出当前生命周期`state`、`initialized`、`started`、`mode`、`attitude_source`、`position_source`、`imu_prediction_count`和`last_state_timestamp`。`mode`为`PURE_INS`或`KF6`；当前姿态源为独立软件INS，KF不得向Pure INS姿态回注。

`ESTIMATOR GNSS`先按既有顺序输出`supported`、冻结的`fusion_enabled`和`origin_valid`，冻结原点经纬高，位置/速度聚合更新与接受/拒绝计数，以及`last_update_state`、`last_skip_reason`、量测/状态时间和量测年龄。旧字段不得删除、改名或重新排序。其后追加position EN/U与velocity EN/U四组NIS、六个innovation、四组effective std、六个P对角、分组接受/拒绝计数、四组reject streak、`reacquire_active_mask/reacquire_count`及最近inflation group/factor/attempt。状态至少区分`DISABLED`、`WAIT_ORIGIN`、`WAIT_SAMPLE`、`ACCEPTED`、`REJECTED`、`STALE`和`INVALID`。若START前未形成合格原点，START后必须显示`fusion_enabled=0`、`last_update_state=DISABLED`和`reason=NO_PREFLIGHT_ORIGIN`；飞行中后续获得fix不得改变该许可或重建原点，内部reacquisition也不得绕过这一限制。

`KF STATUS`输出`initialized`、固定`state_dimension=6`、预测计数、序贯更新总数、GNSS位置/速度及气压更新计数、最近更新类型/时间和现有拒绝计数的汇总`innovation_reject_count`；旧字段之后只追加`reacquire_count`和`reacquire_active_mask`摘要。接受计数包含正常接受与软化接受；GNSS位置和速度仍按历元各最多计一次，不因EN/U拆分翻倍。该命令不改变KF状态、门控或reacquisition。

`INS STATUS`输出初始化/任务启动、姿态就绪、四元数/速度/位置有效性、软件姿态传播、Calibration correction就绪、当前Calibration有效样本数和最近更新时间。为保持既有字段名，输出仍使用`bias_ready/bias_samples`，其正式数据源已经是SystemCalibration。该命令不输出额外算法内部变量。

`CAL STATUS`输出`mode/state/ready/current_face/last_face/last_face_result/completed_face_mask/samples`。`CAL DETAIL`在此基础上输出accel bias/scale、gyro bias/scale、reject/retry、wait reason和六面均值。`CAL START NONE`完成一次显式identity Calibration并立即READY；`CAL START ONE_FACE`启动System/User所选重力方向的现有静态窗口；`CAL START SIX_FACE`始终清空全部旧六面结果并进入`WAIT_FACE`，之后由`CAL FACE X+|X-|Y+|Y-|Z+|Z-`逐面采集。`CAL FACE`在SIX_FACE的`WAIT_FACE`或`READY`均可重采已完成面；只有请求与最新静止姿态检查全部通过时才清对应completed bit、使Calibration/Alignment不再READY并保留其他五面，未接受请求不清bit。`accepted=1`只表示请求已接受，不表示该面完成。真正完成后Console异步输出`EVENT CAL FACE face=<...> result=PASSED ...`；立即拒绝或该面事务失败输出`result=FAILED reason=<...>`。ONE_FACE/NONE或六面总解算最终完成后异步输出`EVENT CAL COMPLETE mode=<...> result=PASSED|FAILED ...`。`CAL STOP`停止采样并保留已完成六面，`CAL RESET`清空结果回到`IDLE/NOT_SELECTED`。所有`CAL START ...`在START前都可重新开始；任何`CAL START ...`或`CAL RESET`均立即使现有Alignment失效。完整语义见[`SYSTEM_CALIBRATION.md`](SYSTEM_CALIBRATION.md)。

`ALIGN STATUS`输出总体`state/ready/config`、32-bit `capability/selected/required/ready` mask和配置诊断，然后只遍历selected sources追加`<key>=<state>`。`ALIGN DETAIL`首行输出总体和mask，随后每个selected source输出一行`ALIGN SOURCE name=<key> ...`专用详情；未选择GNSS时不得出现`gnss=...`，未来选择MAG时主命令无需改动即可出现`mag=...`。`ALIGN START`返回`accepted=1`只表示对准事务已启动；只有required mask全部ready才异步输出`EVENT ALIGN COMPLETE result=PASSED`，事件同样只显示selected sources。`ALIGN START`只在Calibration READY后可用，否则返回`NOT_READY/CALIBRATION_REQUIRED`；它清除并重新采集本次任务姿态与原点。`ALIGN STOP/RESET`不清除Calibration mode、bias或scale。完整语义见[`SYSTEM_ALIGNMENT.md`](SYSTEM_ALIGNMENT.md)。

`SYSTEM READY`保留既有字段，并输出`calibration_ready`、`calibration_mode`、`alignment_ready`和`capability_required_for_air_start=1`。兼容字段`imu_alignment_ready`在0.0.9中等于`calibration_ready`，不再表示Alignment内部子模块；各`<key>_alignment_ready`字段只对selected sources动态输出。正式依赖为`Calibration READY -> Alignment READY -> START READY`。Capability ACK是AIR会话状态，不降低本机`SYSTEM READY ready`；本机`SYSTEM START`不要求AIR Capability握手。当前GNSS selected但optional，气压selected且required；无预飞GNSS原点不阻止READY，但本次任务`gnss_fusion_enabled=0`，气压未ready则Alignment不得READY。

`SYSTEM STACK`只读输出`DeviceTask/InsTask/EstimatorTask/FlightTask/LoggerTask/SerialTask/RadioTask`的`high_water_mark/allocation`，格式为`Task=<high_water_words>/<allocation_words>`并明确`unit=words`。未创建任务由`valid_mask`区分。该命令仅用于栈余量诊断，不参与System Health、READY、START或任何飞行状态判定。

`ESTIMATOR BARO`中的`WAIT_STATE_CATCHUP`表示气压样本时间晚于当前KF状态、正在等待惯性预测追上；这是正常pending等待，不是融合失败，等待期间不重复增加`skipped_count`。

## 8. IO诊断

正式物理I/O查询包括：

```text
IMU IO
GNSS IO
BARO IO
MAG IO
ATTITUDE IO
TELEMETRY IO
SYSTEM CONSOLE IO
```

BARO、MAG和ATTITUDE共用JY901B物理链路，返回相同UART统计并明确`owner=IMU`；它们不伪造独立Transport。GNSS追加UBX/NMEA统计，IMU追加JY901B合法帧、checksum和parser resync。Telemetry只读取TelemetryTask缓存的SPI/LoRa统计，不从Console路径访问SPI。

`IMU IO CLEAR`、`GNSS IO CLEAR`、`TELEMETRY IO CLEAR`和`SYSTEM CONSOLE IO CLEAR`保存当前累计快照作为新基线，之后`IO`显示32位无符号相对增量。BARO、MAG和ATTITUDE与IMU共享JY901B物理基线，因此任一逻辑模块执行`IO CLEAR`都会同时重置四个维护视图的相对零点。没有公共I/O诊断能力的模块返回`UNSUPPORTED`。

清基线不改写Device内部原始累计计数或断流序号，不重启设备或DMA，不清Parser，不丢弃数据，不改变当前健康状态。启动配置产生的历史重启或断流因此可以从维护视图排除，同时运行期新增错误仍继续增长。Console执行清零确认本身可能在基线建立后增加TX字节计数。

## 9. LOG

`LOG INFO`返回当前Storage Device名称及通用接口标识；`LOG STATUS`读取`SystemStorageHealth`，包含initialized、mounted、open、healthy、writes、syncs和errors。接口不公开SDIO、FatFs或具体卡类型。当前公共Storage接口没有独立Transport诊断，因此`LOG IO`和`LOG IO CLEAR`返回`UNSUPPORTED`。LOG失败仅降级，不阻止READY、START、SELFTEST、GNSS或INS/KF。

## 10. Calibration diagnostic 与 Alignment STALE

Calibration 等待/重采原因使用异步边沿文本：

```text
EVENT CAL DIAG face=<X+|X-|Y+|Y-|Z+|Z-|NONE> reason=<NONE|NO_STREAM|GYRO_MOVING|ACCEL_MAGNITUDE|GRAVITY_DIRECTION|VARIANCE|SAMPLE_GAP>
```

只有 `(face, reason)` 变化时输出；相同 reason 不按 IMU sample 刷屏，非 NONE 清除时输出一次 `reason=NONE`。该文本不替代 `CAL STATUS/DETAIL`，后者继续提供 wait_reason、reject、retry 和窗口统计；窗口自动 retry 不等于 Calibration FAILED。

Alignment总体状态增加`STALE`。`ALIGN STATUS`与`ALIGN DETAIL`追加`stale_reason=NONE|MOTION`；source行和`ready_mask`仍表示局部source-ready，不因整体STALE伪造Device failure。进入STALE边沿输出：

```text
EVENT ALIGN STALE reason=MOTION ready_mask=0x00000005
```

此时 `alignment_ready=0`，`SYSTEM READY` 重新变为未就绪，`SYSTEM START` 返回 `ALIGNMENT_REQUIRED`。状态锁存，不因重新静止自动恢复；必须执行新的 `ALIGN START`。START 后 guard 停止，`ALIGN STATUS/DETAIL` 仍为只读。

以上异步输出均由现有 System Console/SerialTask 非阻塞发送路径产生，不增加线程，不由 Calibration/Alignment 算法直接访问 UART。

## 11. 格式错误示例

```text
GNSS STATUS DETAIL
LOG STATUS EXTRA
SYSTEM READY EXTRA
SYSTEM STACK EXTRA
SYSTEM START RESULT EXTRA
```

均返回`BAD_FORMAT/TOKEN_COUNT`。Console RX发生断流时，未以CR/LF结束的半行必须丢弃，断流后的完整命令独立解析。
