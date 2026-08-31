#include "system_gnss_quality.h"

#include <math.h>
#include <stddef.h>

#include "silverstar_assert.h"
#include "system_user_config.h"

static uint8_t SystemGnssQuality_FieldSupported(
    const SystemGnssSample *sample,
    uint32_t field)
{
    return (uint8_t)((sample->supported_fields & field) != 0U);
}

static uint8_t SystemGnssQuality_FieldValid(const SystemGnssSample *sample,
                                             uint32_t field)
{
    return (uint8_t)((sample->valid_fields & field) != 0U);
}

static void SystemGnssQuality_OptionalFieldCheck(
    const SystemGnssSample *sample,
    uint32_t field,
    uint32_t reason,
    uint32_t *reject_mask,
    uint8_t *blocking,
    uint8_t *quality_degraded)
{
    if (SystemGnssQuality_FieldSupported(sample, field) == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_FIELD_UNSUPPORTED;
        *quality_degraded = 1U;
    }
    else if (SystemGnssQuality_FieldValid(sample, field) == 0U)
    {
        *reject_mask |= reason | SYSTEM_GNSS_REJECT_FIELD_INVALID;
        *blocking = 1U;
    }
}

static uint8_t SystemGnssQuality_BasicFixCheck(
    const SystemGnssSample *sample,
    uint32_t *reject_mask,
    uint8_t *quality_degraded)
{
    uint8_t blocking = 0U;

    SILVERSTAR_ASSERT_OBJECT(sample, SystemGnssSample,
        SILVERSTAR_ASSERT_MODULE_SYSTEM);
    if (sample->online == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_OFFLINE;
        blocking = 1U;
    }
    if (SystemGnssQuality_FieldSupported(
            sample, SYSTEM_GNSS_FIELD_FIX_TYPE) == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_NO_FIX |
                        SYSTEM_GNSS_REJECT_FIX_TYPE |
                        SYSTEM_GNSS_REJECT_FIELD_UNSUPPORTED;
        blocking = 1U;
    }
    else if (SystemGnssQuality_FieldValid(
                 sample, SYSTEM_GNSS_FIELD_FIX_TYPE) == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_NO_FIX |
                        SYSTEM_GNSS_REJECT_FIX_TYPE |
                        SYSTEM_GNSS_REJECT_FIELD_INVALID;
        blocking = 1U;
    }
    else if ((sample->fix_type != 3U) && (sample->fix_type != 4U))
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_NO_FIX |
                        SYSTEM_GNSS_REJECT_FIX_TYPE;
        blocking = 1U;
    }

    if (SystemGnssQuality_FieldSupported(
            sample, SYSTEM_GNSS_FIELD_FIX_OK) == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_FIELD_UNSUPPORTED;
        *quality_degraded = 1U;
    }
    else if (SystemGnssQuality_FieldValid(
                 sample, SYSTEM_GNSS_FIELD_FIX_OK) == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_FIX_FLAG |
                        SYSTEM_GNSS_REJECT_FIELD_INVALID;
        blocking = 1U;
    }
    else if (sample->fix_ok == 0U)
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_FIX_FLAG;
        blocking = 1U;
    }
    return blocking;
}

static uint8_t SystemGnssQuality_SampleAgeCheck(
    SystemGnssSample *sample,
    uint64_t now_us)
{
    if ((sample->sample_timestamp_us != 0U) &&
        (sample->sample_timestamp_us <= now_us) &&
        ((now_us - sample->sample_timestamp_us) <=
         ((uint64_t)SYSTEM_GNSS_MAX_SAMPLE_AGE_MS * 1000ULL)))
    {
        return 0U;
    }
    sample->position_reject_mask |= SYSTEM_GNSS_REJECT_STALE;
    sample->velocity_reject_mask |= SYSTEM_GNSS_REJECT_STALE;
    return 1U;
}

static uint8_t SystemGnssQuality_PositionFieldCheck(
    SystemGnssSample *sample)
{
    SILVERSTAR_ASSERT_OBJECT(sample, SystemGnssSample,
        SILVERSTAR_ASSERT_MODULE_SYSTEM);
    if ((SystemGnssQuality_FieldSupported(
             sample, SYSTEM_GNSS_FIELD_POSITION) == 0U) ||
        (SystemGnssQuality_FieldSupported(
             sample, SYSTEM_GNSS_FIELD_HEIGHT) == 0U))
    {
        sample->position_reject_mask |=
            SYSTEM_GNSS_REJECT_FIELD_UNSUPPORTED;
        return 1U;
    }
    if ((SystemGnssQuality_FieldValid(
             sample, SYSTEM_GNSS_FIELD_POSITION) == 0U) ||
        (SystemGnssQuality_FieldValid(
             sample, SYSTEM_GNSS_FIELD_HEIGHT) == 0U))
    {
        sample->position_reject_mask |= SYSTEM_GNSS_REJECT_FIELD_INVALID;
        return 1U;
    }
    return 0U;
}

static uint8_t SystemGnssQuality_SatelliteCheck(
    SystemGnssSample *sample,
    uint32_t *reject_mask)
{
    uint8_t blocking = 0U;

    SILVERSTAR_ASSERT(sample != NULL, SILVERSTAR_ASSERT_MODULE_SYSTEM,
        SILVERSTAR_ASSERT_REASON_NULL_POINTER);
    SILVERSTAR_ASSERT(reject_mask != NULL, SILVERSTAR_ASSERT_MODULE_SYSTEM,
        SILVERSTAR_ASSERT_REASON_NULL_POINTER);
    SystemGnssQuality_OptionalFieldCheck(sample,
        SYSTEM_GNSS_FIELD_SATELLITE_COUNT, SYSTEM_GNSS_REJECT_SATELLITES,
        reject_mask, &blocking, &sample->quality_degraded);
    if ((SystemGnssQuality_FieldSupported(sample,
             SYSTEM_GNSS_FIELD_SATELLITE_COUNT) != 0U) &&
        (SystemGnssQuality_FieldValid(sample,
             SYSTEM_GNSS_FIELD_SATELLITE_COUNT) != 0U) &&
        (sample->satellite_count < SYSTEM_GNSS_MIN_SATELLITES))
    {
        *reject_mask |= SYSTEM_GNSS_REJECT_SATELLITES;
        blocking = 1U;
    }
    return blocking;
}

static uint8_t SystemGnssQuality_AccuracyCheck(
    SystemGnssSample *sample,
    uint32_t field,
    uint32_t reason,
    float value,
    float maximum,
    uint32_t *reject_mask)
{
    uint8_t blocking = 0U;

    SILVERSTAR_ASSERT(sample != NULL, SILVERSTAR_ASSERT_MODULE_SYSTEM,
        SILVERSTAR_ASSERT_REASON_NULL_POINTER);
    SILVERSTAR_ASSERT(reject_mask != NULL, SILVERSTAR_ASSERT_MODULE_SYSTEM,
        SILVERSTAR_ASSERT_REASON_NULL_POINTER);
    SystemGnssQuality_OptionalFieldCheck(sample, field, reason, reject_mask,
        &blocking, &sample->quality_degraded);
    if ((SystemGnssQuality_FieldSupported(sample, field) != 0U) &&
        (SystemGnssQuality_FieldValid(sample, field) != 0U) &&
        (!isfinite(value) || (value < 0.0f) || (value > maximum)))
    {
        *reject_mask |= reason;
        blocking = 1U;
    }
    return blocking;
}

static uint8_t SystemGnssQuality_VelocityValidMaskGet(
    SystemGnssSample *sample)
{
    uint8_t valid_mask = 0U;

    SILVERSTAR_ASSERT_OBJECT(sample, SystemGnssSample,
        SILVERSTAR_ASSERT_MODULE_SYSTEM);
    if (SystemGnssQuality_FieldSupported(
            sample, SYSTEM_GNSS_FIELD_VELOCITY_HORIZONTAL) == 0U)
    {
        sample->velocity_reject_mask |=
            SYSTEM_GNSS_REJECT_FIELD_UNSUPPORTED;
    }
    else if (SystemGnssQuality_FieldValid(
                 sample, SYSTEM_GNSS_FIELD_VELOCITY_HORIZONTAL) == 0U)
    {
        sample->velocity_reject_mask |= SYSTEM_GNSS_REJECT_FIELD_INVALID;
    }
    else
    {
        valid_mask = SYSTEM_GNSS_VEL_VALID_E | SYSTEM_GNSS_VEL_VALID_N;
    }
    if (SystemGnssQuality_FieldSupported(
            sample, SYSTEM_GNSS_FIELD_VELOCITY_VERTICAL) == 0U)
    {
        sample->velocity_reject_mask |=
            SYSTEM_GNSS_REJECT_FIELD_UNSUPPORTED;
        sample->quality_degraded = 1U;
    }
    else if (SystemGnssQuality_FieldValid(
                 sample, SYSTEM_GNSS_FIELD_VELOCITY_VERTICAL) == 0U)
    {
        sample->velocity_reject_mask |= SYSTEM_GNSS_REJECT_FIELD_INVALID;
    }
    else if (valid_mask != 0U)
    {
        valid_mask |= SYSTEM_GNSS_VEL_VALID_U;
    }
    else
    {
        /* Horizontal velocity remains mandatory for a usable solution. */
    }
    return valid_mask;
}

static void SystemGnssQuality_BlockingSet(uint8_t condition,
                                          uint8_t *blocking)
{
    if (condition != 0U)
    {
        *blocking = 1U;
    }
}

SystemDeviceResult SystemGnssQuality_Evaluate(SystemGnssSample *sample,
                                               uint64_t now_us)
{
    uint8_t position_blocking;
    uint8_t velocity_blocking;
    uint8_t velocity_valid_mask;
    uint8_t age_blocking;

    if (sample == NULL)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(sample, SystemGnssSample,
        SILVERSTAR_ASSERT_MODULE_SYSTEM);
    sample->position_reject_mask = 0U;
    sample->velocity_reject_mask = 0U;
    sample->position_usable = 0U;
    sample->velocity_valid_mask = 0U;
    sample->quality_degraded = 0U;

    position_blocking = SystemGnssQuality_BasicFixCheck(
        sample, &sample->position_reject_mask, &sample->quality_degraded);
    velocity_blocking = SystemGnssQuality_BasicFixCheck(
        sample, &sample->velocity_reject_mask, &sample->quality_degraded);
    age_blocking = SystemGnssQuality_SampleAgeCheck(sample, now_us);
    SystemGnssQuality_BlockingSet(age_blocking, &position_blocking);
    SystemGnssQuality_BlockingSet(age_blocking, &velocity_blocking);
    SystemGnssQuality_BlockingSet(
        SystemGnssQuality_PositionFieldCheck(sample), &position_blocking);
    SystemGnssQuality_BlockingSet(SystemGnssQuality_SatelliteCheck(
        sample, &sample->position_reject_mask), &position_blocking);
    SystemGnssQuality_BlockingSet(SystemGnssQuality_AccuracyCheck(sample,
        SYSTEM_GNSS_FIELD_HORIZONTAL_ACCURACY, SYSTEM_GNSS_REJECT_HACC,
        sample->horizontal_accuracy_m, SYSTEM_GNSS_MAX_HORIZONTAL_ACCURACY_M,
        &sample->position_reject_mask), &position_blocking);
    SystemGnssQuality_BlockingSet(SystemGnssQuality_AccuracyCheck(sample,
        SYSTEM_GNSS_FIELD_VERTICAL_ACCURACY, SYSTEM_GNSS_REJECT_VACC,
        sample->vertical_accuracy_m, SYSTEM_GNSS_MAX_VERTICAL_ACCURACY_M,
        &sample->position_reject_mask), &position_blocking);
    SystemGnssQuality_BlockingSet(SystemGnssQuality_SatelliteCheck(
        sample, &sample->velocity_reject_mask), &velocity_blocking);
    SystemGnssQuality_BlockingSet(SystemGnssQuality_AccuracyCheck(sample,
        SYSTEM_GNSS_FIELD_SPEED_ACCURACY, SYSTEM_GNSS_REJECT_SACC,
        sample->speed_accuracy_mps, SYSTEM_GNSS_MAX_SPEED_ACCURACY_MPS,
        &sample->velocity_reject_mask), &velocity_blocking);
    velocity_valid_mask = SystemGnssQuality_VelocityValidMaskGet(sample);

    if (position_blocking == 0U)
    {
        sample->position_usable = 1U;
    }
    if ((velocity_blocking == 0U) && (velocity_valid_mask != 0U))
    {
        sample->velocity_valid_mask = velocity_valid_mask;
    }
    return SYSTEM_DEVICE_OK;
}
