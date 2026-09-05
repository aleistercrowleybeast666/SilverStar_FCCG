#include "estimator_task.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

#include "app_tasks.h"
#include "attitude_frame.h"
#include "FreeRTOS.h"
#include "task.h"
#include "estimator_bus.h"
#include "estimator_barometer_pending.h"
#include "geodesy_local.h"
#include "ins_mechanization.h"
#include "ins_task.h"
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
#include "logger_bus.h"
#endif
#include "platform_critical.h"
#include "platform_memory.h"
#include "silverstar_assert.h"
#include "system_alignment.h"
#include "system_barometer.h"
#include "system_barometer_if.h"
#include "system_estimator_diagnostics.h"
#include "system_estimator_profile.h"
#include "system_gnss_if.h"
#include "system_lifecycle.h"
#include "system_navigation_profile.h"
#include "system_time.h"

#define ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE \
    SYSTEM_ESTIMATOR_GNSS_ORIGIN_WINDOW_SAMPLES
#define ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE \
    SYSTEM_ESTIMATOR_BARO_ORIGIN_WINDOW_SAMPLES
#define ESTIMATOR_ORIGIN_MIN_INLIERS \
    SYSTEM_ESTIMATOR_ORIGIN_MIN_INLIERS
#define ESTIMATOR_GNSS_ORIGIN_MAX_AGE_US \
    SYSTEM_ESTIMATOR_GNSS_ORIGIN_MAX_AGE_US
#define ESTIMATOR_BARO_ORIGIN_MAX_AGE_US \
    SYSTEM_ESTIMATOR_BARO_ORIGIN_MAX_AGE_US
#define ESTIMATOR_MAX_PREDICTIONS_PER_CYCLE 64U
#define ESTIMATOR_ORIGIN_FREEZE_MAX_RETRIES \
    SYSTEM_ESTIMATOR_ORIGIN_FREEZE_WAIT_MS

typedef struct
{
    SystemGnssSample samples[ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE];
    float enu_m[ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE][3];
    uint16_t head;
    uint16_t count;
    uint32_t last_sequence;
    uint8_t ready_event_sent;
} EstimatorGnssOriginWindow;

typedef struct
{
    EstimatorPressureSnapshot samples[ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE];
    uint16_t head;
    uint16_t count;
    uint32_t last_sequence;
    uint8_t ready_event_sent;
} EstimatorBarometerOriginWindow;

typedef struct
{
    NavigationKfContext kf;
    GeoLocalFrame gnss_frame;
    SystemGnssSample frozen_gnss;
    float frozen_baro_altitude_m;
    float frozen_baro_pressure_pa;
    float gnss_origin_position_std_m[3];
    float initial_velocity_std_mps[3];
    float baro_origin_std_m;
    float actual_p0_diagonal[6];
    float q_nb[4];
    EstimatorGnssOriginWindow gnss_window;
    EstimatorBarometerOriginWindow baro_window;
    SystemEstimatorGnssDiagnostics gnss_diagnostics;
    SystemKfDiagnostics kf_diagnostics;
    SystemEstimatorBaroDiagnostics baro_diagnostics;
    EstimatorBarometerPendingContext pending_barometer;
    uint32_t last_gnss_sequence;
    uint32_t last_baro_sequence;
    uint32_t output_sequence;
    uint16_t gnss_origin_sample_count;
    uint16_t baro_origin_sample_count;
    uint8_t gnss_origin_valid;
    uint8_t gnss_fusion_enabled;
    uint8_t baro_origin_valid;
    uint8_t origin_collection_frozen;
    uint8_t initialized;
    uint8_t mission_running;
} EstimatorRuntime;

typedef struct
{
    uint32_t position;
    uint32_t velocity;
    uint32_t barometer;
} EstimatorUpdateCounts;

typedef struct
{
    int64_t latitude_sum;
    int64_t longitude_sum;
    int64_t height_sum;
    double final_latitude_sum;
    double final_longitude_sum;
    double final_height_sum;
    double horizontal_accuracy_sum;
    double vertical_accuracy_sum;
    double velocity_sum[3];
    double velocity_square_sum[3];
    double velocity_variance_sum[3];
    float mean_enu[3];
    float variance_enu[3];
    float inlier_mean_enu[3];
    float horizontal_limit;
    float vertical_limit;
    uint16_t velocity_count[3];
    uint16_t start;
    uint16_t inlier_count;
    uint8_t velocity_valid_mask;
} EstimatorGnssFreezeWork;

typedef struct
{
    double sum;
    double variance_sum;
    double inlier_sum;
    double inlier_variance_sum;
    double pressure_sum;
    float mean;
    float limit;
    uint16_t start;
    uint16_t inlier_count;
    uint16_t pressure_count;
} EstimatorBarometerFreezeWork;

typedef enum
{
    ESTIMATOR_GNSS_PREPARE_STOP = 0U,
    ESTIMATOR_GNSS_PREPARE_CONTINUE
} EstimatorGnssPrepareResult;

typedef struct
{
    SystemGnssSample sample;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    FlightLogGnssMeasurementRecord measurement;
#endif
    NavigationKfGnssEpoch epoch;
    NavigationKfGnssSeparatedUpdateResult position_group_result;
    NavigationKfGnssSeparatedUpdateResult velocity_group_result;
    float position_enu_m[3];
    float position_variance[3];
    float velocity_variance[3];
    uint64_t age_us;
    uint8_t position_accepted;
    uint8_t velocity_accepted;
    uint8_t velocity_dimension;
} EstimatorGnssUpdateWork;

typedef enum
{
    ESTIMATOR_BAROMETER_PREPARE_STOP = 0U,
    ESTIMATOR_BAROMETER_PREPARE_CONTINUE
} EstimatorBarometerPrepareResult;

typedef struct
{
    EstimatorPressureSnapshot pressure;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    FlightLogBaroMeasurementRecord measurement;
#endif
    float altitude_m;
    float relative_altitude_m;
    float variance_m2;
} EstimatorBarometerUpdateWork;

static PLATFORM_CPU_FAST_BSS EstimatorRuntime s_estimator;
static EstimatorOutputSnapshot s_snapshot;
static EstimatorOutputSnapshot s_published_snapshot;
static volatile uint8_t s_origin_collection_busy;

static PlatformCriticalState EstimatorTask_IrqLock(void)
{
    return PlatformCritical_Enter();
}

static void EstimatorTask_IrqUnlock(PlatformCriticalState state)
{
    PlatformCritical_Exit(state);
}

static void EstimatorTask_SnapshotCommit(void)
{
    uint32_t primask = EstimatorTask_IrqLock();

    s_published_snapshot = s_snapshot;
    EstimatorTask_IrqUnlock(primask);
}

static float Estimator_Max(float lhs, float rhs)
{
    return (lhs > rhs) ? lhs : rhs;
}

static uint8_t Estimator_BarometerAltitudeResolve(
    const EstimatorPressureSnapshot *pressure,
    float *altitude_m)
{
    SystemBarometerSample sample;

    if ((pressure == NULL) || (altitude_m == NULL))
    {
        return 0U;
    }
    (void)memset(&sample, 0, sizeof(sample));
    sample.pressure_pa = pressure->pressure_pa;
    sample.altitude_m = pressure->altitude_m;
    sample.supported_fields = pressure->supported_fields;
    sample.valid_fields = pressure->valid_fields;
    return (uint8_t)(SystemBarometer_AltitudeResolve(&sample, altitude_m) ==
                     SYSTEM_DEVICE_OK);
}

static void Estimator_BarometerDiagnosticsPublish(void)
{
    SystemEstimatorBaroDiagnostics_Publish(
        &s_estimator.baro_diagnostics);
}

static void Estimator_BarometerUpdateStateSet(
    SystemEstimatorBaroUpdateState state,
    SystemEstimatorBaroSkipReason reason,
    uint64_t timestamp_us,
    uint8_t count_event)
{
    SystemEstimatorBaroUpdateState previous_state =
        s_estimator.baro_diagnostics.last_update_state;
    SystemEstimatorBaroSkipReason previous_reason =
        s_estimator.baro_diagnostics.last_skip_reason;

    SILVERSTAR_ASSERT(state <=
                      SYSTEM_ESTIMATOR_BARO_UPDATE_WAIT_STATE_CATCHUP,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    SILVERSTAR_ASSERT((reason <=
                       SYSTEM_ESTIMATOR_BARO_SKIP_WAIT_STATE_CATCHUP) &&
                      (count_event <= 1U),
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    SystemEstimatorBaroDiagnostics_UpdateRecord(
        &s_estimator.baro_diagnostics, state, reason,
        timestamp_us, count_event);
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    if ((state != previous_state) || (reason != previous_reason))
    {
        (void)LoggerBus_EventPush(timestamp_us,
                                  FLIGHT_LOG_EVENT_BARO_FUSION_STATE,
                                  (uint32_t)state,
                                  (uint32_t)reason);
    }
#else
    (void)previous_state;
    (void)previous_reason;
#endif
    Estimator_BarometerDiagnosticsPublish();
}

static uint8_t Estimator_Kf6Selected(void)
{
    return SYSTEM_BUILD_ESTIMATOR_ENABLED;
}

static uint32_t Estimator_AgeToU32(uint64_t age_us)
{
    return (age_us > UINT32_MAX) ? UINT32_MAX : (uint32_t)age_us;
}

static uint16_t Estimator_RingStart(uint16_t head,
                                    uint16_t count,
                                    uint16_t capacity)
{
    return (uint16_t)((head + capacity - count) % capacity);
}

static uint8_t Estimator_GnssOriginSampleValid(
    const SystemGnssSample *sample)
{
    return (uint8_t)((sample != NULL) &&
                     (sample->position_usable != 0U) &&
                     (sample->latitude_e7 >= -900000000) &&
                     (sample->latitude_e7 <= 900000000) &&
                     (sample->longitude_e7 >= -1800000000) &&
                     (sample->longitude_e7 <= 1800000000) &&
                     isfinite(sample->horizontal_accuracy_m) &&
                     isfinite(sample->vertical_accuracy_m) &&
                     (sample->horizontal_accuracy_m > 0.0f) &&
                     (sample->vertical_accuracy_m > 0.0f));
}

static uint8_t Estimator_GnssSampleFresh(
    const SystemGnssSample *sample,
    uint64_t now_us)
{
    uint64_t timestamp_us;

    if (sample == NULL)
    {
        return 0U;
    }
    timestamp_us = (sample->receive_timestamp_us != 0U) ?
        sample->receive_timestamp_us : sample->sample_timestamp_us;
    return (uint8_t)((timestamp_us != 0U) &&
                     (timestamp_us <= now_us) &&
                     ((now_us - timestamp_us) <=
                      ESTIMATOR_GNSS_ORIGIN_MAX_AGE_US));
}

static uint8_t Estimator_GnssOriginWindowReady(uint64_t now_us)
{
    const EstimatorGnssOriginWindow *window = &s_estimator.gnss_window;
    const SystemGnssSample *latest;

    if (window->count < ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE)
    {
        return 0U;
    }
    latest = &window->samples[(uint16_t)(
        (window->head + ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE - 1U) %
        ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE)];
    return Estimator_GnssSampleFresh(latest, now_us);
}

static void Estimator_StatusDiagnosticsPublish(
    uint64_t state_timestamp_us,
    uint8_t kf6_selected)
{
    SystemEstimatorStatusDiagnostics status;

    (void)memset(&status, 0, sizeof(status));
    status.last_state_timestamp_us = state_timestamp_us;
    status.imu_prediction_count = s_estimator.kf.predict_count;
    status.mode = (kf6_selected != 0U) ?
        SYSTEM_ESTIMATOR_MODE_KF6 : SYSTEM_ESTIMATOR_MODE_PURE_INS;
    status.attitude_source = SYSTEM_ESTIMATOR_ATTITUDE_SOURCE_SOFTWARE_INS;
    status.position_source = (kf6_selected != 0U) ?
        SYSTEM_ESTIMATOR_POSITION_SOURCE_KF6 :
        SYSTEM_ESTIMATOR_POSITION_SOURCE_PURE_INS;
    status.initialized = s_estimator.initialized;
    status.started = s_estimator.mission_running;
    SystemEstimatorStatusDiagnostics_Publish(&status);
}

static void Estimator_GnssAvailabilityRefresh(
    uint8_t kf6_selected,
    uint64_t now_us)
{
    SILVERSTAR_ASSERT(kf6_selected <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT((s_estimator.origin_collection_frozen <= 1U) &&
                      (s_estimator.mission_running <= 1U),
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    s_estimator.gnss_diagnostics.supported = 1U;
    if ((s_estimator.origin_collection_frozen != 0U) ||
        (s_estimator.mission_running != 0U))
    {
        s_estimator.gnss_diagnostics.origin_ready =
            s_estimator.gnss_origin_valid;
        s_estimator.gnss_diagnostics.fusion_enabled =
            s_estimator.gnss_fusion_enabled;
    }
    else
    {
        s_estimator.gnss_diagnostics.origin_ready =
            Estimator_GnssOriginWindowReady(now_us);
        s_estimator.gnss_diagnostics.fusion_enabled = (uint8_t)(
            (kf6_selected != 0U) &&
            (s_estimator.gnss_diagnostics.origin_ready != 0U));
    }
    s_estimator.gnss_diagnostics.origin_valid =
        s_estimator.gnss_origin_valid;
    s_estimator.gnss_diagnostics.origin_lat_e7 =
        s_estimator.frozen_gnss.latitude_e7;
    s_estimator.gnss_diagnostics.origin_lon_e7 =
        s_estimator.frozen_gnss.longitude_e7;
    s_estimator.gnss_diagnostics.origin_height_mm =
        s_estimator.frozen_gnss.ellipsoid_height_mm;
}

static void Estimator_UpdateCountsRefresh(EstimatorUpdateCounts *counts)
{
    SILVERSTAR_ASSERT_OBJECT(counts, EstimatorUpdateCounts,
                             SILVERSTAR_ASSERT_MODULE_APP);
    counts->position = s_estimator.kf.position_accept_count +
        s_estimator.kf.position_soft_count +
        s_estimator.kf.position_reject_count;
    counts->velocity = s_estimator.kf.velocity_accept_count +
        s_estimator.kf.velocity_soft_count +
        s_estimator.kf.velocity_reject_count;
    counts->barometer = s_estimator.kf.baro_accept_count +
        s_estimator.kf.baro_soft_count + s_estimator.kf.baro_reject_count;
    s_estimator.gnss_diagnostics.position_updates = counts->position;
    s_estimator.gnss_diagnostics.velocity_updates = counts->velocity;
    s_estimator.gnss_diagnostics.position_accept_count =
        s_estimator.kf.position_accept_count +
        s_estimator.kf.position_soft_count;
    s_estimator.gnss_diagnostics.position_reject_count =
        s_estimator.kf.position_reject_count;
    s_estimator.gnss_diagnostics.velocity_accept_count =
        s_estimator.kf.velocity_accept_count +
        s_estimator.kf.velocity_soft_count;
    s_estimator.gnss_diagnostics.velocity_reject_count =
        s_estimator.kf.velocity_reject_count;
}

static void Estimator_GnssNisRefresh(void)
{
    s_estimator.gnss_diagnostics.position_horizontal_nis =
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL];
    s_estimator.gnss_diagnostics.position_vertical_nis =
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_POSITION_VERTICAL];
    s_estimator.gnss_diagnostics.velocity_horizontal_nis =
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL];
    s_estimator.gnss_diagnostics.velocity_vertical_nis =
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL];
}

static void Estimator_GnssInnovationRefresh(void)
{
    s_estimator.gnss_diagnostics.innovation_e_m =
        s_estimator.kf.last_position_innovation[0];
    s_estimator.gnss_diagnostics.innovation_n_m =
        s_estimator.kf.last_position_innovation[1];
    s_estimator.gnss_diagnostics.innovation_u_m =
        s_estimator.kf.last_position_innovation[2];
    s_estimator.gnss_diagnostics.innovation_ve_mps =
        s_estimator.kf.last_velocity_innovation[0];
    s_estimator.gnss_diagnostics.innovation_vn_mps =
        s_estimator.kf.last_velocity_innovation[1];
    s_estimator.gnss_diagnostics.innovation_vu_mps =
        s_estimator.kf.last_velocity_innovation[2];
}

static void Estimator_GnssUncertaintyRefresh(void)
{
    SILVERSTAR_ASSERT(isfinite(s_estimator.kf.covariance[0][0]),
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_FLOAT_NOT_FINITE);
    SILVERSTAR_ASSERT(isfinite(s_estimator.kf.covariance[5][5]),
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_FLOAT_NOT_FINITE);
    s_estimator.gnss_diagnostics.position_horizontal_effective_std_m =
        sqrtf(Estimator_Max(
            s_estimator.kf.last_position_effective_variance[0],
            s_estimator.kf.last_position_effective_variance[1]));
    s_estimator.gnss_diagnostics.position_vertical_effective_std_m =
        sqrtf(Estimator_Max(
            s_estimator.kf.last_position_effective_variance[2], 0.0f));
    s_estimator.gnss_diagnostics.velocity_horizontal_effective_std_mps =
        sqrtf(Estimator_Max(
            s_estimator.kf.last_velocity_effective_variance[0],
            s_estimator.kf.last_velocity_effective_variance[1]));
    s_estimator.gnss_diagnostics.velocity_vertical_effective_std_mps =
        sqrtf(Estimator_Max(
            s_estimator.kf.last_velocity_effective_variance[2], 0.0f));
    s_estimator.gnss_diagnostics.covariance_position_e_m2 =
        s_estimator.kf.covariance[0][0];
    s_estimator.gnss_diagnostics.covariance_position_n_m2 =
        s_estimator.kf.covariance[1][1];
    s_estimator.gnss_diagnostics.covariance_position_u_m2 =
        s_estimator.kf.covariance[2][2];
    s_estimator.gnss_diagnostics.covariance_velocity_e_m2ps2 =
        s_estimator.kf.covariance[3][3];
    s_estimator.gnss_diagnostics.covariance_velocity_n_m2ps2 =
        s_estimator.kf.covariance[4][4];
    s_estimator.gnss_diagnostics.covariance_velocity_u_m2ps2 =
        s_estimator.kf.covariance[5][5];
}

static void Estimator_GnssPositionGroupCountersRefresh(void)
{
    s_estimator.gnss_diagnostics.position_horizontal_accept_count =
        s_estimator.kf.gnss_group_accept_count[
            NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL] +
        s_estimator.kf.gnss_group_soft_count[
            NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL];
    s_estimator.gnss_diagnostics.position_horizontal_reject_count =
        s_estimator.kf.gnss_group_reject_count[
            NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL];
    s_estimator.gnss_diagnostics.position_vertical_accept_count =
        s_estimator.kf.gnss_group_accept_count[
            NAV_KF_GNSS_GROUP_POSITION_VERTICAL] +
        s_estimator.kf.gnss_group_soft_count[
            NAV_KF_GNSS_GROUP_POSITION_VERTICAL];
    s_estimator.gnss_diagnostics.position_vertical_reject_count =
        s_estimator.kf.gnss_group_reject_count[
            NAV_KF_GNSS_GROUP_POSITION_VERTICAL];
}

static void Estimator_GnssVelocityGroupCountersRefresh(void)
{
    s_estimator.gnss_diagnostics.velocity_horizontal_accept_count =
        s_estimator.kf.gnss_group_accept_count[
            NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL] +
        s_estimator.kf.gnss_group_soft_count[
            NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL];
    s_estimator.gnss_diagnostics.velocity_horizontal_reject_count =
        s_estimator.kf.gnss_group_reject_count[
            NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL];
    s_estimator.gnss_diagnostics.velocity_vertical_accept_count =
        s_estimator.kf.gnss_group_accept_count[
            NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL] +
        s_estimator.kf.gnss_group_soft_count[
            NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL];
    s_estimator.gnss_diagnostics.velocity_vertical_reject_count =
        s_estimator.kf.gnss_group_reject_count[
            NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL];
}

static void Estimator_GnssReacquisitionRefresh(void)
{
    SILVERSTAR_ASSERT(
        s_estimator.kf.gnss_reacquisition.active_mask <
        (uint8_t)(1U << NAV_KF_GNSS_GROUP_COUNT),
        SILVERSTAR_ASSERT_MODULE_APP,
        SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(
        (s_estimator.kf.gnss_reacquisition.last_inflation_group <
         NAV_KF_GNSS_GROUP_COUNT) ||
        (s_estimator.kf.gnss_reacquisition.last_inflation_group == 0xFFU),
        SILVERSTAR_ASSERT_MODULE_APP,
        SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    s_estimator.gnss_diagnostics.position_horizontal_reject_streak =
        s_estimator.kf.gnss_reacquisition.group[
            NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL].reject_streak;
    s_estimator.gnss_diagnostics.position_vertical_reject_streak =
        s_estimator.kf.gnss_reacquisition.group[
            NAV_KF_GNSS_GROUP_POSITION_VERTICAL].reject_streak;
    s_estimator.gnss_diagnostics.velocity_horizontal_reject_streak =
        s_estimator.kf.gnss_reacquisition.group[
            NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL].reject_streak;
    s_estimator.gnss_diagnostics.velocity_vertical_reject_streak =
        s_estimator.kf.gnss_reacquisition.group[
            NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL].reject_streak;
    s_estimator.gnss_diagnostics.reacquire_count =
        s_estimator.kf.gnss_reacquisition.reacquire_count;
    s_estimator.gnss_diagnostics.reacquire_active_mask =
        s_estimator.kf.gnss_reacquisition.active_mask;
    s_estimator.gnss_diagnostics.last_inflation_group =
        (SystemEstimatorGnssInflationGroup)
            s_estimator.kf.gnss_reacquisition.last_inflation_group;
    s_estimator.gnss_diagnostics.last_inflation_factor =
        s_estimator.kf.gnss_reacquisition.last_inflation_factor;
    s_estimator.gnss_diagnostics.last_inflation_attempt =
        s_estimator.kf.gnss_reacquisition.last_inflation_attempt;
}

static void Estimator_GnssStateRefresh(uint8_t kf6_selected)
{
    SILVERSTAR_ASSERT(s_estimator.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.gnss_fusion_enabled <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (kf6_selected == 0U)
    {
        s_estimator.gnss_diagnostics.last_update_state =
            SYSTEM_ESTIMATOR_GNSS_UPDATE_DISABLED;
        s_estimator.gnss_diagnostics.last_skip_reason =
            SYSTEM_ESTIMATOR_GNSS_SKIP_FUSION_MODE_DISABLED;
    }
    else if ((s_estimator.mission_running != 0U) &&
             (s_estimator.gnss_fusion_enabled == 0U))
    {
        s_estimator.gnss_diagnostics.last_update_state =
            SYSTEM_ESTIMATOR_GNSS_UPDATE_DISABLED;
        s_estimator.gnss_diagnostics.last_skip_reason =
            SYSTEM_ESTIMATOR_GNSS_SKIP_NO_PREFLIGHT_ORIGIN;
    }
    else if (s_estimator.mission_running == 0U)
    {
        s_estimator.gnss_diagnostics.last_update_state =
            (s_estimator.gnss_diagnostics.origin_ready != 0U) ?
                SYSTEM_ESTIMATOR_GNSS_UPDATE_WAIT_SAMPLE :
                SYSTEM_ESTIMATOR_GNSS_UPDATE_WAIT_ORIGIN;
        s_estimator.gnss_diagnostics.last_skip_reason =
            (s_estimator.gnss_diagnostics.origin_ready != 0U) ?
                SYSTEM_ESTIMATOR_GNSS_SKIP_NONE :
                SYSTEM_ESTIMATOR_GNSS_SKIP_NO_PREFLIGHT_ORIGIN;
    }
}

static void Estimator_KfDiagnosticsPublish(
    const EstimatorUpdateCounts *counts,
    uint8_t kf6_selected)
{
    SILVERSTAR_ASSERT_OBJECT(counts, EstimatorUpdateCounts,
                             SILVERSTAR_ASSERT_MODULE_APP);
    s_estimator.kf_diagnostics.initialized = (uint8_t)(
        (kf6_selected != 0U) && (s_estimator.initialized != 0U));
    s_estimator.kf_diagnostics.state_dimension = 6U;
    s_estimator.kf_diagnostics.prediction_count =
        s_estimator.kf.predict_count;
    s_estimator.kf_diagnostics.position_update_count = counts->position;
    s_estimator.kf_diagnostics.velocity_update_count = counts->velocity;
    s_estimator.kf_diagnostics.baro_update_count = counts->barometer;
    s_estimator.kf_diagnostics.sequential_update_count =
        counts->position + counts->velocity + counts->barometer;
    s_estimator.kf_diagnostics.innovation_reject_count =
        s_estimator.kf.position_reject_count +
        s_estimator.kf.velocity_reject_count +
        s_estimator.kf.baro_reject_count;
    s_estimator.kf_diagnostics.reacquire_count =
        s_estimator.kf.gnss_reacquisition.reacquire_count;
    s_estimator.kf_diagnostics.reacquire_active_mask =
        s_estimator.kf.gnss_reacquisition.active_mask;
    SystemKfDiagnostics_Publish(&s_estimator.kf_diagnostics);
}

static void Estimator_DiagnosticsPublish(uint64_t state_timestamp_us)
{
    EstimatorUpdateCounts counts;
    uint8_t kf6_selected = Estimator_Kf6Selected();
    uint64_t now_us = SystemTime_GetMonotonicUs();

    Estimator_StatusDiagnosticsPublish(state_timestamp_us, kf6_selected);
    Estimator_GnssAvailabilityRefresh(kf6_selected, now_us);
    Estimator_UpdateCountsRefresh(&counts);
    Estimator_GnssNisRefresh();
    Estimator_GnssInnovationRefresh();
    Estimator_GnssUncertaintyRefresh();
    Estimator_GnssPositionGroupCountersRefresh();
    Estimator_GnssVelocityGroupCountersRefresh();
    Estimator_GnssReacquisitionRefresh();
    Estimator_GnssStateRefresh(kf6_selected);
    SystemEstimatorGnssDiagnostics_Publish(
        &s_estimator.gnss_diagnostics);
    Estimator_KfDiagnosticsPublish(&counts, kf6_selected);
}

static void Estimator_OriginWindowReset(void)
{
    SILVERSTAR_ASSERT(ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE > 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    SILVERSTAR_ASSERT(ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE > 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    (void)memset(&s_estimator.gnss_window,
                 0,
                 sizeof(s_estimator.gnss_window));
    (void)memset(&s_estimator.baro_window,
                 0,
                 sizeof(s_estimator.baro_window));
    (void)memset(&s_estimator.frozen_gnss,
                 0,
                 sizeof(s_estimator.frozen_gnss));
    (void)memset(s_estimator.gnss_origin_position_std_m,
                 0,
                 sizeof(s_estimator.gnss_origin_position_std_m));
    (void)memset(s_estimator.initial_velocity_std_mps,
                 0,
                 sizeof(s_estimator.initial_velocity_std_mps));
    (void)memset(s_estimator.actual_p0_diagonal,
                 0,
                 sizeof(s_estimator.actual_p0_diagonal));
    s_estimator.frozen_baro_altitude_m = 0.0f;
    s_estimator.frozen_baro_pressure_pa = 0.0f;
    s_estimator.baro_origin_std_m = 0.0f;
    s_estimator.gnss_origin_sample_count = 0U;
    s_estimator.baro_origin_sample_count = 0U;
    s_estimator.gnss_origin_valid = 0U;
    s_estimator.gnss_fusion_enabled = 0U;
    s_estimator.baro_origin_valid = 0U;
    s_estimator.origin_collection_frozen = 0U;
    (void)memset(&s_estimator.gnss_diagnostics, 0,
                 sizeof(s_estimator.gnss_diagnostics));
    s_estimator.gnss_diagnostics.last_inflation_group =
        SYSTEM_ESTIMATOR_GNSS_INFLATION_NONE;
    s_estimator.gnss_diagnostics.last_inflation_factor = 1.0f;
    s_estimator.gnss_diagnostics.last_update_state =
        SYSTEM_ESTIMATOR_GNSS_UPDATE_WAIT_ORIGIN;
    s_estimator.gnss_diagnostics.last_skip_reason =
        SYSTEM_ESTIMATOR_GNSS_SKIP_NO_PREFLIGHT_ORIGIN;
    (void)memset(&s_estimator.kf_diagnostics, 0,
                 sizeof(s_estimator.kf_diagnostics));
    s_estimator.kf_diagnostics.state_dimension = 6U;
    (void)memset(&s_estimator.baro_diagnostics, 0,
                 sizeof(s_estimator.baro_diagnostics));
    s_estimator.baro_diagnostics.origin_required_count =
        ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE;
    s_estimator.baro_diagnostics.origin_state =
        SYSTEM_ESTIMATOR_BARO_ORIGIN_COLLECTING;
    s_estimator.baro_diagnostics.last_update_state =
        SYSTEM_ESTIMATOR_BARO_UPDATE_NO_SAMPLE;
    s_estimator.baro_diagnostics.last_skip_reason =
        SYSTEM_ESTIMATOR_BARO_SKIP_NO_SAMPLE;
    Estimator_BarometerDiagnosticsPublish();
    Estimator_DiagnosticsPublish(0U);
}

static uint8_t Estimator_OriginCollectionBegin(void)
{
    uint32_t primask;

    if (SystemAlignment_IsCollecting() == 0U) { return 0U; }
    primask = EstimatorTask_IrqLock();
    if ((s_estimator.origin_collection_frozen != 0U) ||
        (s_estimator.mission_running != 0U))
    {
        EstimatorTask_IrqUnlock(primask);
        return 0U;
    }
    s_origin_collection_busy = 1U;
    EstimatorTask_IrqUnlock(primask);
    return 1U;
}

static void Estimator_GnssOriginCollect(uint64_t now_us)
{
    SystemGnssSample sample;
    SystemDeviceResult result;
    uint16_t index;

    SILVERSTAR_ASSERT(s_estimator.gnss_window.head <
                      ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_INDEX_RANGE);
    SILVERSTAR_ASSERT(s_estimator.gnss_window.count <=
                      ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    s_estimator.gnss_diagnostics.supported = 1U;
    result = SystemGnss_LatestSampleGet(&sample);
    if (result == SYSTEM_DEVICE_OK)
    {
        s_estimator.gnss_diagnostics.last_measurement_timestamp_us =
            sample.sample_timestamp_us;
        s_estimator.gnss_diagnostics.gnss_ready = (uint8_t)(
            (Estimator_GnssOriginSampleValid(&sample) != 0U) &&
            (Estimator_GnssSampleFresh(&sample, now_us) != 0U));
    }
    else
    {
        s_estimator.gnss_diagnostics.gnss_ready = 0U;
    }
    if ((result != SYSTEM_DEVICE_OK) ||
        (sample.sequence == s_estimator.gnss_window.last_sequence) ||
        (Estimator_GnssOriginSampleValid(&sample) == 0U))
    { return; }
    index = s_estimator.gnss_window.head;
    s_estimator.gnss_window.samples[index] = sample;
    s_estimator.gnss_window.head = (uint16_t)(
        (index + 1U) % ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE);
    if (s_estimator.gnss_window.count < ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE)
    {
        s_estimator.gnss_window.count++;
    }
    s_estimator.gnss_window.last_sequence = sample.sequence;
    if ((s_estimator.gnss_window.count >= ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE) &&
        (s_estimator.gnss_window.ready_event_sent == 0U))
    {
        s_estimator.gnss_window.ready_event_sent = 1U;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
        (void)LoggerBus_EventPush(SystemTime_GetMonotonicUs(),
                                  FLIGHT_LOG_EVENT_ORIGIN_WINDOW_READY,
                                  1U, s_estimator.gnss_window.count);
#endif
    }
}

static void Estimator_BarometerOriginCollect(void)
{
    EstimatorPressureSnapshot pressure;
    float altitude_m;
    uint16_t index;

    SILVERSTAR_ASSERT(s_estimator.baro_window.head <
                      ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_INDEX_RANGE);
    SILVERSTAR_ASSERT(s_estimator.baro_window.count <=
                      ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    s_estimator.baro_diagnostics.source_supported = 1U;
    if ((EstimatorBus_PressureGetLatest(&pressure) == 0U) ||
        (pressure.sequence == s_estimator.baro_window.last_sequence))
    { return; }
    s_estimator.baro_window.last_sequence = pressure.sequence;
    s_estimator.baro_diagnostics.sample_timestamp_us = pressure.timestamp_us;
    s_estimator.baro_diagnostics.sample_valid = (uint8_t)(
        (pressure.valid != 0U) &&
        (Estimator_BarometerAltitudeResolve(&pressure, &altitude_m) != 0U));
    if (s_estimator.baro_diagnostics.sample_valid != 0U)
    {
        pressure.altitude_m = altitude_m;
        index = s_estimator.baro_window.head;
        s_estimator.baro_window.samples[index] = pressure;
        s_estimator.baro_window.head = (uint16_t)(
            (index + 1U) % ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE);
        if (s_estimator.baro_window.count < ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE)
        {
            s_estimator.baro_window.count++;
        }
        if ((s_estimator.baro_window.count >=
             ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE) &&
            (s_estimator.baro_window.ready_event_sent == 0U))
        {
            s_estimator.baro_window.ready_event_sent = 1U;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
            (void)LoggerBus_EventPush(
                SystemTime_GetMonotonicUs(),
                FLIGHT_LOG_EVENT_ORIGIN_WINDOW_READY,
                2U, s_estimator.baro_window.count);
#endif
        }
        s_estimator.baro_diagnostics.origin_sample_count =
            s_estimator.baro_window.count;
        s_estimator.baro_diagnostics.origin_state =
            (s_estimator.baro_window.count >=
             ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE) ?
                SYSTEM_ESTIMATOR_BARO_ORIGIN_READY :
                SYSTEM_ESTIMATOR_BARO_ORIGIN_COLLECTING;
    }
    Estimator_BarometerDiagnosticsPublish();
}

static void Estimator_OriginWindowCollect(void)
{
    uint32_t primask;
    if (Estimator_OriginCollectionBegin() == 0U) { return; }
    Estimator_GnssOriginCollect(SystemTime_GetMonotonicUs());
    Estimator_BarometerOriginCollect();
    primask = EstimatorTask_IrqLock();
    s_origin_collection_busy = 0U;
    EstimatorTask_IrqUnlock(primask);
    Estimator_DiagnosticsPublish(0U);
}

static uint8_t Estimator_GnssFreezeWindowUsable(
    const EstimatorGnssOriginWindow *window)
{
    const SystemGnssSample *latest;
    uint64_t timestamp_us;
    uint64_t now_us;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (window->count < ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE) { return 0U; }
    latest = &window->samples[(uint16_t)(
        (window->head + ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE - 1U) %
        ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE)];
    timestamp_us = (latest->receive_timestamp_us != 0U) ?
        latest->receive_timestamp_us : latest->sample_timestamp_us;
    now_us = SystemTime_GetMonotonicUs();
    return (uint8_t)((timestamp_us <= now_us) &&
                     ((now_us - timestamp_us) <=
                      ESTIMATOR_GNSS_ORIGIN_MAX_AGE_US));
}

static uint8_t Estimator_GnssRoughFrameInit(
    const EstimatorGnssOriginWindow *window,
    EstimatorGnssFreezeWork *work,
    GeoLocalFrame *frame)
{
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE);
        const SystemGnssSample *sample = &window->samples[ring_index];

        work->latitude_sum += sample->latitude_e7;
        work->longitude_sum += sample->longitude_e7;
        work->height_sum += sample->ellipsoid_height_mm;
    }
    return GeoLocalFrame_Init(
        frame,
        (int32_t)(work->latitude_sum / window->count),
        (int32_t)(work->longitude_sum / window->count),
        (int32_t)(work->height_sum / window->count));
}

static uint8_t Estimator_GnssEnuMeanBuild(
    EstimatorGnssOriginWindow *window,
    EstimatorGnssFreezeWork *work,
    const GeoLocalFrame *frame)
{
    uint16_t index;
    uint8_t axis;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE);
        const SystemGnssSample *sample = &window->samples[ring_index];

        if (GeoLocalFrame_ToEnu(frame, sample->latitude_e7,
                sample->longitude_e7, sample->ellipsoid_height_mm,
                window->enu_m[index]) == 0U)
        { return 0U; }
        for (axis = 0U; axis < 3U; axis++)
        {
            work->mean_enu[axis] += window->enu_m[index][axis];
        }
    }
    for (axis = 0U; axis < 3U; axis++)
    {
        work->mean_enu[axis] /= (float)window->count;
    }
    return 1U;
}

static void Estimator_GnssEnuLimitsBuild(
    const EstimatorGnssOriginWindow *window,
    EstimatorGnssFreezeWork *work)
{
    uint16_t index;
    uint8_t axis;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (index = 0U; index < window->count; index++)
    {
        for (axis = 0U; axis < 3U; axis++)
        {
            float difference = window->enu_m[index][axis] -
                               work->mean_enu[axis];
            work->variance_enu[axis] += difference * difference;
        }
    }
    for (axis = 0U; axis < 3U; axis++)
    {
        work->variance_enu[axis] /= (float)window->count;
    }
    work->horizontal_limit = Estimator_Max(
        3.0f * sqrtf(work->variance_enu[0] + work->variance_enu[1]),
        SYSTEM_ESTIMATOR_GNSS_HORIZONTAL_OUTLIER_FLOOR_M);
    work->vertical_limit = Estimator_Max(
        3.0f * sqrtf(work->variance_enu[2]),
        SYSTEM_ESTIMATOR_GNSS_VERTICAL_OUTLIER_FLOOR_M);
}

static uint8_t Estimator_GnssEnuSampleInlier(
    const EstimatorGnssOriginWindow *window,
    const EstimatorGnssFreezeWork *work,
    uint16_t index)
{
    float east_difference;
    float north_difference;
    float up_difference;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT(index < window->count,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_INDEX_RANGE);
    east_difference = window->enu_m[index][0] - work->mean_enu[0];
    north_difference = window->enu_m[index][1] - work->mean_enu[1];
    up_difference = window->enu_m[index][2] - work->mean_enu[2];
    return (uint8_t)(
        (sqrtf((east_difference * east_difference) +
               (north_difference * north_difference)) <=
         work->horizontal_limit) &&
        (fabsf(up_difference) <= work->vertical_limit));
}

static uint8_t Estimator_VelocityAxisMaskGet(uint8_t axis)
{
    static const uint8_t velocity_axis_mask[3] =
    {
        SYSTEM_GNSS_VEL_VALID_E,
        SYSTEM_GNSS_VEL_VALID_N,
        SYSTEM_GNSS_VEL_VALID_U
    };

    return (axis < 3U) ? velocity_axis_mask[axis] : 0U;
}

static void Estimator_GnssInliersCollect(
    const EstimatorGnssOriginWindow *window,
    EstimatorGnssFreezeWork *work)
{
    uint16_t index;
    uint8_t axis;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index;
        const SystemGnssSample *sample;

        if (Estimator_GnssEnuSampleInlier(window, work, index) == 0U)
        { continue; }
        ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE);
        sample = &window->samples[ring_index];
        work->final_latitude_sum += (double)sample->latitude_e7;
        work->final_longitude_sum += (double)sample->longitude_e7;
        work->final_height_sum += (double)sample->ellipsoid_height_mm;
        work->horizontal_accuracy_sum +=
            (double)sample->horizontal_accuracy_m;
        work->vertical_accuracy_sum += (double)sample->vertical_accuracy_m;
        for (axis = 0U; axis < 3U; axis++)
        {
            uint8_t axis_mask = Estimator_VelocityAxisMaskGet(axis);
            work->inlier_mean_enu[axis] += window->enu_m[index][axis];
            if ((sample->velocity_valid_mask & axis_mask) != 0U)
            {
                float velocity = sample->velocity_enu_mps[axis];
                work->velocity_sum[axis] += (double)velocity;
                work->velocity_square_sum[axis] +=
                    (double)velocity * (double)velocity;
                if (isfinite(sample->velocity_variance_m2ps2[axis]) &&
                    (sample->velocity_variance_m2ps2[axis] >= 0.0f))
                {
                    work->velocity_variance_sum[axis] +=
                        (double)sample->velocity_variance_m2ps2[axis];
                }
                work->velocity_count[axis]++;
            }
        }
        work->inlier_count++;
    }
}

static void Estimator_GnssInlierVarianceBuild(
    const EstimatorGnssOriginWindow *window,
    EstimatorGnssFreezeWork *work)
{
    uint16_t index;
    uint8_t axis;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (axis = 0U; axis < 3U; axis++)
    {
        work->inlier_mean_enu[axis] /= (float)work->inlier_count;
        work->variance_enu[axis] = 0.0f;
    }
    for (index = 0U; index < window->count; index++)
    {
        if (Estimator_GnssEnuSampleInlier(window, work, index) == 0U)
        { continue; }
        for (axis = 0U; axis < 3U; axis++)
        {
            float difference = window->enu_m[index][axis] -
                               work->inlier_mean_enu[axis];
            work->variance_enu[axis] += difference * difference;
        }
    }
}

static void Estimator_GnssFrozenPositionCommit(
    const EstimatorGnssOriginWindow *window,
    const EstimatorGnssFreezeWork *work)
{
    uint16_t latest_index;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    latest_index = (uint16_t)(
        (window->head + ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE - 1U) %
        ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE);
    (void)memset(&s_estimator.frozen_gnss, 0,
                 sizeof(s_estimator.frozen_gnss));
    s_estimator.frozen_gnss = window->samples[latest_index];
    s_estimator.frozen_gnss.latitude_e7 = (int32_t)(
        work->final_latitude_sum / (double)work->inlier_count);
    s_estimator.frozen_gnss.longitude_e7 = (int32_t)(
        work->final_longitude_sum / (double)work->inlier_count);
    s_estimator.frozen_gnss.ellipsoid_height_mm = (int32_t)(
        work->final_height_sum / (double)work->inlier_count);
    s_estimator.frozen_gnss.horizontal_accuracy_m = (float)(
        work->horizontal_accuracy_sum / (double)work->inlier_count);
    s_estimator.frozen_gnss.vertical_accuracy_m = (float)(
        work->vertical_accuracy_sum / (double)work->inlier_count);
    s_estimator.frozen_gnss.position_usable = 1U;
    s_estimator.frozen_gnss.velocity_valid_mask = 0U;
}

static void Estimator_GnssFrozenVelocityCommit(
    const EstimatorGnssFreezeWork *work)
{
    uint8_t axis;
    uint8_t velocity_valid_mask = 0U;

    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT(work->inlier_count >= ESTIMATOR_ORIGIN_MIN_INLIERS,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    for (axis = 0U; axis < 3U; axis++)
    {
        float empirical_variance = work->variance_enu[axis] /
                                   (float)work->inlier_count;
        s_estimator.gnss_origin_position_std_m[axis] =
            sqrtf(Estimator_Max(empirical_variance, 0.0f));
        s_estimator.frozen_gnss.velocity_enu_mps[axis] = 0.0f;
        s_estimator.frozen_gnss.velocity_variance_m2ps2[axis] = 0.0f;
        s_estimator.initial_velocity_std_mps[axis] = 0.0f;
        if (work->velocity_count[axis] >= ESTIMATOR_ORIGIN_MIN_INLIERS)
        {
            double count = (double)work->velocity_count[axis];
            double mean_velocity = work->velocity_sum[axis] / count;
            double empirical_velocity_variance =
                (work->velocity_square_sum[axis] / count) -
                (mean_velocity * mean_velocity);
            double reported_velocity_variance =
                work->velocity_variance_sum[axis] / count;
            float selected_variance = (float)Estimator_Max(
                (float)empirical_velocity_variance,
                (float)reported_velocity_variance);

            selected_variance = Estimator_Max(selected_variance, 0.0f);
            s_estimator.frozen_gnss.velocity_enu_mps[axis] =
                (float)mean_velocity;
            s_estimator.frozen_gnss.velocity_variance_m2ps2[axis] =
                selected_variance;
            s_estimator.initial_velocity_std_mps[axis] =
                sqrtf(selected_variance);
            velocity_valid_mask |= Estimator_VelocityAxisMaskGet(axis);
        }
    }
    s_estimator.frozen_gnss.velocity_valid_mask = velocity_valid_mask;
}

static uint8_t Estimator_GnssOriginFreeze(void)
{
    EstimatorGnssOriginWindow *window = &s_estimator.gnss_window;
    GeoLocalFrame temporary_frame;
    EstimatorGnssFreezeWork work;

    (void)memset(&work, 0, sizeof(work));
    SILVERSTAR_ASSERT_OBJECT(window, EstimatorGnssOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (Estimator_GnssFreezeWindowUsable(window) == 0U) { return 0U; }
    work.start = Estimator_RingStart(window->head, window->count,
                                     ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE);
    if (Estimator_GnssRoughFrameInit(
            window, &work, &temporary_frame) == 0U)
    { return 0U; }
    if (Estimator_GnssEnuMeanBuild(
            window, &work, &temporary_frame) == 0U)
    { return 0U; }
    Estimator_GnssEnuLimitsBuild(window, &work);

    Estimator_GnssInliersCollect(window, &work);
    if (work.inlier_count < ESTIMATOR_ORIGIN_MIN_INLIERS)
    {
        return 0U;
    }
    Estimator_GnssInlierVarianceBuild(window, &work);

    Estimator_GnssFrozenPositionCommit(window, &work);
    Estimator_GnssFrozenVelocityCommit(&work);
    s_estimator.gnss_origin_sample_count = work.inlier_count;
    if (GeoLocalFrame_Init(&s_estimator.gnss_frame,
                           s_estimator.frozen_gnss.latitude_e7,
                           s_estimator.frozen_gnss.longitude_e7,
                           s_estimator.frozen_gnss.ellipsoid_height_mm) == 0U)
    {
        return 0U;
    }
    return 1U;
}

static uint8_t Estimator_BarometerFreezeWindowUsable(
    const EstimatorBarometerOriginWindow *window)
{
    const EstimatorPressureSnapshot *latest;
    uint64_t now_us;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorBarometerOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (window->count < ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE) { return 0U; }
    latest = &window->samples[(uint16_t)(
        (window->head + ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE - 1U) %
        ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE)];
    now_us = SystemTime_GetMonotonicUs();
    return (uint8_t)((latest->timestamp_us <= now_us) &&
                     ((now_us - latest->timestamp_us) <=
                      ESTIMATOR_BARO_ORIGIN_MAX_AGE_US));
}

static void Estimator_BarometerFreezeLimitsBuild(
    const EstimatorBarometerOriginWindow *window,
    EstimatorBarometerFreezeWork *work)
{
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorBarometerOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE);
        work->sum += (double)window->samples[ring_index].altitude_m;
    }
    work->mean = (float)(work->sum / (double)window->count);
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE);
        float difference = window->samples[ring_index].altitude_m -
                           work->mean;
        work->variance_sum += (double)difference * (double)difference;
    }
    work->limit = Estimator_Max(
        3.0f * sqrtf((float)(work->variance_sum /
                             (double)window->count)),
        SYSTEM_ESTIMATOR_BARO_OUTLIER_FLOOR_M);
}

static void Estimator_BarometerInliersCollect(
    const EstimatorBarometerOriginWindow *window,
    EstimatorBarometerFreezeWork *work)
{
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorBarometerOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerFreezeWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE);
        const EstimatorPressureSnapshot *sample = &window->samples[ring_index];
        float altitude = sample->altitude_m;

        if (fabsf(altitude - work->mean) > work->limit) { continue; }
        work->inlier_sum += (double)altitude;
        if (((sample->supported_fields & SYSTEM_BARO_FIELD_PRESSURE) != 0U) &&
            ((sample->valid_fields & SYSTEM_BARO_FIELD_PRESSURE) != 0U) &&
            isfinite(sample->pressure_pa) && (sample->pressure_pa > 0.0f))
        {
            work->pressure_sum += (double)sample->pressure_pa;
            work->pressure_count++;
        }
        work->inlier_count++;
    }
}

static void Estimator_BarometerOriginCommit(
    const EstimatorBarometerOriginWindow *window,
    EstimatorBarometerFreezeWork *work)
{
    uint16_t index;

    SILVERSTAR_ASSERT_OBJECT(window, EstimatorBarometerOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT(work->inlier_count >= ESTIMATOR_ORIGIN_MIN_INLIERS,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    s_estimator.frozen_baro_altitude_m =
        (float)(work->inlier_sum / (double)work->inlier_count);
    if (work->pressure_count != 0U)
    {
        s_estimator.frozen_baro_pressure_pa =
            (float)(work->pressure_sum / (double)work->pressure_count);
    }
    for (index = 0U; index < window->count; index++)
    {
        uint16_t ring_index = (uint16_t)(
            (work->start + index) % ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE);
        float altitude = window->samples[ring_index].altitude_m;
        float difference;

        if (fabsf(altitude - work->mean) > work->limit) { continue; }
        difference = altitude - s_estimator.frozen_baro_altitude_m;
        work->inlier_variance_sum +=
            (double)difference * (double)difference;
    }
    s_estimator.baro_origin_std_m = sqrtf((float)(
        work->inlier_variance_sum / (double)work->inlier_count));
    s_estimator.baro_origin_sample_count = work->inlier_count;
    s_estimator.baro_diagnostics.origin_pressure_valid =
        (uint8_t)(work->pressure_count != 0U);
}

static uint8_t Estimator_BarometerOriginFreeze(void)
{
    EstimatorBarometerOriginWindow *window = &s_estimator.baro_window;
    EstimatorBarometerFreezeWork work;

    (void)memset(&work, 0, sizeof(work));
    SILVERSTAR_ASSERT_OBJECT(window, EstimatorBarometerOriginWindow,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (Estimator_BarometerFreezeWindowUsable(window) == 0U) { return 0U; }
    work.start = Estimator_RingStart(window->head, window->count,
                                     ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE);
    Estimator_BarometerFreezeLimitsBuild(window, &work);
    Estimator_BarometerInliersCollect(window, &work);
    if (work.inlier_count < ESTIMATOR_ORIGIN_MIN_INLIERS)
    {
        return 0U;
    }
    Estimator_BarometerOriginCommit(window, &work);
    return 1U;
}

static float Estimator_ResultScale(NavigationKfUpdateResult result,
                                   float nis,
                                   float soft_threshold,
                                   float maximum_scale)
{
    float scale;

    if (result != NAV_KF_UPDATE_SOFT_WEIGHTED)
    {
        return 1.0f;
    }
    scale = nis / soft_threshold;
    return (scale > maximum_scale) ? maximum_scale : scale;
}

static EstimatorGnssPrepareResult Estimator_GnssSamplePrepare(
    uint64_t state_timestamp_us,
    EstimatorGnssUpdateWork *work)
{
    SystemDeviceResult sample_result;

    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    s_estimator.gnss_diagnostics.last_state_timestamp_us =
        state_timestamp_us;
    sample_result = SystemGnss_LatestSampleGet(&work->sample);
    s_estimator.gnss_diagnostics.supported = 1U;
    if (sample_result == SYSTEM_DEVICE_OK)
    {
        s_estimator.gnss_diagnostics.last_measurement_timestamp_us =
            work->sample.sample_timestamp_us;
        s_estimator.gnss_diagnostics.gnss_ready = (uint8_t)(
            (Estimator_GnssOriginSampleValid(&work->sample) != 0U) &&
            (Estimator_GnssSampleFresh(
                 &work->sample, SystemTime_GetMonotonicUs()) != 0U));
    }
    else
    {
        s_estimator.gnss_diagnostics.gnss_ready = 0U;
    }
    if (s_estimator.gnss_fusion_enabled == 0U)
    {
        s_estimator.gnss_diagnostics.last_update_state =
            SYSTEM_ESTIMATOR_GNSS_UPDATE_DISABLED;
        s_estimator.gnss_diagnostics.last_skip_reason =
            SYSTEM_ESTIMATOR_GNSS_SKIP_NO_PREFLIGHT_ORIGIN;
        return ESTIMATOR_GNSS_PREPARE_STOP;
    }
    if (sample_result != SYSTEM_DEVICE_OK)
    {
        if (s_estimator.gnss_diagnostics.last_measurement_timestamp_us == 0U)
        {
            s_estimator.gnss_diagnostics.last_update_state =
                SYSTEM_ESTIMATOR_GNSS_UPDATE_WAIT_SAMPLE;
            s_estimator.gnss_diagnostics.last_skip_reason =
                SYSTEM_ESTIMATOR_GNSS_SKIP_NO_SAMPLE;
        }
        return ESTIMATOR_GNSS_PREPARE_STOP;
    }
    if (work->sample.sequence == s_estimator.last_gnss_sequence)
    { return ESTIMATOR_GNSS_PREPARE_STOP; }
    if (work->sample.sample_timestamp_us > state_timestamp_us)
    {
        s_estimator.gnss_diagnostics.last_update_state =
            SYSTEM_ESTIMATOR_GNSS_UPDATE_WAIT_SAMPLE;
        s_estimator.gnss_diagnostics.last_skip_reason =
            SYSTEM_ESTIMATOR_GNSS_SKIP_WAIT_STATE_CATCHUP;
        return ESTIMATOR_GNSS_PREPARE_STOP;
    }
    s_estimator.last_gnss_sequence = work->sample.sequence;
    return ESTIMATOR_GNSS_PREPARE_CONTINUE;
}

static EstimatorGnssPrepareResult Estimator_GnssMeasurementPrepare(
    uint64_t state_timestamp_us,
    EstimatorGnssUpdateWork *work)
{
    const SystemGnssSample *sample;
    const uint8_t all_velocity_mask =
        SYSTEM_GNSS_VEL_VALID_E | SYSTEM_GNSS_VEL_VALID_N |
        SYSTEM_GNSS_VEL_VALID_U;

    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    sample = &work->sample;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)memset(&work->measurement, 0, sizeof(work->measurement));
    work->measurement.sample_timestamp_us = sample->sample_timestamp_us;
    work->measurement.receive_timestamp_us = sample->receive_timestamp_us;
    work->measurement.sequence = sample->sequence;
    (void)memcpy(work->measurement.velocity_enu_mps,
                 sample->velocity_enu_mps,
                 sizeof(work->measurement.velocity_enu_mps));
    work->measurement.velocity_valid_mask = sample->velocity_valid_mask;
    work->measurement.position_usable = sample->position_usable;
    work->measurement.fusion_allowed = s_estimator.gnss_fusion_enabled;
#endif
    work->age_us = state_timestamp_us - sample->sample_timestamp_us;
    s_snapshot.last_gnss_timestamp_us = sample->sample_timestamp_us;
    s_snapshot.last_gnss_sequence = sample->sequence;
    s_snapshot.last_gnss_age_us = Estimator_AgeToU32(work->age_us);
    s_snapshot.gnss_velocity_valid_mask = sample->velocity_valid_mask;
    if ((s_estimator.gnss_origin_valid != 0U) &&
        (sample->position_usable != 0U))
    {
        s_snapshot.measurement_attempt_mask |=
            ESTIMATOR_ATTEMPT_GNSS_POSITION;
    }
    if ((sample->velocity_valid_mask & all_velocity_mask) == all_velocity_mask)
    { work->velocity_dimension = 3U; }
    else if ((sample->velocity_valid_mask &
              (SYSTEM_GNSS_VEL_VALID_E | SYSTEM_GNSS_VEL_VALID_N)) ==
             (SYSTEM_GNSS_VEL_VALID_E | SYSTEM_GNSS_VEL_VALID_N))
    { work->velocity_dimension = 2U; }
    if (work->velocity_dimension != 0U)
    {
        s_snapshot.measurement_attempt_mask |=
            ESTIMATOR_ATTEMPT_GNSS_VELOCITY;
    }
    if (work->age_us <= SYSTEM_ESTIMATOR_MEASUREMENT_MAX_AGE_US)
    { return ESTIMATOR_GNSS_PREPARE_CONTINUE; }
    s_snapshot.health_flags |= ESTIMATOR_HEALTH_GNSS_MEASUREMENT_INVALID;
    s_estimator.gnss_diagnostics.gnss_ready = 0U;
    s_estimator.gnss_diagnostics.last_update_state =
        SYSTEM_ESTIMATOR_GNSS_UPDATE_STALE;
    s_estimator.gnss_diagnostics.last_skip_reason =
        SYSTEM_ESTIMATOR_GNSS_SKIP_STALE;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)LoggerBus_GnssMeasurementPush(
        sample->sample_timestamp_us, 0U, &work->measurement);
#endif
    return ESTIMATOR_GNSS_PREPARE_STOP;
}

static EstimatorGnssPrepareResult Estimator_GnssPositionBuild(
    EstimatorGnssUpdateWork *work)
{
    float horizontal_std;
    float vertical_std;
    uint8_t index;

    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if ((s_snapshot.measurement_attempt_mask &
         ESTIMATOR_ATTEMPT_GNSS_POSITION) == 0U)
    { return ESTIMATOR_GNSS_PREPARE_CONTINUE; }
    if (GeoLocalFrame_ToEnu(
            &s_estimator.gnss_frame, work->sample.latitude_e7,
            work->sample.longitude_e7, work->sample.ellipsoid_height_mm,
            work->position_enu_m) == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_GEODESY_ERROR;
        s_estimator.gnss_diagnostics.last_update_state =
            SYSTEM_ESTIMATOR_GNSS_UPDATE_INVALID;
        s_estimator.gnss_diagnostics.last_skip_reason =
            SYSTEM_ESTIMATOR_GNSS_SKIP_GEODESY_ERROR;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
        (void)LoggerBus_GnssMeasurementPush(
            work->sample.sample_timestamp_us, 0U, &work->measurement);
#endif
        return ESTIMATOR_GNSS_PREPARE_STOP;
    }
    horizontal_std = SystemEstimatorProfile_GnssStdResolve(
        SYSTEM_ESTIMATOR_GNSS_STD_HORIZONTAL_POSITION,
        work->sample.horizontal_accuracy_m);
    vertical_std = SystemEstimatorProfile_GnssStdResolve(
        SYSTEM_ESTIMATOR_GNSS_STD_VERTICAL_POSITION,
        work->sample.vertical_accuracy_m);
    work->position_variance[0] = (horizontal_std * horizontal_std) +
        (s_estimator.gnss_origin_position_std_m[0] *
         s_estimator.gnss_origin_position_std_m[0]);
    work->position_variance[1] = (horizontal_std * horizontal_std) +
        (s_estimator.gnss_origin_position_std_m[1] *
         s_estimator.gnss_origin_position_std_m[1]);
    work->position_variance[2] = (vertical_std * vertical_std) +
        (s_estimator.gnss_origin_position_std_m[2] *
         s_estimator.gnss_origin_position_std_m[2]);
    for (index = 0U; index < 3U; index++)
    {
        s_snapshot.gnss_position_enu_m[index] = work->position_enu_m[index];
        s_snapshot.position_innovation[index] = work->position_enu_m[index] -
                                                s_estimator.kf.state[index];
        s_snapshot.position_variance_r[index] =
            work->position_variance[index];
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
        work->measurement.position_enu_m[index] = work->position_enu_m[index];
        work->measurement.position_variance_m2[index] =
            work->position_variance[index];
#endif
        work->epoch.position_enu_m[index] = work->position_enu_m[index];
        work->epoch.position_std_m[index] =
            sqrtf(work->position_variance[index]);
    }
    work->epoch.valid_group_mask |= NAV_KF_GNSS_GROUP_MASK(
        NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL) |
        NAV_KF_GNSS_GROUP_MASK(NAV_KF_GNSS_GROUP_POSITION_VERTICAL);
    return ESTIMATOR_GNSS_PREPARE_CONTINUE;
}

static void Estimator_GnssVelocityBuild(EstimatorGnssUpdateWork *work)
{
    uint8_t index;

    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT(work->velocity_dimension <= 3U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    if (work->velocity_dimension == 0U) { return; }
    for (index = 0U; index < 3U; index++)
    {
        float std_mps = SystemEstimatorProfile_GnssStdResolve(
            SYSTEM_ESTIMATOR_GNSS_STD_VELOCITY,
            sqrtf(Estimator_Max(
                work->sample.velocity_variance_m2ps2[index], 0.0f)));
        work->velocity_variance[index] = std_mps * std_mps;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
        work->measurement.velocity_variance_m2ps2[index] =
            work->velocity_variance[index];
#endif
        s_snapshot.gnss_velocity_enu_mps[index] =
            work->sample.velocity_enu_mps[index];
        s_snapshot.velocity_variance_r[index] =
            work->velocity_variance[index];
        work->epoch.velocity_enu_mps[index] =
            work->sample.velocity_enu_mps[index];
        work->epoch.velocity_std_mps[index] = std_mps;
    }
    work->epoch.valid_group_mask |= NAV_KF_GNSS_GROUP_MASK(
        NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL);
    if (work->velocity_dimension == 3U)
    {
        work->epoch.valid_group_mask |= NAV_KF_GNSS_GROUP_MASK(
            NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL);
    }
    s_snapshot.velocity_update_dimension = work->velocity_dimension;
}

static void Estimator_GnssPositionUpdate(
    uint64_t state_timestamp_us,
    const SystemEstimatorProfile *profile,
    EstimatorGnssUpdateWork *work)
{
    float horizontal_scale;
    float vertical_scale;

    SILVERSTAR_ASSERT_OBJECT(profile, SystemEstimatorProfile,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if ((s_snapshot.measurement_attempt_mask &
         ESTIMATOR_ATTEMPT_GNSS_POSITION) == 0U)
    { return; }
    s_snapshot.position_update_result =
        NavigationKf_UpdateGnssPositionSeparated(
            &s_estimator.kf, work->position_enu_m,
            work->position_variance, &work->position_group_result);
    horizontal_scale = Estimator_ResultScale(
        work->position_group_result.horizontal_result,
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL],
        profile->nis_2d_soft, profile->nis_max_r_scale);
    vertical_scale = Estimator_ResultScale(
        work->position_group_result.vertical_result,
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_POSITION_VERTICAL],
        profile->nis_1d_soft, profile->nis_max_r_scale);
    s_snapshot.position_r_scale = Estimator_Max(
        horizontal_scale, vertical_scale);
    s_estimator.kf_diagnostics.last_update_type =
        SYSTEM_KF_UPDATE_GNSS_POSITION;
    s_estimator.kf_diagnostics.last_update_timestamp_us = state_timestamp_us;
    if ((s_snapshot.position_update_result == NAV_KF_UPDATE_ACCEPTED) ||
        (s_snapshot.position_update_result == NAV_KF_UPDATE_SOFT_WEIGHTED))
    {
        s_snapshot.gnss_position_update_count++;
        work->position_accepted = 1U;
    }
    else
    {
        s_snapshot.position_reject_count++;
    }
}

static void Estimator_GnssVelocityUpdate(
    uint64_t state_timestamp_us,
    const SystemEstimatorProfile *profile,
    EstimatorGnssUpdateWork *work)
{
    float horizontal_scale;
    float vertical_scale = 1.0f;
    uint8_t index;

    SILVERSTAR_ASSERT_OBJECT(profile, SystemEstimatorProfile,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (work->velocity_dimension == 0U) { return; }
    for (index = 0U; index < 3U; index++)
    {
        s_snapshot.velocity_innovation[index] =
            work->sample.velocity_enu_mps[index] -
            s_estimator.kf.state[index + 3U];
    }
    s_snapshot.velocity_update_result =
        NavigationKf_UpdateGnssVelocitySeparated(
            &s_estimator.kf, work->sample.velocity_enu_mps,
            work->velocity_variance,
            (uint8_t)(work->velocity_dimension == 3U),
            &work->velocity_group_result);
    horizontal_scale = Estimator_ResultScale(
        work->velocity_group_result.horizontal_result,
        s_estimator.kf.last_gnss_group_nis[
            NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL],
        profile->nis_2d_soft, profile->nis_max_r_scale);
    if (work->velocity_group_result.vertical_attempted != 0U)
    {
        vertical_scale = Estimator_ResultScale(
            work->velocity_group_result.vertical_result,
            s_estimator.kf.last_gnss_group_nis[
                NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL],
            profile->nis_1d_soft, profile->nis_max_r_scale);
    }
    s_snapshot.velocity_r_scale = Estimator_Max(
        horizontal_scale, vertical_scale);
    s_estimator.kf_diagnostics.last_update_type =
        SYSTEM_KF_UPDATE_GNSS_VELOCITY;
    s_estimator.kf_diagnostics.last_update_timestamp_us = state_timestamp_us;
    if ((s_snapshot.velocity_update_result == NAV_KF_UPDATE_ACCEPTED) ||
        (s_snapshot.velocity_update_result == NAV_KF_UPDATE_SOFT_WEIGHTED))
    {
        s_snapshot.gnss_velocity_update_count++;
        work->velocity_accepted = 1U;
    }
    else
    {
        s_snapshot.velocity_reject_count++;
    }
}

static void Estimator_GnssGroupResultsProcess(
    const EstimatorGnssUpdateWork *work)
{
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (work->position_group_result.horizontal_attempted != 0U)
    {
        NavigationKf_GnssGroupResultProcess(
            &s_estimator.kf, NAV_KF_GNSS_GROUP_POSITION_HORIZONTAL,
            work->position_group_result.horizontal_result);
        NavigationKf_GnssGroupResultProcess(
            &s_estimator.kf, NAV_KF_GNSS_GROUP_POSITION_VERTICAL,
            work->position_group_result.vertical_result);
    }
    if (work->velocity_group_result.horizontal_attempted != 0U)
    {
        NavigationKf_GnssGroupResultProcess(
            &s_estimator.kf, NAV_KF_GNSS_GROUP_VELOCITY_HORIZONTAL,
            work->velocity_group_result.horizontal_result);
        if (work->velocity_group_result.vertical_attempted != 0U)
        {
            NavigationKf_GnssGroupResultProcess(
                &s_estimator.kf, NAV_KF_GNSS_GROUP_VELOCITY_VERTICAL,
                work->velocity_group_result.vertical_result);
        }
    }
}

static void Estimator_GnssUpdateFinalize(
    const EstimatorGnssUpdateWork *work)
{
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorGnssUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT(work->velocity_dimension <= 3U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LENGTH_RANGE);
    if (work->velocity_dimension == 0U)
    {
        if ((s_snapshot.measurement_attempt_mask &
             ESTIMATOR_ATTEMPT_GNSS_POSITION) == 0U)
        {
            s_estimator.gnss_diagnostics.last_update_state =
                SYSTEM_ESTIMATOR_GNSS_UPDATE_INVALID;
            s_estimator.gnss_diagnostics.last_skip_reason =
                SYSTEM_ESTIMATOR_GNSS_SKIP_MEASUREMENT_INVALID;
        }
        else
        {
            s_estimator.gnss_diagnostics.last_update_state =
                (work->position_accepted != 0U) ?
                    SYSTEM_ESTIMATOR_GNSS_UPDATE_ACCEPTED :
                    SYSTEM_ESTIMATOR_GNSS_UPDATE_REJECTED;
            s_estimator.gnss_diagnostics.last_skip_reason =
                SYSTEM_ESTIMATOR_GNSS_SKIP_NONE;
        }
    }
    else
    {
        s_estimator.gnss_diagnostics.last_update_state =
            ((work->position_accepted != 0U) ||
             (work->velocity_accepted != 0U)) ?
                SYSTEM_ESTIMATOR_GNSS_UPDATE_ACCEPTED :
                SYSTEM_ESTIMATOR_GNSS_UPDATE_REJECTED;
        s_estimator.gnss_diagnostics.last_skip_reason =
            SYSTEM_ESTIMATOR_GNSS_SKIP_NONE;
    }
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)LoggerBus_GnssMeasurementPush(
        work->sample.sample_timestamp_us,
        s_snapshot.measurement_attempt_mask, &work->measurement);
#endif
}

static void Estimator_GnssUpdate(uint64_t state_timestamp_us)
{
    const SystemEstimatorProfile *profile;
    EstimatorGnssUpdateWork work;

    (void)memset(&work, 0, sizeof(work));
    if (Estimator_GnssSamplePrepare(state_timestamp_us, &work) ==
        ESTIMATOR_GNSS_PREPARE_STOP)
    { return; }
    if (Estimator_GnssMeasurementPrepare(state_timestamp_us, &work) ==
        ESTIMATOR_GNSS_PREPARE_STOP)
    { return; }

    profile = SystemEstimatorProfile_Get();
    SILVERSTAR_ASSERT_OBJECT(profile, SystemEstimatorProfile,
                             SILVERSTAR_ASSERT_MODULE_APP);
    work.epoch.timestamp_us = work.sample.sample_timestamp_us;

    if (Estimator_GnssPositionBuild(&work) == ESTIMATOR_GNSS_PREPARE_STOP)
    { return; }

    Estimator_GnssVelocityBuild(&work);
    if (work.epoch.valid_group_mask != 0U)
    {
        NavigationKf_GnssEpochTrack(&s_estimator.kf, &work.epoch);
    }

    Estimator_GnssPositionUpdate(state_timestamp_us, profile, &work);

    Estimator_GnssVelocityUpdate(state_timestamp_us, profile, &work);

    Estimator_GnssGroupResultsProcess(&work);
    Estimator_GnssUpdateFinalize(&work);
}

static EstimatorBarometerPrepareResult Estimator_BarometerPendingPrepare(
    uint64_t state_timestamp_us,
    EstimatorBarometerUpdateWork *work)
{
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (s_estimator.baro_diagnostics.source_supported == 0U)
    {
        Estimator_BarometerUpdateStateSet(
            SYSTEM_ESTIMATOR_BARO_UPDATE_UNSUPPORTED,
            SYSTEM_ESTIMATOR_BARO_SKIP_UNSUPPORTED, state_timestamp_us,
            (uint8_t)(s_estimator.baro_diagnostics.last_update_state !=
                      SYSTEM_ESTIMATOR_BARO_UPDATE_UNSUPPORTED));
        return ESTIMATOR_BAROMETER_PREPARE_STOP;
    }
    if (s_estimator.pending_barometer.valid == 0U)
    {
        if (EstimatorBus_PressureGetLatest(&work->pressure) == 0U)
        {
            Estimator_BarometerUpdateStateSet(
                SYSTEM_ESTIMATOR_BARO_UPDATE_NO_SAMPLE,
                SYSTEM_ESTIMATOR_BARO_SKIP_NO_SAMPLE, state_timestamp_us,
                (uint8_t)(s_estimator.baro_diagnostics.last_update_state !=
                          SYSTEM_ESTIMATOR_BARO_UPDATE_NO_SAMPLE));
            return ESTIMATOR_BAROMETER_PREPARE_STOP;
        }
        (void)EstimatorBarometerPending_TryLatch(
            &s_estimator.pending_barometer, &work->pressure,
            s_estimator.last_baro_sequence);
    }
    if (EstimatorBarometerPending_Get(
            &s_estimator.pending_barometer, &work->pressure) == 0U)
    { return ESTIMATOR_BAROMETER_PREPARE_STOP; }
    return ESTIMATOR_BAROMETER_PREPARE_CONTINUE;
}

static EstimatorBarometerPrepareResult Estimator_BarometerSampleValidate(
    uint64_t state_timestamp_us,
    EstimatorBarometerUpdateWork *work)
{
    uint64_t age_us;

    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    s_estimator.baro_diagnostics.sample_timestamp_us =
        work->pressure.timestamp_us;
    s_estimator.baro_diagnostics.sample_valid = 0U;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)memset(&work->measurement, 0, sizeof(work->measurement));
    work->measurement.sample_timestamp_us = work->pressure.timestamp_us;
    work->measurement.receive_timestamp_us = work->pressure.receive_timestamp_us;
    work->measurement.sequence = work->pressure.sequence;
#endif
    if ((work->pressure.valid == 0U) ||
        (Estimator_BarometerAltitudeResolve(
             &work->pressure, &work->altitude_m) == 0U))
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_BARO_MEASUREMENT_INVALID;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
        (void)LoggerBus_BaroMeasurementPush(
            work->pressure.timestamp_us, 0U, &work->measurement);
#endif
        Estimator_BarometerUpdateStateSet(
            SYSTEM_ESTIMATOR_BARO_UPDATE_INVALID,
            SYSTEM_ESTIMATOR_BARO_SKIP_INVALID, state_timestamp_us, 1U);
        (void)EstimatorBarometerPending_Consume(
            &s_estimator.pending_barometer, &s_estimator.last_baro_sequence);
        return ESTIMATOR_BAROMETER_PREPARE_STOP;
    }
    s_estimator.baro_diagnostics.sample_valid = 1U;
    if (work->pressure.timestamp_us > state_timestamp_us)
    {
        Estimator_BarometerUpdateStateSet(
            SYSTEM_ESTIMATOR_BARO_UPDATE_WAIT_STATE_CATCHUP,
            SYSTEM_ESTIMATOR_BARO_SKIP_WAIT_STATE_CATCHUP,
            state_timestamp_us, 0U);
        return ESTIMATOR_BAROMETER_PREPARE_STOP;
    }
    age_us = state_timestamp_us - work->pressure.timestamp_us;
    s_snapshot.last_baro_timestamp_us = work->pressure.timestamp_us;
    s_snapshot.last_baro_sequence = work->pressure.sequence;
    s_snapshot.last_baro_age_us = Estimator_AgeToU32(age_us);
    if (age_us <= SYSTEM_ESTIMATOR_MEASUREMENT_MAX_AGE_US)
    { return ESTIMATOR_BAROMETER_PREPARE_CONTINUE; }
    s_snapshot.health_flags |= ESTIMATOR_HEALTH_BARO_MEASUREMENT_INVALID;
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)LoggerBus_BaroMeasurementPush(
        work->pressure.timestamp_us, 0U, &work->measurement);
#endif
    Estimator_BarometerUpdateStateSet(
        SYSTEM_ESTIMATOR_BARO_UPDATE_STALE,
        SYSTEM_ESTIMATOR_BARO_SKIP_STALE, state_timestamp_us, 1U);
    (void)EstimatorBarometerPending_Consume(
        &s_estimator.pending_barometer, &s_estimator.last_baro_sequence);
    return ESTIMATOR_BAROMETER_PREPARE_STOP;
}

static EstimatorBarometerPrepareResult Estimator_BarometerOriginCheck(
    uint64_t state_timestamp_us,
    EstimatorBarometerUpdateWork *work)
{
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if (s_estimator.baro_origin_valid != 0U)
    { return ESTIMATOR_BAROMETER_PREPARE_CONTINUE; }
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)LoggerBus_BaroMeasurementPush(
        work->pressure.timestamp_us, 0U, &work->measurement);
#endif
    Estimator_BarometerUpdateStateSet(
        SYSTEM_ESTIMATOR_BARO_UPDATE_ORIGIN_NOT_READY,
        SYSTEM_ESTIMATOR_BARO_SKIP_ORIGIN_NOT_READY,
        state_timestamp_us, 1U);
    (void)EstimatorBarometerPending_Consume(
        &s_estimator.pending_barometer, &s_estimator.last_baro_sequence);
    return ESTIMATOR_BAROMETER_PREPARE_STOP;
}

static void Estimator_BarometerMeasurementUpdate(
    uint64_t state_timestamp_us,
    const SystemEstimatorProfile *profile,
    EstimatorBarometerUpdateWork *work)
{
    SILVERSTAR_ASSERT_OBJECT(profile, SystemEstimatorProfile,
                             SILVERSTAR_ASSERT_MODULE_APP);
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    s_snapshot.measurement_attempt_mask |= ESTIMATOR_ATTEMPT_BAROMETER;
    work->relative_altitude_m = work->altitude_m -
                                s_estimator.frozen_baro_altitude_m;
    s_snapshot.baro_relative_altitude_m = work->relative_altitude_m;
    work->variance_m2 = Estimator_Max(
        work->pressure.variance_m2,
        profile->barometer_altitude_std_m *
        profile->barometer_altitude_std_m);
    work->variance_m2 += s_estimator.baro_origin_std_m *
                         s_estimator.baro_origin_std_m;
    s_snapshot.baro_innovation = work->relative_altitude_m -
                                 s_estimator.kf.state[2];
    s_snapshot.baro_variance_r = work->variance_m2;
    s_estimator.baro_diagnostics.relative_altitude_m =
        work->relative_altitude_m;
    s_estimator.baro_diagnostics.measurement_variance = work->variance_m2;
    s_estimator.baro_diagnostics.last_innovation = s_snapshot.baro_innovation;
    s_estimator.baro_diagnostics.last_innovation_variance =
        work->variance_m2 + s_estimator.kf.covariance[2][2];
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    work->measurement.relative_altitude_m = work->relative_altitude_m;
    work->measurement.variance_m2 = work->variance_m2;
    work->measurement.valid_mask =
        (work->pressure.valid != 0U) ? 1UL : 0UL;
#endif
    s_snapshot.baro_update_result = NavigationKf_UpdateBaroAltitude(
        &s_estimator.kf, work->relative_altitude_m, work->variance_m2);
    s_estimator.kf_diagnostics.last_update_type = SYSTEM_KF_UPDATE_BAROMETER;
    s_estimator.kf_diagnostics.last_update_timestamp_us = state_timestamp_us;
    s_snapshot.baro_r_scale = Estimator_ResultScale(
        s_snapshot.baro_update_result, s_estimator.kf.last_baro_nis,
        profile->nis_1d_soft, profile->nis_max_r_scale);
}

static void Estimator_BarometerResultProcess(uint64_t state_timestamp_us)
{
    SILVERSTAR_ASSERT(
        s_snapshot.baro_update_result <= NAV_KF_UPDATE_NUMERIC_ERROR,
        SILVERSTAR_ASSERT_MODULE_APP,
        SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    SILVERSTAR_ASSERT(s_estimator.baro_diagnostics.sample_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if ((s_snapshot.baro_update_result == NAV_KF_UPDATE_ACCEPTED) ||
        (s_snapshot.baro_update_result == NAV_KF_UPDATE_SOFT_WEIGHTED))
    {
        s_snapshot.baro_update_count++;
        if (s_snapshot.baro_update_result == NAV_KF_UPDATE_ACCEPTED)
        {
            Estimator_BarometerUpdateStateSet(
                SYSTEM_ESTIMATOR_BARO_UPDATE_ACCEPTED,
                SYSTEM_ESTIMATOR_BARO_SKIP_NONE, state_timestamp_us, 1U);
        }
        else
        {
            Estimator_BarometerUpdateStateSet(
                SYSTEM_ESTIMATOR_BARO_UPDATE_SOFTENED,
                SYSTEM_ESTIMATOR_BARO_SKIP_NONE, state_timestamp_us, 1U);
        }
    }
    else
    {
        s_snapshot.baro_reject_count++;
        Estimator_BarometerUpdateStateSet(
            SYSTEM_ESTIMATOR_BARO_UPDATE_REJECTED,
            SYSTEM_ESTIMATOR_BARO_SKIP_NONE, state_timestamp_us, 1U);
    }
}

static void Estimator_BarometerUpdateFinish(
    const EstimatorBarometerUpdateWork *work)
{
    SILVERSTAR_ASSERT_OBJECT(work, EstimatorBarometerUpdateWork,
                             SILVERSTAR_ASSERT_MODULE_APP);
    s_estimator.baro_diagnostics.last_nis = s_estimator.kf.last_baro_nis;
    Estimator_BarometerDiagnosticsPublish();
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    (void)LoggerBus_BaroMeasurementPush(
        work->pressure.timestamp_us, s_snapshot.measurement_attempt_mask,
        &work->measurement);
#endif
    (void)EstimatorBarometerPending_Consume(
        &s_estimator.pending_barometer, &s_estimator.last_baro_sequence);
}

static void Estimator_BarometerUpdate(uint64_t state_timestamp_us)
{
    const SystemEstimatorProfile *profile;
    EstimatorBarometerUpdateWork work;

    (void)memset(&work, 0, sizeof(work));
    if (Estimator_BarometerPendingPrepare(state_timestamp_us, &work) ==
        ESTIMATOR_BAROMETER_PREPARE_STOP)
    { return; }
    if (Estimator_BarometerSampleValidate(state_timestamp_us, &work) ==
        ESTIMATOR_BAROMETER_PREPARE_STOP)
    { return; }
    if (Estimator_BarometerOriginCheck(state_timestamp_us, &work) ==
        ESTIMATOR_BAROMETER_PREPARE_STOP)
    { return; }

    profile = SystemEstimatorProfile_Get();
    Estimator_BarometerMeasurementUpdate(state_timestamp_us, profile, &work);
    Estimator_BarometerResultProcess(state_timestamp_us);
    Estimator_BarometerUpdateFinish(&work);
}

static void Estimator_SnapshotPublish(uint64_t timestamp_us)
{
    EstimatorBusStats bus_stats;
    uint8_t row;

    SILVERSTAR_ASSERT(s_estimator.output_sequence < UINT32_MAX,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_SEQUENCE_INVARIANT);
    EstimatorBus_StatsGet(&bus_stats);
    s_snapshot.timestamp_us = timestamp_us;
    s_snapshot.update_sequence = ++s_estimator.output_sequence;
    memcpy(s_snapshot.position_enu_m, s_estimator.kf.state,
           sizeof(s_snapshot.position_enu_m));
    memcpy(s_snapshot.velocity_enu_mps, &s_estimator.kf.state[3],
           sizeof(s_snapshot.velocity_enu_mps));
    memcpy(s_snapshot.q_nb, s_estimator.q_nb, sizeof(s_snapshot.q_nb));
    memcpy(s_snapshot.covariance, s_estimator.kf.covariance,
           sizeof(s_snapshot.covariance));
    for (row = 0U; row < 6U; row++)
    {
        s_snapshot.covariance_diagonal[row] =
            s_estimator.kf.covariance[row][row];
    }
    SILVERSTAR_ASSERT(row == 6U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_LOOP_BOUND);
    memcpy(s_snapshot.process_accel_std_mps2,
           s_estimator.kf.process_accel_std_mps2,
           sizeof(s_snapshot.process_accel_std_mps2));
    s_snapshot.last_position_nis = s_estimator.kf.last_position_nis;
    s_snapshot.last_velocity_nis = s_estimator.kf.last_velocity_nis;
    s_snapshot.last_baro_nis = s_estimator.kf.last_baro_nis;
    s_snapshot.predict_count = s_estimator.kf.predict_count;
    s_snapshot.prediction_queue_overflow_count =
        bus_stats.prediction_overflow_count;
    s_snapshot.health_flags |= s_estimator.kf.health_flags;
    s_snapshot.initialized = s_estimator.initialized;
    s_snapshot.mission_running = s_estimator.mission_running;
    s_snapshot.gnss_origin_valid = s_estimator.gnss_origin_valid;
    s_snapshot.baro_origin_valid = s_estimator.baro_origin_valid;
    EstimatorTask_SnapshotCommit();
    Estimator_DiagnosticsPublish(timestamp_us);
}

#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
static uint32_t Estimator_MeasurementResultFlagBuild(
    uint32_t attempt_bit,
    NavigationKfUpdateResult result,
    uint32_t accepted_bit,
    uint32_t soft_bit,
    uint32_t rejected_bit)
{
    SILVERSTAR_ASSERT(result <= NAV_KF_UPDATE_NUMERIC_ERROR,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    SILVERSTAR_ASSERT((attempt_bit != 0U) && (accepted_bit != 0U) &&
                      (soft_bit != 0U) && (rejected_bit != 0U),
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if ((s_snapshot.measurement_attempt_mask & attempt_bit) == 0U)
    {
        return 0U;
    }
    if (result == NAV_KF_UPDATE_ACCEPTED)
    {
        return accepted_bit;
    }
    if (result == NAV_KF_UPDATE_SOFT_WEIGHTED)
    {
        return soft_bit;
    }
    return rejected_bit;
}

static uint32_t Estimator_MeasurementFlagsBuild(void)
{
    uint32_t flags = 0U;

    SILVERSTAR_ASSERT(
        (s_snapshot.measurement_attempt_mask &
         ~(ESTIMATOR_ATTEMPT_GNSS_POSITION |
           ESTIMATOR_ATTEMPT_GNSS_VELOCITY |
           ESTIMATOR_ATTEMPT_BAROMETER)) == 0U,
        SILVERSTAR_ASSERT_MODULE_APP,
        SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(
        (s_snapshot.position_update_result <= NAV_KF_UPDATE_NUMERIC_ERROR) &&
        (s_snapshot.velocity_update_result <= NAV_KF_UPDATE_NUMERIC_ERROR) &&
        (s_snapshot.baro_update_result <= NAV_KF_UPDATE_NUMERIC_ERROR),
        SILVERSTAR_ASSERT_MODULE_APP,
        SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    flags |= Estimator_MeasurementResultFlagBuild(
        ESTIMATOR_ATTEMPT_GNSS_POSITION,
        s_snapshot.position_update_result,
        ESTIMATOR_MEAS_POSITION_ACCEPTED,
        ESTIMATOR_MEAS_POSITION_SOFT,
        ESTIMATOR_MEAS_POSITION_REJECTED);
    flags |= Estimator_MeasurementResultFlagBuild(
        ESTIMATOR_ATTEMPT_GNSS_VELOCITY,
        s_snapshot.velocity_update_result,
        ESTIMATOR_MEAS_VELOCITY_ACCEPTED,
        ESTIMATOR_MEAS_VELOCITY_SOFT,
        ESTIMATOR_MEAS_VELOCITY_REJECTED);
    flags |= Estimator_MeasurementResultFlagBuild(
        ESTIMATOR_ATTEMPT_BAROMETER,
        s_snapshot.baro_update_result,
        ESTIMATOR_MEAS_BARO_ACCEPTED,
        ESTIMATOR_MEAS_BARO_SOFT,
        ESTIMATOR_MEAS_BARO_REJECTED);
    return flags;
}

static void Estimator_BaseLogBuild(FlightLogEstimatorRecord *base)
{
    SILVERSTAR_ASSERT_OBJECT(base, FlightLogEstimatorRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(base, 0, sizeof(*base));
    memcpy(base->position_enu_m, s_snapshot.position_enu_m,
           sizeof(base->position_enu_m));
    memcpy(base->velocity_enu_mps, s_snapshot.velocity_enu_mps,
           sizeof(base->velocity_enu_mps));
    memcpy(base->covariance_diagonal, s_snapshot.covariance_diagonal,
           sizeof(base->covariance_diagonal));
    memcpy(base->gnss_position_enu_m, s_snapshot.gnss_position_enu_m,
           sizeof(base->gnss_position_enu_m));
    memcpy(base->gnss_velocity_enu_mps, s_snapshot.gnss_velocity_enu_mps,
           sizeof(base->gnss_velocity_enu_mps));
    base->baro_relative_altitude_m = s_snapshot.baro_relative_altitude_m;
    base->last_position_nis = s_snapshot.last_position_nis;
    base->last_velocity_nis = s_snapshot.last_velocity_nis;
    base->last_baro_nis = s_snapshot.last_baro_nis;
    base->measurement_result_flags = Estimator_MeasurementFlagsBuild();
    base->health_flags = s_snapshot.health_flags;
    base->prediction_queue_overflow_count =
        s_snapshot.prediction_queue_overflow_count;
    base->gnss_sequence = s_snapshot.last_gnss_sequence;
    base->baro_sequence = s_snapshot.last_baro_sequence;
    base->gnss_timestamp_us = s_snapshot.last_gnss_timestamp_us;
    base->baro_timestamp_us = s_snapshot.last_baro_timestamp_us;
    base->gnss_measurement_age_us = s_snapshot.last_gnss_age_us;
    base->baro_measurement_age_us = s_snapshot.last_baro_age_us;
    base->gnss_origin_valid = s_snapshot.gnss_origin_valid;
    base->baro_origin_valid = s_snapshot.baro_origin_valid;
    base->initialized = s_snapshot.initialized;
    base->mission_running = s_snapshot.mission_running;
}

static void Estimator_DiagnosticLogBuild(
    FlightLogKf6DiagnosticRecord *diagnostic)
{
    SILVERSTAR_ASSERT_OBJECT(diagnostic, FlightLogKf6DiagnosticRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(diagnostic, 0, sizeof(*diagnostic));
    memcpy(diagnostic->position_innovation, s_snapshot.position_innovation,
           sizeof(diagnostic->position_innovation));
    memcpy(diagnostic->velocity_innovation, s_snapshot.velocity_innovation,
           sizeof(diagnostic->velocity_innovation));
    diagnostic->baro_innovation = s_snapshot.baro_innovation;
    memcpy(diagnostic->position_variance_r, s_snapshot.position_variance_r,
           sizeof(diagnostic->position_variance_r));
    memcpy(diagnostic->velocity_variance_r, s_snapshot.velocity_variance_r,
           sizeof(diagnostic->velocity_variance_r));
    diagnostic->baro_variance_r = s_snapshot.baro_variance_r;
    diagnostic->position_nis = s_snapshot.last_position_nis;
    diagnostic->velocity_nis = s_snapshot.last_velocity_nis;
    diagnostic->baro_nis = s_snapshot.last_baro_nis;
    diagnostic->position_r_scale = s_snapshot.position_r_scale;
    diagnostic->velocity_r_scale = s_snapshot.velocity_r_scale;
    diagnostic->baro_r_scale = s_snapshot.baro_r_scale;
    memcpy(diagnostic->process_accel_std_mps2,
           s_snapshot.process_accel_std_mps2,
           sizeof(diagnostic->process_accel_std_mps2));
    diagnostic->gnss_velocity_valid_mask =
        s_snapshot.gnss_velocity_valid_mask;
    diagnostic->velocity_update_dimension =
        s_snapshot.velocity_update_dimension;
    diagnostic->position_update_result =
        (uint8_t)s_snapshot.position_update_result;
    diagnostic->velocity_update_result =
        (uint8_t)s_snapshot.velocity_update_result;
    diagnostic->baro_update_result =
        (uint8_t)s_snapshot.baro_update_result;
}

static void Estimator_FullPLogBuild(FlightLogKf6FullPRecord *full_p)
{
    uint8_t row;
    uint8_t column;
    uint8_t upper_index = 0U;

    SILVERSTAR_ASSERT_OBJECT(full_p, FlightLogKf6FullPRecord,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(full_p, 0, sizeof(*full_p));
    for (row = 0U; row < 6U; row++)
    {
        for (column = row; column < 6U; column++)
        {
            full_p->covariance_upper_triangle[upper_index++] =
                s_snapshot.covariance[row][column];
        }
    }
    SILVERSTAR_ASSERT(upper_index == 21U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_POSTCONDITION);
}

static void Estimator_LogPush(uint64_t timestamp_us)
{
    FlightLogEstimatorRecord base;
    FlightLogKf6DiagnosticRecord diagnostic;
    FlightLogKf6FullPRecord full_p;

    Estimator_BaseLogBuild(&base);
    Estimator_DiagnosticLogBuild(&diagnostic);
    Estimator_FullPLogBuild(&full_p);
    (void)LoggerBus_EstimatorPush(timestamp_us, 0U, &base);
    (void)LoggerBus_Kf6DiagnosticPush(
        timestamp_us, s_snapshot.measurement_attempt_mask, &diagnostic);
    (void)LoggerBus_Kf6FullPPush(timestamp_us, &full_p);
}
#endif

static void Estimator_PureInsPublish(uint64_t timestamp_us)
{
    InsOutputSnapshot pure_ins;

    if (Ins_GetLatestSnapshot(&pure_ins) == 0U)
    {
        return;
    }
    SILVERSTAR_ASSERT(pure_ins.ins_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(pure_ins.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if ((pure_ins.ins_valid == 0U) ||
        (pure_ins.mission_running == 0U))
    {
        return;
    }

    (void)memset(&s_snapshot, 0, sizeof(s_snapshot));
    s_snapshot.timestamp_us = timestamp_us;
    s_snapshot.update_sequence = ++s_estimator.output_sequence;
    (void)memcpy(s_snapshot.q_nb, pure_ins.q_nb, sizeof(s_snapshot.q_nb));
    (void)memcpy(s_snapshot.position_enu_m,
                 pure_ins.position_n_m,
                 sizeof(s_snapshot.position_enu_m));
    (void)memcpy(s_snapshot.velocity_enu_mps,
                 pure_ins.velocity_n_mps,
                 sizeof(s_snapshot.velocity_enu_mps));
    s_snapshot.initialized = 1U;
    s_snapshot.mission_running = 1U;
    s_snapshot.gnss_origin_valid = s_estimator.gnss_origin_valid;
    s_snapshot.baro_origin_valid = s_estimator.baro_origin_valid;
    EstimatorTask_SnapshotCommit();
}

static void Estimator_PredictionProcess(
    const SystemInertialIncrement *prediction)
{
    float delta_velocity_enu_mps[3];
    float q_start[4];
    SystemLifecycleState lifecycle_state = SystemLifecycle_GetState();

    if (prediction == NULL)
    {
        return;
    }
    SILVERSTAR_ASSERT_OBJECT(prediction, SystemInertialIncrement,
                             SILVERSTAR_ASSERT_MODULE_APP);
    if ((s_estimator.mission_running == 0U) ||
        ((lifecycle_state != SYSTEM_STATE_FLIGHT) &&
         (lifecycle_state != SYSTEM_STATE_RECOVERY)))
    {
        return;
    }
    if (Estimator_Kf6Selected() == 0U)
    {
        Estimator_PureInsPublish(prediction->timestamp_us);
        Estimator_DiagnosticsPublish(prediction->timestamp_us);
        return;
    }
    memcpy(q_start, s_estimator.q_nb, sizeof(q_start));
    Ins_TransformDeltaVelocityToNavigation(
        q_start,
        prediction->delta_velocity_b_sculling_corrected,
        prediction->dt_s,
        SYSTEM_LOCAL_GRAVITY_MPS2,
        delta_velocity_enu_mps);
    if (Attitude_PropagateQuaternionBodyIncrement(
            q_start,
            prediction->delta_theta_b_corrected,
            s_estimator.q_nb) == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_KF_NUMERIC_ERROR;
        return;
    }
    if (NavigationKf_Predict(&s_estimator.kf,
                             delta_velocity_enu_mps,
                             prediction->dt_s) == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_KF_NUMERIC_ERROR;
        return;
    }
    s_snapshot.measurement_attempt_mask = 0U;
    s_snapshot.position_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_snapshot.velocity_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_snapshot.baro_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_snapshot.velocity_update_dimension = 0U;
    s_snapshot.position_r_scale = 1.0f;
    s_snapshot.velocity_r_scale = 1.0f;
    s_snapshot.baro_r_scale = 1.0f;
    Estimator_GnssUpdate(prediction->timestamp_us);
    Estimator_BarometerUpdate(prediction->timestamp_us);
    Estimator_SnapshotPublish(prediction->timestamp_us);
#if (SILVERSTAR_PROTOCOL_LOGGING_ENABLED != 0U)
    Estimator_LogPush(prediction->timestamp_us);
#endif
}

static void Estimator_PredictionsProcessCycle(void)
{
    SystemInertialIncrement prediction;
    uint32_t prediction_index;

    for (prediction_index = 0U;
         prediction_index < ESTIMATOR_MAX_PREDICTIONS_PER_CYCLE;
         prediction_index++)
    {
        if (EstimatorBus_PredictionPop(&prediction) !=
            ESTIMATOR_BUS_RESULT_OK)
        {
            break;
        }
        Estimator_PredictionProcess(&prediction);
    }
    if (prediction_index == ESTIMATOR_MAX_PREDICTIONS_PER_CYCLE)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_PREDICTION_QUEUE_OVERFLOW;
    }
}

static uint8_t Estimator_OriginCollectionIdleGet(void)
{
    uint32_t primask = EstimatorTask_IrqLock();
    uint8_t idle = (uint8_t)(s_origin_collection_busy == 0U);

    EstimatorTask_IrqUnlock(primask);
    return idle;
}

static SystemDeviceResult Estimator_OriginCollectionWait(void)
{
    uint32_t retry;

    for (retry = 0U; retry < ESTIMATOR_ORIGIN_FREEZE_MAX_RETRIES; retry++)
    {
        if (Estimator_OriginCollectionIdleGet() != 0U)
        {
            return SYSTEM_DEVICE_OK;
        }
        vTaskDelay(pdMS_TO_TICKS(1U));
    }
    return SYSTEM_DEVICE_TIMEOUT;
}

void AppTask_Estimator(void *argument)
{
    (void)argument;
    (void)memset(&s_estimator, 0, sizeof(s_estimator));
    (void)memset(&s_snapshot, 0, sizeof(s_snapshot));
    (void)memset(&s_published_snapshot, 0, sizeof(s_published_snapshot));
    NavigationKf_Init(&s_estimator.kf);
    SystemEstimatorBaroDiagnostics_Reset();
    SystemEstimatorStatusDiagnostics_Reset();
    SystemEstimatorGnssDiagnostics_Reset();
    SystemKfDiagnostics_Reset();
    Estimator_OriginWindowReset();
    s_origin_collection_busy = 0U;

    for (;;)
    {
        Estimator_OriginWindowCollect();
        Estimator_PredictionsProcessCycle();
        vTaskDelay(pdMS_TO_TICKS(1U));
    }
}

SystemDeviceResult EstimatorTask_FreezeOrigins(void)
{
    uint32_t primask;

    SILVERSTAR_ASSERT(s_estimator.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.origin_collection_frozen <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_estimator.mission_running != 0U)
    {
        return SYSTEM_DEVICE_BAD_STATE;
    }
    primask = EstimatorTask_IrqLock();
    s_estimator.origin_collection_frozen = 1U;
    EstimatorTask_IrqUnlock(primask);
    if (Estimator_OriginCollectionWait() != SYSTEM_DEVICE_OK)
    {
        s_estimator.origin_collection_frozen = 0U;
        return SYSTEM_DEVICE_TIMEOUT;
    }
    s_estimator.gnss_origin_valid = Estimator_GnssOriginFreeze();
    if (Estimator_Kf6Selected() == 0U)
    {
        s_estimator.gnss_fusion_enabled = 0U;
    }
    else
    {
        s_estimator.gnss_fusion_enabled =
            (SYSTEM_ESTIMATOR_GNSS_FUSION_REQUIRES_PREFLIGHT_ORIGIN != 0U) ?
                s_estimator.gnss_origin_valid : 1U;
    }
    s_estimator.baro_origin_valid = Estimator_BarometerOriginFreeze();
    s_estimator.baro_diagnostics.origin_sample_count =
        s_estimator.baro_origin_sample_count;
    s_estimator.baro_diagnostics.origin_altitude_m =
        s_estimator.frozen_baro_altitude_m;
    s_estimator.baro_diagnostics.origin_pressure_pa =
        s_estimator.frozen_baro_pressure_pa;
    s_estimator.baro_diagnostics.origin_state =
        (s_estimator.baro_origin_valid != 0U) ?
            SYSTEM_ESTIMATOR_BARO_ORIGIN_FROZEN :
        (s_estimator.baro_diagnostics.source_supported != 0U) ?
            SYSTEM_ESTIMATOR_BARO_ORIGIN_COLLECTING :
            SYSTEM_ESTIMATOR_BARO_ORIGIN_UNAVAILABLE;
    Estimator_BarometerDiagnosticsPublish();
    if (s_estimator.gnss_origin_valid == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_GNSS_ORIGIN_UNAVAILABLE;
    }
    if (s_estimator.baro_origin_valid == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_BARO_ORIGIN_UNAVAILABLE;
    }
    Estimator_DiagnosticsPublish(0U);
    return (s_estimator.baro_origin_valid != 0U) ?
        SYSTEM_DEVICE_OK : SYSTEM_DEVICE_NOT_READY;
}

static SystemDeviceResult Estimator_PureInsMissionInitialize(void)
{
    SILVERSTAR_ASSERT(s_estimator.gnss_origin_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.baro_origin_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    EstimatorBarometerPending_Reset(&s_estimator.pending_barometer);
    s_estimator.last_gnss_sequence = 0U;
    s_estimator.last_baro_sequence = 0U;
    s_estimator.output_sequence = 0U;
    s_estimator.initialized = 1U;
    s_estimator.mission_running = 1U;
    (void)memset(s_estimator.actual_p0_diagonal,
                 0,
                 sizeof(s_estimator.actual_p0_diagonal));
    (void)memset(&s_snapshot, 0, sizeof(s_snapshot));
    (void)memcpy(s_snapshot.q_nb,
                 s_estimator.q_nb,
                 sizeof(s_snapshot.q_nb));
    s_snapshot.initialized = 1U;
    s_snapshot.mission_running = 1U;
    s_snapshot.gnss_origin_valid = s_estimator.gnss_origin_valid;
    s_snapshot.baro_origin_valid = s_estimator.baro_origin_valid;
    Estimator_BarometerUpdateStateSet(
        SYSTEM_ESTIMATOR_BARO_UPDATE_DISABLED,
        SYSTEM_ESTIMATOR_BARO_SKIP_DISABLED,
        SystemTime_GetMonotonicUs(), 1U);
    EstimatorTask_SnapshotCommit();
    Estimator_DiagnosticsPublish(0U);
    return SYSTEM_DEVICE_OK;
}

static void Estimator_KfProfileApply(const SystemEstimatorProfile *profile)
{
    float soft_threshold[3];
    float hard_threshold[3];

    SILVERSTAR_ASSERT_OBJECT(profile, SystemEstimatorProfile,
                             SILVERSTAR_ASSERT_MODULE_APP);
    NavigationKf_Init(&s_estimator.kf);
    NavigationKf_SetProcessAccelStd(&s_estimator.kf,
                                    profile->process_accel_std_mps2);
    NavigationKf_SetBaroStd(&s_estimator.kf,
                            profile->barometer_altitude_std_m);
    soft_threshold[0] = profile->nis_1d_soft;
    soft_threshold[1] = profile->nis_2d_soft;
    soft_threshold[2] = profile->nis_3d_soft;
    hard_threshold[0] = profile->nis_1d_hard;
    hard_threshold[1] = profile->nis_2d_hard;
    hard_threshold[2] = profile->nis_3d_hard;
    NavigationKf_SetNisThresholds(&s_estimator.kf,
                                  soft_threshold,
                                  hard_threshold,
                                  profile->nis_max_r_scale);
}

static void Estimator_KfP0Build(float p0[6][6])
{
    float position_std[3];
    float velocity_std[3];
    uint8_t index;

    SILVERSTAR_ASSERT_OBJECT(p0, float, SILVERSTAR_ASSERT_MODULE_APP);
    if (s_estimator.gnss_origin_valid != 0U)
    {
        position_std[0] = Estimator_Max(
            s_estimator.frozen_gnss.horizontal_accuracy_m,
            s_estimator.gnss_origin_position_std_m[0]);
        position_std[1] = Estimator_Max(
            s_estimator.frozen_gnss.horizontal_accuracy_m,
            s_estimator.gnss_origin_position_std_m[1]);
        position_std[2] = Estimator_Max(
            s_estimator.frozen_gnss.vertical_accuracy_m,
            s_estimator.gnss_origin_position_std_m[2]);
        for (index = 0U; index < 3U; index++)
        {
            velocity_std[index] = Estimator_Max(
                sqrtf(Estimator_Max(
                    s_estimator.frozen_gnss.velocity_variance_m2ps2[index],
                    0.0f)),
                s_estimator.initial_velocity_std_mps[index]);
        }
        SystemEstimatorProfile_BuildP0(
            p0, position_std, velocity_std,
            s_estimator.frozen_gnss.velocity_valid_mask);
    }
    else
    {
        SystemEstimatorProfile_BuildP0(p0, NULL, NULL, 0U);
    }
}

static SystemDeviceResult Estimator_KfReset(float p0[6][6])
{
    uint8_t index;

    SILVERSTAR_ASSERT_OBJECT(p0, float, SILVERSTAR_ASSERT_MODULE_APP);
    if (NavigationKf_ResetWithCovariance(&s_estimator.kf, &p0[0][0]) == 0U)
    {
        return SYSTEM_DEVICE_INTERNAL_ERROR;
    }
    for (index = 0U; index < 6U; index++)
    {
        s_estimator.actual_p0_diagonal[index] = p0[index][index];
    }
    return SYSTEM_DEVICE_OK;
}

static void Estimator_KfInitialVelocityApply(void)
{
    static const uint8_t masks[3] =
    {
        SYSTEM_GNSS_VEL_VALID_E,
        SYSTEM_GNSS_VEL_VALID_N,
        SYSTEM_GNSS_VEL_VALID_U
    };
    uint8_t index;

    SILVERSTAR_ASSERT(s_estimator.gnss_origin_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(
        (s_estimator.frozen_gnss.velocity_valid_mask &
         ~(SYSTEM_GNSS_VEL_VALID_E | SYSTEM_GNSS_VEL_VALID_N |
           SYSTEM_GNSS_VEL_VALID_U)) == 0U,
        SILVERSTAR_ASSERT_MODULE_APP,
        SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_estimator.gnss_origin_valid != 0U)
    {
        for (index = 0U; index < 3U; index++)
        {
            if ((s_estimator.frozen_gnss.velocity_valid_mask &
                 masks[index]) != 0U)
            {
                s_estimator.kf.state[index + 3U] =
                    s_estimator.frozen_gnss.velocity_enu_mps[index];
            }
        }
    }
}

static void Estimator_KfRuntimeInitialize(void)
{
    SILVERSTAR_ASSERT(s_estimator.gnss_origin_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.baro_origin_valid <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    s_estimator.last_gnss_sequence =
        (s_estimator.gnss_origin_valid != 0U) ?
            s_estimator.frozen_gnss.sequence : 0U;
    s_estimator.last_baro_sequence =
        (s_estimator.baro_origin_valid != 0U) ?
            s_estimator.baro_window.last_sequence : 0U;
    EstimatorBarometerPending_Reset(&s_estimator.pending_barometer);
    s_estimator.output_sequence = 0U;
    s_estimator.initialized = 1U;
    s_estimator.mission_running = 1U;
    (void)memset(&s_snapshot, 0, sizeof(s_snapshot));
    s_snapshot.position_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_snapshot.velocity_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_snapshot.baro_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_snapshot.position_r_scale = 1.0f;
    s_snapshot.velocity_r_scale = 1.0f;
    s_snapshot.baro_r_scale = 1.0f;
    if (s_estimator.gnss_origin_valid == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_GNSS_ORIGIN_UNAVAILABLE;
    }
    if (s_estimator.baro_origin_valid == 0U)
    {
        s_snapshot.health_flags |= ESTIMATOR_HEALTH_BARO_ORIGIN_UNAVAILABLE;
        Estimator_BarometerUpdateStateSet(
            SYSTEM_ESTIMATOR_BARO_UPDATE_ORIGIN_NOT_READY,
            SYSTEM_ESTIMATOR_BARO_SKIP_ORIGIN_NOT_READY,
            SystemTime_GetMonotonicUs(), 1U);
    }
}

SystemDeviceResult EstimatorTask_InitializeMission(void)
{
    const SystemEstimatorProfile *profile;
    SystemDeviceResult result;
    float p0[6][6];

    SILVERSTAR_ASSERT(s_estimator.initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (Ins_GetInitialAttitude(s_estimator.q_nb) == 0U)
    {
        return SYSTEM_DEVICE_NOT_READY;
    }
    if (Estimator_Kf6Selected() == 0U)
    {
        return Estimator_PureInsMissionInitialize();
    }
    profile = SystemEstimatorProfile_Get();
    Estimator_KfProfileApply(profile);
    Estimator_KfP0Build(p0);
    result = Estimator_KfReset(p0);
    if (result != SYSTEM_DEVICE_OK)
    {
        return result;
    }
    Estimator_KfInitialVelocityApply();
    Estimator_KfRuntimeInitialize();
    Estimator_SnapshotPublish(0U);
    return SYSTEM_DEVICE_OK;
}

void EstimatorTask_RollbackMissionStart(void)
{
    uint32_t primask;

    /*
     * Roll back only the mission-start transaction.  The preflight origin
     * windows are deliberately preserved so a failed START attempt does not
     * force Alignment to collect them from scratch again.  Frozen origin
     * results are invalidated and will be recomputed from the preserved
     * windows on the next START attempt.
     */
    s_estimator.mission_running = 0U;
    s_estimator.initialized = 0U;
    NavigationKf_Reset(&s_estimator.kf);
    s_snapshot.initialized = 0U;
    s_snapshot.mission_running = 0U;
    s_snapshot.gnss_origin_valid = 0U;
    s_snapshot.baro_origin_valid = 0U;
    EstimatorTask_SnapshotCommit();
    EstimatorBarometerPending_Reset(&s_estimator.pending_barometer);

    s_estimator.gnss_origin_valid = 0U;
    s_estimator.gnss_fusion_enabled = 0U;
    s_estimator.baro_origin_valid = 0U;
    s_estimator.gnss_origin_sample_count = 0U;
    s_estimator.baro_origin_sample_count = 0U;
    s_estimator.baro_diagnostics.origin_sample_count = 0U;
    s_estimator.baro_diagnostics.origin_state =
        (s_estimator.baro_diagnostics.source_supported != 0U) ?
            SYSTEM_ESTIMATOR_BARO_ORIGIN_COLLECTING :
            SYSTEM_ESTIMATOR_BARO_ORIGIN_UNAVAILABLE;
    Estimator_BarometerDiagnosticsPublish();
    Estimator_DiagnosticsPublish(0U);

    /* Resume collection only after all rollback-visible state is coherent. */
    primask = EstimatorTask_IrqLock();
    s_estimator.origin_collection_frozen = 0U;
    EstimatorTask_IrqUnlock(primask);
    SILVERSTAR_ASSERT(s_estimator.mission_running == 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_POSTCONDITION);
    SILVERSTAR_ASSERT(s_estimator.initialized == 0U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_POSTCONDITION);
}

void EstimatorTask_AbortMission(void)
{
    s_estimator.mission_running = 0U;
    s_estimator.initialized = 0U;
    NavigationKf_Reset(&s_estimator.kf);
    s_snapshot.initialized = 0U;
    s_snapshot.mission_running = 0U;
    EstimatorTask_SnapshotCommit();
    EstimatorBarometerPending_Reset(&s_estimator.pending_barometer);
    Estimator_OriginWindowReset();
}

uint8_t Estimator_GetInitialStateSnapshot(
    EstimatorInitialStateSnapshot *snapshot)
{
    uint32_t primask;

    if (snapshot == NULL)
    {
        return 0U;
    }
    SILVERSTAR_ASSERT_OBJECT(snapshot, EstimatorInitialStateSnapshot,
                             SILVERSTAR_ASSERT_MODULE_APP);
    primask = EstimatorTask_IrqLock();
    (void)memset(snapshot, 0, sizeof(*snapshot));
    snapshot->gnss_origin_latitude_e7 = s_estimator.frozen_gnss.latitude_e7;
    snapshot->gnss_origin_longitude_e7 = s_estimator.frozen_gnss.longitude_e7;
    snapshot->gnss_origin_height_mm =
        s_estimator.frozen_gnss.ellipsoid_height_mm;
    (void)memcpy(snapshot->gnss_origin_position_std_m,
                 s_estimator.gnss_origin_position_std_m,
                 sizeof(snapshot->gnss_origin_position_std_m));
    if (Estimator_Kf6Selected() != 0U)
    {
        (void)memcpy(snapshot->initial_velocity_enu_mps,
                     s_estimator.frozen_gnss.velocity_enu_mps,
                     sizeof(snapshot->initial_velocity_enu_mps));
        (void)memcpy(snapshot->initial_velocity_std_mps,
                     s_estimator.initial_velocity_std_mps,
                     sizeof(snapshot->initial_velocity_std_mps));
    }
    snapshot->barometer_origin_altitude_m =
        s_estimator.frozen_baro_altitude_m;
    snapshot->barometer_origin_std_m = s_estimator.baro_origin_std_m;
    (void)memcpy(snapshot->p0_diagonal,
                 s_estimator.actual_p0_diagonal,
                 sizeof(snapshot->p0_diagonal));
    snapshot->gnss_sample_count = s_estimator.gnss_origin_sample_count;
    snapshot->barometer_sample_count = s_estimator.baro_origin_sample_count;
    snapshot->gnss_origin_valid = s_estimator.gnss_origin_valid;
    snapshot->barometer_origin_valid = s_estimator.baro_origin_valid;
    snapshot->velocity_valid_mask = (Estimator_Kf6Selected() != 0U) ?
        s_estimator.frozen_gnss.velocity_valid_mask : 0U;
    snapshot->valid = s_estimator.initialized;
    EstimatorTask_IrqUnlock(primask);
    return snapshot->valid;
}

uint8_t Estimator_GetLatestSnapshot(EstimatorOutputSnapshot *snapshot)
{
    EstimatorOutputSnapshot published;
    uint32_t primask;

    if (snapshot == NULL)
    {
        return 0U;
    }
    primask = EstimatorTask_IrqLock();
    published = s_published_snapshot;
    EstimatorTask_IrqUnlock(primask);
    *snapshot = published;
    return published.initialized;
}

SystemDeviceResult EstimatorTask_OriginsReset(void)
{
    uint32_t primask;

    SILVERSTAR_ASSERT(s_estimator.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.origin_collection_frozen <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_estimator.mission_running != 0U)
    {
        return SYSTEM_DEVICE_BAD_STATE;
    }
    primask = EstimatorTask_IrqLock();
    if (s_origin_collection_busy != 0U)
    {
        EstimatorTask_IrqUnlock(primask);
        return SYSTEM_DEVICE_BUSY;
    }
    /* Command callers must not wait on the estimator task. The short reset
     * and idle check are atomic with respect to origin collection. */
    s_estimator.origin_collection_frozen = 1U;
    Estimator_OriginWindowReset();
    EstimatorTask_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult EstimatorTask_GnssAlignmentStatusGet(
    SystemAlignmentGnssStatus *status)
{
    const EstimatorGnssOriginWindow *window;
    const SystemGnssSample *latest;
    uint64_t now_us;
    uint32_t primask;
    uint8_t window_ready;

    if (status == NULL)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(status, SystemAlignmentGnssStatus,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(status, 0, sizeof(*status));
    status->device_name = SystemGnss_NameGet();
    now_us = SystemTime_GetMonotonicUs();
    primask = EstimatorTask_IrqLock();
    window = &s_estimator.gnss_window;
    status->supported = 1U;
    status->origin_valid = s_estimator.gnss_origin_valid;
    status->sample_count = (s_estimator.gnss_origin_valid != 0U) ?
        s_estimator.gnss_origin_sample_count : window->count;
    if (s_estimator.gnss_origin_valid != 0U)
    {
        status->origin_lat_e7 = s_estimator.frozen_gnss.latitude_e7;
        status->origin_lon_e7 = s_estimator.frozen_gnss.longitude_e7;
        status->origin_height_mm =
            s_estimator.frozen_gnss.ellipsoid_height_mm;
        status->horizontal_accuracy_m =
            s_estimator.frozen_gnss.horizontal_accuracy_m;
        status->vertical_accuracy_m =
            s_estimator.frozen_gnss.vertical_accuracy_m;
    }
    else if (window->count != 0U)
    {
        latest = &window->samples[(uint16_t)(
            (window->head + ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE - 1U) %
            ESTIMATOR_GNSS_ORIGIN_WINDOW_SIZE)];
        status->horizontal_accuracy_m = latest->horizontal_accuracy_m;
        status->vertical_accuracy_m = latest->vertical_accuracy_m;
    }
    window_ready = Estimator_GnssOriginWindowReady(now_us);
    EstimatorTask_IrqUnlock(primask);
    status->ready = (uint8_t)((status->origin_valid != 0U) ||
                              (window_ready != 0U));
    status->state = (status->supported == 0U) ?
        SYSTEM_ALIGNMENT_COMPONENT_DISABLED :
        (status->ready != 0U) ? SYSTEM_ALIGNMENT_COMPONENT_READY :
                               SYSTEM_ALIGNMENT_COMPONENT_NOT_READY;
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult EstimatorTask_BarometerAlignmentStatusGet(
    SystemAlignmentBarometerStatus *status)
{
    uint32_t primask;

    if (status == NULL)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(status, SystemAlignmentBarometerStatus,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(status, 0, sizeof(*status));
    status->device_name = SystemBarometer_NameGet();
    primask = EstimatorTask_IrqLock();
    status->supported = 1U;
    status->origin_valid = s_estimator.baro_origin_valid;
    status->sample_count = (s_estimator.baro_origin_valid != 0U) ?
        s_estimator.baro_origin_sample_count : s_estimator.baro_window.count;
    status->origin_pressure_pa = s_estimator.frozen_baro_pressure_pa;
    status->origin_altitude_m = s_estimator.frozen_baro_altitude_m;
    status->ready = (uint8_t)((status->origin_valid != 0U) ||
        (s_estimator.baro_window.count >=
         ESTIMATOR_BARO_ORIGIN_WINDOW_SIZE));
    EstimatorTask_IrqUnlock(primask);
    status->state = (status->supported == 0U) ?
        SYSTEM_ALIGNMENT_COMPONENT_DISABLED :
        (status->ready != 0U) ? SYSTEM_ALIGNMENT_COMPONENT_READY :
                               SYSTEM_ALIGNMENT_COMPONENT_COLLECTING;
    return SYSTEM_DEVICE_OK;
}
