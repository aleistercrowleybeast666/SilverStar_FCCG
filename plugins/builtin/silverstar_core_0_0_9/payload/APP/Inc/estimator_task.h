#ifndef __ESTIMATOR_TASK_H
#define __ESTIMATOR_TASK_H

#include <stdint.h>

#include "system_device_types.h"
#include "system_alignment.h"

#ifndef SYSTEM_BUILD_ESTIMATOR_ENABLED
#define SYSTEM_BUILD_ESTIMATOR_ENABLED 1U
#endif

#if SYSTEM_BUILD_ESTIMATOR_ENABLED != 0U
#include "navigation_kf.h"
#else
typedef enum
{
    NAV_KF_UPDATE_ACCEPTED = 0U,
    NAV_KF_UPDATE_SOFT_WEIGHTED,
    NAV_KF_UPDATE_REJECTED_NIS,
    NAV_KF_UPDATE_REJECTED_INVALID,
    NAV_KF_UPDATE_NUMERIC_ERROR
} NavigationKfUpdateResult;
#endif

#define ESTIMATOR_HEALTH_NONE                       0U
#define ESTIMATOR_HEALTH_PREDICTION_QUEUE_OVERFLOW (1U << 0)
#define ESTIMATOR_HEALTH_GNSS_ORIGIN_UNAVAILABLE   (1U << 1)
#define ESTIMATOR_HEALTH_BARO_ORIGIN_UNAVAILABLE   (1U << 2)
#define ESTIMATOR_HEALTH_KF_NUMERIC_ERROR           (1U << 3)
#define ESTIMATOR_HEALTH_GNSS_MEASUREMENT_INVALID  (1U << 4)
#define ESTIMATOR_HEALTH_BARO_MEASUREMENT_INVALID  (1U << 5)
#define ESTIMATOR_HEALTH_GEODESY_ERROR              (1U << 6)

#define ESTIMATOR_MEAS_POSITION_ACCEPTED (1U << 0)
#define ESTIMATOR_MEAS_POSITION_SOFT     (1U << 1)
#define ESTIMATOR_MEAS_POSITION_REJECTED (1U << 2)
#define ESTIMATOR_MEAS_VELOCITY_ACCEPTED (1U << 3)
#define ESTIMATOR_MEAS_VELOCITY_SOFT     (1U << 4)
#define ESTIMATOR_MEAS_VELOCITY_REJECTED (1U << 5)
#define ESTIMATOR_MEAS_BARO_ACCEPTED     (1U << 6)
#define ESTIMATOR_MEAS_BARO_SOFT         (1U << 7)
#define ESTIMATOR_MEAS_BARO_REJECTED     (1U << 8)

#define ESTIMATOR_ATTEMPT_GNSS_POSITION (1U << 0)
#define ESTIMATOR_ATTEMPT_GNSS_VELOCITY (1U << 1)
#define ESTIMATOR_ATTEMPT_BAROMETER     (1U << 2)

typedef struct
{
    uint64_t timestamp_us;
    uint32_t update_sequence;

    float position_enu_m[3];
    float velocity_enu_mps[3];
    float q_nb[4];
    float covariance_diagonal[6];
    float covariance[6][6];
    float gnss_position_enu_m[3];
    float gnss_velocity_enu_mps[3];
    float baro_relative_altitude_m;

    float position_innovation[3];
    float velocity_innovation[3];
    float baro_innovation;
    float position_variance_r[3];
    float velocity_variance_r[3];
    float baro_variance_r;

    float last_position_nis;
    float last_velocity_nis;
    float last_baro_nis;
    float position_r_scale;
    float velocity_r_scale;
    float baro_r_scale;
    float process_accel_std_mps2[3];

    uint32_t predict_count;
    uint32_t gnss_position_update_count;
    uint32_t gnss_velocity_update_count;
    uint32_t baro_update_count;
    uint32_t position_reject_count;
    uint32_t velocity_reject_count;
    uint32_t baro_reject_count;
    uint32_t prediction_queue_overflow_count;
    uint32_t health_flags;
    uint32_t measurement_attempt_mask;

    uint64_t last_gnss_timestamp_us;
    uint64_t last_baro_timestamp_us;
    uint32_t last_gnss_sequence;
    uint32_t last_baro_sequence;
    uint32_t last_gnss_age_us;
    uint32_t last_baro_age_us;

    uint8_t initialized;
    uint8_t mission_running;
    uint8_t gnss_origin_valid;
    uint8_t baro_origin_valid;
    uint8_t gnss_velocity_valid_mask;
    uint8_t velocity_update_dimension;
    NavigationKfUpdateResult position_update_result;
    NavigationKfUpdateResult velocity_update_result;
    NavigationKfUpdateResult baro_update_result;
} EstimatorOutputSnapshot;

typedef struct
{
    int32_t gnss_origin_latitude_e7;
    int32_t gnss_origin_longitude_e7;
    int32_t gnss_origin_height_mm;
    float gnss_origin_position_std_m[3];
    float initial_velocity_enu_mps[3];
    float initial_velocity_std_mps[3];
    float barometer_origin_altitude_m;
    float barometer_origin_std_m;
    float p0_diagonal[6];
    uint16_t gnss_sample_count;
    uint16_t barometer_sample_count;
    uint8_t gnss_origin_valid;
    uint8_t barometer_origin_valid;
    uint8_t velocity_valid_mask;
    uint8_t valid;
} EstimatorInitialStateSnapshot;

void AppTask_Estimator(void *argument);
SystemDeviceResult EstimatorTask_FreezeOrigins(void);
SystemDeviceResult EstimatorTask_InitializeMission(void);
void EstimatorTask_AbortMission(void);
void EstimatorTask_RollbackMissionStart(void);
uint8_t Estimator_GetInitialStateSnapshot(
    EstimatorInitialStateSnapshot *snapshot);
uint8_t Estimator_GetLatestSnapshot(EstimatorOutputSnapshot *snapshot);
SYSTEM_WARN_UNUSED_RESULT SystemDeviceResult EstimatorTask_OriginsReset(void);
SYSTEM_WARN_UNUSED_RESULT SystemDeviceResult
EstimatorTask_GnssAlignmentStatusGet(SystemAlignmentGnssStatus *status);
SYSTEM_WARN_UNUSED_RESULT SystemDeviceResult
EstimatorTask_BarometerAlignmentStatusGet(
    SystemAlignmentBarometerStatus *status);

#endif /* __ESTIMATOR_TASK_H */
