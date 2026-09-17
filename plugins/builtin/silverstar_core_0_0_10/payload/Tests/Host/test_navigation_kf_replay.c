#include <string.h>
#include "navigation_kf_replay.h"
#include "system_time.h"
#include "platform_time.h"
#include "platform_critical.h"
#include "test_common.h"

PlatformResult PlatformTime_Init(void) { return PLATFORM_OK; }
uint64_t PlatformTime_Us(void) { return 0ULL; }
PlatformCriticalState PlatformCritical_Enter(void) { return 0U; }
void PlatformCritical_Exit(PlatformCriticalState state) { (void)state; }

static NavigationReplayContext s_reference_history;
static NavigationReplayStorage s_reference_storage;
static NavigationReplayStorage s_delayed_storage;
static NavigationReplayContext s_delayed_history;
static NavigationKfContext s_reference;
static NavigationKfContext s_delayed;
static NavigationKfContext s_wrong;

static void Test_Initialize(void)
{
    NavigationKf_Init(&s_reference);
    NavigationKf_Reset(&s_reference);
    s_delayed = s_reference;
    s_wrong = s_reference;
    NavigationReplay_Reset(&s_reference_history, &s_reference_storage, &s_reference, 1000000ULL, 7U);
    NavigationReplay_Reset(&s_delayed_history, &s_delayed_storage, &s_delayed, 1000000ULL, 7U);
}

static void Test_Compare(void)
{
    unsigned int i, j;
    /* Restored mathematical counters must not accumulate replay invocations. */
    TEST_CHECK(s_reference.predict_count == s_delayed.predict_count);
    TEST_CHECK(s_reference.position_accept_count == s_delayed.position_accept_count);
    TEST_CHECK(s_reference.position_soft_count == s_delayed.position_soft_count);
    TEST_CHECK(s_reference.position_reject_count == s_delayed.position_reject_count);
    TEST_CHECK(s_reference.velocity_accept_count == s_delayed.velocity_accept_count);
    TEST_CHECK(s_reference.velocity_soft_count == s_delayed.velocity_soft_count);
    TEST_CHECK(s_reference.velocity_reject_count == s_delayed.velocity_reject_count);
    TEST_CHECK(s_reference.baro_accept_count == s_delayed.baro_accept_count);
    TEST_CHECK(s_reference.baro_soft_count == s_delayed.baro_soft_count);
    TEST_CHECK(s_reference.baro_reject_count == s_delayed.baro_reject_count);
    TEST_CHECK(s_reference.numeric_error_count == s_delayed.numeric_error_count);
    for (i = 0U; i < 6U; i++)
    {
        TEST_CHECK(isfinite(s_delayed.state[i]));
        TEST_CHECK_NEAR(s_reference.state[i], s_delayed.state[i], 2.0e-5f);
        TEST_CHECK(s_delayed.covariance[i][i] >= 0.0f);
        for (j = 0U; j < 6U; j++)
        {
            TEST_CHECK(isfinite(s_delayed.covariance[i][j]));
            TEST_CHECK_NEAR(s_reference.covariance[i][j], s_delayed.covariance[i][j], 2.0e-5f);
            TEST_CHECK_NEAR(s_delayed.covariance[i][j], s_delayed.covariance[j][i], 1.0e-6f);
        }
    }
}

static NavigationReplayEvent Test_Event(unsigned int step, uint8_t kind)
{
    NavigationReplayEvent event;
    unsigned int axis;
    (void)memset(&event, 0, sizeof(event));
    event.measurement_timestamp_us = 1000000ULL + (uint64_t)step * 5000ULL;
    event.receive_timestamp_us = event.measurement_timestamp_us;
    event.epoch = 7U;
    event.sequence = step;
    event.source = kind;
    event.kind = kind;
    event.valid_group_mask = 15U;
    event.vertical_valid = 1U;
    for (axis = 0U; axis < 3U; axis++)
    {
        event.position[axis] = 0.2f * sinf((float)step * 0.03f);
        event.velocity[axis] = 0.05f * cosf((float)step * 0.03f);
        event.position_variance[axis] = 2.25f;
        event.velocity_variance[axis] = 0.04f;
    }
    event.altitude = 0.5f * sinf((float)step * 0.03f);
    event.altitude_variance = 6.25f;
    return event;
}

static void Test_MixedAndWrap(void)
{
    unsigned int step, kind;
    const unsigned int delays[3] = {16U, 54U, 20U};
    const uint8_t kinds[3] = {NAV_REPLAY_POSITION, NAV_REPLAY_VELOCITY, NAV_REPLAY_BAROMETER};
    NavigationReplayOutcome outcome;
    Test_Initialize();
    for (step = 1U; step <= 2064U; step++)
    {
        const float delta[3] = {0.0005f, -0.0002f, 0.002f * sinf((float)step * 0.04f)};
        uint64_t timestamp = 1000000ULL + (uint64_t)step * 5000ULL;
        TEST_CHECK(NavigationReplay_Predict(&s_reference_history, &s_reference, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        TEST_CHECK(NavigationKf_Predict(&s_wrong, delta, 0.005f) != 0U);
        for (kind = 0U; kind < 3U; kind++)
        {
            if ((step <= 2000U) && ((step % 8U) == 0U))
            {
                NavigationReplayEvent event = Test_Event(step, kinds[kind]);
                TEST_CHECK(NavigationReplay_Insert(&s_reference_history, &s_reference, &event, &outcome) == NAV_REPLAY_OK);
            }
            if ((step > delays[kind]) && (step - delays[kind] <= 2000U) &&
                (((step - delays[kind]) % 8U) == 0U))
            {
                NavigationReplayEvent event = Test_Event(step - delays[kind], kinds[kind]);
                event.receive_timestamp_us = timestamp;
                TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
                /* Negative control: historical timestamp, update current x/P. */
                if (kind == 0U)
                { (void)NavigationKf_UpdateGnssPositionSeparated(&s_wrong, event.position, event.position_variance, &outcome.position_groups); }
                else if (kind == 1U)
                { (void)NavigationKf_UpdateGnssVelocitySeparated(&s_wrong, event.velocity, event.velocity_variance, 1U, &outcome.velocity_groups); }
                else
                { (void)NavigationKf_UpdateBaroAltitude(&s_wrong, event.altitude, event.altitude_variance); }
            }
        }
    }
    Test_Compare();
    TEST_CHECK(fabsf(s_wrong.state[2] - s_reference.state[2]) > 1.0e-4f);
    TEST_CHECK(s_delayed_history.diagnostics.replay_count == 750U);
    TEST_CHECK(s_delayed_history.diagnostics.max_steps <= NAV_REPLAY_MAX_STEPS);
    TEST_CHECK(s_delayed_history.diagnostics.history_miss_count == 0U);
    (void)printf("history_bytes=%u max_steps=%u event_hwm=%u\n", (unsigned int)(sizeof(s_delayed_history) + sizeof(s_delayed_storage)),
        (unsigned int)s_delayed_history.diagnostics.max_steps, (unsigned int)s_delayed_history.diagnostics.event_high_water);
}

static void Test_BarometerAndTies(void)
{
    unsigned int step;
    NavigationReplayOutcome outcome;
    NavigationReplayEvent baro = Test_Event(20U, NAV_REPLAY_BAROMETER);
    NavigationReplayEvent gnss = Test_Event(20U, NAV_REPLAY_POSITION | NAV_REPLAY_VELOCITY);
    Test_Initialize();
    for (step = 1U; step <= 80U; step++)
    {
        const float delta[3] = {0.0f, 0.0f, 0.003f};
        uint64_t timestamp = 1000000ULL + (uint64_t)step * 5000ULL;
        TEST_CHECK(NavigationReplay_Predict(&s_reference_history, &s_reference, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        if (step == 20U)
        {
            TEST_CHECK(NavigationReplay_Insert(&s_reference_history, &s_reference, &gnss, &outcome) == NAV_REPLAY_OK);
            TEST_CHECK(NavigationReplay_Insert(&s_reference_history, &s_reference, &baro, &outcome) == NAV_REPLAY_OK);
        }
        if (step == 60U)
        {
            TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &baro, &outcome) == NAV_REPLAY_OK);
            TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &gnss, &outcome) == NAV_REPLAY_OK);
        }
    }
    Test_Compare();
    s_wrong = s_delayed;
    baro.measurement_timestamp_us = 1U;
    TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &baro, &outcome) == NAV_REPLAY_HISTORY_MISS);
    TEST_CHECK(memcmp(&s_wrong, &s_delayed, sizeof(s_wrong)) == 0);
    baro.epoch = 6U;
    TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &baro, &outcome) == NAV_REPLAY_EPOCH_MISMATCH);
    TEST_CHECK(memcmp(&s_wrong, &s_delayed, sizeof(s_wrong)) == 0);
}

static void Test_ReceiveClockAndTimeSync(void)
{
    NavigationKfGnssEpoch epoch;
    NavigationReplayEvent event;
    unsigned int step, group;
    uint64_t measurement = 0U;
    Test_Initialize();
    (void)memset(&epoch, 0, sizeof(epoch));
    epoch.valid_group_mask = 15U;
    for (group = 0U; group < 3U; group++)
    { epoch.position_std_m[group] = 1.5f; epoch.velocity_std_mps[group] = 0.15f; }
    for (step = 1U; step < 80U; step++)
    {
        epoch.timestamp_us = 1000000ULL + (uint64_t)step * 40000ULL;
        TEST_CHECK(NavigationReplay_ReceiveTrack(&s_delayed_history, &epoch, &event) == NAV_REPLAY_OK);
        TEST_CHECK(SystemTime_MeasurementTimestampResolve(epoch.timestamp_us, epoch.timestamp_us, 0U, 270U, &measurement) == SYSTEM_MEASUREMENT_TIME_OK);
        TEST_CHECK(measurement == epoch.timestamp_us - 270000ULL);
        for (group = 0U; group < 4U; group++)
        { TEST_CHECK(event.evidence[group].generation == 0U); TEST_CHECK(event.evidence[group].outage == 0U); }
    }
    epoch.timestamp_us += 350000ULL;
    TEST_CHECK(NavigationReplay_ReceiveTrack(&s_delayed_history, &epoch, &event) == NAV_REPLAY_OK);
    for (group = 0U; group < 4U; group++)
    { TEST_CHECK(event.evidence[group].generation == 1U); TEST_CHECK(event.evidence[group].outage == 1U); }
    TEST_CHECK(SystemTime_MeasurementTimestampResolve(2000000ULL, 1800000ULL, 1U, 270U, &measurement) == SYSTEM_MEASUREMENT_TIME_OK);
    TEST_CHECK(measurement == 1800000ULL);
    TEST_CHECK(SystemTime_MeasurementTimestampResolve(100ULL, 0ULL, 0U, 270U, &measurement) == SYSTEM_MEASUREMENT_TIME_INVALID);
    TEST_CHECK(SystemTime_MeasurementTimestampResolve(0x100000010ULL, 0ULL, 0U, 270U, &measurement) == SYSTEM_MEASUREMENT_TIME_OK);
    TEST_CHECK(measurement == 0x100000010ULL - 270000ULL);
}

static void Test_ZeroDelayLegacy(void)
{
    unsigned int step, axis;
    NavigationReplayOutcome outcome;
    Test_Initialize();
    for (step = 1U; step <= 700U; step++)
    {
        const float delta[3] = {0.0003f, -0.0001f, 0.0002f};
        uint64_t timestamp = 1000000ULL + (uint64_t)step * 5000ULL;
        TEST_CHECK(NavigationKf_Predict(&s_reference, delta, 0.005f) != 0U);
        TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        if (((step % 8U) == 0U) && ((step < 200U) || (step > 280U)))
        {
            NavigationReplayEvent event = Test_Event(step, NAV_REPLAY_POSITION | NAV_REPLAY_VELOCITY);
            NavigationKfGnssEpoch epoch;
            NavigationKfGnssSeparatedUpdateResult position, velocity;
            (void)memset(&epoch, 0, sizeof(epoch));
            /* Duplicate receive epochs retain legacy measurement updates but
             * cannot authorize GNSS recovery. Keep these two validities separate. */
            epoch.timestamp_us = (step == 160U) ? timestamp - 40000ULL : timestamp;
            epoch.valid_group_mask = 15U;
            for (axis = 0U; axis < 3U; axis++)
            {
                /* A real outage followed by consistent hard innovations. */
                if (step > 280U) { event.position[axis] += 80.0f; }
                epoch.position_enu_m[axis] = event.position[axis];
                epoch.velocity_enu_mps[axis] = event.velocity[axis];
                epoch.position_std_m[axis] = sqrtf(event.position_variance[axis]);
                epoch.velocity_std_mps[axis] = sqrtf(event.velocity_variance[axis]);
            }
            NavigationKf_GnssEpochTrack(&s_reference, &epoch);
            TEST_CHECK(NavigationReplay_ReceiveTrack(&s_delayed_history, &epoch, &event) == NAV_REPLAY_OK);
            (void)NavigationKf_UpdateGnssPositionSeparated(&s_reference, event.position, event.position_variance, &position);
            (void)NavigationKf_UpdateGnssVelocitySeparated(&s_reference, event.velocity, event.velocity_variance, 1U, &velocity);
            NavigationKf_GnssGroupResultProcess(&s_reference, NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL, position.horizontal_result);
            NavigationKf_GnssGroupResultProcess(&s_reference, NAV_KF_GNSS_GROUP_POSITION_VERTICAL, position.vertical_result);
            NavigationKf_GnssGroupResultProcess(&s_reference, NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL, velocity.horizontal_result);
            NavigationKf_GnssGroupResultProcess(&s_reference, NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL, velocity.vertical_result);
            TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
            event.kind = NAV_REPLAY_BAROMETER;
            (void)NavigationKf_UpdateBaroAltitude(&s_reference, event.altitude, event.altitude_variance);
            TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
        }
        TEST_CHECK(memcmp(s_reference.state, s_delayed.state, sizeof(s_reference.state)) == 0);
        TEST_CHECK(memcmp(s_reference.covariance, s_delayed.covariance, sizeof(s_reference.covariance)) == 0);
        TEST_CHECK(s_reference.gnss_reacquisition.reacquire_count == s_delayed.gnss_reacquisition.reacquire_count);
    }
    TEST_CHECK(s_delayed_history.diagnostics.replay_count == 0U);
}

static void Test_BarometerBetweenImuSamples(void)
{
    unsigned int step;
    NavigationReplayOutcome outcome;
    NavigationReplayEvent event = Test_Event(40U, NAV_REPLAY_BAROMETER);
    event.measurement_timestamp_us -= 2500ULL;
    event.altitude = 0.7f;
    Test_Initialize();
    for (step = 1U; step <= 100U; step++)
    {
        const float delta[3] = {0.0f, 0.0f, 0.004f};
        const float half_delta[3] = {0.0f, 0.0f, 0.002f};
        uint64_t timestamp = 1000000ULL + (uint64_t)step * 5000ULL;
        if (step == 40U)
        {
            TEST_CHECK(NavigationKf_Predict(&s_reference, half_delta, 0.0025f) != 0U);
            (void)NavigationKf_UpdateBaroAltitude(&s_reference, event.altitude, event.altitude_variance);
            TEST_CHECK(NavigationKf_Predict(&s_reference, half_delta, 0.0025f) != 0U);
        }
        else { TEST_CHECK(NavigationKf_Predict(&s_reference, delta, 0.005f) != 0U); }
        TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        if (step == 90U)
        { TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK); }
    }
    Test_Compare();
    TEST_CHECK(s_delayed_history.diagnostics.replay_count == 1U);
}

static void Test_OverflowEpochAndDiscontinuity(void)
{
    NavigationReplayOutcome outcome;
    NavigationReplayEvent event;
    const float delta[3] = {0.0f, 0.0f, 0.0f};
    unsigned int index;
    Test_Initialize();
    TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, 1005000ULL, delta, 0.005f) == NAV_REPLAY_OK);
    event = Test_Event(1U, NAV_REPLAY_BAROMETER);
    for (index = 0U; index < NAV_REPLAY_BARO_CAPACITY; index++)
    {
        event.sequence = index;
        TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
    }
    s_wrong = s_delayed;
    event.sequence++;
    TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OVERFLOW);
    TEST_CHECK(s_delayed_history.diagnostics.overflow_count == 1U);
    TEST_CHECK(memcmp(&s_delayed, &s_wrong, sizeof(s_delayed)) == 0);
    NavigationReplay_Reset(&s_delayed_history, &s_delayed_storage, &s_delayed, 1005000ULL, 8U);
    TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_EPOCH_MISMATCH);
    TEST_CHECK(memcmp(&s_delayed, &s_wrong, sizeof(s_delayed)) == 0);
    TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, 1004000ULL, delta, 0.005f) == NAV_REPLAY_DISCONTINUITY);
    TEST_CHECK(memcmp(&s_delayed, &s_wrong, sizeof(s_delayed)) == 0);
}

static void Test_HardInputAndRateCapacity(void)
{
    NavigationReplayOutcome outcome;
    NavigationReplayEvent event;
    unsigned int step;
    Test_Initialize();
    event = Test_Event(0U, NAV_REPLAY_BAROMETER);
    event.altitude = NAN;
    s_wrong = s_delayed;
    TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_INVALID);
    TEST_CHECK(memcmp(&s_delayed, &s_wrong, sizeof(s_delayed)) == 0);
    event.altitude = 0.0f;
    event.receive_timestamp_us = 999999ULL;
    TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_HISTORY_MISS);
    TEST_CHECK(memcmp(&s_delayed, &s_wrong, sizeof(s_delayed)) == 0);
    for (step = 1U; step <= 144U; step++)
    {
        const float delta[3] = {0.0f, 0.0f, 0.0f};
        NavigationReplayResult result;
        s_wrong = s_delayed;
        result = NavigationReplay_Predict(&s_delayed_history, &s_delayed,
            1000000ULL + (uint64_t)step * 2500ULL, delta, 0.0025f);
        if (step < 144U) { TEST_CHECK(result == NAV_REPLAY_OK); }
        else
        {
            TEST_CHECK(result == NAV_REPLAY_OVERFLOW);
            TEST_CHECK(memcmp(&s_delayed, &s_wrong, sizeof(s_delayed)) == 0);
        }
    }
    TEST_CHECK(s_delayed_history.diagnostics.overflow_count == 1U);
    NavigationReplay_RuntimeRecord(&s_delayed_history, 50ULL);
    NavigationReplay_RuntimeRecord(&s_delayed_history, 25ULL);
    TEST_CHECK(s_delayed_history.diagnostics.last_runtime_us == 25U);
    TEST_CHECK(s_delayed_history.diagnostics.max_runtime_us == 50U);
    NavigationReplay_RuntimeRecord(&s_delayed_history, UINT64_MAX);
    TEST_CHECK(s_delayed_history.diagnostics.last_runtime_us == UINT32_MAX);
    TEST_CHECK(s_delayed_history.diagnostics.max_runtime_us == UINT32_MAX);
    NavigationKf_Init(&s_wrong);
    NavigationKf_SetBaroStd(&s_wrong, 1.0f);
    TEST_CHECK_NEAR(s_wrong.baro_std_m, 1.0f, 0.0f);
    TEST_CHECK(NavigationKf_UpdateBaroAltitude(&s_wrong, 1.0f,
        s_wrong.baro_std_m * s_wrong.baro_std_m) == NAV_KF_UPDATE_ACCEPTED);
    TEST_CHECK_NEAR(s_wrong.state[2], 0.9f, 1.0e-6f);
    TEST_CHECK_NEAR(s_wrong.covariance[2][2], 0.9f, 1.0e-6f);
}

static void Test_NominalFullRate(unsigned int barometer_delay_steps)
{
    unsigned int step;
    NavigationReplayOutcome outcome;
    Test_Initialize();
    for (step = 1U; step <= 1100U + barometer_delay_steps; step++)
    {
        const float delta[3] = {0.0001f, 0.0002f, 0.0003f};
        uint64_t timestamp = 1000000ULL + (uint64_t)step * 5000ULL;
        NavigationReplayEvent event;
        TEST_CHECK(NavigationReplay_Predict(&s_reference_history, &s_reference, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        TEST_CHECK(NavigationReplay_Predict(&s_delayed_history, &s_delayed, timestamp, delta, 0.005f) == NAV_REPLAY_OK);
        /* 25 Hz packets: position delay 0, velocity delay 270 ms. */
        if ((step + 54U <= 1000U) && (((step + 54U) % 8U) == 0U))
        {
            event = Test_Event(step, NAV_REPLAY_VELOCITY);
            TEST_CHECK(NavigationReplay_Insert(&s_reference_history, &s_reference, &event, &outcome) == NAV_REPLAY_OK);
        }
        if ((step <= 1000U) && ((step % 8U) == 0U))
        {
            if (step > 54U)
            {
                event = Test_Event(step - 54U, NAV_REPLAY_VELOCITY);
                event.receive_timestamp_us = timestamp;
                TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
            }
            event = Test_Event(step, NAV_REPLAY_POSITION);
            TEST_CHECK(NavigationReplay_Insert(&s_reference_history, &s_reference, &event, &outcome) == NAV_REPLAY_OK);
            TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
        }
        /* Actual JY901B configuration is 200 Hz, including pressure/height. */
        if (step <= 1000U)
        {
            event = Test_Event(step, NAV_REPLAY_BAROMETER);
            TEST_CHECK(NavigationReplay_Insert(&s_reference_history, &s_reference, &event, &outcome) == NAV_REPLAY_OK);
        }
        if ((step > barometer_delay_steps) && (step - barometer_delay_steps <= 1000U))
        {
            event = Test_Event(step - barometer_delay_steps, NAV_REPLAY_BAROMETER);
            event.receive_timestamp_us = timestamp;
            TEST_CHECK(NavigationReplay_Insert(&s_delayed_history, &s_delayed, &event, &outcome) == NAV_REPLAY_OK);
        }
    }
    Test_Compare();
    TEST_CHECK(s_reference_history.diagnostics.overflow_count == 0U);
    TEST_CHECK(s_delayed_history.diagnostics.overflow_count == 0U);
    TEST_CHECK(s_delayed_history.diagnostics.history_miss_count == 0U);
    (void)printf("nominal_200hz_baro_delay_steps=%u max_steps=%u event_hwm=%u\n",
        barometer_delay_steps, (unsigned int)s_delayed_history.diagnostics.max_steps,
        (unsigned int)s_delayed_history.diagnostics.event_high_water);
}

int main(void)
{
    Test_NominalFullRate(0U);
    Test_NominalFullRate(20U);
    Test_NominalFullRate(110U); /* Configured maximum 550 ms. */
    Test_HardInputAndRateCapacity();
    Test_ZeroDelayLegacy();
    Test_BarometerBetweenImuSamples();
    Test_OverflowEpochAndDiscontinuity();
    Test_MixedAndWrap();
    Test_BarometerAndTies();
    Test_ReceiveClockAndTimeSync();
    return Test_Finish("navigation_kf_replay");
}
