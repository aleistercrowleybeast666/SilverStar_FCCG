#include <stdint.h>
#include <string.h>

#include "host_platform_mock.h"
#include "logger_bus.h"
#include "sslog_protocol.h"
#include "system_descriptor_if.h"
#include "system_log_policy.h"
#include "system_user_config.h"
#include "test_common.h"

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

static void Test_RecordMetadata(void)
{
    const SslogRecordMetadata *metadata;
    uint16_t index;

    TEST_CHECK(SslogRecords_RecordCountGet() == SSLOG_RECORD_COUNT);
    TEST_CHECK(SSLOG_RECORD_COUNT == 28U);
    TEST_CHECK(FLIGHT_LOG_RECORD_SAMPLE == 0x01U);
    TEST_CHECK(FLIGHT_LOG_RECORD_MISSION_CONFIG == 0x19U);
    TEST_CHECK(FLIGHT_LOG_RECORD_DEVICE_DESCRIPTOR == 0x1AU);
    TEST_CHECK(FLIGHT_LOG_RECORD_ALGORITHM_DESCRIPTOR == 0x1BU);
    TEST_CHECK(FLIGHT_LOG_RECORD_LOG_STREAM_DESCRIPTOR == 0x1CU);
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

static void Test_StreamConfiguration(void)
{
    SystemLogStreamConfig config;

    SystemLogPolicy_Init();
    TEST_CHECK(SystemLogPolicy_StreamCountGet() == SSLOG_RECORD_COUNT);
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
    Test_StreamConfiguration();
    Test_DescriptorBundle();
    Test_QueueOverflowAndFinalization();
    return Test_Finish("logger");
}
