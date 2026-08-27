#include <stdint.h>
#include <string.h>

#include "diagnostic_log.h"
#include "host_platform_mock.h"
#include "imu_sample_bus.h"
#include "ins_task.h"
#include "logger_bus.h"
#include "project_log_decoder_profile.h"
#include "sslog_protocol.h"
#include "system_descriptor_if.h"
#include "system_lifecycle.h"
#include "system_log_policy.h"
#include "system_telemetry_transport_if.h"
#include "system_user_config.h"
#include "test_common.h"

static SystemLifecycleState s_lifecycle_state = SYSTEM_STATE_FLIGHT;
static ImuSampleBusStats s_imu_bus_stats;
static InsOutputSnapshot s_ins_snapshot;
static SystemTelemetryHealth s_telemetry_health;
static SystemDeviceResult s_telemetry_health_result = SYSTEM_DEVICE_OK;
static uint32_t s_imu_bus_stats_get_count;
static uint32_t s_telemetry_health_get_count;
static uint8_t s_ins_snapshot_available = 1U;

SystemLifecycleState SystemLifecycle_GetState(void)
{
    return s_lifecycle_state;
}

void ImuSampleBus_StatsGet(ImuSampleBusStats *stats)
{
    s_imu_bus_stats_get_count++;
    if (stats != NULL)
    {
        *stats = s_imu_bus_stats;
    }
}

uint8_t Ins_GetLatestSnapshot(InsOutputSnapshot *snapshot)
{
    if (snapshot != NULL)
    {
        *snapshot = s_ins_snapshot;
    }
    return s_ins_snapshot_available;
}

SystemDeviceResult SystemTelemetry_HealthGet(SystemTelemetryHealth *health)
{
    s_telemetry_health_get_count++;
    if ((health != NULL) &&
        (s_telemetry_health_result == SYSTEM_DEVICE_OK))
    {
        *health = s_telemetry_health;
    }
    return s_telemetry_health_result;
}

static uint16_t Test_U16Get(const uint8_t *data)
{
    return (uint16_t)((uint16_t)data[0] | ((uint16_t)data[1] << 8U));
}

static uint32_t Test_U32Get(const uint8_t *data)
{
    return (uint32_t)data[0] |
           ((uint32_t)data[1] << 8U) |
           ((uint32_t)data[2] << 16U) |
           ((uint32_t)data[3] << 24U);
}

static void Test_LoggerQueueDrain(void)
{
    FlightLogRecord record;
    uint16_t index;

    for (index = 0U; index < SYSTEM_LOG_RECORD_QUEUE_DEPTH; index++)
    {
        if (LoggerBus_Pop(&record) != LOGGER_BUS_RESULT_OK)
        {
            break;
        }
    }
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
}

static void Test_RecordMetadata(void)
{
    const SslogRecordMetadata *metadata;
    uint16_t index;

    TEST_CHECK(SslogRecords_RecordCountGet() == SSLOG_RECORD_COUNT);
    TEST_CHECK(SSLOG_RECORD_COUNT == 29U);
    TEST_CHECK(FLIGHT_LOG_RECORD_SAMPLE == 0x01U);
    TEST_CHECK(FLIGHT_LOG_RECORD_STATS == 0x03U);
    TEST_CHECK(FLIGHT_LOG_RECORD_TELEMETRY_DIAG == 0x0CU);
    TEST_CHECK(FLIGHT_LOG_RECORD_MISSION_CONFIG == 0x19U);
    TEST_CHECK(FLIGHT_LOG_RECORD_DEVICE_DESCRIPTOR == 0x1AU);
    TEST_CHECK(FLIGHT_LOG_RECORD_ALGORITHM_DESCRIPTOR == 0x1BU);
    TEST_CHECK(FLIGHT_LOG_RECORD_LOG_STREAM_DESCRIPTOR == 0x1CU);
    TEST_CHECK(FLIGHT_LOG_RECORD_DECODER_PROFILE_DESCRIPTOR == 0x1DU);
    TEST_CHECK(FLIGHT_LOG_POWER_PAYLOAD_SIZE == 48U);
    TEST_CHECK(FLIGHT_LOG_STATS_PAYLOAD_SIZE == 16U);
    TEST_CHECK(FLIGHT_LOG_TELEMETRY_DIAG_PAYLOAD_SIZE == 48U);
    TEST_CHECK(FLIGHT_LOG_IMU_NATIVE_PAYLOAD_SIZE == 80U);
    TEST_CHECK(FLIGHT_LOG_GNSS_NATIVE_PAYLOAD_SIZE == 84U);
    TEST_CHECK(FLIGHT_LOG_BARO_NATIVE_PAYLOAD_SIZE == 48U);
    TEST_CHECK(FLIGHT_LOG_MAG_NATIVE_PAYLOAD_SIZE == 60U);
    TEST_CHECK(FLIGHT_LOG_HW_QUAT_NATIVE_PAYLOAD_SIZE == 48U);
    TEST_CHECK(FLIGHT_LOG_DEVICE_DESCRIPTOR_PAYLOAD_SIZE == 26U);
    TEST_CHECK(FLIGHT_LOG_DECODER_PROFILE_DESCRIPTOR_PAYLOAD_SIZE == 64U);
    for (index = 0U; index < SSLOG_RECORD_COUNT; index++)
    {
        metadata = SslogRecords_MetadataByIndexGet(index);
        TEST_CHECK(metadata != NULL);
        if (metadata != NULL)
        {
            TEST_CHECK(metadata->record_version == 0U);
            TEST_CHECK(metadata->payload_size != 0U);
            TEST_CHECK(metadata->payload_size <= SSLOG_MAX_PAYLOAD_SIZE);
            TEST_CHECK(metadata->name != NULL);
        }
    }
    TEST_CHECK(SslogRecords_MetadataByIndexGet(SSLOG_RECORD_COUNT) == NULL);
    TEST_CHECK(SslogRecords_MetadataGet((FlightLogRecordType)0x7FU) == NULL);
}

static void Test_FileHeaderAndCrc(void)
{
    static const uint8_t crc_vector[] =
        {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    FlightLogFileHeaderInfo info;
    uint8_t buffer[FLIGHT_LOG_FILE_HEADER_SIZE];
    uint16_t serialized_size = 0U;
    uint32_t stored_crc;

    (void)memset(&info, 0, sizeof(info));
    info.profile_id = SYSTEM_LOG_PROFILE_ID;
    info.nominal_imu_rate_hz = SYSTEM_IMU_OUTPUT_RATE_HZ;
    info.nominal_ins_rate_hz =
        SYSTEM_IMU_OUTPUT_RATE_HZ / SYSTEM_MECHANIZATION_SUBSAMPLE_COUNT;
    info.coordinate_frame = 1U;
    info.position_axis_order[0] = 1U;
    info.position_axis_order[1] = 2U;
    info.position_axis_order[2] = 3U;
    info.quaternion_order = 1U;
    info.quaternion_semantics = 1U;
    info.local_gravity_mps2 = SYSTEM_LOCAL_GRAVITY_MPS2;
    (void)memcpy(info.air_compatibility_tag, "AIRCPV0", 7U);
    (void)memcpy(info.build_tag, SILVERSTAR_LOG_BUILD_TAG, 8U);
    info.mechanization_subsample_count =
        SYSTEM_MECHANIZATION_SUBSAMPLE_COUNT;
    info.firmware_version[0] = SILVERSTAR_VERSION_MAJOR;
    info.firmware_version[1] = SILVERSTAR_VERSION_MINOR;
    info.firmware_version[2] = SILVERSTAR_VERSION_PATCH;
    info.firmware_version[3] = SILVERSTAR_VERSION_BUILD;
    TEST_CHECK(FlightLog_Crc32(crc_vector, sizeof(crc_vector)) ==
               0xCBF43926UL);
    TEST_CHECK(FlightLog_FileHeaderSerialize(
        &info, buffer, sizeof(buffer), &serialized_size) ==
        FLIGHT_LOG_SERIALIZE_RESULT_OK);
    TEST_CHECK(serialized_size == FLIGHT_LOG_FILE_HEADER_SIZE);
    TEST_CHECK(memcmp(buffer, "SSLOG0", 6U) == 0);
    TEST_CHECK(Test_U16Get(&buffer[10]) == FLIGHT_LOG_FILE_HEADER_SIZE);
    TEST_CHECK(Test_U16Get(&buffer[12]) == FLIGHT_LOG_RECORD_HEADER_SIZE);
    TEST_CHECK(buffer[50] == SILVERSTAR_VERSION_PATCH);
    stored_crc = Test_U32Get(&buffer[FLIGHT_LOG_FILE_HEADER_SIZE - 4U]);
    TEST_CHECK(stored_crc == FlightLog_Crc32(
        buffer, FLIGHT_LOG_FILE_HEADER_SIZE - 4U));
}

static void Test_RecordEndianAndUnknownType(void)
{
    FlightLogRecord record;
    FlightLogRecord decoded;
    uint8_t buffer[FLIGHT_LOG_MAX_RECORD_SIZE];
    uint16_t serialized_size = 0U;
    uint16_t deserialized_size = 0U;
    uint32_t record_sequence = 0U;
    uint32_t stored_crc;

    (void)memset(&record, 0, sizeof(record));
    record.record_type = FLIGHT_LOG_RECORD_EVENT;
    record.timestamp_us = 0x0102030405060708ULL;
    record.valid_flags = 0xA1B2C3D4UL;
    record.payload.event.event_id = FLIGHT_LOG_EVENT_MISSION_START;
    record.payload.event.arg0 = 0x11223344UL;
    record.payload.event.arg1 = 0x55667788UL;
    TEST_CHECK(FlightLog_RecordSerialize(
        &record, 0x89ABCDEFUL, buffer, sizeof(buffer), &serialized_size) ==
        FLIGHT_LOG_SERIALIZE_RESULT_OK);
    TEST_CHECK(serialized_size == (FLIGHT_LOG_RECORD_HEADER_SIZE +
               FLIGHT_LOG_EVENT_PAYLOAD_SIZE + FLIGHT_LOG_RECORD_CRC_SIZE));
    TEST_CHECK(Test_U32Get(&buffer[0]) == 0x31474C46UL);
    TEST_CHECK(buffer[4] == 0U);
    TEST_CHECK(buffer[5] == FLIGHT_LOG_RECORD_EVENT);
    TEST_CHECK(Test_U16Get(&buffer[6]) == FLIGHT_LOG_EVENT_PAYLOAD_SIZE);
    TEST_CHECK(Test_U32Get(&buffer[8]) == 0x89ABCDEFUL);
    TEST_CHECK(buffer[12] == 0x08U && buffer[19] == 0x01U);
    TEST_CHECK(Test_U32Get(&buffer[20]) == 0xA1B2C3D4UL);
    TEST_CHECK(buffer[24] == FLIGHT_LOG_EVENT_MISSION_START);
    TEST_CHECK(Test_U32Get(&buffer[28]) == 0x11223344UL);
    TEST_CHECK(Test_U32Get(&buffer[32]) == 0x55667788UL);
    stored_crc = Test_U32Get(&buffer[serialized_size - 4U]);
    TEST_CHECK(stored_crc == FlightLog_Crc32(buffer, serialized_size - 4U));

    TEST_CHECK(FlightLog_RecordDeserialize(buffer, serialized_size, &decoded,
        &record_sequence, &deserialized_size) ==
        FLIGHT_LOG_DESERIALIZE_RESULT_OK);
    TEST_CHECK(deserialized_size == serialized_size);
    TEST_CHECK(record_sequence == 0x89ABCDEFUL);
    TEST_CHECK(decoded.record_type == FLIGHT_LOG_RECORD_EVENT);
    TEST_CHECK(decoded.timestamp_us == 0x0102030405060708ULL);
    TEST_CHECK(decoded.valid_flags == 0xA1B2C3D4UL);
    TEST_CHECK(decoded.payload.event.event_id ==
        FLIGHT_LOG_EVENT_MISSION_START);
    TEST_CHECK(decoded.payload.event.arg0 == 0x11223344UL);
    TEST_CHECK(decoded.payload.event.arg1 == 0x55667788UL);

    TEST_CHECK(FlightLog_RecordDeserialize(buffer, serialized_size - 1U,
        &decoded, &record_sequence, &deserialized_size) ==
        FLIGHT_LOG_DESERIALIZE_RESULT_BUFFER_SMALL);
    buffer[0] ^= 0x01U;
    TEST_CHECK(FlightLog_RecordDeserialize(buffer, serialized_size, &decoded,
        &record_sequence, &deserialized_size) ==
        FLIGHT_LOG_DESERIALIZE_RESULT_BAD_SYNC);
    buffer[0] ^= 0x01U;
    buffer[4] = 1U;
    TEST_CHECK(FlightLog_RecordDeserialize(buffer, serialized_size, &decoded,
        &record_sequence, &deserialized_size) ==
        FLIGHT_LOG_DESERIALIZE_RESULT_BAD_VERSION);
    buffer[4] = 0U;
    buffer[6] ^= 0x01U;
    TEST_CHECK(FlightLog_RecordDeserialize(buffer, serialized_size, &decoded,
        &record_sequence, &deserialized_size) ==
        FLIGHT_LOG_DESERIALIZE_RESULT_BAD_SIZE);
    buffer[6] ^= 0x01U;
    buffer[24] ^= 0x01U;
    TEST_CHECK(FlightLog_RecordDeserialize(buffer, serialized_size, &decoded,
        &record_sequence, &deserialized_size) ==
        FLIGHT_LOG_DESERIALIZE_RESULT_BAD_CRC);
    buffer[24] ^= 0x01U;

    record.record_type = (FlightLogRecordType)0x7FU;
    TEST_CHECK(FlightLog_RecordSerialize(
        &record, 0U, buffer, sizeof(buffer), &serialized_size) ==
               FLIGHT_LOG_SERIALIZE_RESULT_BAD_TYPE);
}

static void Test_GeneratedPayloadRoundTrip(void)
{
    FlightLogRecord source;
    FlightLogRecord decoded;
    uint8_t first[SSLOG_MAX_PAYLOAD_SIZE];
    uint8_t second[SSLOG_MAX_PAYLOAD_SIZE];
    uint16_t index;

    for (index = 0U; index < SSLOG_RECORD_COUNT; index++)
    {
        const SslogRecordMetadata *metadata =
            SslogRecords_MetadataByIndexGet(index);
        uint16_t first_size;
        uint16_t decoded_size;
        uint16_t second_size;

        TEST_CHECK(metadata != NULL);
        if (metadata == NULL)
        {
            continue;
        }
        (void)memset(&source, 0, sizeof(source));
        (void)memset(&decoded, 0, sizeof(decoded));
        (void)memset(&source.payload, 0xA5, sizeof(source.payload));
        source.record_type = metadata->record_type;
        decoded.record_type = metadata->record_type;

        first_size = SslogRecords_PayloadSerialize(&source, first,
            sizeof(first));
        decoded_size = SslogRecords_PayloadDeserialize(&decoded, first,
            first_size);
        second_size = SslogRecords_PayloadSerialize(&decoded, second,
            sizeof(second));
        TEST_CHECK(first_size == metadata->payload_size);
        TEST_CHECK(decoded_size == metadata->payload_size);
        TEST_CHECK(second_size == metadata->payload_size);
        TEST_CHECK(memcmp(first, second, metadata->payload_size) == 0);
        TEST_CHECK(SslogRecords_PayloadSerialize(&source, first,
            (uint16_t)(metadata->payload_size - 1U)) == 0U);
        TEST_CHECK(SslogRecords_PayloadDeserialize(&decoded, first,
            (uint16_t)(metadata->payload_size - 1U)) == 0U);
    }
}

static void Test_DiagnosticRecordCodec(void)
{
    FlightLogRecord source;
    FlightLogRecord decoded;
    uint8_t payload[FLIGHT_LOG_TELEMETRY_DIAG_PAYLOAD_SIZE];
    uint16_t payload_size;

    (void)memset(&source, 0, sizeof(source));
    (void)memset(&decoded, 0, sizeof(decoded));
    source.record_type = FLIGHT_LOG_RECORD_STATS;
    source.payload.stats.imu_queue_overflow_count = 0x01020304UL;
    source.payload.stats.logger_queue_overflow_count = 0x11121314UL;
    source.payload.stats.ins_update_count = 0x21222324UL;
    source.payload.stats.health_flags = 0x31323334UL;
    decoded.record_type = FLIGHT_LOG_RECORD_STATS;
    payload_size = SslogRecords_PayloadSerialize(
        &source, payload, sizeof(payload));
    TEST_CHECK(payload_size == FLIGHT_LOG_STATS_PAYLOAD_SIZE);
    TEST_CHECK(payload[0] == 0x04U && payload[3] == 0x01U);
    TEST_CHECK(Test_U32Get(&payload[4]) == 0x11121314UL);
    TEST_CHECK(Test_U32Get(&payload[8]) == 0x21222324UL);
    TEST_CHECK(Test_U32Get(&payload[12]) == 0x31323334UL);
    TEST_CHECK(SslogRecords_PayloadDeserialize(
        &decoded, payload, payload_size) == payload_size);
    TEST_CHECK(decoded.payload.stats.health_flags == 0x31323334UL);

    (void)memset(&source, 0, sizeof(source));
    (void)memset(&decoded, 0, sizeof(decoded));
    source.record_type = FLIGHT_LOG_RECORD_TELEMETRY_DIAG;
    source.payload.telemetry_diagnostic.last_transmit_timestamp_us =
        0x0102030405060708ULL;
    source.payload.telemetry_diagnostic.last_receive_timestamp_us =
        0x1112131415161718ULL;
    source.payload.telemetry_diagnostic.transmit_packet_count = 0x21222324UL;
    source.payload.telemetry_diagnostic.receive_packet_count = 0x31323334UL;
    source.payload.telemetry_diagnostic.transmit_error_count = 0x41424344UL;
    source.payload.telemetry_diagnostic.receive_error_count = 0x51525354UL;
    source.payload.telemetry_diagnostic.integrity_error_count = 0x61626364UL;
    source.payload.telemetry_diagnostic.last_rssi_dbm = -123;
    source.payload.telemetry_diagnostic.last_snr_q4 = -7;
    source.payload.telemetry_diagnostic.online = 1U;
    decoded.record_type = FLIGHT_LOG_RECORD_TELEMETRY_DIAG;
    payload_size = SslogRecords_PayloadSerialize(
        &source, payload, sizeof(payload));
    TEST_CHECK(payload_size == FLIGHT_LOG_TELEMETRY_DIAG_PAYLOAD_SIZE);
    TEST_CHECK(payload[0] == 0x08U && payload[7] == 0x01U);
    TEST_CHECK(Test_U32Get(&payload[16]) == 0x21222324UL);
    TEST_CHECK(payload[36] == 0x85U && payload[37] == 0xFFU);
    TEST_CHECK(payload[38] == 0xF9U && payload[39] == 1U);
    TEST_CHECK(payload[40] == 0U && payload[47] == 0U);
    TEST_CHECK(SslogRecords_PayloadDeserialize(
        &decoded, payload, payload_size) == payload_size);
    TEST_CHECK(decoded.payload.telemetry_diagnostic.
               last_receive_timestamp_us == 0x1112131415161718ULL);
    TEST_CHECK(decoded.payload.telemetry_diagnostic.last_rssi_dbm == -123);
    TEST_CHECK(decoded.payload.telemetry_diagnostic.last_snr_q4 == -7);
    TEST_CHECK(decoded.payload.telemetry_diagnostic.online == 1U);
}

static void Test_InstanceSourceCodec(void)
{
    FlightLogRecord source;
    FlightLogRecord decoded;
    uint8_t payload[SSLOG_MAX_PAYLOAD_SIZE];
    uint16_t payload_size;

    (void)memset(&source, 0, sizeof(source));
    (void)memset(&decoded, 0, sizeof(decoded));
    source.record_type = FLIGHT_LOG_RECORD_IMU_NATIVE;
    source.payload.imu_native.source_descriptor_id = 0x1234U;
    source.payload.imu_native.instance_id = 7U;
    source.payload.imu_native.sequence = 0x01020304UL;
    decoded.record_type = FLIGHT_LOG_RECORD_IMU_NATIVE;
    payload_size = SslogRecords_PayloadSerialize(
        &source, payload, sizeof(payload));
    TEST_CHECK(payload_size == FLIGHT_LOG_IMU_NATIVE_PAYLOAD_SIZE);
    TEST_CHECK(payload[0] == 0x34U);
    TEST_CHECK(payload[1] == 0x12U);
    TEST_CHECK(payload[2] == 7U);
    TEST_CHECK(payload[3] == 0U);
    TEST_CHECK(SslogRecords_PayloadDeserialize(
        &decoded, payload, payload_size) == payload_size);
    TEST_CHECK(decoded.payload.imu_native.source_descriptor_id == 0x1234U);
    TEST_CHECK(decoded.payload.imu_native.instance_id == 7U);
    TEST_CHECK(decoded.payload.imu_native.sequence == 0x01020304UL);
}

static void Test_SourceChangeEventPacking(void)
{
    uint32_t arg0 = FLIGHT_LOG_SENSOR_SOURCE_CHANGE_ARG0(
        SYSTEM_DEVICE_CLASS_IMU, 1U, 2U,
        FLIGHT_LOG_SENSOR_SOURCE_CHANGE_FAILOVER);
    uint32_t arg1 = FLIGHT_LOG_SENSOR_SOURCE_CHANGE_ARG1(
        0x1234U, 0xABCDU);

    TEST_CHECK((arg0 & 0xFFUL) == SYSTEM_DEVICE_CLASS_IMU);
    TEST_CHECK(((arg0 >> 8U) & 0xFFUL) == 1U);
    TEST_CHECK(((arg0 >> 16U) & 0xFFUL) == 2U);
    TEST_CHECK(((arg0 >> 24U) & 0xFFUL) ==
               FLIGHT_LOG_SENSOR_SOURCE_CHANGE_FAILOVER);
    TEST_CHECK((arg1 & 0xFFFFUL) == 0x1234U);
    TEST_CHECK(((arg1 >> 16U) & 0xFFFFUL) == 0xABCDU);
}

static void Test_StreamConfiguration(void)
{
    SystemLogStreamConfig config;

    SystemLogPolicy_Init();
    TEST_CHECK(SystemLogPolicy_StreamCountGet() == SSLOG_RECORD_COUNT);
    TEST_CHECK(SystemLogPolicy_StreamGet(
        FLIGHT_LOG_RECORD_STATS, &config) == SYSTEM_DEVICE_OK);
    TEST_CHECK(config.enabled != 0U);
    TEST_CHECK(config.period_us == 1000000UL);
    TEST_CHECK(config.policy == SSLOG_STREAM_POLICY_PERIODIC);
    TEST_CHECK(SystemLogPolicy_StreamGet(
        FLIGHT_LOG_RECORD_TELEMETRY_DIAG, &config) == SYSTEM_DEVICE_OK);
    TEST_CHECK(config.enabled != 0U);
    TEST_CHECK(config.period_us == 200000UL);
    TEST_CHECK(config.policy == SSLOG_STREAM_POLICY_PERIODIC);
    TEST_CHECK(SystemLogPolicy_StreamGet(
        FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC, &config) == SYSTEM_DEVICE_OK);
    TEST_CHECK(config.enabled != 0U);
    TEST_CHECK(config.decimation == 4U);
    config.decimation = 3U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    SystemLogPolicy_EmissionReset();
    TEST_CHECK(SystemLogPolicy_ShouldEmit(
        FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC) != 0U);
    TEST_CHECK(SystemLogPolicy_ShouldEmit(
        FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC) == 0U);
    TEST_CHECK(SystemLogPolicy_ShouldEmit(
        FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC) == 0U);
    TEST_CHECK(SystemLogPolicy_ShouldEmit(
        FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC) != 0U);
    SystemLogPolicy_Freeze();
    config.decimation = 2U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) ==
               SYSTEM_DEVICE_BAD_STATE);
    SystemLogPolicy_UnfreezeForRollback();
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
}

static void Test_StatsProducer(void)
{
    DiagnosticLogPeriodicState state = {0ULL};
    DiagnosticLogPeriodicState empty_ins_state = {0ULL};
    FlightLogRecord record;
    SystemLogStreamConfig config;
    uint16_t index;

    TEST_CHECK(LoggerBus_Init() == LOGGER_BUS_RESULT_OK);
    LoggerBus_Reset();
    s_lifecycle_state = SYSTEM_STATE_FLIGHT;
    (void)memset(&s_imu_bus_stats, 0, sizeof(s_imu_bus_stats));
    (void)memset(&s_ins_snapshot, 0, sizeof(s_ins_snapshot));
    s_imu_bus_stats.overflow_count = 23UL;
    s_imu_bus_stats_get_count = 0U;
    s_ins_snapshot.update_seq = 456UL;
    s_ins_snapshot.health_flags = 0xA5A55A5AUL;
    s_ins_snapshot_available = 1U;
    TEST_CHECK(SystemLogPolicy_StreamGet(
        FLIGHT_LOG_RECORD_STATS, &config) == SYSTEM_DEVICE_OK);
    config.enabled = 1U;
    config.period_us = 1000000UL;
    config.decimation = 1U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    for (index = 0U; index < SYSTEM_LOG_RECORD_QUEUE_DEPTH; index++)
    {
        TEST_CHECK(LoggerBus_EventPush(index, FLIGHT_LOG_EVENT_BOOT,
            index, 0U) == LOGGER_BUS_RESULT_OK);
    }
    TEST_CHECK(LoggerBus_EventPush(999ULL, FLIGHT_LOG_EVENT_BOOT,
        0U, 0U) == LOGGER_BUS_RESULT_FULL);
    Test_LoggerQueueDrain();
    DiagnosticLog_StatsProcess(&state, 999999ULL);
    TEST_CHECK(s_imu_bus_stats_get_count == 0U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    DiagnosticLog_StatsProcess(&state, 1000000ULL);
    TEST_CHECK(s_imu_bus_stats_get_count == 1U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK);
    TEST_CHECK(record.record_type == FLIGHT_LOG_RECORD_STATS);
    TEST_CHECK(record.timestamp_us == 1000000ULL);
    TEST_CHECK(record.payload.stats.imu_queue_overflow_count == 23UL);
    TEST_CHECK(record.payload.stats.logger_queue_overflow_count == 1UL);
    TEST_CHECK(record.payload.stats.ins_update_count == 456UL);
    TEST_CHECK(record.payload.stats.health_flags == 0xA5A55A5AUL);
    DiagnosticLog_StatsProcess(&state, 1000000ULL);
    TEST_CHECK(s_imu_bus_stats_get_count == 1U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);

    s_ins_snapshot_available = 0U;
    DiagnosticLog_StatsProcess(&empty_ins_state, 1000000ULL);
    TEST_CHECK(s_imu_bus_stats_get_count == 2U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK);
    TEST_CHECK(record.payload.stats.ins_update_count == 0U);
    TEST_CHECK(record.payload.stats.health_flags == 0U);
    config.enabled = 0U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    empty_ins_state.last_emission_us = 0ULL;
    DiagnosticLog_StatsProcess(&empty_ins_state, 2000000ULL);
    TEST_CHECK(s_imu_bus_stats_get_count == 2U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    config.enabled = 1U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    s_lifecycle_state = SYSTEM_STATE_PREFLIGHT;
    DiagnosticLog_StatsProcess(&empty_ins_state, 2000000ULL);
    TEST_CHECK(s_imu_bus_stats_get_count == 2U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    s_lifecycle_state = SYSTEM_STATE_FLIGHT;
}

static void Test_TelemetryDiagnosticProducer(void)
{
    DiagnosticLogPeriodicState state = {0ULL};
    DiagnosticLogPeriodicState retry_state = {0ULL};
    FlightLogRecord record;
    SystemLogStreamConfig config;

    LoggerBus_Reset();
    s_lifecycle_state = SYSTEM_STATE_RECOVERY;
    (void)memset(&s_telemetry_health, 0, sizeof(s_telemetry_health));
    s_telemetry_health.last_transmit_timestamp_us = 101ULL;
    s_telemetry_health.last_receive_timestamp_us = 202ULL;
    s_telemetry_health.transmit_packet_count = 303UL;
    s_telemetry_health.receive_packet_count = 404UL;
    s_telemetry_health.transmit_error_count = 5UL;
    s_telemetry_health.receive_error_count = 6UL;
    s_telemetry_health.integrity_error_count = 7UL;
    s_telemetry_health.last_rssi_dbm = -88;
    s_telemetry_health.last_snr_q4 = -9;
    s_telemetry_health.online = 1U;
    s_telemetry_health_result = SYSTEM_DEVICE_OK;
    s_telemetry_health_get_count = 0U;
    TEST_CHECK(SystemLogPolicy_StreamGet(
        FLIGHT_LOG_RECORD_TELEMETRY_DIAG, &config) == SYSTEM_DEVICE_OK);
    config.enabled = 1U;
    config.period_us = 200000UL;
    config.decimation = 1U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    DiagnosticLog_TelemetryProcess(&state, 199999ULL);
    TEST_CHECK(s_telemetry_health_get_count == 0U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    DiagnosticLog_TelemetryProcess(&state, 200000ULL);
    TEST_CHECK(s_telemetry_health_get_count == 1U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK);
    TEST_CHECK(record.record_type == FLIGHT_LOG_RECORD_TELEMETRY_DIAG);
    TEST_CHECK(record.timestamp_us == 200000ULL);
    TEST_CHECK(record.payload.telemetry_diagnostic.
               last_transmit_timestamp_us == 101ULL);
    TEST_CHECK(record.payload.telemetry_diagnostic.
               last_receive_timestamp_us == 202ULL);
    TEST_CHECK(record.payload.telemetry_diagnostic.
               transmit_packet_count == 303UL);
    TEST_CHECK(record.payload.telemetry_diagnostic.
               receive_packet_count == 404UL);
    TEST_CHECK(record.payload.telemetry_diagnostic.transmit_error_count == 5UL);
    TEST_CHECK(record.payload.telemetry_diagnostic.receive_error_count == 6UL);
    TEST_CHECK(record.payload.telemetry_diagnostic.integrity_error_count == 7UL);
    TEST_CHECK(record.payload.telemetry_diagnostic.last_rssi_dbm == -88);
    TEST_CHECK(record.payload.telemetry_diagnostic.last_snr_q4 == -9);
    TEST_CHECK(record.payload.telemetry_diagnostic.online == 1U);
    DiagnosticLog_TelemetryProcess(&state, 200000ULL);
    TEST_CHECK(s_telemetry_health_get_count == 1U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);

    s_telemetry_health_result = SYSTEM_DEVICE_IO_ERROR;
    DiagnosticLog_TelemetryProcess(&retry_state, 200000ULL);
    TEST_CHECK(s_telemetry_health_get_count == 2U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    s_telemetry_health_result = SYSTEM_DEVICE_OK;
    DiagnosticLog_TelemetryProcess(&retry_state, 200001ULL);
    TEST_CHECK(s_telemetry_health_get_count == 3U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK);
    config.enabled = 0U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    retry_state.last_emission_us = 0ULL;
    DiagnosticLog_TelemetryProcess(&retry_state, 400000ULL);
    TEST_CHECK(s_telemetry_health_get_count == 3U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    config.enabled = 1U;
    TEST_CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    s_lifecycle_state = SYSTEM_STATE_PREFLIGHT;
    DiagnosticLog_TelemetryProcess(&retry_state, 400000ULL);
    TEST_CHECK(s_telemetry_health_get_count == 3U);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_EMPTY);
    s_lifecycle_state = SYSTEM_STATE_FLIGHT;
}

static void Test_DescriptorBundle(void)
{
    FlightLogRecord record;
    uint16_t device_count = 0U;
    uint16_t algorithm_count = 0U;
    uint16_t stream_count = 0U;
    uint16_t total_count;

    TEST_CHECK(LoggerBus_Init() == LOGGER_BUS_RESULT_OK);
    LoggerBus_Reset();
    TEST_CHECK(LoggerBus_SystemConfigPush(1234ULL) == LOGGER_BUS_RESULT_OK);
    total_count = LoggerBus_Count();
    TEST_CHECK(total_count == (uint16_t)(1U +
               SystemDescriptor_DeviceCountGet() +
               SystemDescriptor_AlgorithmCountGet() +
               SSLOG_RECORD_COUNT));
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK);
    TEST_CHECK(record.record_type == FLIGHT_LOG_RECORD_SYSTEM_CONFIG);
    TEST_CHECK(record.payload.system_config.version[2] ==
               SILVERSTAR_VERSION_PATCH);
    TEST_CHECK(record.payload.system_config.device_descriptor_count ==
               SystemDescriptor_DeviceCountGet());
    TEST_CHECK(record.payload.system_config.algorithm_descriptor_count ==
               SystemDescriptor_AlgorithmCountGet());
    TEST_CHECK(record.payload.system_config.log_stream_descriptor_count ==
               SSLOG_RECORD_COUNT);
    while (LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK)
    {
        if (record.record_type == FLIGHT_LOG_RECORD_DEVICE_DESCRIPTOR)
        {
            TEST_CHECK(record.payload.device_descriptor.descriptor_id != 0U);
            if ((record.payload.device_descriptor.flags &
                 SYSTEM_DESCRIPTOR_FLAG_SHARED_PHYSICAL) != 0U)
            {
                TEST_CHECK(record.payload.device_descriptor.
                           physical_device_id != 0U);
            }
            device_count++;
        }
        else if (record.record_type ==
                 FLIGHT_LOG_RECORD_ALGORITHM_DESCRIPTOR)
        {
            algorithm_count++;
        }
        else if (record.record_type ==
                 FLIGHT_LOG_RECORD_LOG_STREAM_DESCRIPTOR)
        {
            stream_count++;
            TEST_CHECK(record.payload.stream_descriptor.record_version == 0U);
            TEST_CHECK(record.payload.stream_descriptor.decimation != 0U);
        }
    }
    TEST_CHECK(device_count == SystemDescriptor_DeviceCountGet());
    TEST_CHECK(algorithm_count == SystemDescriptor_AlgorithmCountGet());
    TEST_CHECK(stream_count == SSLOG_RECORD_COUNT);
}

static void Test_DecoderProfileDescriptor(void)
{
    ProjectLogDecoderProfile profile;
    FlightLogRecord record;
    FlightLogRecord decoded;
    uint8_t payload[FLIGHT_LOG_DECODER_PROFILE_DESCRIPTOR_PAYLOAD_SIZE];
    uint16_t payload_size;

    ProjectLogDecoderProfile_Get(&profile);
    LoggerBus_Reset();
    TEST_CHECK(LoggerBus_DecoderProfileDescriptorPush(4321ULL) ==
               LOGGER_BUS_RESULT_OK);
    TEST_CHECK(LoggerBus_Pop(&record) == LOGGER_BUS_RESULT_OK);
    TEST_CHECK(record.record_type ==
               FLIGHT_LOG_RECORD_DECODER_PROFILE_DESCRIPTOR);
    TEST_CHECK(record.timestamp_us == 4321ULL);
    TEST_CHECK(record.payload.decoder_profile_descriptor.
               package_schema_major == 1U);
    TEST_CHECK(record.payload.decoder_profile_descriptor.
               container_format_major == 0U);
    TEST_CHECK(memcmp(record.payload.decoder_profile_descriptor.
               record_catalog_hash_128,
               profile.record_catalog_hash_128, 16U) == 0);
    TEST_CHECK(memcmp(record.payload.decoder_profile_descriptor.
               project_semantics_hash_128,
               profile.project_semantics_hash_128, 16U) == 0);
    TEST_CHECK(memcmp(record.payload.decoder_profile_descriptor.
               generation_profile_hash_128,
               profile.generation_profile_hash_128, 16U) == 0);
    payload_size = SslogRecords_PayloadSerialize(
        &record, payload, sizeof(payload));
    TEST_CHECK(payload_size == sizeof(payload));
    TEST_CHECK(payload[0] == 1U && payload[1] == 0U);
    TEST_CHECK(payload[2] == 0U && payload[3] == 0U);
    TEST_CHECK(payload[4] == 0U && payload[5] == 0U);
    (void)memset(&decoded, 0, sizeof(decoded));
    decoded.record_type = FLIGHT_LOG_RECORD_DECODER_PROFILE_DESCRIPTOR;
    TEST_CHECK(SslogRecords_PayloadDeserialize(
        &decoded, payload, sizeof(payload)) == sizeof(payload));
    TEST_CHECK(memcmp(&record.payload.decoder_profile_descriptor,
        &decoded.payload.decoder_profile_descriptor,
        sizeof(record.payload.decoder_profile_descriptor)) == 0);
}

static void Test_QueueOverflowAndFinalization(void)
{
    uint16_t index;

    LoggerBus_Reset();
    for (index = 0U; index < SYSTEM_LOG_RECORD_QUEUE_DEPTH; index++)
    {
        TEST_CHECK(LoggerBus_EventPush(
            index, FLIGHT_LOG_EVENT_BOOT, index, 0U) ==
            LOGGER_BUS_RESULT_OK);
    }
    TEST_CHECK(LoggerBus_EventPush(
        999U, FLIGHT_LOG_EVENT_BOOT, 0U, 0U) == LOGGER_BUS_RESULT_FULL);
    TEST_CHECK(LoggerBus_OverflowCountGet() == 1U);
    TEST_CHECK(LoggerBus_FinalizationArm(1000ULL) == LOGGER_BUS_RESULT_OK);
    TEST_CHECK(LoggerBus_FinalizationProcess(
        1000ULL + ((uint64_t)SYSTEM_LOG_POST_LANDING_GRACE_MS * 1000ULL) -
        1ULL) == LOGGER_BUS_FINALIZATION_ARMED);
    TEST_CHECK(LoggerBus_FinalizationProcess(
        1000ULL + ((uint64_t)SYSTEM_LOG_POST_LANDING_GRACE_MS * 1000ULL)) ==
        LOGGER_BUS_FINALIZATION_DRAINING);
    TEST_CHECK(LoggerBus_EventPush(
        2000ULL, FLIGHT_LOG_EVENT_BOOT, 0U, 0U) ==
        LOGGER_BUS_RESULT_BAD_STATE);
    LoggerBus_FinalizationComplete();
    TEST_CHECK(LoggerBus_FinalizationStateGet() ==
               LOGGER_BUS_FINALIZATION_FINALIZED);
}

int main(void)
{
    HostPlatformMock_Reset();
    Test_RecordMetadata();
    Test_FileHeaderAndCrc();
    Test_RecordEndianAndUnknownType();
    Test_GeneratedPayloadRoundTrip();
    Test_DiagnosticRecordCodec();
    Test_InstanceSourceCodec();
    Test_SourceChangeEventPacking();
    Test_StreamConfiguration();
    Test_StatsProducer();
    Test_TelemetryDiagnosticProducer();
    Test_DescriptorBundle();
    Test_DecoderProfileDescriptor();
    Test_QueueOverflowAndFinalization();
    return Test_Finish("logger");
}
