#include "system_version.h"
#include "jy901b_sensor_adapter.h"

#include <stddef.h>
#include <string.h>

#include "project_resources.h"
#include "jy901b_config.h"
#include "jy901b_imu_build_capabilities.h"
#include "platform_critical.h"
#include "platform_time.h"
#include "platform_uart.h"
#include "silverstar_assert.h"
#include "system_user_config.h"

static volatile uint8_t s_initialized;
static volatile uint8_t s_started;
static volatile uint8_t s_runtime_owner_active;
static SystemDeviceHealth s_health;
static SystemImuConfig s_effective_config;
static IMUData s_published_data;
static uint32_t s_imu_logical_sequence;
static IMUAlgorithm s_staged_algorithm = Algorithm_6Axis;

static uint8_t Jy901bAdapter_ImuSampleBuild(const IMUData *data,
                                              SystemImuSample *sample)
{
    uint8_t index;

    if ((data == NULL) || (sample == NULL) ||
        ((data->ValidMask & 0x03U) != 0x03U) ||
        (data->AccFrameCount == 0U) || (data->GyroFrameCount == 0U))
    {
        return 0U;
    }
    SILVERSTAR_ASSERT_OBJECT(data, IMUData,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    (void)memset(sample, 0, sizeof(*sample));
    sample->sample_timestamp_us =
        (data->AccTimestampUs > data->GyroTimestampUs) ?
            data->AccTimestampUs : data->GyroTimestampUs;
    sample->receive_timestamp_us = sample->sample_timestamp_us;
    for (index = 0U; index < 3U; index++)
    {
        sample->accel_raw[index] = data->AccRaw[index];
        sample->gyro_raw[index] = data->GyroRaw[index];
        sample->accel_b_mps2[index] = data->Acc[index];
        sample->gyro_b_radps[index] = data->Gyro[index];
    }
    sample->temperature_c = data->TemperatureC;
    sample->valid_mask = SYSTEM_IMU_VALID_ACCEL |
                         SYSTEM_IMU_VALID_GYRO |
                         SYSTEM_IMU_VALID_TEMPERATURE;
    return 1U;
}

static void Jy901bAdapter_NativeSampleConvert(const Jy901bImuSample *native,
                                               SystemImuSample *sample)
{
    uint8_t index;

    (void)memset(sample, 0, sizeof(*sample));
    sample->sample_timestamp_us = native->sample_timestamp_us;
    sample->receive_timestamp_us = native->sample_timestamp_us;
    for (index = 0U; index < 3U; index++)
    {
        sample->accel_raw[index] = native->accel_raw[index];
        sample->gyro_raw[index] = native->gyro_raw[index];
        sample->accel_b_mps2[index] = native->accel_mps2[index];
        sample->gyro_b_radps[index] = native->gyro_radps[index];
    }
    sample->temperature_c = native->temperature_c;
    sample->valid_mask = SYSTEM_IMU_VALID_ACCEL |
                         SYSTEM_IMU_VALID_GYRO |
                         SYSTEM_IMU_VALID_TEMPERATURE;
}

static const uint32_t s_baud_candidates[] =
{
    IMU_UART_BAUD_230400,
    IMU_UART_BAUD_115200,
    IMU_UART_BAUD_57600,
    IMU_UART_BAUD_38400,
    IMU_UART_BAUD_19200,
    IMU_UART_BAUD_9600,
    IMU_UART_BAUD_4800
};

#define JY901B_LEGAL_FRAME_WAIT_MAX_POLLS 1024U

static void Jy901bAdapter_EffectiveRangeUpdate(const IMUConfig *config)
{
    static const float accel_ranges_g[] = {2.0f, 4.0f, 8.0f, 16.0f};
    static const float gyro_ranges_dps[] = {200.0f, 500.0f, 1000.0f, 2000.0f};

    SILVERSTAR_ASSERT_OBJECT(config, IMUConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (((config->ValidMask & IMU_CONFIG_VALID_ACCEL_RANGE) != 0U) &&
        (config->AccelRangeValue <
         (sizeof(accel_ranges_g) / sizeof(accel_ranges_g[0]))))
    {
        s_effective_config.accel_range_g =
            accel_ranges_g[config->AccelRangeValue];
        s_effective_config.requested_mask |= SYSTEM_IMU_CFG_ACCEL_RANGE;
    }
    if (((config->ValidMask & IMU_CONFIG_VALID_GYRO_RANGE) != 0U) &&
        (config->GyroRangeValue <
         (sizeof(gyro_ranges_dps) / sizeof(gyro_ranges_dps[0]))))
    {
        s_effective_config.gyro_range_dps =
            gyro_ranges_dps[config->GyroRangeValue];
        s_effective_config.requested_mask |= SYSTEM_IMU_CFG_GYRO_RANGE;
    }
}

static void Jy901bAdapter_EffectiveConfigUpdate(
    const IMUConfig *private_config)
{
    if (private_config == NULL) { return; }
    SILVERSTAR_ASSERT_OBJECT(private_config, IMUConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((private_config->ValidMask & IMU_CONFIG_VALID_RATE) != 0U)
    {
        switch ((IMUOutputRate)private_config->OutputRateValue)
        {
            case OutputRate_0_2Hz:
            case OutputRate_0_5Hz:
            case OutputRate_Single0C:
            case OutputRate_None:
            case OutputRate_Single:
                s_effective_config.output_rate_hz = 0U;
                break;
            case OutputRate_1Hz: s_effective_config.output_rate_hz = 1U; break;
            case OutputRate_2Hz: s_effective_config.output_rate_hz = 2U; break;
            case OutputRate_5Hz: s_effective_config.output_rate_hz = 5U; break;
            case OutputRate_10Hz: s_effective_config.output_rate_hz = 10U; break;
            case OutputRate_20Hz: s_effective_config.output_rate_hz = 20U; break;
            case OutputRate_50Hz: s_effective_config.output_rate_hz = 50U; break;
            case OutputRate_100Hz: s_effective_config.output_rate_hz = 100U; break;
            case OutputRate_200Hz: s_effective_config.output_rate_hz = 200U; break;
            default: s_effective_config.output_rate_hz = 0U; break;
        }
        s_effective_config.requested_mask |= SYSTEM_IMU_CFG_OUTPUT_RATE;
    }
    if ((private_config->ValidMask & IMU_CONFIG_VALID_BANDWIDTH) != 0U)
    {
        switch ((IMUBandwidth)private_config->BandwidthValue)
        {
            case Bandwidth_256Hz: s_effective_config.accel_bandwidth_hz = 256.0f; break;
            case Bandwidth_188Hz: s_effective_config.accel_bandwidth_hz = 188.0f; break;
            case Bandwidth_98Hz: s_effective_config.accel_bandwidth_hz = 98.0f; break;
            case Bandwidth_42Hz: s_effective_config.accel_bandwidth_hz = 42.0f; break;
            case Bandwidth_20Hz: s_effective_config.accel_bandwidth_hz = 20.0f; break;
            case Bandwidth_10Hz: s_effective_config.accel_bandwidth_hz = 10.0f; break;
            case Bandwidth_5Hz: s_effective_config.accel_bandwidth_hz = 5.0f; break;
            default: s_effective_config.accel_bandwidth_hz = 0.0f; break;
        }
        s_effective_config.gyro_bandwidth_hz =
            s_effective_config.accel_bandwidth_hz;
        s_effective_config.requested_mask |=
            SYSTEM_IMU_CFG_ACCEL_BANDWIDTH |
            SYSTEM_IMU_CFG_GYRO_BANDWIDTH;
    }
    Jy901bAdapter_EffectiveRangeUpdate(private_config);
}

static uint8_t Jy901bAdapter_LegalFramesWait(uint32_t timeout_ms)
{
    uint32_t start_tick = PlatformTime_Ms();
    uint32_t poll;

    for (poll = 0U; poll < JY901B_LEGAL_FRAME_WAIT_MAX_POLLS; poll++)
    {
        IMU_Poll();
        if (IMU_GetConsecutiveLegalFrameCount() >=
            JY901B_BAUD_VERIFY_FRAME_COUNT)
        {
            return 1U;
        }
        PlatformTime_DelayMs(1U);
        if ((PlatformTime_Ms() - start_tick) >= timeout_ms)
        {
            break;
        }
    }

    return 0U;
}

static uint8_t Jy901bAdapter_BaudCandidateTry(uint32_t baudrate)
{
    if (PlatformUart_BaudSet(PROJECT_RESOURCE_IMU_UART, baudrate) != PLATFORM_OK)
    {
        return 0U;
    }
    IMU_StreamReset();
    (void)PlatformUart_RxFlush(PROJECT_RESOURCE_IMU_UART);
    return Jy901bAdapter_LegalFramesWait(JY901B_BAUD_SCAN_DWELL_MS);
}

static uint8_t Jy901bAdapter_BaudRescueRun(void)
{
    IMUConfig private_config;
    uint32_t elapsed_ms;
    uint32_t detected_baudrate = 0U;
    uint8_t pass;
    uint8_t index;

    SILVERSTAR_ASSERT_OBJECT(&s_health, SystemDeviceHealth,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (JY901B_BAUD_RESCUE_ENABLE == 0U)
    {
        return 1U;
    }

    for (pass = 0U; pass < JY901B_BAUD_SCAN_PASS_COUNT; pass++)
    {
        for (index = 0U;
             index < (uint8_t)(sizeof(s_baud_candidates) /
                               sizeof(s_baud_candidates[0]));
             index++)
        {
            if (Jy901bAdapter_BaudCandidateTry(s_baud_candidates[index]) != 0U)
            {
                detected_baudrate = s_baud_candidates[index];
                break;
            }
        }
        if (detected_baudrate == 0U)
        {
            continue;
        }

        (void)IMU_ReadCurrentConfigPartial(&private_config, &elapsed_ms);
        Jy901bAdapter_EffectiveConfigUpdate(&private_config);
        if ((JY901B_BAUD_NORMALIZE_ENABLE != 0U) &&
            (detected_baudrate != IMU_DEFAULT_BAUDRATE))
        {
            if (IMU_SetBaudrate(Baudrate_230400) != IMU_OK)
            {
                detected_baudrate = 0U;
                continue;
            }
            detected_baudrate = IMU_DEFAULT_BAUDRATE;
        }

        IMU_StreamReset();
        (void)PlatformUart_RxFlush(PROJECT_RESOURCE_IMU_UART);
        if (Jy901bAdapter_LegalFramesWait(
                JY901B_BAUD_SCAN_DWELL_MS) != 0U)
        {
            return 1U;
        }
        detected_baudrate = 0U;
    }

    (void)PlatformUart_BaudSet(PROJECT_RESOURCE_IMU_UART, JY901B_UART_BOOT_BAUD);
    IMU_StreamReset();
    (void)PlatformUart_RxFlush(PROJECT_RESOURCE_IMU_UART);
    return 0U;
}

static uint32_t Jy901bAdapter_IrqLock(void)
{
    return PlatformCritical_Enter();
}

static void Jy901bAdapter_IrqUnlock(uint32_t primask)
{
    PlatformCritical_Exit(primask);
}

SystemDeviceResult Jy901bAdapter_SharedInit(void)
{
    IMUState state;

    SILVERSTAR_ASSERT_OBJECT(&s_health, SystemDeviceHealth,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_initialized != 0U)
    {
        return SYSTEM_DEVICE_ALREADY_MATCHED;
    }
    (void)memset(&s_health, 0, sizeof(s_health));
    (void)memset(&s_effective_config, 0, sizeof(s_effective_config));
    (void)memset(&s_published_data, 0, sizeof(s_published_data));
    s_imu_logical_sequence = 0U;
    s_runtime_owner_active = 0U;
    state = IMU_LocalGravitySet(SYSTEM_LOCAL_GRAVITY_MPS2);
    if (state == IMU_OK)
    {
        state = IMU_Init();
    }
    if (state != IMU_OK)
    {
        s_health.error_count++;
        return (state == IMU_RESP_TIMEOUT) ? SYSTEM_DEVICE_TIMEOUT :
                                             SYSTEM_DEVICE_IO_ERROR;
    }
    if (Jy901bAdapter_BaudRescueRun() == 0U)
    {
        s_health.timeout_count++;
        return SYSTEM_DEVICE_TIMEOUT;
    }
    s_initialized = 1U;
    s_health.initialized = 1U;
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult Jy901bAdapter_AlgorithmStage(IMUAlgorithm algorithm)
{
    if ((algorithm != Algorithm_6Axis) && (algorithm != Algorithm_9Axis))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    s_staged_algorithm = algorithm;
    return SYSTEM_DEVICE_CONFIG_DELEGATED;
}

SystemDeviceResult Jy901bAdapter_SharedStart(void)
{
    uint32_t primask;

    if (s_initialized == 0U) { return SYSTEM_DEVICE_NOT_READY; }
    if (s_started != 0U) { return SYSTEM_DEVICE_ALREADY_MATCHED; }
    primask = Jy901bAdapter_IrqLock();
    s_started = 1U;
    s_health.started = 1U;
    Jy901bAdapter_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult Jy901bAdapter_SharedStop(void)
{
    uint32_t primask = Jy901bAdapter_IrqLock();

    s_started = 0U;
    s_health.started = 0U;
    Jy901bAdapter_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

void Jy901bAdapter_SharedProcess(void)
{
    const IMUData *data;
    IMUData snapshot;
    PlatformUartDiagnostics io_diagnostics;
    SystemDeviceHealth health;
    uint32_t primask;

    SILVERSTAR_ASSERT_OBJECT(&s_health, SystemDeviceHealth,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_started == 0U) { return; }
    IMU_Poll();
    (void)PlatformUart_DiagnosticsGet(PROJECT_RESOURCE_IMU_UART, &io_diagnostics);
    data = IMU_GetData();
    snapshot = *data;
    primask = Jy901bAdapter_IrqLock();
    health = s_health;
    Jy901bAdapter_IrqUnlock(primask);
    health.last_sample_timestamp_us =
        (snapshot.GyroTimestampUs > snapshot.AccTimestampUs) ?
            snapshot.GyroTimestampUs : snapshot.AccTimestampUs;
    health.last_receive_timestamp_us = health.last_sample_timestamp_us;
    health.sample_count = s_imu_logical_sequence;
    health.error_count += Jy901bImu_OverflowCountTake();
    health.online = IMU_IsOnline();
    health.healthy = (uint8_t)((health.online != 0U) &&
        ((snapshot.ValidMask & 0x03U) == 0x03U) &&
        (io_diagnostics.rx_active != 0U));
    primask = Jy901bAdapter_IrqLock();
    s_published_data = snapshot;
    s_health = health;
    Jy901bAdapter_IrqUnlock(primask);
}

SystemDeviceResult Jy901bAdapter_SharedHealthGet(SystemDeviceHealth *health)
{
    uint32_t primask;

    if (health == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    primask = Jy901bAdapter_IrqLock();
    *health = s_health;
    Jy901bAdapter_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult Jy901bAdapter_SharedSnapshotGet(IMUData *snapshot)
{
    uint32_t primask;

    if (snapshot == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    if (s_initialized == 0U) { return SYSTEM_DEVICE_NOT_READY; }
    primask = Jy901bAdapter_IrqLock();
    *snapshot = s_published_data;
    Jy901bAdapter_IrqUnlock(primask);
    return (snapshot->FrameCount != 0U) ? SYSTEM_DEVICE_OK :
                                         SYSTEM_DEVICE_NOT_READY;
}

static SystemDeviceResult Jy901bImuAdapter_Init(void)
{
    return Jy901bAdapter_SharedInit();
}

static SystemDeviceResult Jy901bImuAdapter_Start(void)
{
    return Jy901bAdapter_SharedStart();
}

static SystemDeviceResult Jy901bImuAdapter_Stop(void)
{
    return Jy901bAdapter_SharedStop();
}

static SystemDeviceResult Jy901bImuAdapter_RuntimeOwnerActivate(void)
{
    uint32_t primask;

    if (s_started == 0U) { return SYSTEM_DEVICE_NOT_READY; }
    primask = Jy901bAdapter_IrqLock();
    if (s_runtime_owner_active != 0U)
    {
        Jy901bAdapter_IrqUnlock(primask);
        return SYSTEM_DEVICE_ALREADY_MATCHED;
    }
    s_runtime_owner_active = 1U;
    Jy901bAdapter_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult Jy901bAdapter_ConfigAccessCheck(void)
{
    return (s_runtime_owner_active != 0U) ? SYSTEM_DEVICE_BUSY :
                                            SYSTEM_DEVICE_OK;
}

static void Jy901bImuAdapter_Process(void)
{
    Jy901bAdapter_SharedProcess();
}

static SystemDeviceResult Jy901bImuAdapter_GetInfo(SystemDeviceInfo *info)
{
    if (info == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    info->device_name = "JY901B IMU Adapter";
    info->model_name = "JY901B";
    info->driver_version = SILVERSTAR_PRODUCT_STRING;
    info->capability_mask = SYSTEM_IMU_CAP_ACCEL |
                            SYSTEM_IMU_CAP_GYRO |
                            SYSTEM_IMU_CAP_TEMPERATURE |
                            SYSTEM_IMU_CAP_CONFIG_OUTPUT_RATE |
                            SYSTEM_IMU_CAP_CONFIG_BANDWIDTH |
                            SYSTEM_IMU_CAP_CONFIG_RANGE;
    info->configuration_mask = SYSTEM_IMU_CFG_OUTPUT_RATE |
                               SYSTEM_IMU_CFG_ACCEL_BANDWIDTH |
                               SYSTEM_IMU_CFG_GYRO_BANDWIDTH |
                               SYSTEM_IMU_CFG_ACCEL_RANGE |
                               SYSTEM_IMU_CFG_GYRO_RANGE;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_GetCapabilities(uint32_t *mask)
{
    SystemDeviceInfo info;

    if (mask == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)Jy901bImuAdapter_GetInfo(&info);
    *mask = info.capability_mask;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_GetLatestSample(
    SystemImuSample *sample)
{
    IMUData data;
    uint8_t index;
    SystemDeviceResult result;

    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    result = Jy901bAdapter_SharedSnapshotGet(&data);
    if (result != SYSTEM_DEVICE_OK) { return result; }
    (void)index;
    if (Jy901bAdapter_ImuSampleBuild(&data, sample) == 0U)
    {
        return SYSTEM_DEVICE_NOT_READY;
    }
    sample->sequence = s_imu_logical_sequence;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_GetNextSample(
    SystemImuSample *sample)
{
    Jy901bImuSample native;
    Jy901bImuSampleGetResult result;

    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    result = Jy901bImu_SampleGetNext(&native);
    if (result == JY901B_IMU_SAMPLE_GET_EMPTY)
    {
        return SYSTEM_DEVICE_NOT_READY;
    }
    if (result != JY901B_IMU_SAMPLE_GET_OK)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    Jy901bAdapter_NativeSampleConvert(&native, sample);
    sample->sequence = ++s_imu_logical_sequence;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_RunSelfTest(
    SystemDeviceSelfTestResult *result)
{
    if (result == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(result, 0, sizeof(*result));
    result->unsupported_mask = 1U;
    return SYSTEM_DEVICE_UNSUPPORTED;
}

SystemDeviceResult Jy901bAdapter_OutputRateValueGet(uint16_t rate_hz,
                                                     IMUOutputRate *value)
{
    if (value == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    switch (rate_hz)
    {
        case 1U: *value = OutputRate_1Hz; break;
        case 2U: *value = OutputRate_2Hz; break;
        case 5U: *value = OutputRate_5Hz; break;
        case 10U: *value = OutputRate_10Hz; break;
        case 20U: *value = OutputRate_20Hz; break;
        case 50U: *value = OutputRate_50Hz; break;
        case 100U: *value = OutputRate_100Hz; break;
        case 200U: *value = OutputRate_200Hz; break;
        default: return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    return SYSTEM_DEVICE_OK;
}

static uint8_t Jy901bImuAdapter_BandwidthToValue(float bandwidth_hz,
                                                   IMUBandwidth *value)
{
    if (value == NULL) { return 0U; }
    if (bandwidth_hz == 5.0f) { *value = Bandwidth_5Hz; }
    else if (bandwidth_hz == 10.0f) { *value = Bandwidth_10Hz; }
    else if (bandwidth_hz == 20.0f) { *value = Bandwidth_20Hz; }
    else if (bandwidth_hz == 42.0f) { *value = Bandwidth_42Hz; }
    else if (bandwidth_hz == 98.0f) { *value = Bandwidth_98Hz; }
    else if (bandwidth_hz == 188.0f) { *value = Bandwidth_188Hz; }
    else if (bandwidth_hz == 256.0f) { *value = Bandwidth_256Hz; }
    else { return 0U; }
    return 1U;
}

static SystemDeviceResult Jy901bImuAdapter_ConfigValidate(
    const SystemImuConfig *config,
    SystemDeviceConfigReport *report)
{
    IMUOutputRate rate;
    IMUBandwidth bandwidth;
    const uint32_t supported = SYSTEM_IMU_CFG_OUTPUT_RATE |
                               SYSTEM_IMU_CFG_ACCEL_BANDWIDTH |
                               SYSTEM_IMU_CFG_GYRO_BANDWIDTH |
                               SYSTEM_IMU_CFG_ACCEL_RANGE |
                               SYSTEM_IMU_CFG_GYRO_RANGE;

    if ((config == NULL) || (report == NULL))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(config, SystemImuConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    (void)memset(report, 0, sizeof(*report));
    report->requested_mask = config->requested_mask;
    report->required_mask = config->required_mask;
    report->supported_mask = supported;
    report->unsupported_required_mask = config->required_mask & ~supported;
    report->unsupported_optional_mask = (config->requested_mask & ~supported) &
                                        ~config->required_mask;
    if ((report->unsupported_required_mask != 0U) ||
        (((config->requested_mask & SYSTEM_IMU_CFG_OUTPUT_RATE) != 0U) &&
         (Jy901bAdapter_OutputRateValueGet(config->output_rate_hz, &rate) !=
          SYSTEM_DEVICE_OK)) ||
        (((config->requested_mask & SYSTEM_IMU_CFG_ACCEL_BANDWIDTH) != 0U) &&
         (Jy901bImuAdapter_BandwidthToValue(
             config->accel_bandwidth_hz, &bandwidth) == 0U)) ||
        (((config->requested_mask & SYSTEM_IMU_CFG_GYRO_BANDWIDTH) != 0U) &&
         (Jy901bImuAdapter_BandwidthToValue(
             config->gyro_bandwidth_hz, &bandwidth) == 0U)) ||
        (((config->requested_mask & (SYSTEM_IMU_CFG_ACCEL_BANDWIDTH |
                                     SYSTEM_IMU_CFG_GYRO_BANDWIDTH)) ==
          (SYSTEM_IMU_CFG_ACCEL_BANDWIDTH |
           SYSTEM_IMU_CFG_GYRO_BANDWIDTH)) &&
         (config->accel_bandwidth_hz != config->gyro_bandwidth_hz)) ||
        (((config->requested_mask & SYSTEM_IMU_CFG_ACCEL_RANGE) != 0U) &&
         (config->accel_range_g != 2.0f) &&
         (config->accel_range_g != 4.0f) &&
         (config->accel_range_g != 8.0f) &&
         (config->accel_range_g != 16.0f)) ||
        (((config->requested_mask & SYSTEM_IMU_CFG_GYRO_RANGE) != 0U) &&
         (config->gyro_range_dps != 200.0f) &&
         (config->gyro_range_dps != 500.0f) &&
         (config->gyro_range_dps != 1000.0f) &&
         (config->gyro_range_dps != 2000.0f)))
    {
        report->verify_failed_mask = config->requested_mask & supported;
        return SYSTEM_DEVICE_VERIFY_FAILED;
    }
    report->matched_mask = config->requested_mask & supported;
    report->success = 1U;
    return (report->unsupported_optional_mask != 0U) ?
        SYSTEM_DEVICE_UNSUPPORTED : SYSTEM_DEVICE_OK;
}

static void Jy901bImuAdapter_EffectiveConfigApply(
    const SystemImuConfig *config,
    const SystemDeviceConfigReport *report)
{
    SILVERSTAR_ASSERT_OBJECT(config, SystemImuConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    s_effective_config.requested_mask |= report->applied_mask;
    s_effective_config.required_mask =
        (s_effective_config.required_mask & ~report->applied_mask) |
        (config->required_mask & report->applied_mask);
    if ((report->applied_mask & SYSTEM_IMU_CFG_OUTPUT_RATE) != 0U)
    {
        s_effective_config.output_rate_hz = config->output_rate_hz;
    }
    if ((report->applied_mask & SYSTEM_IMU_CFG_ACCEL_BANDWIDTH) != 0U)
    {
        s_effective_config.accel_bandwidth_hz = config->accel_bandwidth_hz;
    }
    if ((report->applied_mask & SYSTEM_IMU_CFG_GYRO_BANDWIDTH) != 0U)
    {
        s_effective_config.gyro_bandwidth_hz = config->gyro_bandwidth_hz;
    }
    if ((report->applied_mask & SYSTEM_IMU_CFG_ACCEL_RANGE) != 0U)
    {
        s_effective_config.accel_range_g = config->accel_range_g;
    }
    if ((report->applied_mask & SYSTEM_IMU_CFG_GYRO_RANGE) != 0U)
    {
        s_effective_config.gyro_range_dps = config->gyro_range_dps;
    }
}

static SystemDeviceResult Jy901bImuAdapter_ApplyConfig(
    const SystemImuConfig *config,
    SystemDeviceConfigReport *report)
{
    IMUOutputRate rate;
    IMUState state;
    SystemDeviceResult result;

    if ((config == NULL) || (report == NULL))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(config, SystemImuConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (Jy901bAdapter_ConfigAccessCheck() != SYSTEM_DEVICE_OK)
    {
        (void)memset(report, 0, sizeof(*report));
        return SYSTEM_DEVICE_BUSY;
    }
    result = Jy901bImuAdapter_ConfigValidate(config, report);

    if ((result != SYSTEM_DEVICE_OK) && (result != SYSTEM_DEVICE_UNSUPPORTED))
    {
        return result;
    }
    rate = OutputRate_200Hz;
    if ((config->requested_mask & SYSTEM_IMU_CFG_OUTPUT_RATE) != 0U)
    {
        (void)Jy901bAdapter_OutputRateValueGet(config->output_rate_hz, &rate);
    }
    state = IMU_ApplyDefaultConfig(rate, s_staged_algorithm);
    if (state != IMU_OK)
    {
        report->verify_failed_mask = config->requested_mask;
        report->failed_mask = report->matched_mask;
        report->detail_code = (uint32_t)state;
        report->success = 0U;
        return (state == IMU_RESP_TIMEOUT) ? SYSTEM_DEVICE_TIMEOUT :
                                             SYSTEM_DEVICE_IO_ERROR;
    }
    report->applied_mask = report->matched_mask;
    report->persisted = 1U;
    report->success = 1U;
    Jy901bImuAdapter_EffectiveConfigApply(config, report);
    return result;
}

static uint32_t Jy901bImuAdapter_ConfigMismatchMaskGet(
    const IMUConfig *config,
    IMUOutputRate expected_rate)
{
    uint32_t mismatch_mask = 0U;

    SILVERSTAR_ASSERT_OBJECT(config, IMUConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (config->BaudrateValue != IMU_DEFAULT_BAUD_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_BAUD; }
    if (config->OutputRateValue != (uint16_t)expected_rate)
    { mismatch_mask |= IMU_CONFIG_VALID_RATE; }
    if (config->BandwidthValue != IMU_DEFAULT_BANDWIDTH_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_BANDWIDTH; }
    if (config->AlgorithmValue != (uint16_t)s_staged_algorithm)
    { mismatch_mask |= IMU_CONFIG_VALID_ALGORITHM; }
    if (config->OrientationValue != IMU_DEFAULT_ORIENT_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_ORIENTATION; }
    if (config->GyroRangeValue != IMU_DEFAULT_GYRO_RANGE_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_GYRO_RANGE; }
    if (config->AccelRangeValue != IMU_DEFAULT_ACCEL_RANGE_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_ACCEL_RANGE; }
    if (config->FusionFilterValue != IMU_DEFAULT_FUSION_FILTER_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_FUSION_FILTER; }
    if (config->AccelerationFilterValue != IMU_DEFAULT_ACCEL_FILTER_VALUE)
    { mismatch_mask |= IMU_CONFIG_VALID_ACCEL_FILTER; }
    if (config->ReturnContentValue != FC_IMU_RETURN_CONTENT_DEFAULT)
    { mismatch_mask |= IMU_CONFIG_VALID_RETURN_CONTENT; }
    return mismatch_mask;
}

static SystemDeviceResult Jy901bImuAdapter_VerifyConfig(
    const SystemImuConfig *config,
    SystemDeviceConfigReport *report)
{
    IMUConfig private_config;
    IMUOutputRate expected_rate = OutputRate_200Hz;
    IMUState state;
    uint32_t mismatch_mask = 0U;
    SystemDeviceResult validation;

    if ((config == NULL) || (report == NULL))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(config, SystemImuConfig,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (Jy901bAdapter_ConfigAccessCheck() != SYSTEM_DEVICE_OK)
    {
        (void)memset(report, 0, sizeof(*report));
        return SYSTEM_DEVICE_BUSY;
    }
    validation = Jy901bImuAdapter_ConfigValidate(config, report);

    if ((validation != SYSTEM_DEVICE_OK) &&
        (validation != SYSTEM_DEVICE_UNSUPPORTED))
    {
        return validation;
    }
    if ((config->requested_mask & SYSTEM_IMU_CFG_OUTPUT_RATE) != 0U)
    {
        (void)Jy901bAdapter_OutputRateValueGet(config->output_rate_hz,
                                                 &expected_rate);
    }
    state = IMU_ReadCurrentConfig(&private_config);
    if (state != IMU_OK)
    {
        report->matched_mask = 0U;
        report->verify_failed_mask = config->requested_mask;
        report->failed_mask = report->verify_failed_mask;
        report->detail_code = (uint32_t)state;
        report->success = 0U;
        return (state == IMU_RESP_TIMEOUT) ? SYSTEM_DEVICE_TIMEOUT :
                                             SYSTEM_DEVICE_IO_ERROR;
    }
    mismatch_mask = Jy901bImuAdapter_ConfigMismatchMaskGet(&private_config,
        expected_rate);
    report->detail_code = mismatch_mask;
    if (mismatch_mask != 0U)
    {
        report->matched_mask = 0U;
        report->verify_failed_mask = config->requested_mask;
        report->failed_mask = report->verify_failed_mask;
        report->success = 0U;
        return SYSTEM_DEVICE_VERIFY_FAILED;
    }
    report->success = 1U;
    return validation;
}

static SystemDeviceResult Jy901bImuAdapter_GetIoDiagnostics(
    SystemDeviceIoDiagnostics *diagnostics)
{
    PlatformUartDiagnostics source;

    if (diagnostics == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    SILVERSTAR_ASSERT_OBJECT(diagnostics, SystemDeviceIoDiagnostics,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    (void)PlatformUart_DiagnosticsGet(PROJECT_RESOURCE_IMU_UART, &source);
    (void)memset(diagnostics, 0, sizeof(*diagnostics));
    diagnostics->supported_mask = SYSTEM_DEVICE_IO_VALID_TRANSPORT |
        SYSTEM_DEVICE_IO_VALID_RX_BYTES |
        SYSTEM_DEVICE_IO_VALID_RX_EVENTS |
        SYSTEM_DEVICE_IO_VALID_RX_IDLE_EVENTS |
        SYSTEM_DEVICE_IO_VALID_RX_TC_EVENTS |
        SYSTEM_DEVICE_IO_VALID_RX_DISCARDED |
        SYSTEM_DEVICE_IO_VALID_UART_OVERRUN |
        SYSTEM_DEVICE_IO_VALID_UART_FRAMING |
        SYSTEM_DEVICE_IO_VALID_UART_NOISE |
        SYSTEM_DEVICE_IO_VALID_UART_PARITY |
        SYSTEM_DEVICE_IO_VALID_DMA_ERRORS |
        SYSTEM_DEVICE_IO_VALID_RX_RESTARTS |
        SYSTEM_DEVICE_IO_VALID_RX_RESTART_FAILS |
        SYSTEM_DEVICE_IO_VALID_DISCONTINUITIES |
        SYSTEM_DEVICE_IO_VALID_RX_ACTIVE;
    diagnostics->valid_mask = diagnostics->supported_mask;
    diagnostics->transport_type = SYSTEM_DEVICE_TRANSPORT_UART;
    diagnostics->owner = SYSTEM_DEVICE_IO_OWNER_SELF;
    diagnostics->rx_bytes = source.rx_bytes;
    diagnostics->rx_event_count = source.rx_event_count;
    diagnostics->rx_idle_event_count = source.rx_idle_event_count;
    diagnostics->rx_transfer_complete_count =
        source.rx_transfer_complete_count;
    diagnostics->rx_discarded_bytes = source.rx_discarded_bytes;
    diagnostics->uart_overrun_error_count =
        source.uart_overrun_error_count;
    diagnostics->uart_framing_error_count =
        source.uart_framing_error_count;
    diagnostics->uart_noise_error_count = source.uart_noise_error_count;
    diagnostics->uart_parity_error_count = source.uart_parity_error_count;
    diagnostics->dma_error_count = source.dma_error_count;
    diagnostics->rx_restart_count = source.rx_restart_count;
    diagnostics->rx_restart_failure_count = source.rx_restart_failure_count;
    diagnostics->rx_discontinuity_count = source.rx_discontinuity_count;
    diagnostics->rx_active = source.rx_active;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_GetIoDetail(
    SystemImuIoDetail *detail)
{
    IMUStreamDiagnostics source;

    if (detail == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    IMU_StreamDiagnosticsGet(&source);
    detail->valid_frame_count = source.valid_frame_count;
    detail->checksum_error_count = source.checksum_error_count;
    detail->parser_resync_count = source.parser_resync_count;
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult Jy901bAdapter_FrameHealthGet(IMUFrameType frame_type,
                                                 SystemDeviceHealth *health)
{
    IMUData snapshot;
    uint64_t timestamp_us = 0U;
    uint64_t now_us;
    uint32_t count = 0U;
    uint32_t valid_mask = 0U;
    uint8_t recent;
    SystemDeviceResult result;

    if (health == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    SILVERSTAR_ASSERT_OBJECT(health, SystemDeviceHealth,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    result = Jy901bAdapter_SharedHealthGet(health);
    if (result != SYSTEM_DEVICE_OK) { return result; }
    (void)memset(&snapshot, 0, sizeof(snapshot));
    result = Jy901bAdapter_SharedSnapshotGet(&snapshot);
    if ((result != SYSTEM_DEVICE_OK) &&
        (result != SYSTEM_DEVICE_NOT_READY))
    {
        return result;
    }
    switch (frame_type)
    {
        case IMUFrameNone:
        case IMUFrameAcc:
        case IMUFrameGyro:
        case IMUFrameEuler:
            return SYSTEM_DEVICE_INVALID_ARGUMENT;
        case IMUFrameMag:
            timestamp_us = snapshot.MagTimestampUs;
            count = snapshot.MagFrameCount;
            valid_mask = (1U << 3);
            break;
        case IMUFramePressureHeight:
            timestamp_us = snapshot.PressureTimestampUs;
            count = snapshot.PressureFrameCount;
            valid_mask = (1U << 4);
            break;
        case IMUFrameQuaternion:
            timestamp_us = snapshot.QuaternionTimestampUs;
            count = snapshot.QuaternionFrameCount;
            valid_mask = (1U << 5);
            break;
        default:
            return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    now_us = PlatformTime_Us();
    recent = (uint8_t)((timestamp_us != 0U) && (now_us >= timestamp_us) &&
        ((now_us - timestamp_us) <= ((uint64_t)IMU_ONLINE_TIMEOUT_MS * 1000ULL)));
    health->last_sample_timestamp_us = timestamp_us;
    health->last_receive_timestamp_us = timestamp_us;
    health->sample_count = count;
    health->online = (uint8_t)((health->initialized != 0U) &&
                               (health->started != 0U) &&
                               (recent != 0U));
    health->healthy = (uint8_t)((health->online != 0U) &&
                                ((snapshot.ValidMask & valid_mask) != 0U));
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_GetEffectiveConfig(
    SystemImuConfig *config)
{
    if (config == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    *config = s_effective_config;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bImuAdapter_GetNoise(
    SystemImuNoiseCharacteristics *noise)
{
    if (noise == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(noise, 0, sizeof(*noise));
    noise->recommended_process_accel_std_mps2[0] =
        JY901B_IMU_RECOMMENDED_PROCESS_ACCEL_E_STD_MPS2;
    noise->recommended_process_accel_std_mps2[1] =
        JY901B_IMU_RECOMMENDED_PROCESS_ACCEL_N_STD_MPS2;
    noise->recommended_process_accel_std_mps2[2] =
        JY901B_IMU_RECOMMENDED_PROCESS_ACCEL_U_STD_MPS2;
    noise->valid_mask = SYSTEM_IMU_NOISE_VALID_PROCESS_ACCEL_STD;
    return SYSTEM_DEVICE_OK;
}

const char *SystemImu_NameGet(void) { return "JY901B IMU"; }
SystemDeviceResult SystemImu_Init(void) { return Jy901bImuAdapter_Init(); }
SystemDeviceResult SystemImu_Start(void) { return Jy901bImuAdapter_Start(); }
SystemDeviceResult SystemImu_Stop(void) { return Jy901bImuAdapter_Stop(); }
SystemDeviceResult SystemImu_RuntimeOwnerActivate(void)
{
    return Jy901bImuAdapter_RuntimeOwnerActivate();
}
void SystemImu_Process(void) { Jy901bImuAdapter_Process(); }
SystemDeviceResult SystemImu_InfoGet(SystemDeviceInfo *info)
{
    return Jy901bImuAdapter_GetInfo(info);
}
SystemDeviceResult SystemImu_CapabilitiesGet(uint32_t *capability_mask)
{
    return Jy901bImuAdapter_GetCapabilities(capability_mask);
}
SystemDeviceResult SystemImu_HealthGet(SystemDeviceHealth *health)
{
    return Jy901bAdapter_SharedHealthGet(health);
}
SystemDeviceResult SystemImu_IoDiagnosticsGet(
    SystemDeviceIoDiagnostics *diagnostics)
{
    return Jy901bImuAdapter_GetIoDiagnostics(diagnostics);
}
SystemDeviceResult SystemImu_IoDetailGet(SystemImuIoDetail *detail)
{
    return Jy901bImuAdapter_GetIoDetail(detail);
}
SystemDeviceResult SystemImu_LatestSampleGet(SystemImuSample *sample)
{
    return Jy901bImuAdapter_GetLatestSample(sample);
}
SystemDeviceResult SystemImu_NextSampleGet(SystemImuSample *sample)
{
    return Jy901bImuAdapter_GetNextSample(sample);
}
SystemDeviceResult SystemImu_SelfTestRun(SystemDeviceSelfTestResult *result)
{
    return Jy901bImuAdapter_RunSelfTest(result);
}
SystemDeviceResult SystemImu_ConfigApply(const SystemImuConfig *config,
                                         SystemDeviceConfigReport *report)
{
    return Jy901bImuAdapter_ApplyConfig(config, report);
}
SystemDeviceResult SystemImu_ConfigVerify(const SystemImuConfig *config,
                                          SystemDeviceConfigReport *report)
{
    return Jy901bImuAdapter_VerifyConfig(config, report);
}
SystemDeviceResult SystemImu_EffectiveConfigGet(SystemImuConfig *config)
{
    return Jy901bImuAdapter_GetEffectiveConfig(config);
}
SystemDeviceResult SystemImu_NoiseCharacteristicsGet(
    SystemImuNoiseCharacteristics *noise)
{
    return Jy901bImuAdapter_GetNoise(noise);
}
