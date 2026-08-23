#include "system_user_config.h"

#if defined(TEST_EXPECT_DEFAULT_JY901B_PROFILE)
_Static_assert(SYSTEM_ALIGNMENT_ALGORITHM ==
               SYSTEM_ALIGNMENT_GRAVITY_KNOWN_YAW,
               "Default alignment must be Gravity Known Yaw");
_Static_assert(SYSTEM_USER_MAGNETOMETER_ENABLE == 0U,
               "Default JY901B magnetometer adapter must be disabled");
_Static_assert(SYSTEM_SELECTED_IMU_ACCEL_AVAILABLE != 0U,
               "Default JY901B accel must be available");
_Static_assert(SYSTEM_SELECTED_IMU_GYRO_AVAILABLE != 0U,
               "Default JY901B gyro must be available");
_Static_assert(SYSTEM_SELECTED_IMU_LANDING_IMPACT_QUALIFIED == 0U,
               "Default JY901B impact qualification must remain false");
#endif

int main(void)
{
    return 0;
}
