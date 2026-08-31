#include "logger_bus.h"

#include <stddef.h>
#include <string.h>

#include "common_spsc_queue.h"
#include "platform_critical.h"
#include "project_log_decoder_profile.h"
#include "silverstar_assert.h"
#include "system_descriptor_if.h"
#include "system_estimator_profile.h"
#include "system_log_policy.h"
#include "system_navigation_profile.h"
#include "system_profile.h"
#include "system_user_config.h"
#include "system_version.h"

#define LOGGER_RECORD_QUEUE_DEPTH \
    SYSTEM_LOG_RECORD_QUEUE_DEPTH
#define LOGGER_ESTIMATOR_RECORD_QUEUE_DEPTH \
    SYSTEM_LOG_ESTIMATOR_QUEUE_DEPTH

_Static_assert(FLIGHT_LOG_MAX_PAYLOAD_SIZE >=
               FLIGHT_LOG_SAMPLE_PAYLOAD_SIZE,
               "SSLOG payload capacity is too small");
_Static_assert(FLIGHT_LOG_RECORD_DECODER_PROFILE_DESCRIPTOR <= 0xFFU,
               "SSLOG0 record type must fit in one byte");
static CommonSpscQueue s_logger_queue;
static FlightLogRecord s_logger_storage[LOGGER_RECORD_QUEUE_DEPTH];
static CommonSpscQueue s_estimator_logger_queue;
static FlightLogRecord
    s_estimator_logger_storage[LOGGER_ESTIMATOR_RECORD_QUEUE_DEPTH];
static uint8_t s_initialized;
static uint8_t s_next_estimator_queue;
static uint8_t s_accepting_records;
static LoggerBusFinalizationState s_finalization_state;
static uint64_t s_finalization_deadline_us;

static PlatformCriticalState LoggerBus_IrqLock(void)
{
    return PlatformCritical_Enter();
}

static void LoggerBus_IrqUnlock(PlatformCriticalState state)
{
    PlatformCritical_Exit(state);
}

static LoggerBusResult LoggerBus_PushStateGet(void)
{
    LoggerBusResult result;
    PlatformCriticalState state = LoggerBus_IrqLock();

    result = ((s_initialized != 0U) && (s_accepting_records != 0U)) ?
        LOGGER_BUS_RESULT_OK : LOGGER_BUS_RESULT_BAD_STATE;
    LoggerBus_IrqUnlock(state);
    return result;
}

static LoggerBusResult LoggerBus_QueuePush(
    CommonSpscQueue *queue, const FlightLogRecord *record)
{
    CommonSpscQueueResult queue_result;
    PlatformCriticalState state;

    if ((queue == NULL) || (record == NULL))
    {
        return LOGGER_BUS_RESULT_BAD_PARAM;
    }
    SILVERSTAR_ASSERT_OBJECT(queue, CommonSpscQueue,
                             SILVERSTAR_ASSERT_MODULE_APP);
    state = LoggerBus_IrqLock();
    if ((s_initialized == 0U) || (s_accepting_records == 0U))
    {
        LoggerBus_IrqUnlock(state);
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    queue_result = CommonSpscQueue_Push(queue, record);
    LoggerBus_IrqUnlock(state);
    if (queue_result == COMMON_SPSC_QUEUE_RESULT_OK)
    {
        return LOGGER_BUS_RESULT_OK;
    }
    return (queue_result == COMMON_SPSC_QUEUE_RESULT_FULL) ?
        LOGGER_BUS_RESULT_FULL : LOGGER_BUS_RESULT_BAD_PARAM;
}

static LoggerBusResult LoggerBus_RecordPush(
    FlightLogRecordType type, uint64_t timestamp_us,
    uint32_t valid_flags, const void *payload,
    size_t payload_size, uint8_t estimator_queue)
{
    FlightLogRecord record;

    if ((payload == NULL) || (payload_size > sizeof(record.payload)))
    {
        return LOGGER_BUS_RESULT_BAD_PARAM;
    }
    (void)memset(&record, 0, sizeof(record));
    record.record_type = type;
    record.timestamp_us = timestamp_us;
    record.valid_flags = valid_flags;
    /* In-memory queue copy only; SSLOG wire bytes use the generated codec. */
    (void)memcpy(&record.payload, payload, payload_size);
    return LoggerBus_QueuePush(
        (estimator_queue != 0U) ?
            &s_estimator_logger_queue : &s_logger_queue,
        &record);
}

static LoggerBusResult LoggerBus_ConfiguredRecordPush(
    FlightLogRecordType type, uint64_t timestamp_us,
    uint32_t valid_flags, const void *payload,
    size_t payload_size, uint8_t estimator_queue)
{
    if (payload == NULL) { return LOGGER_BUS_RESULT_BAD_PARAM; }
    if (LoggerBus_PushStateGet() != LOGGER_BUS_RESULT_OK)
    {
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    if (SystemLogPolicy_ShouldEmit(type) == 0U)
    {
        return LOGGER_BUS_RESULT_OK;
    }
    return LoggerBus_RecordPush(type, timestamp_us, valid_flags,
                                payload, payload_size, estimator_queue);
}

LoggerBusResult LoggerBus_Init(void)
{
    CommonSpscQueueResult normal_result;
    CommonSpscQueueResult estimator_result;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_accepting_records <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_initialized != 0U) { return LOGGER_BUS_RESULT_OK; }
    SystemLogPolicy_Init();
    (void)memset(s_logger_storage, 0, sizeof(s_logger_storage));
    (void)memset(s_estimator_logger_storage, 0,
                 sizeof(s_estimator_logger_storage));
    normal_result = CommonSpscQueue_Init(
        &s_logger_queue, s_logger_storage,
        LOGGER_RECORD_QUEUE_DEPTH, sizeof(FlightLogRecord));
    estimator_result = CommonSpscQueue_Init(
        &s_estimator_logger_queue, s_estimator_logger_storage,
        LOGGER_ESTIMATOR_RECORD_QUEUE_DEPTH, sizeof(FlightLogRecord));
    if ((normal_result != COMMON_SPSC_QUEUE_RESULT_OK) ||
        (estimator_result != COMMON_SPSC_QUEUE_RESULT_OK))
    {
        return LOGGER_BUS_RESULT_BAD_PARAM;
    }
    s_initialized = 1U;
    s_next_estimator_queue = 0U;
    s_accepting_records = 1U;
    s_finalization_state = LOGGER_BUS_FINALIZATION_IDLE;
    s_finalization_deadline_us = 0ULL;
    SystemLogPolicy_EmissionReset();
    return LOGGER_BUS_RESULT_OK;
}

void LoggerBus_Reset(void)
{
    PlatformCriticalState state = LoggerBus_IrqLock();

    if (s_initialized != 0U)
    {
        CommonSpscQueue_Reset(&s_logger_queue);
        CommonSpscQueue_Reset(&s_estimator_logger_queue);
        s_next_estimator_queue = 0U;
        s_accepting_records = 1U;
        s_finalization_state = LOGGER_BUS_FINALIZATION_IDLE;
        s_finalization_deadline_us = 0ULL;
    }
    LoggerBus_IrqUnlock(state);
    SystemLogPolicy_EmissionReset();
}

LoggerBusResult LoggerBus_SamplePush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogSampleRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_SAMPLE, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_EventPush(
    uint64_t timestamp_us, FlightLogEventId event_id,
    uint32_t arg0, uint32_t arg1)
{
    FlightLogEventRecord record;

    if ((event_id < FLIGHT_LOG_EVENT_BOOT) ||
        (event_id > FLIGHT_LOG_EVENT_SENSOR_SOURCE_CHANGE))
    {
        return LOGGER_BUS_RESULT_BAD_PARAM;
    }
    (void)memset(&record, 0, sizeof(record));
    record.event_id = event_id;
    record.arg0 = arg0;
    record.arg1 = arg1;
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_EVENT, timestamp_us, 0U,
        &record, sizeof(record), 0U);
}

LoggerBusResult LoggerBus_StatsPush(
    uint64_t timestamp_us, const FlightLogStatsRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_STATS, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_EstimatorPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogEstimatorRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_ESTIMATOR, timestamp_us, valid_flags,
        record, sizeof(*record), 1U);
}

static void LoggerBus_EstimatorConfigBuild(
    FlightLogSystemConfigRecord *record,
    const SystemEstimatorProfile *estimator_profile)
{
    SILVERSTAR_ASSERT_OBJECT(record, FlightLogSystemConfigRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(estimator_profile, SystemEstimatorProfile,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memcpy(record->p0_diagonal, estimator_profile->p0_diagonal,
                 sizeof(record->p0_diagonal));
    (void)memcpy(record->process_accel_std_mps2,
                 estimator_profile->process_accel_std_mps2,
                 sizeof(record->process_accel_std_mps2));
    record->measurement_profile[0] = estimator_profile->gnss_accuracy_scale;
    record->measurement_profile[1] =
        estimator_profile->gnss_horizontal_position_std_floor_m;
    record->measurement_profile[2] =
        estimator_profile->gnss_vertical_position_std_floor_m;
    record->measurement_profile[3] =
        estimator_profile->gnss_velocity_std_floor_mps;
    record->measurement_profile[4] =
        estimator_profile->barometer_altitude_std_m;
    record->nis_profile[0] = estimator_profile->nis_1d_soft;
    record->nis_profile[1] = estimator_profile->nis_1d_hard;
    record->nis_profile[2] = estimator_profile->nis_2d_soft;
    record->nis_profile[3] = estimator_profile->nis_2d_hard;
    record->nis_profile[4] = estimator_profile->nis_3d_soft;
    record->nis_profile[5] = estimator_profile->nis_3d_hard;
    record->nis_profile[6] = estimator_profile->nis_max_r_scale;
}

static void LoggerBus_SystemConfigBuild(
    FlightLogSystemConfigRecord *record)
{
    const SystemEstimatorProfile *estimator_profile =
        SystemEstimatorProfile_Get();

    SILVERSTAR_ASSERT_OBJECT(record, FlightLogSystemConfigRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(record, 0, sizeof(*record));
    record->version[0] = SILVERSTAR_VERSION_MAJOR;
    record->version[1] = SILVERSTAR_VERSION_MINOR;
    record->version[2] = SILVERSTAR_VERSION_PATCH;
    record->version[3] = SILVERSTAR_VERSION_BUILD;
    record->profile_id = SystemProfile_Get()->profile_id;
    record->device_config_digest = SystemDescriptor_ConfigDigestGet();
    record->configured_imu_rate_hz = SYSTEM_IMU_OUTPUT_RATE_HZ;
    record->configured_gnss_rate_hz = SYSTEM_GNSS_NAVIGATION_RATE_HZ;
    record->configured_magnetometer_rate_hz =
        SYSTEM_MAGNETOMETER_OUTPUT_RATE_HZ;
    record->configured_barometer_rate_hz =
        SYSTEM_BAROMETER_OUTPUT_RATE_HZ;
    record->configured_hardware_quaternion_rate_hz =
        SYSTEM_HARDWARE_QUATERNION_OUTPUT_RATE_HZ;
    record->mechanization_subsample_count =
        SYSTEM_MECHANIZATION_SUBSAMPLE_COUNT;
    record->expected_ins_rate_hz = (uint16_t)(SYSTEM_IMU_OUTPUT_RATE_HZ /
        SYSTEM_MECHANIZATION_SUBSAMPLE_COUNT);
    record->mechanization_min_sample_rate_hz =
        SYSTEM_MECHANIZATION_SAMPLE_RATE_MIN_HZ;
    record->mechanization_max_sample_rate_hz =
        SYSTEM_MECHANIZATION_SAMPLE_RATE_MAX_HZ;
    record->log_profile_id = SYSTEM_LOG_PROFILE_ID;
    record->sync_period_us = (uint32_t)SYSTEM_LOG_SYNC_PERIOD_US;
    record->aggregation_buffer_size = SYSTEM_LOG_AGGREGATION_BUFFER_SIZE;
    record->normal_queue_depth = SYSTEM_LOG_RECORD_QUEUE_DEPTH;
    record->estimator_queue_depth = SYSTEM_LOG_ESTIMATOR_QUEUE_DEPTH;
    record->device_descriptor_count =
        SystemDescriptor_DeviceCountGet();
    record->algorithm_descriptor_count =
        SystemDescriptor_AlgorithmCountGet();
    record->log_stream_descriptor_count =
        SystemLogPolicy_StreamCountGet();
    LoggerBus_EstimatorConfigBuild(record, estimator_profile);
}

static LoggerBusResult LoggerBus_DeviceDescriptorsPush(
    uint64_t timestamp_us)
{
    FlightLogDeviceDescriptorRecord record;
    SystemDeviceDescriptor descriptor;
    LoggerBusResult result;
    uint16_t count = SystemDescriptor_DeviceCountGet();
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(&record, FlightLogDeviceDescriptorRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (count > SYSTEM_DESCRIPTOR_DEVICE_COUNT_MAX)
    {
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    for (index = 0U; index < count; index++)
    {
        if (SystemDescriptor_DeviceGet(index, &descriptor) !=
            SYSTEM_DEVICE_OK)
        {
            return LOGGER_BUS_RESULT_BAD_STATE;
        }
        (void)memset(&record, 0, sizeof(record));
        record.descriptor_id = descriptor.descriptor_id;
        record.physical_device_id = descriptor.physical_device_id;
        record.device_class = (uint8_t)descriptor.device_class;
        record.instance_id = descriptor.instance_id;
        record.driver_id = descriptor.driver_id;
        record.flags = descriptor.flags;
        record.capability_mask = descriptor.capability_mask;
        record.configured_rate_hz = descriptor.configured_rate_hz;
        record.driver_name_hash = descriptor.driver_name_hash;
        record.model_name_hash = descriptor.model_name_hash;
        result = LoggerBus_RecordPush(
            FLIGHT_LOG_RECORD_DEVICE_DESCRIPTOR, timestamp_us, 0U,
            &record, sizeof(record), 0U);
        if (result != LOGGER_BUS_RESULT_OK) { return result; }
    }
    return LOGGER_BUS_RESULT_OK;
}

static LoggerBusResult LoggerBus_AlgorithmDescriptorsPush(
    uint64_t timestamp_us)
{
    FlightLogAlgorithmDescriptorRecord record;
    SystemAlgorithmDescriptor descriptor;
    LoggerBusResult result;
    uint16_t count = SystemDescriptor_AlgorithmCountGet();
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(&record, FlightLogAlgorithmDescriptorRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (count > SYSTEM_DESCRIPTOR_ALGORITHM_COUNT_MAX)
    {
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    for (index = 0U; index < count; index++)
    {
        if (SystemDescriptor_AlgorithmGet(index, &descriptor) !=
            SYSTEM_DEVICE_OK)
        {
            return LOGGER_BUS_RESULT_BAD_STATE;
        }
        (void)memset(&record, 0, sizeof(record));
        record.descriptor_id = descriptor.descriptor_id;
        record.algorithm_class = (uint8_t)descriptor.algorithm_class;
        record.instance_id = descriptor.instance_id;
        record.algorithm_id = descriptor.algorithm_id;
        record.flags = descriptor.flags;
        record.config_digest = descriptor.config_digest;
        record.name_hash = descriptor.name_hash;
        result = LoggerBus_RecordPush(
            FLIGHT_LOG_RECORD_ALGORITHM_DESCRIPTOR, timestamp_us, 0U,
            &record, sizeof(record), 0U);
        if (result != LOGGER_BUS_RESULT_OK) { return result; }
    }
    return LOGGER_BUS_RESULT_OK;
}

static LoggerBusResult LoggerBus_StreamDescriptorsPush(
    uint64_t timestamp_us)
{
    const SslogRecordMetadata *metadata;
    FlightLogStreamDescriptorRecord record;
    SystemLogStreamConfig config;
    LoggerBusResult result;
    uint16_t count = SystemLogPolicy_StreamCountGet();
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(&record, FlightLogStreamDescriptorRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (count > SSLOG_RECORD_COUNT)
    {
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    for (index = 0U; index < count; index++)
    {
        if (SystemLogPolicy_StreamByIndexGet(index, &config) !=
            SYSTEM_DEVICE_OK)
        {
            return LOGGER_BUS_RESULT_BAD_STATE;
        }
        metadata = SslogRecords_MetadataGet(config.record_type);
        if (metadata == NULL) { return LOGGER_BUS_RESULT_BAD_STATE; }
        (void)memset(&record, 0, sizeof(record));
        record.record_type = (uint8_t)config.record_type;
        record.record_version = metadata->record_version;
        record.enabled = config.enabled;
        record.policy = (uint8_t)config.policy;
        record.decimation = config.decimation;
        record.period_us = config.period_us;
        result = LoggerBus_RecordPush(
            FLIGHT_LOG_RECORD_LOG_STREAM_DESCRIPTOR, timestamp_us, 0U,
            &record, sizeof(record), 0U);
        if (result != LOGGER_BUS_RESULT_OK) { return result; }
    }
    return LOGGER_BUS_RESULT_OK;
}

LoggerBusResult LoggerBus_SystemConfigPush(uint64_t timestamp_us)
{
    FlightLogSystemConfigRecord record;
    LoggerBusResult result;
    uint16_t required_slots;
    uint16_t used_slots;
    PlatformCriticalState state;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_accepting_records <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (LoggerBus_PushStateGet() != LOGGER_BUS_RESULT_OK)
    {
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    if (SystemLogPolicy_ShouldEmit(FLIGHT_LOG_RECORD_SYSTEM_CONFIG) == 0U)
    {
        return LOGGER_BUS_RESULT_OK;
    }
    required_slots = (uint16_t)(1U + SystemDescriptor_DeviceCountGet() +
        SystemDescriptor_AlgorithmCountGet() +
        SystemLogPolicy_StreamCountGet());
    state = LoggerBus_IrqLock();
    used_slots = CommonSpscQueue_Count(&s_logger_queue);
    LoggerBus_IrqUnlock(state);
    if (required_slots > LOGGER_RECORD_QUEUE_DEPTH)
    {
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    if (used_slots > (LOGGER_RECORD_QUEUE_DEPTH - required_slots))
    {
        return LOGGER_BUS_RESULT_FULL;
    }
    LoggerBus_SystemConfigBuild(&record);
    result = LoggerBus_RecordPush(
        FLIGHT_LOG_RECORD_SYSTEM_CONFIG, timestamp_us, 0U,
        &record, sizeof(record), 0U);
    if (result != LOGGER_BUS_RESULT_OK) { return result; }
    result = LoggerBus_DeviceDescriptorsPush(timestamp_us);
    if (result != LOGGER_BUS_RESULT_OK) { return result; }
    result = LoggerBus_AlgorithmDescriptorsPush(timestamp_us);
    if (result != LOGGER_BUS_RESULT_OK) { return result; }
    return LoggerBus_StreamDescriptorsPush(timestamp_us);
}

LoggerBusResult LoggerBus_MissionConfigPush(uint64_t timestamp_us)
{
    FlightLogMissionConfigRecord record;

    (void)memset(&record, 0, sizeof(record));
    SILVERSTAR_ASSERT_OBJECT(&record, FlightLogMissionConfigRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    record.alignment_algorithm = (uint8_t)SYSTEM_ALIGNMENT_ALGORITHM;
    record.rocket_longitudinal_axis =
        (uint8_t)SYSTEM_FLIGHT_ROCKET_LONGITUDINAL_AXIS;
    record.deploy_trigger_mask =
        (uint8_t)SYSTEM_FLIGHT_DEPLOY_TRIGGER_MASK;
    record.tilt_reference = (uint8_t)SYSTEM_FLIGHT_TILT_REFERENCE;
    record.landing_enable = SYSTEM_FLIGHT_LANDING_DETECTION_ENABLE;
    record.landing_mode = (uint8_t)SYSTEM_FLIGHT_LANDING_MODE;
    record.impact_capable = SYSTEM_IMU_CAP_LANDING_IMPACT_DETECTION;
    record.known_yaw_deg = SYSTEM_ALIGNMENT_KNOWN_YAW_DEG;
    record.magnetic_declination_deg =
        SYSTEM_ALIGNMENT_MAGNETIC_DECLINATION_DEG;
    record.tilt_threshold_deg = SYSTEM_FLIGHT_TILT_THRESHOLD_DEG;
    record.apogee_vz_threshold_mps =
        SYSTEM_FLIGHT_APOGEE_VZ_THRESHOLD_MPS;
    record.deploy_confirm_ms = SYSTEM_FLIGHT_DEPLOY_CONFIRM_MS;
    record.deploy_delay_ms = SYSTEM_FLIGHT_DEPLOY_DELAY_MS;
    record.baro_trigger_window_ms =
        SYSTEM_FLIGHT_LANDING_BARO_TRIGGER_WINDOW_MS;
    record.baro_trigger_min_samples =
        SYSTEM_FLIGHT_LANDING_BARO_TRIGGER_MIN_SAMPLES;
    record.baro_trigger_rate_mps =
        SYSTEM_FLIGHT_LANDING_BARO_TRIGGER_RATE_MPS;
    record.candidate_duration_ms =
        SYSTEM_FLIGHT_LANDING_CANDIDATE_DURATION_MS;
    record.baro_confirm_rate_mps =
        SYSTEM_FLIGHT_LANDING_BARO_CONFIRM_RATE_MPS;
    record.baro_max_span_m = SYSTEM_FLIGHT_LANDING_BARO_MAX_SPAN_M;
    record.candidate_baro_min_samples =
        SYSTEM_FLIGHT_LANDING_BARO_MIN_SAMPLES;
    record.candidate_imu_min_samples =
        SYSTEM_FLIGHT_LANDING_IMU_MIN_SAMPLES;
    record.candidate_min_coverage_percent =
        SYSTEM_FLIGHT_LANDING_MIN_COVERAGE_PERCENT;
    record.impact_inhibit_ms =
        SYSTEM_FLIGHT_LANDING_IMPACT_INHIBIT_MS;
    record.impact_threshold_mps2 =
        SYSTEM_FLIGHT_LANDING_IMPACT_THRESHOLD_MPS2;
    record.still_gyro_threshold_radps =
        SYSTEM_FLIGHT_LANDING_STILL_GYRO_THRESHOLD_RADPS;
    record.still_accel_tolerance_mps2 =
        SYSTEM_FLIGHT_LANDING_STILL_ACCEL_TOLERANCE_MPS2;
    record.landing_confirm_ms = SYSTEM_FLIGHT_LANDING_CONFIRM_MS;
    record.landing_sample_max_age_ms =
        SYSTEM_FLIGHT_LANDING_SAMPLE_MAX_AGE_MS;
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_MISSION_CONFIG, timestamp_us, 0U,
        &record, sizeof(record), 0U);
}

static void LoggerBus_DecoderProfileRecordBuild(
    const ProjectLogDecoderProfile *profile,
    FlightLogDecoderProfileDescriptorRecord *record)
{
    SILVERSTAR_ASSERT_OBJECT(profile, ProjectLogDecoderProfile,
        SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(record, FlightLogDecoderProfileDescriptorRecord,
        SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(record, 0, sizeof(*record));
    record->package_schema_major = profile->package_schema_major;
    record->package_schema_minor = profile->package_schema_minor;
    record->container_format_major = profile->container_format_major;
    record->container_format_minor = profile->container_format_minor;
    (void)memcpy(record->record_catalog_hash_128,
        profile->record_catalog_hash_128,
        sizeof(record->record_catalog_hash_128));
    (void)memcpy(record->project_semantics_hash_128,
        profile->project_semantics_hash_128,
        sizeof(record->project_semantics_hash_128));
    (void)memcpy(record->generation_profile_hash_128,
        profile->generation_profile_hash_128,
        sizeof(record->generation_profile_hash_128));
}

LoggerBusResult LoggerBus_DecoderProfileDescriptorPush(uint64_t timestamp_us)
{
    ProjectLogDecoderProfile profile;
    FlightLogDecoderProfileDescriptorRecord record;

    ProjectLogDecoderProfile_Get(&profile);
    LoggerBus_DecoderProfileRecordBuild(&profile, &record);
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_DECODER_PROFILE_DESCRIPTOR,
        timestamp_us, 0U, &record, sizeof(record), 0U);
}

LoggerBusResult LoggerBus_RawSensorPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogRawSensorRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_RAW_SENSOR, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_PureInsPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogPureInsRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_PURE_INS, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_Kf6DiagnosticPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogKf6DiagnosticRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_KF6_DIAGNOSTIC, timestamp_us, valid_flags,
        record, sizeof(*record), 1U);
}

LoggerBusResult LoggerBus_Kf6FullPPush(
    uint64_t timestamp_us, const FlightLogKf6FullPRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_KF6_FULL_P, timestamp_us, 0U,
        record, sizeof(*record), 1U);
}

LoggerBusResult LoggerBus_PowerPush(
    uint64_t timestamp_us, const FlightLogPowerRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_POWER, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_HealthPush(
    uint64_t timestamp_us, const FlightLogHealthRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_HEALTH, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_TelemetryDiagnosticPush(
    uint64_t timestamp_us,
    const FlightLogTelemetryDiagnosticRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_TELEMETRY_DIAG, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_InitialStatePush(
    uint64_t timestamp_us, const FlightLogInitialStateRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_INITIAL_STATE, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_ImuNativePush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogImuNativeRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_IMU_NATIVE, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_GnssNativePush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogGnssNativeRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_GNSS_NATIVE, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_BaroNativePush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogBaroNativeRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_BARO_NATIVE, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_MagNativePush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogMagNativeRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_MAG_NATIVE, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_HardwareQuaternionNativePush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogHardwareQuaternionNativeRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_HW_QUAT_NATIVE, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_InertialIncrementPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogInertialIncrementRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_INERTIAL_INCREMENT, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_GnssMeasurementPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogGnssMeasurementRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_GNSS_MEASUREMENT, timestamp_us, valid_flags,
        record, sizeof(*record), 1U);
}

LoggerBusResult LoggerBus_BaroMeasurementPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogBaroMeasurementRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_BARO_MEASUREMENT, timestamp_us, valid_flags,
        record, sizeof(*record), 1U);
}

LoggerBusResult LoggerBus_ImuCorrectedPush(
    uint64_t timestamp_us, uint32_t valid_flags,
    const FlightLogImuCorrectedRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_IMU_CORRECTED, timestamp_us, valid_flags,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_CalibrationResultPush(
    uint64_t timestamp_us,
    const FlightLogCalibrationResultRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_CALIBRATION_RESULT, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_AlignmentResultPush(
    uint64_t timestamp_us,
    const FlightLogAlignmentResultRecord *record)
{
    return LoggerBus_ConfiguredRecordPush(
        FLIGHT_LOG_RECORD_ALIGNMENT_RESULT, timestamp_us, 0U,
        record, sizeof(*record), 0U);
}

LoggerBusResult LoggerBus_FinalizationArm(uint64_t landing_timestamp_us)
{
    const uint64_t grace_us =
        (uint64_t)SYSTEM_LOG_POST_LANDING_GRACE_MS * 1000ULL;
    PlatformCriticalState state = LoggerBus_IrqLock();

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_finalization_state <=
                      LOGGER_BUS_FINALIZATION_FINALIZED,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    if (s_initialized == 0U)
    {
        LoggerBus_IrqUnlock(state);
        return LOGGER_BUS_RESULT_BAD_STATE;
    }
    if (s_finalization_state == LOGGER_BUS_FINALIZATION_IDLE)
    {
        s_finalization_deadline_us =
            (landing_timestamp_us > (UINT64_MAX - grace_us)) ? UINT64_MAX :
            (landing_timestamp_us + grace_us);
        s_finalization_state = LOGGER_BUS_FINALIZATION_ARMED;
        LoggerBus_IrqUnlock(state);
        return LOGGER_BUS_RESULT_OK;
    }
    if (s_finalization_state == LOGGER_BUS_FINALIZATION_ARMED)
    {
        LoggerBus_IrqUnlock(state);
        return LOGGER_BUS_RESULT_OK;
    }
    LoggerBus_IrqUnlock(state);
    return LOGGER_BUS_RESULT_BAD_STATE;
}

LoggerBusFinalizationState LoggerBus_FinalizationProcess(uint64_t now_us)
{
    LoggerBusFinalizationState finalization_state;
    PlatformCriticalState state = LoggerBus_IrqLock();

    if ((s_finalization_state == LOGGER_BUS_FINALIZATION_ARMED) &&
        (now_us >= s_finalization_deadline_us))
    {
        s_accepting_records = 0U;
        s_finalization_state = LOGGER_BUS_FINALIZATION_DRAINING;
    }
    finalization_state = s_finalization_state;
    LoggerBus_IrqUnlock(state);
    return finalization_state;
}

void LoggerBus_FinalizationComplete(void)
{
    PlatformCriticalState state = LoggerBus_IrqLock();

    if (s_finalization_state == LOGGER_BUS_FINALIZATION_DRAINING)
    {
        s_finalization_state = LOGGER_BUS_FINALIZATION_FINALIZED;
    }
    LoggerBus_IrqUnlock(state);
}

LoggerBusFinalizationState LoggerBus_FinalizationStateGet(void)
{
    LoggerBusFinalizationState finalization_state;
    PlatformCriticalState state = LoggerBus_IrqLock();

    finalization_state = s_finalization_state;
    LoggerBus_IrqUnlock(state);
    return finalization_state;
}

static LoggerBusResult LoggerBus_QueuePop(
    CommonSpscQueue *queue, FlightLogRecord *record)
{
    CommonSpscQueueResult result;
    PlatformCriticalState state;

    if ((queue == NULL) || (record == NULL))
    {
        return LOGGER_BUS_RESULT_BAD_PARAM;
    }
    state = LoggerBus_IrqLock();
    result = CommonSpscQueue_Pop(queue, record);
    LoggerBus_IrqUnlock(state);
    if (result == COMMON_SPSC_QUEUE_RESULT_OK)
    {
        return LOGGER_BUS_RESULT_OK;
    }
    return (result == COMMON_SPSC_QUEUE_RESULT_EMPTY) ?
        LOGGER_BUS_RESULT_EMPTY : LOGGER_BUS_RESULT_BAD_PARAM;
}

LoggerBusResult LoggerBus_Pop(FlightLogRecord *record)
{
    return LoggerBus_QueuePop(&s_logger_queue, record);
}

LoggerBusResult LoggerBus_EstimatorPop(FlightLogRecord *record)
{
    return LoggerBus_QueuePop(&s_estimator_logger_queue, record);
}

LoggerBusResult LoggerBus_NextPop(FlightLogRecord *record)
{
    LoggerBusResult result;

    if (record == NULL) { return LOGGER_BUS_RESULT_BAD_PARAM; }
    SILVERSTAR_ASSERT_OBJECT(record, FlightLogRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (s_next_estimator_queue != 0U)
    {
        result = LoggerBus_EstimatorPop(record);
        if (result == LOGGER_BUS_RESULT_EMPTY)
        {
            result = LoggerBus_Pop(record);
        }
    }
    else
    {
        result = LoggerBus_Pop(record);
        if (result == LOGGER_BUS_RESULT_EMPTY)
        {
            result = LoggerBus_EstimatorPop(record);
        }
    }
    if (result == LOGGER_BUS_RESULT_OK)
    {
        s_next_estimator_queue = (uint8_t)(s_next_estimator_queue == 0U);
    }
    return result;
}

uint16_t LoggerBus_Count(void)
{
    uint16_t count;
    PlatformCriticalState state = LoggerBus_IrqLock();

    count = (uint16_t)(CommonSpscQueue_Count(&s_logger_queue) +
                       CommonSpscQueue_Count(&s_estimator_logger_queue));
    LoggerBus_IrqUnlock(state);
    return count;
}

uint32_t LoggerBus_OverflowCountGet(void)
{
    uint32_t count;
    PlatformCriticalState state = LoggerBus_IrqLock();

    count = s_logger_queue.overflow_count +
            s_estimator_logger_queue.overflow_count;
    LoggerBus_IrqUnlock(state);
    return count;
}
