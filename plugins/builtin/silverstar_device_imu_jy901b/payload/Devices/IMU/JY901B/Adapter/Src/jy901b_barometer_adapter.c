#include "system_version.h"
#include "system_barometer_if.h"

#include <stddef.h>
#include <string.h>

#include "jy901b_barometer_build_capabilities.h"
#include "jy901b_sensor_adapter.h"
#include "silverstar_assert.h"
#include "system_user_config.h"

static SystemBarometerConfig s_effective_config;

static SystemDeviceResult Jy901bBarometerAdapter_GetHealth(
    SystemDeviceHealth *health)
{
    return Jy901bAdapter_FrameHealthGet(IMUFramePressureHeight, health);
}

static SystemDeviceResult Jy901bBarometerAdapter_Init(void)
{
    return Jy901bAdapter_SharedInit();
}

static SystemDeviceResult Jy901bBarometerAdapter_Start(void)
{
    SystemDeviceResult result = Jy901bAdapter_SharedStart();

    return (result == SYSTEM_DEVICE_ALREADY_MATCHED) ? SYSTEM_DEVICE_OK : result;
}

static SystemDeviceResult Jy901bBarometerAdapter_Stop(void)
{
    return SYSTEM_DEVICE_OK;
}

static void Jy901bBarometerAdapter_Process(void)
{
}

static SystemDeviceResult Jy901bBarometerAdapter_GetInfo(SystemDeviceInfo *info)
{
    if (info == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    info->device_name = "JY901B Barometer Adapter";
    info->model_name = "JY901B";
    info->driver_version = SILVERSTAR_PRODUCT_STRING;
    info->capability_mask = SYSTEM_BARO_VALID_PRESSURE |
                            SYSTEM_BARO_VALID_ALTITUDE |
                            SYSTEM_BARO_VALID_VARIANCE;
    info->configuration_mask = SYSTEM_BARO_CFG_OUTPUT_RATE;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bBarometerAdapter_GetCapabilities(uint32_t *mask)
{
    if (mask == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    *mask = SYSTEM_BARO_VALID_PRESSURE |
            SYSTEM_BARO_VALID_ALTITUDE |
            SYSTEM_BARO_VALID_VARIANCE;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bBarometerAdapter_GetSample(
    SystemBarometerSample *sample)
{
    IMUData data;
    SystemDeviceResult result;

    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    SILVERSTAR_ASSERT_OBJECT(sample, SystemBarometerSample,
                             SILVERSTAR_ASSERT_MODULE_DEVICE);
    result = Jy901bAdapter_SharedSnapshotGet(&data);
    if (result != SYSTEM_DEVICE_OK) { return result; }
    if ((data.ValidMask & (1U << 4)) == 0U) { return SYSTEM_DEVICE_NOT_READY; }
    (void)memset(sample, 0, sizeof(*sample));
    sample->sample_timestamp_us = data.PressureTimestampUs;
    sample->receive_timestamp_us = data.PressureTimestampUs;
    sample->sequence = data.PressureFrameCount;
    sample->pressure_raw_pa = data.PressureRawPa;
    sample->altitude_raw_cm = data.HeightRawCm;
    sample->pressure_pa = data.PressurePa;
    sample->altitude_m = data.HeightCm * 0.01f;
    sample->altitude_variance_m2 =
        JY901B_BAROMETER_RECOMMENDED_ALTITUDE_STD_M *
        JY901B_BAROMETER_RECOMMENDED_ALTITUDE_STD_M;
    sample->supported_fields = SYSTEM_BARO_FIELD_PRESSURE |
                               SYSTEM_BARO_FIELD_ALTITUDE |
                               SYSTEM_BARO_FIELD_VARIANCE;
    sample->valid_fields = sample->supported_fields;
    sample->valid_mask = sample->valid_fields;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bBarometerAdapter_SelfTest(
    SystemDeviceSelfTestResult *result)
{
    if (result == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(result, 0, sizeof(*result));
    result->unsupported_mask = 1U;
    return SYSTEM_DEVICE_UNSUPPORTED;
}

static SystemDeviceResult Jy901bBarometerAdapter_ConfigCheck(
    const SystemBarometerConfig *config,
    SystemDeviceConfigReport *report)
{
    if ((config == NULL) || (report == NULL))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(config, SystemBarometerConfig,
                             SILVERSTAR_ASSERT_MODULE_DEVICE);
    (void)memset(report, 0, sizeof(*report));
    report->requested_mask = config->requested_mask;
    report->required_mask = config->required_mask;
    report->supported_mask = SYSTEM_BARO_CFG_OUTPUT_RATE;
    report->unsupported_required_mask = config->required_mask &
                                        ~SYSTEM_BARO_CFG_OUTPUT_RATE;
    report->unsupported_optional_mask = (config->requested_mask &
                                         ~SYSTEM_BARO_CFG_OUTPUT_RATE) &
                                        ~config->required_mask;
    if ((report->unsupported_required_mask != 0U) ||
        (((config->requested_mask & SYSTEM_BARO_CFG_OUTPUT_RATE) != 0U) &&
         (config->output_rate_hz != SYSTEM_IMU_OUTPUT_RATE_HZ)))
    {
        report->verify_failed_mask = config->requested_mask;
        report->failed_mask = config->requested_mask;
        return SYSTEM_DEVICE_VERIFY_FAILED;
    }
    report->matched_mask = config->requested_mask & SYSTEM_BARO_CFG_OUTPUT_RATE;
    report->success = 1U;
    return (report->unsupported_optional_mask != 0U) ?
        SYSTEM_DEVICE_UNSUPPORTED : SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bBarometerAdapter_ApplyConfig(
    const SystemBarometerConfig *config,
    SystemDeviceConfigReport *report)
{
    SystemDeviceResult result = Jy901bBarometerAdapter_ConfigCheck(config, report);

    if ((result != SYSTEM_DEVICE_OK) && (result != SYSTEM_DEVICE_UNSUPPORTED))
    { return result; }
    s_effective_config = *config;
    report->delegated_mask = report->matched_mask;
    report->applied_mask = 0U;
    report->matched_mask = 0U;
    return (report->delegated_mask != 0U) ?
        SYSTEM_DEVICE_CONFIG_DELEGATED : result;
}

static SystemDeviceResult Jy901bBarometerAdapter_VerifyConfig(
    const SystemBarometerConfig *config,
    SystemDeviceConfigReport *report)
{
    uint16_t value;
    IMUOutputRate expected_rate;
    IMUState state;
    SystemDeviceResult result =
        Jy901bBarometerAdapter_ConfigCheck(config, report);

    if ((result != SYSTEM_DEVICE_OK) && (result != SYSTEM_DEVICE_UNSUPPORTED))
    { return result; }
    SILVERSTAR_ASSERT_OBJECT(config, SystemBarometerConfig,
                             SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((config->requested_mask & SYSTEM_BARO_CFG_OUTPUT_RATE) == 0U)
    { return result; }
    if (Jy901bAdapter_ConfigAccessCheck() != SYSTEM_DEVICE_OK)
    { return SYSTEM_DEVICE_BUSY; }
    if (Jy901bAdapter_OutputRateValueGet(config->output_rate_hz,
                                          &expected_rate) != SYSTEM_DEVICE_OK)
    { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    state = IMU_ReadOutputRate(&value);
    if ((state != IMU_OK) || (value != (uint16_t)expected_rate))
    {
        report->matched_mask = 0U;
        report->verify_failed_mask = SYSTEM_BARO_CFG_OUTPUT_RATE;
        report->failed_mask = report->verify_failed_mask;
        report->detail_code = (state != IMU_OK) ? (uint32_t)state : value;
        report->success = 0U;
        return (state == IMU_RESP_TIMEOUT) ? SYSTEM_DEVICE_TIMEOUT :
                                             SYSTEM_DEVICE_VERIFY_FAILED;
    }
    return result;
}

static SystemDeviceResult Jy901bBarometerAdapter_GetConfig(
    SystemBarometerConfig *config)
{
    if (config == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    *config = s_effective_config;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Jy901bBarometerAdapter_GetNoise(
    SystemBarometerNoiseCharacteristics *noise)
{
    if (noise == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(noise, 0, sizeof(*noise));
    noise->recommended_altitude_std_m =
        JY901B_BAROMETER_RECOMMENDED_ALTITUDE_STD_M;
    noise->pressure_noise_std_pa = 0.0f;
    noise->valid_mask = SYSTEM_BAROMETER_NOISE_VALID_ALTITUDE_STD;
    return SYSTEM_DEVICE_OK;
}

const char *SystemBarometer_NameGet(void) { return "JY901B Barometer"; }
SystemDeviceResult SystemBarometer_Init(void)
{ return Jy901bBarometerAdapter_Init(); }
SystemDeviceResult SystemBarometer_Start(void)
{ return Jy901bBarometerAdapter_Start(); }
SystemDeviceResult SystemBarometer_Stop(void)
{ return Jy901bBarometerAdapter_Stop(); }
void SystemBarometer_Process(void) { Jy901bBarometerAdapter_Process(); }
SystemDeviceResult SystemBarometer_InfoGet(SystemDeviceInfo *info)
{ return Jy901bBarometerAdapter_GetInfo(info); }
SystemDeviceResult SystemBarometer_CapabilitiesGet(uint32_t *mask)
{ return Jy901bBarometerAdapter_GetCapabilities(mask); }
SystemDeviceResult SystemBarometer_HealthGet(SystemDeviceHealth *health)
{ return Jy901bBarometerAdapter_GetHealth(health); }
SystemDeviceResult SystemBarometer_LatestSampleGet(
    SystemBarometerSample *sample)
{ return Jy901bBarometerAdapter_GetSample(sample); }
SystemDeviceResult SystemBarometer_SelfTestRun(
    SystemDeviceSelfTestResult *result)
{ return Jy901bBarometerAdapter_SelfTest(result); }
SystemDeviceResult SystemBarometer_ConfigApply(
    const SystemBarometerConfig *config, SystemDeviceConfigReport *report)
{ return Jy901bBarometerAdapter_ApplyConfig(config, report); }
SystemDeviceResult SystemBarometer_ConfigVerify(
    const SystemBarometerConfig *config, SystemDeviceConfigReport *report)
{ return Jy901bBarometerAdapter_VerifyConfig(config, report); }
SystemDeviceResult SystemBarometer_EffectiveConfigGet(
    SystemBarometerConfig *config)
{ return Jy901bBarometerAdapter_GetConfig(config); }
SystemDeviceResult SystemBarometer_NoiseCharacteristicsGet(
    SystemBarometerNoiseCharacteristics *noise)
{ return Jy901bBarometerAdapter_GetNoise(noise); }
