# SilverStar Storage 与飞行日志协议

> 文档版本：0.0.9
> 日志容器：SSLOG0（profile id 0）
> 适用范围：SilverStar 0.0.9

## 1. 职责分层

```text
APP/System producers
    -> FlightLogRecord
LoggerBus
    -> bounded static normal/estimator queues
LoggerTask
    -> Protocol/SSLOG serialize + aggregate + flush
SystemLogSink Interface
    -> SilverStar 0.5 Log Sink Service
SystemStorage Interface
    -> SilverStar 0.5 Storage Service / FatFs / SDIO
```

`Protocol/SSLOG`不知道任务和Storage；LoggerBus不知道wire encoding、FatFs和文件名；LoggerTask不知道介质物理类型；System Console只公开`LOG`抽象，不接受`TF`别名。

当前TF/SDIO Storage和文件Log Sink实现位于`Board/SilverStar_0_5/Services`，因为它们是板级/FatFs glue。未来换介质只替换Board Service和Target选择，不改变System、LoggerBus或Maintenance命令。

## 2. 权威源码与解析器参考

固件运行时的权威声明和实现是：

```text
Protocol/SSLOG/Inc/sslog_records.h
Protocol/SSLOG/Src/sslog_records.c
```

它们以普通受控C源码定义Record ID、Record version、payload size、静态metadata，以及所有Record逐字段显式little-endian serializer/deserializer。`SslogRecords_PayloadSerialize()`与`SslogRecords_PayloadDeserialize()`对每个多字节整数和float bit pattern显式读写；`FlightLogRecord`及其payload union只属于进程内类型，禁止用`memcpy`、强制指针转换或`sizeof(C struct)`直接生成/读取wire payload。LoggerBus内部复制有界记录不构成wire编码，真正出入SSLOG字节流必须经过上述codec。

离线解析器参考资料位于：

- `Protocol/SSLOG/schema/sslog_schema.json`；
- `Protocol/SSLOG/schema/sslog_parser_metadata.json`。

这些JSON供电脑端解析器和人工审查参考，不进入固件构建，不在运行时解析，也不驱动authoritative Make。项目默认stream policy由`Generated/Src/project_log_config.c`拥有。当前工程不存在SSLOG生成脚本或`sslog-generate`/`sslog-check`目标，任何firmware build都不得启动Python。

## 3. 文件头

文件头固定64 bytes，全部little-endian：

| 偏移 | 长度 | 字段 |
|---:|---:|---|
| 0 | 8 | `SSLOG0` + 两个`0x00` |
| 8 | 2 | log profile id，当前0 |
| 10 | 2 | file header size=64 |
| 12 | 2 | record header size=24 |
| 14 | 2 | nominal IMU rate |
| 16 | 2 | nominal INS rate |
| 18 | 1 | coordinate frame=ENU |
| 19..21 | 3 | position axis order E/N/U |
| 22 | 1 | quaternion order WXYZ |
| 23 | 1 | Hamilton body-to-navigation语义 |
| 24 | 4 | local gravity，float32 |
| 28 | 8 | AIR兼容标识`AIR-NCRC` |
| 36 | 8 | firmware build tag，0.0.9为`SILV0009` |
| 44 | 2 | Record CRC size=4 |
| 46 | 2 | mechanization subsample count |
| 48..51 | 4 | firmware major/minor/patch/build |
| 52 | 2 | max serialized Record size |
| 54..59 | 6 | reserved，写0 |
| 60 | 4 | file header CRC32 |

CRC为CRC-32/ISO-HDLC（反射多项式`0xEDB88320`，初值/终值异或`0xFFFFFFFF`），与常用`zlib.crc32()`结果一致。

## 4. Record格式与version

```text
u32 sync                 0x31474C46，文件字节"FLG1"
u8  record_version       来自静态Record metadata
u8  record_type
u16 payload_length
u32 record_sequence
u64 timestamp_us
u32 valid_flags
u8  payload[payload_length]
u32 crc32                覆盖header + payload
```

公共header固定24 bytes，尾CRC固定4 bytes。解析器对未知`record_type`或未知`record_version`按`payload_length`和CRC安全跳过；CRC失败时扫描下一sync；断电造成的末尾半条Record忽略。

`record_version`只属于单个Record schema，不是SSLOG容器版本。当前所有Record为version 0。`MISSION_CONFIG` payload不再保存第二个冗余version字段；唯一权威版本就是公共header/静态metadata。

新增独立语义优先分配新Record ID；同一ID发生不兼容payload变化才递增该Record version。只有文件头、公共Record framing、CRC或同步恢复规则整体不兼容时才定义SSLOG1。

## 5. Record目录

| ID | 名称 | payload bytes | 默认策略 |
|---:|---|---:|---|
| 0x01 | SAMPLE | 196 | disabled/decimation |
| 0x02 | EVENT | 12 | event |
| 0x03 | STATS | 16 | disabled/periodic |
| 0x04 | ESTIMATOR | 136 | decimation=4 |
| 0x05 | SYSTEM_CONFIG | 132 | one-shot |
| 0x06 | RAW_SENSOR | 132 | disabled/decimation |
| 0x07 | PURE_INS | 68 | decimation=1 |
| 0x08 | KF6_DIAGNOSTIC | 104 | decimation=4 |
| 0x09 | KF6_FULL_P | 84 | decimation=4 |
| 0x0A | POWER | 44 | periodic |
| 0x0B | HEALTH | 40 | periodic |
| 0x0C | TELEMETRY_DIAG | 48 | periodic |
| 0x0D | INITIAL_STATE | 144 | one-shot |
| 0x0E | IMU_NATIVE | 76 | disabled/decimation |
| 0x0F | GNSS_NATIVE | 80 | decimation=1 |
| 0x10 | BARO_NATIVE | 44 | decimation=1 |
| 0x11 | MAG_NATIVE | 56 | decimation=1；能力关闭时无producer |
| 0x12 | HW_QUAT_NATIVE | 44 | decimation=1 |
| 0x13 | INERTIAL_INCREMENT | 52 | decimation=1 |
| 0x14 | GNSS_MEASUREMENT | 72 | every |
| 0x15 | BARO_MEASUREMENT | 32 | every |
| 0x16 | IMU_CORRECTED | 60 | decimation=1 |
| 0x17 | CALIBRATION_RESULT | 72 | event |
| 0x18 | ALIGNMENT_RESULT | 96 | event |
| 0x19 | MISSION_CONFIG | 91 | one-shot |
| 0x1A | DEVICE_DESCRIPTOR | 24 | one-shot，每实例一条 |
| 0x1B | ALGORITHM_DESCRIPTOR | 16 | one-shot，每实例一条 |
| 0x1C | LOG_STREAM_DESCRIPTOR | 12 | one-shot，每stream一条 |

精确Record ID、字段、顺序、类型和wire codec以`sslog_records.*`为固件权威；默认stream参数以`project_log_config.c`为当前项目权威。schema和parser metadata是需要随协议源码同步审查的离线参考。最大payload为256 bytes，当前最大196 bytes。

## 6. Stream policy

0.0.9删除`SYSTEM_LOG_MASK_*` 32-bit瓶颈。`SystemLogPolicy`维护：

```c
typedef struct
{
    FlightLogRecordType record_type;
    uint8_t enabled;
    uint16_t decimation;
    uint32_t period_us;
    SslogStreamPolicy policy;
} SystemLogStreamConfig;
```

静态runtime表大小为`SSLOG_RECORD_COUNT`，不使用heap。默认值来自`ProjectLogConfig_StreamByIndexGet()`；START时冻结，rollback才允许解冻。策略包括EVERY、DECIMATION、PERIODIC、EVENT和ONE_SHOT。算法启用与算法日志启用独立；没有运行的数据源自然不会产生Record。

每个stream最终配置通过`LOG_STREAM_DESCRIPTOR`记录，离线工具不需要推断C宏。

## 7. Descriptor设计

旧`SYSTEM_CONFIG`中的固定device/provider ID数组、algorithm数组和log decimation数组已删除。`SYSTEM_CONFIG`只保存固件/Profile、配置digest、速率、队列容量、descriptor计数和最终Estimator参数。

- `DEVICE_DESCRIPTOR`：descriptor ID、class、instance、driver ID、flags、capability、rate、driver/model name hash；
- `ALGORITHM_DESCRIPTOR`：descriptor ID、class、instance、algorithm ID、flags、config digest、name hash；
- `LOG_STREAM_DESCRIPTOR`：record type/version、enabled、policy、decimation、period。

Target内部descriptor表仍有明确编译期容量上界，这是无heap内存证明；扩展实例通过多写Record完成，不受某个payload固定数组槽数限制。

## 8. 离线重放

默认重放层级：

1. `IMU_CORRECTED`：实际进入INS的Calibration后机体系加速度/角速度；
2. GNSS/Baro/Mag/Hardware Quaternion native公共样本；
3. `INERTIAL_INCREMENT`和Estimator实际量测；
4. Pure INS、KF6 state/diagnostic/P；
5. System/Mission配置、descriptor、Calibration、Alignment和Initial State。

正式默认不保证保存每个UART/UBX原始字节，也不把`IMU_NATIVE`当成离线重新标定的唯一输入。需要底层协议诊断时应定义新的可选RAW_DEVICE_FRAME类Record，不复用导航Record含义。

每条Record携带真实单调时间戳；解析器不得用标称频率重建时间。在线与Host重放应复用同一C Algorithm实现，Python只负责解析、调度、参数扫描和绘图。

## 9. 写盘、flush与收尾

LoggerTask使用静态Record buffer和aggregation buffer。完整Record才进入聚合；空间不足、关键Record或sync周期到达时批量写入。文件头、System/Mission config、descriptor、Initial State、关键Lifecycle/Calibration/Alignment事件应尽力及时flush。

Landing确认后先把LANDING EVENT可靠加入LoggerBus，再以landing timestamp建立post-landing grace截止时间。截止前继续记录正常尾段；截止后Bus拒绝新Push但不计作overflow，LoggerTask排空normal/estimator queue、写完aggregation、flush并结束session。临时I/O失败按策略重试，只有全部成功才锁存finalized。本次上电不再自动开启第二个session。

Storage/Log失败不得阻止、拒绝或回滚START、Deploy或Landing；它只进入Health、事件和丢弃计数。

## 10. 新Record流程

1. 在`sslog_records.h`分配未使用ID、version、payload size和metadata，在`project_log_config.c`声明当前项目默认policy；
2. 在`sslog_protocol.h`定义字段名、数组长度和类型相匹配的内存payload类型；
3. 在`sslog_records.c`增加逐字段显式little-endian serializer/deserializer；不得退回C struct直写wire；
4. 增加所有Record的encode-decode-encode字节一致性、长度、little-endian、CRC、buffer-small、bad version/type/size/CRC和queue overflow Host测试；
5. 若由新producer产生，增加LoggerBus窄Push接口与明确overflow行为；
6. 同步更新本文、schema和parser metadata参考资料；
7. 运行Host、architecture-check和Debug/Release目标构建，并确认构建日志没有Python/生成器调用。

禁止新增runtime serializer函数指针表、动态Record注册或JSON runtime parser。

## 11. 验收边界

Host测试覆盖28类payload双向codec字节往返、Record长度、endian、完整Record解码错误、CRC、descriptor、stream policy、queue和finalization。架构检查同时禁止payload struct直写wire，限制`Generated/`文件集合，并确认authoritative manifest不调用Python或生成器。ARM编译证明F407 Storage/Log Board Service可链接；没有TF卡长时间写入、断电注入和文件恢复实测时，不得声称Storage硬件已经验证。
