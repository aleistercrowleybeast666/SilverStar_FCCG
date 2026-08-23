#include "app_tasks.h"

#include <stddef.h>
#include <string.h>

#include "FreeRTOS.h"
#include "task.h"
#include "air_protocol.h"
#include "logger_bus.h"
#include "platform_memory.h"
#include "silverstar_assert.h"
#include "system_log_sink_if.h"
#include "system_profile.h"
#include "system_startup.h"
#include "system_time.h"
#include "system_user_config.h"
#include "system_version.h"

#define LOGGER_MAX_TEXT_LENGTH 128U

typedef struct
{
    uint32_t record_sequence;
    uint32_t aggregate_length;
    uint64_t last_flush_us;
    uint64_t next_retry_us;
    uint8_t session_active;
    uint8_t session_finalized;
    uint8_t header_written;
    uint8_t startup_report_written;
} LoggerRuntime;

static LoggerRuntime s_logger;
static uint8_t s_record_buffer[FLIGHT_LOG_MAX_RECORD_SIZE];
static PLATFORM_DMA_ACCESSIBLE uint8_t
    s_aggregate_buffer[SYSTEM_LOG_AGGREGATION_BUFFER_SIZE];

static void LoggerTask_HeaderInfoBuild(FlightLogFileHeaderInfo *info)
{
    static const uint8_t air_tag[] = AIR_PROTOCOL_COMPATIBILITY_TAG;
    static const uint8_t build_tag[] = SILVERSTAR_LOG_BUILD_TAG;

    _Static_assert(sizeof(air_tag) == 9U,
                   "AIR compatibility tag must contain eight bytes");
    _Static_assert(sizeof(build_tag) == 9U,
                   "SSLOG build tag must contain eight bytes");

    SILVERSTAR_ASSERT_OBJECT(info, FlightLogFileHeaderInfo,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(info, 0, sizeof(*info));
    info->profile_id = SYSTEM_LOG_PROFILE_ID;
    info->nominal_imu_rate_hz = SYSTEM_IMU_OUTPUT_RATE_HZ;
    info->nominal_ins_rate_hz = (uint16_t)(SYSTEM_IMU_OUTPUT_RATE_HZ /
        SYSTEM_MECHANIZATION_SUBSAMPLE_COUNT);
    info->coordinate_frame = 1U;
    info->position_axis_order[0] = 3U;
    info->position_axis_order[1] = 1U;
    info->position_axis_order[2] = 2U;
    info->quaternion_order = 1U;
    info->quaternion_semantics = 1U;
    info->local_gravity_mps2 = SYSTEM_LOCAL_GRAVITY_MPS2;
    (void)memcpy(info->air_compatibility_tag, air_tag,
                 sizeof(info->air_compatibility_tag));
    (void)memcpy(info->build_tag, build_tag, sizeof(info->build_tag));
    info->mechanization_subsample_count =
        SYSTEM_MECHANIZATION_SUBSAMPLE_COUNT;
    info->firmware_version[0] = SILVERSTAR_VERSION_MAJOR;
    info->firmware_version[1] = SILVERSTAR_VERSION_MINOR;
    info->firmware_version[2] = SILVERSTAR_VERSION_PATCH;
    info->firmware_version[3] = SILVERSTAR_VERSION_BUILD;
}

static uint8_t LoggerTask_SinkWrite(const uint8_t *data, uint32_t length)
{
    uint32_t written = 0U;

    if ((s_logger.session_active == 0U) ||
        (data == NULL) || (length == 0U))
    {
        return 0U;
    }
    return (uint8_t)((SystemLogSink_Write(data, length, &written) ==
                      SYSTEM_DEVICE_OK) && (written == length));
}

static uint8_t LoggerTask_AggregateWrite(void)
{
    if (s_logger.aggregate_length == 0U) { return 1U; }
    if (LoggerTask_SinkWrite(s_aggregate_buffer,
                             s_logger.aggregate_length) == 0U)
    {
        return 0U;
    }
    s_logger.aggregate_length = 0U;
    return 1U;
}

static uint8_t LoggerTask_Flush(void)
{
    if ((LoggerTask_AggregateWrite() == 0U) ||
        (SystemLogSink_Flush() != SYSTEM_DEVICE_OK))
    {
        return 0U;
    }
    s_logger.last_flush_us = SystemTime_GetMonotonicUs();
    return 1U;
}

static void LoggerTask_Close(void)
{
    if (s_logger.session_active != 0U)
    {
        /* The sink owns write/close error counters; close remains best effort. */
        (void)LoggerTask_AggregateWrite();
        (void)SystemLogSink_SessionEnd();
    }
    s_logger.session_active = 0U;
    s_logger.aggregate_length = 0U;
}

static uint8_t LoggerTask_SessionOpen(void)
{
    FlightLogFileHeaderInfo header_info;
    SystemLogSessionInfo info;
    SystemDeviceResult result;
    uint16_t header_size = 0U;

    SILVERSTAR_ASSERT(s_logger.session_active <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_logger.header_written <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    result = SystemLogSink_Init();
    if ((result != SYSTEM_DEVICE_OK) &&
        (result != SYSTEM_DEVICE_ALREADY_MATCHED))
    {
        return 0U;
    }
    (void)memset(&info, 0, sizeof(info));
    info.profile_id = SystemProfile_Get()->profile_id;
    info.version_major = SILVERSTAR_VERSION_MAJOR;
    info.version_minor = SILVERSTAR_VERSION_MINOR;
    info.version_patch = SILVERSTAR_VERSION_PATCH;
    result = SystemLogSink_SessionBegin(&info);
    if ((result != SYSTEM_DEVICE_OK) &&
        (result != SYSTEM_DEVICE_ALREADY_MATCHED))
    {
        return 0U;
    }
    s_logger.session_active = 1U;
    s_logger.last_flush_us = SystemTime_GetMonotonicUs();
    if (s_logger.header_written == 0U)
    {
        LoggerTask_HeaderInfoBuild(&header_info);
        if ((FlightLog_FileHeaderSerialize(&header_info, s_record_buffer,
                                           sizeof(s_record_buffer),
                                           &header_size) !=
             FLIGHT_LOG_SERIALIZE_RESULT_OK) ||
            (LoggerTask_SinkWrite(s_record_buffer, header_size) == 0U) ||
            (SystemLogSink_Flush() != SYSTEM_DEVICE_OK))
        {
            LoggerTask_Close();
            return 0U;
        }
        s_logger.header_written = 1U;
        s_logger.record_sequence = 0U;
        s_logger.last_flush_us = SystemTime_GetMonotonicUs();
    }
    return 1U;
}

static uint8_t LoggerTask_RecordIsCritical(const FlightLogRecord *record)
{
    if (record == NULL) { return 0U; }
    if ((record->record_type == FLIGHT_LOG_RECORD_SYSTEM_CONFIG) ||
        (record->record_type == FLIGHT_LOG_RECORD_DEVICE_DESCRIPTOR) ||
        (record->record_type == FLIGHT_LOG_RECORD_ALGORITHM_DESCRIPTOR) ||
        (record->record_type == FLIGHT_LOG_RECORD_LOG_STREAM_DESCRIPTOR) ||
        (record->record_type == FLIGHT_LOG_RECORD_INITIAL_STATE) ||
        (record->record_type == FLIGHT_LOG_RECORD_CALIBRATION_RESULT) ||
        (record->record_type == FLIGHT_LOG_RECORD_ALIGNMENT_RESULT))
    {
        return 1U;
    }
    return (uint8_t)((record->record_type == FLIGHT_LOG_RECORD_EVENT) &&
        ((record->payload.event.event_id == FLIGHT_LOG_EVENT_MISSION_START) ||
         (record->payload.event.event_id == FLIGHT_LOG_EVENT_SELF_TEST_COMPLETE) ||
         (record->payload.event.event_id == FLIGHT_LOG_EVENT_LANDING) ||
         (record->payload.event.event_id == FLIGHT_LOG_EVENT_SYSTEM_FAULT)));
}

static uint8_t LoggerTask_Finalize(void)
{
    if ((s_logger.session_active == 0U) ||
        (LoggerTask_AggregateWrite() == 0U) ||
        (SystemLogSink_Flush() != SYSTEM_DEVICE_OK) ||
        (SystemLogSink_SessionEnd() != SYSTEM_DEVICE_OK))
    {
        return 0U;
    }
    s_logger.last_flush_us = SystemTime_GetMonotonicUs();
    s_logger.session_active = 0U;
    s_logger.session_finalized = 1U;
    s_logger.aggregate_length = 0U;
    LoggerBus_FinalizationComplete();
    return 1U;
}

static uint8_t LoggerTask_RecordAppend(const FlightLogRecord *record)
{
    uint16_t serialized_size = 0U;

    if (record == NULL) { return 0U; }
    SILVERSTAR_ASSERT_OBJECT(record, FlightLogRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (FlightLog_RecordSerialize(record, s_logger.record_sequence,
                                  s_record_buffer,
                                  sizeof(s_record_buffer),
                                  &serialized_size) !=
        FLIGHT_LOG_SERIALIZE_RESULT_OK)
    {
        return 0U;
    }
    if ((s_logger.aggregate_length + serialized_size) >
        sizeof(s_aggregate_buffer))
    {
        if (LoggerTask_AggregateWrite() == 0U) { return 0U; }
    }
    (void)memcpy(&s_aggregate_buffer[s_logger.aggregate_length],
                 s_record_buffer, serialized_size);
    s_logger.aggregate_length += serialized_size;
    s_logger.record_sequence++;
    if ((LoggerTask_RecordIsCritical(record) != 0U) &&
        (LoggerTask_Flush() == 0U))
    {
        return 0U;
    }
    return 1U;
}

static uint32_t LoggerTask_StringHash(const char *text)
{
    uint32_t hash = 2166136261UL;
    uint32_t index;

    if (text == NULL) { return 0U; }
    for (index = 0U; index < LOGGER_MAX_TEXT_LENGTH; index++)
    {
        if (text[index] == '\0')
        {
            return hash;
        }
        hash ^= (uint8_t)text[index];
        hash *= 16777619UL;
    }
    SILVERSTAR_ASSERT(index < LOGGER_MAX_TEXT_LENGTH,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    return 0U;
}

static uint8_t LoggerTask_StartupEventAppend(uint64_t timestamp_us,
                                             FlightLogEventId event_id,
                                             uint32_t arg0,
                                             uint32_t arg1)
{
    FlightLogRecord record;

    (void)memset(&record, 0, sizeof(record));
    record.record_type = FLIGHT_LOG_RECORD_EVENT;
    record.timestamp_us = timestamp_us;
    record.payload.event.event_id = event_id;
    record.payload.event.arg0 = arg0;
    record.payload.event.arg1 = arg1;
    return LoggerTask_RecordAppend(&record);
}

static uint8_t LoggerTask_StartupDeviceAppend(
    uint64_t timestamp_us,
    const SystemStartupDeviceReport *device)
{
    uint32_t identity;
    uint32_t results;

    SILVERSTAR_ASSERT_OBJECT(device, SystemStartupDeviceReport,
                             SILVERSTAR_ASSERT_MODULE_APP);
    identity = (uint32_t)device->device_id |
        ((uint32_t)device->required << 8U) |
        ((uint32_t)device->safety_critical << 9U) |
        ((uint32_t)device->present << 10U) |
        ((device->capability_mask & 0xFFFFUL) << 16U);
    results = ((uint32_t)device->init_result) |
        ((uint32_t)device->start_result << 4U) |
        ((uint32_t)device->config_result << 8U) |
        ((uint32_t)device->persist_result << 12U) |
        ((uint32_t)device->verify_result << 16U) |
        ((uint32_t)device->communication_result << 20U);
    if ((LoggerTask_StartupEventAppend(timestamp_us,
            FLIGHT_LOG_EVENT_STARTUP_DEVICE_RESULT,
            identity, results) == 0U) ||
        (LoggerTask_StartupEventAppend(timestamp_us,
            FLIGHT_LOG_EVENT_STARTUP_CONFIG_MASKS,
            device->requested_mask, device->applied_mask) == 0U) ||
        (LoggerTask_StartupEventAppend(timestamp_us,
            FLIGHT_LOG_EVENT_STARTUP_CONFIG_FAILURES,
            device->delegated_mask, device->failed_mask) == 0U) ||
        (LoggerTask_StartupEventAppend(timestamp_us,
            FLIGHT_LOG_EVENT_STARTUP_DEVICE_DETAIL,
            device->detail_code, device->retry_count) == 0U) ||
        (LoggerTask_StartupEventAppend(timestamp_us,
            FLIGHT_LOG_EVENT_STARTUP_DEVICE_NAMES,
            LoggerTask_StringHash(device->device_name),
            LoggerTask_StringHash(device->model_name)) == 0U))
    { return 0U; }
    return 1U;
}

static uint8_t LoggerTask_StartupGnssAppend(
    uint64_t timestamp_us,
    const SystemGnssConfigTransactionReport *gnss)
{
    uint32_t results;

    SILVERSTAR_ASSERT_OBJECT(gnss, SystemGnssConfigTransactionReport,
                             SILVERSTAR_ASSERT_MODULE_APP);
    results = ((uint32_t)gnss->uart_baudrate_result) |
        ((uint32_t)gnss->uart_settle_result << 4U) |
        ((uint32_t)gnss->protocol_result << 8U) |
        ((uint32_t)gnss->nav_pvt_result << 12U) |
        ((uint32_t)gnss->rate_result << 16U) |
        ((uint32_t)gnss->dynamic_model_result << 20U) |
        ((uint32_t)gnss->signals_result << 24U) |
        ((uint32_t)gnss->pvt_recovery_result << 28U);
    if (LoggerTask_StartupEventAppend(
            timestamp_us,
            FLIGHT_LOG_EVENT_GNSS_CONFIG_TRANSACTION,
            results,
            ((uint32_t)gnss->failed_stage << 16U) |
            ((uint32_t)gnss->ack_result << 8U) |
            (uint32_t)gnss->write_layers) == 0U)
    {
        return 0U;
    }
    return 1U;
}

static uint8_t LoggerTask_StartupReportWrite(void)
{
    const SystemStartupReport *report = SystemStartup_GetReport();
    uint8_t index;

    if ((report == NULL) || (report->completed == 0U)) { return 0U; }
    SILVERSTAR_ASSERT_OBJECT(report, SystemStartupReport,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (LoggerTask_StartupEventAppend(report->timestamp_us,
            FLIGHT_LOG_EVENT_SELF_TEST_COMPLETE, report->passed,
            ((report->required_failure_mask & 0xFFFFUL) << 16U) |
             (report->warning_mask & 0xFFFFUL)) == 0U)
    { return 0U; }
    for (index = 0U; index < report->device_count; index++)
    {
        if (LoggerTask_StartupDeviceAppend(
                report->timestamp_us, &report->devices[index]) == 0U)
        { return 0U; }
    }
    return LoggerTask_StartupGnssAppend(
        report->timestamp_us, &report->gnss_config);
}

static void LoggerTask_SessionOpenTry(uint64_t now_us)
{
    SILVERSTAR_ASSERT(s_logger.session_active == 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_logger.startup_report_written <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (now_us < s_logger.next_retry_us) { return; }
    if (LoggerTask_SessionOpen() == 0U)
    {
        s_logger.next_retry_us = now_us + SYSTEM_LOG_RETRY_PERIOD_US;
    }
    else if ((s_logger.startup_report_written == 0U) &&
             (LoggerTask_StartupReportWrite() == 0U))
    {
        LoggerTask_Close();
        s_logger.next_retry_us = now_us + SYSTEM_LOG_RETRY_PERIOD_US;
    }
    else
    {
        s_logger.startup_report_written = 1U;
    }
}

static uint8_t LoggerTask_DrainFinalizeTry(
    uint64_t now_us,
    LoggerBusFinalizationState finalization_state)
{
    if ((s_logger.session_active == 0U) ||
        (finalization_state != LOGGER_BUS_FINALIZATION_DRAINING) ||
        (LoggerBus_Count() != 0U))
    { return 0U; }
    if ((now_us >= s_logger.next_retry_us) &&
        (LoggerTask_Finalize() == 0U))
    {
        s_logger.next_retry_us = now_us + SYSTEM_LOG_RETRY_PERIOD_US;
    }
    return 1U;
}

void AppTask_Logger(void *argument)
{
    FlightLogRecord record;
    LoggerBusFinalizationState finalization_state;
    uint64_t now_us;

    (void)argument;
    (void)memset(&s_logger, 0, sizeof(s_logger));
    SILVERSTAR_ASSERT(s_logger.session_active == 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_logger.session_finalized == 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    for (;;)
    {
        now_us = SystemTime_GetMonotonicUs();
        finalization_state = LoggerBus_FinalizationProcess(now_us);
        if ((s_logger.session_finalized != 0U) ||
            (finalization_state == LOGGER_BUS_FINALIZATION_FINALIZED))
        {
            vTaskDelay(pdMS_TO_TICKS(10U));
            continue;
        }
        if (s_logger.session_active == 0U)
        {
            LoggerTask_SessionOpenTry(now_us);
            vTaskDelay(pdMS_TO_TICKS(10U));
            continue;
        }

        if (LoggerBus_NextPop(&record) == LOGGER_BUS_RESULT_OK)
        {
            if (LoggerTask_RecordAppend(&record) == 0U)
            {
                LoggerTask_Close();
                s_logger.next_retry_us = now_us + SYSTEM_LOG_RETRY_PERIOD_US;
            }
        }
        else
        {
            vTaskDelay(pdMS_TO_TICKS(2U));
        }

        now_us = SystemTime_GetMonotonicUs();
        finalization_state = LoggerBus_FinalizationProcess(now_us);
        if (LoggerTask_DrainFinalizeTry(now_us, finalization_state) != 0U)
        {
            vTaskDelay(pdMS_TO_TICKS(2U));
            continue;
        }
        if ((s_logger.session_active != 0U) &&
            ((now_us - s_logger.last_flush_us) >= SYSTEM_LOG_SYNC_PERIOD_US))
        {
            if (LoggerTask_Flush() == 0U)
            {
                LoggerTask_Close();
                s_logger.next_retry_us = now_us + SYSTEM_LOG_RETRY_PERIOD_US;
            }
        }
    }
}
