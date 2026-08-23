#include <stdint.h>
#include <string.h>

#include "air_protocol.h"
#include "system_alignment.h"
#include "system_barometer_if.h"
#include "system_calibration.h"
#include "system_gnss_if.h"
#include "system_hardware_quaternion_if.h"
#include "system_imu_if.h"
#include "system_magnetometer_if.h"
#include "system_navigation_profile.h"
#include "system_sensor_status.h"
#include "test_common.h"

static SystemAlignmentSummary s_alignment;
static SystemNavigationProfile s_navigation;
static uint8_t s_calibration_ready;

static SystemDeviceResult Mock_HealthGet(SystemDeviceHealth *health)
{
    if (health == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(health, 0, sizeof(*health));
    health->initialized = 1U;
    health->started = 1U;
    health->online = 1U;
    health->healthy = 1U;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Mock_ImuGet(SystemImuSample *sample)
{
    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(sample, 0, sizeof(*sample));
    sample->valid_mask = SYSTEM_IMU_VALID_ACCEL | SYSTEM_IMU_VALID_GYRO;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Mock_GnssGet(SystemGnssSample *sample)
{
    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(sample, 0, sizeof(*sample));
    sample->position_usable = 1U;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Mock_BarometerGet(SystemBarometerSample *sample)
{
    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(sample, 0, sizeof(*sample));
    sample->valid_fields = SYSTEM_BARO_FIELD_ALTITUDE |
                           SYSTEM_BARO_FIELD_PRESSURE;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Mock_MagnetometerGet(
    SystemMagnetometerSample *sample)
{
    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(sample, 0, sizeof(*sample));
    sample->valid_mask = SYSTEM_MAG_VALID_PHYSICAL_UNIT;
    sample->calibration_valid = 1U;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Mock_HardwareAttitudeGet(
    SystemHardwareQuaternionSample *sample)
{
    if (sample == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(sample, 0, sizeof(*sample));
    sample->quaternion_wxyz[0] = 1.0f;
    sample->normalized = 1U;
    sample->valid = 1U;
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult SystemImu_HealthGet(SystemDeviceHealth *health)
{ return Mock_HealthGet(health); }
SystemDeviceResult SystemImu_LatestSampleGet(SystemImuSample *sample)
{ return Mock_ImuGet(sample); }
SystemDeviceResult SystemGnss_HealthGet(SystemDeviceHealth *health)
{ return Mock_HealthGet(health); }
SystemDeviceResult SystemGnss_LatestSampleGet(SystemGnssSample *sample)
{ return Mock_GnssGet(sample); }
SystemDeviceResult SystemBarometer_HealthGet(SystemDeviceHealth *health)
{ return Mock_HealthGet(health); }
SystemDeviceResult SystemBarometer_LatestSampleGet(
    SystemBarometerSample *sample)
{ return Mock_BarometerGet(sample); }
SystemDeviceResult SystemMagnetometer_HealthGet(SystemDeviceHealth *health)
{ return Mock_HealthGet(health); }
SystemDeviceResult SystemMagnetometer_LatestSampleGet(
    SystemMagnetometerSample *sample)
{ return Mock_MagnetometerGet(sample); }
SystemDeviceResult SystemHardwareQuaternion_HealthGet(
    SystemDeviceHealth *health)
{ return Mock_HealthGet(health); }
SystemDeviceResult SystemHardwareQuaternion_LatestSampleGet(
    SystemHardwareQuaternionSample *sample)
{ return Mock_HardwareAttitudeGet(sample); }

SystemDeviceResult SystemAlignment_SummaryGet(SystemAlignmentSummary *summary)
{
    if (summary == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    *summary = s_alignment;
    return SYSTEM_DEVICE_OK;
}

uint8_t SystemCalibration_IsReady(void)
{
    return s_calibration_ready;
}

const SystemNavigationProfile *SystemNavigationProfile_Get(void)
{
    return &s_navigation;
}

static void Test_DefaultBuildSnapshotOmitsMagnetometer(void)
{
    SystemSensorStatus status;
    uint8_t index;

    (void)memset(&s_alignment, 0, sizeof(s_alignment));
    (void)memset(&s_navigation, 0, sizeof(s_navigation));
    s_navigation.alignment_algorithm = SYSTEM_ALIGNMENT_GRAVITY_KNOWN_YAW;
    s_calibration_ready = 1U;

    SystemSensorStatus_Reset();
    TEST_CHECK(SYSTEM_USER_MAGNETOMETER_ENABLE == 0U);
    TEST_CHECK(SystemSensorStatus_CountGet() == 4U);
    for (index = 0U; index < SystemSensorStatus_CountGet(); index++)
    {
        TEST_CHECK(SystemSensorStatus_Get(index, &status) ==
                   SYSTEM_DEVICE_OK);
        TEST_CHECK(status.sensor_id != SILVERSTAR_SENSOR_ID_MAGNETOMETER);
    }
}

static void Test_BuildTimeDescriptorsAndSnapshot(void)
{
    static const uint8_t expected_ids[4] =
    {
        SILVERSTAR_SENSOR_ID_IMU,
        SILVERSTAR_SENSOR_ID_GNSS,
        SILVERSTAR_SENSOR_ID_BAROMETER,
        SILVERSTAR_SENSOR_ID_EXTERNAL_ATTITUDE
    };
    SystemSensorStatusSnapshotInfo info;
    SystemSensorStatus status;
    uint8_t index;

    (void)memset(&s_alignment, 0, sizeof(s_alignment));
    (void)memset(&s_navigation, 0, sizeof(s_navigation));
    s_alignment.selected_mask = SYSTEM_ALIGNMENT_SOURCE_MASK_ATTITUDE |
        SYSTEM_ALIGNMENT_SOURCE_MASK_BARO_ORIGIN;
    s_alignment.required_mask = SYSTEM_ALIGNMENT_SOURCE_MASK_ATTITUDE |
        SYSTEM_ALIGNMENT_SOURCE_MASK_BARO_ORIGIN;
    s_navigation.alignment_algorithm =
        SYSTEM_ALIGNMENT_HW_QUAT_6AXIS_KNOWN_YAW;
    s_calibration_ready = 1U;

    SystemSensorStatus_Reset();
    TEST_CHECK(SystemSensorStatus_CountGet() == 4U);
    TEST_CHECK(SystemSensorStatus_SummaryFlagsGet() ==
        (AIR_SENSOR_SUMMARY_IMU_PRESENT |
         AIR_SENSOR_SUMMARY_GNSS_PRESENT |
         AIR_SENSOR_SUMMARY_AUX_SENSOR_PRESENT |
         AIR_SENSOR_SUMMARY_SNAPSHOT_SUPPORTED));

    for (index = 0U; index < 4U; index++)
    {
        TEST_CHECK(SystemSensorStatus_Get(index, &status) ==
                   SYSTEM_DEVICE_OK);
        TEST_CHECK(status.sensor_id == expected_ids[index]);
        TEST_CHECK((status.status_flags &
                    SYSTEM_SENSOR_STATUS_REGISTERED) != 0U);
    }
    TEST_CHECK(SystemSensorStatus_Get(0U, &status) == SYSTEM_DEVICE_OK);
    TEST_CHECK((status.status_flags &
                SYSTEM_SENSOR_STATUS_REQUIRED_FOR_START) != 0U);
    TEST_CHECK((status.status_flags &
                SYSTEM_SENSOR_STATUS_ALIGNMENT_USED) != 0U);
    TEST_CHECK(SystemSensorStatus_Get(1U, &status) == SYSTEM_DEVICE_OK);
    TEST_CHECK((status.status_flags &
                SYSTEM_SENSOR_STATUS_REQUIRED_FOR_START) == 0U);
    TEST_CHECK(SystemSensorStatus_Get(2U, &status) == SYSTEM_DEVICE_OK);
    TEST_CHECK((status.status_flags &
                SYSTEM_SENSOR_STATUS_REQUIRED_FOR_START) != 0U);
    TEST_CHECK(SystemSensorStatus_Get(3U, &status) == SYSTEM_DEVICE_OK);
    TEST_CHECK((status.status_flags &
                SYSTEM_SENSOR_STATUS_ALIGNMENT_USED) != 0U);

    TEST_CHECK(SystemSensorStatus_SnapshotCapture(
        AIR_ALIGNMENT_STATE_READY) == SYSTEM_DEVICE_OK);
    TEST_CHECK(SystemSensorStatus_SnapshotInfoGet(&info) == SYSTEM_DEVICE_OK);
    TEST_CHECK(info.snapshot_id == 1U);
    TEST_CHECK(info.sequence == 1U);
    TEST_CHECK(info.total == 4U);
    TEST_CHECK(info.alignment_state == AIR_ALIGNMENT_STATE_READY);
    for (index = 0U; index < info.total; index++)
    {
        TEST_CHECK(SystemSensorStatus_SnapshotGet(index, &status) ==
                   SYSTEM_DEVICE_OK);
        TEST_CHECK(status.sensor_id == expected_ids[index]);
    }
    TEST_CHECK(SystemSensorStatus_SnapshotCapture(
        AIR_ALIGNMENT_STATE_FAILED) == SYSTEM_DEVICE_OK);
    TEST_CHECK(SystemSensorStatus_SnapshotInfoGet(&info) == SYSTEM_DEVICE_OK);
    TEST_CHECK(info.snapshot_id == 2U);
    TEST_CHECK(info.sequence == 2U);
    TEST_CHECK(info.alignment_state == AIR_ALIGNMENT_STATE_FAILED);

}

static void Test_InvalidArguments(void)
{
    TEST_CHECK(SystemSensorStatus_Get(0U, NULL) ==
               SYSTEM_DEVICE_INVALID_ARGUMENT);
    TEST_CHECK(SystemSensorStatus_SnapshotInfoGet(NULL) ==
               SYSTEM_DEVICE_INVALID_ARGUMENT);
}

int main(void)
{
    Test_DefaultBuildSnapshotOmitsMagnetometer();
    Test_BuildTimeDescriptorsAndSnapshot();
    Test_InvalidArguments();
    return Test_Finish("sensor_status");
}
