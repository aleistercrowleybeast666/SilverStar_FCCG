#include <stdint.h>
#include <string.h>

#include "host_platform_mock.h"
#include "jy901b_config.h"
#include "jy901b_device.h"
#include "jy901b_instance.h"
#include "project_resources.h"
#include "system_imu_if.h"
#include "system_user_config.h"
#include "test_common.h"

#ifndef PROJECT_RESOURCE_IMU_UART
#define PROJECT_RESOURCE_IMU_UART PLATFORM_UART_1
#endif
#define SystemImu_Init() Jy901bImuInstance_Init(0U)
#define SystemImu_Start() Jy901bImuInstance_Start(0U)
#define SystemImu_Stop() Jy901bImuInstance_Stop(0U)
#define SystemImu_Process() ((void)Jy901bImuInstance_Process(0U))
#define SystemImu_LatestSampleGet(sample) \
    Jy901bImuInstance_LatestSampleGet(0U, (sample))
#define SystemImu_NextSampleGet(sample) \
    Jy901bImuInstance_NextSampleGet(0U, (sample))

static uint8_t Test_ChecksumGet(const uint8_t *frame)
{
    uint8_t checksum = 0U;
    uint8_t index;

    for (index = 0U; index < (IMU_FRAME_LEN - 1U); index++)
    {
        checksum = (uint8_t)(checksum + frame[index]);
    }
    return checksum;
}

static void Test_S16Write(uint8_t *data, int16_t value)
{
    data[0] = (uint8_t)value;
    data[1] = (uint8_t)((uint16_t)value >> 8U);
}

static void Test_FrameBuild(uint8_t type, int16_t x, int16_t y,
                            int16_t z, int16_t temperature,
                            uint8_t *frame)
{
    (void)memset(frame, 0, IMU_FRAME_LEN);
    frame[0] = IMU_FRAME_HEADER;
    frame[1] = type;
    Test_S16Write(&frame[2], x);
    Test_S16Write(&frame[4], y);
    Test_S16Write(&frame[6], z);
    Test_S16Write(&frame[8], temperature);
    frame[10] = Test_ChecksumGet(frame);
}

static void Test_NativeSampleConvertsToSystemInterface(void)
{
    uint8_t frames[2U * IMU_FRAME_LEN];
    SystemImuSample latest;
    SystemImuSample next;

    HostPlatformMock_Reset();
    HostPlatformMock_TimeSetUs(250000ULL);
    TEST_CHECK(SystemImu_Init() == SYSTEM_DEVICE_OK);
    TEST_CHECK(SystemImu_Start() == SYSTEM_DEVICE_OK);
    Test_FrameBuild(IMUFrameAcc, 1024, -1024, 2048, 2500, &frames[0]);
    Test_FrameBuild(IMUFrameGyro, 100, -200, 300, 2500,
                    &frames[IMU_FRAME_LEN]);
    TEST_CHECK(HostPlatformMock_UartRxInject(
        PROJECT_RESOURCE_IMU_UART, frames, sizeof(frames)) == sizeof(frames));
    SystemImu_Process();
    TEST_CHECK(SystemImu_LatestSampleGet(&latest) == SYSTEM_DEVICE_OK);
    TEST_CHECK(SystemImu_NextSampleGet(&next) == SYSTEM_DEVICE_OK);
    TEST_CHECK(latest.sample_timestamp_us == 250000ULL);
    TEST_CHECK(latest.accel_raw[0] == 1024);
    TEST_CHECK(latest.accel_raw[1] == -1024);
    TEST_CHECK(latest.gyro_raw[2] == 300);
    TEST_CHECK_NEAR(latest.accel_b_mps2[2], SYSTEM_LOCAL_GRAVITY_MPS2,
                    1.0e-4f);
    TEST_CHECK_NEAR(latest.temperature_c, 25.0f, 1.0e-5f);
    TEST_CHECK(next.sequence == 1U);
    TEST_CHECK(next.valid_mask == latest.valid_mask);
    TEST_CHECK_NEAR(next.gyro_b_radps[1], latest.gyro_b_radps[1],
                    1.0e-6f);
    TEST_CHECK(SystemImu_Stop() == SYSTEM_DEVICE_OK);
}

int main(void)
{
    Test_NativeSampleConvertsToSystemInterface();
    return Test_Finish("jy901b_adapter");
}
