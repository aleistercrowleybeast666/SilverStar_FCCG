#include "system_profile.h"

#include "system_capabilities.h"
#include "system_user_config.h"
#include "target_build_capabilities.h"

_Static_assert(SYSTEM_PROFILE_OUTPUT_CHANNEL_COUNT > 0U,
               "SYSTEM_PROFILE_OUTPUT_CHANNEL_COUNT must be non-zero");
_Static_assert(SYSTEM_MAGNETOMETER_OUTPUT_RATE_HZ ==
               SYSTEM_IMU_OUTPUT_RATE_HZ,
               "magnetometer and IMU rates must match");
_Static_assert(SYSTEM_BAROMETER_OUTPUT_RATE_HZ == SYSTEM_IMU_OUTPUT_RATE_HZ,
               "barometer and IMU rates must match");
_Static_assert(SYSTEM_HARDWARE_QUATERNION_OUTPUT_RATE_HZ ==
               SYSTEM_IMU_OUTPUT_RATE_HZ,
               "hardware quaternion and IMU rates must match");

static const SystemProfile s_system_profile =
{
    .profile_id = SYSTEM_PROFILE_ID,
    .output_channel_count = SYSTEM_PROFILE_OUTPUT_CHANNEL_COUNT,
    .enabled_capabilities = TARGET_COMPILED_SYSTEM_CAPABILITIES,
    .required_capabilities = SYSTEM_PROFILE_REQUIRED_CAPABILITIES,
    .optional_capabilities = SYSTEM_PROFILE_OPTIONAL_CAPABILITIES
};

static uint8_t s_system_profile_frozen;

const SystemProfile *SystemProfile_Get(void)
{
    return &s_system_profile;
}

uint8_t SystemProfile_IsFrozen(void)
{
    return s_system_profile_frozen;
}

void SystemProfile_Freeze(void)
{
    s_system_profile_frozen = 1U;
}

void SystemProfile_UnfreezeForRollback(void)
{
    s_system_profile_frozen = 0U;
}
