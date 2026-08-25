#include "estimator_task.h"

#include <stddef.h>
#include <string.h>

#include "FreeRTOS.h"
#include "ins_task.h"
#include "platform_critical.h"
#include "platform_memory.h"
#include "silverstar_assert.h"
#include "task.h"

typedef struct
{
    EstimatorOutputSnapshot output;
    EstimatorInitialStateSnapshot initial;
    uint8_t initialized;
    uint8_t mission_running;
} EstimatorNoFusionRuntime;

static PLATFORM_CPU_FAST_BSS EstimatorNoFusionRuntime s_estimator;

static PlatformCriticalState EstimatorNoFusion_IrqLock(void)
{
    return PlatformCritical_Enter();
}

static void EstimatorNoFusion_IrqUnlock(PlatformCriticalState state)
{
    PlatformCritical_Exit(state);
}

static void EstimatorNoFusion_OutputRefresh(void)
{
    InsOutputSnapshot ins;
    PlatformCriticalState state;

    SILVERSTAR_ASSERT(s_estimator.initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if ((s_estimator.mission_running == 0U) ||
        (Ins_GetLatestSnapshot(&ins) == 0U))
    {
        return;
    }
    state = EstimatorNoFusion_IrqLock();
    s_estimator.output.timestamp_us = ins.timestamp_us;
    s_estimator.output.update_sequence = ins.update_seq;
    (void)memcpy(s_estimator.output.position_enu_m,
                 ins.position_n_m,
                 sizeof(s_estimator.output.position_enu_m));
    (void)memcpy(s_estimator.output.velocity_enu_mps,
                 ins.velocity_n_mps,
                 sizeof(s_estimator.output.velocity_enu_mps));
    (void)memcpy(s_estimator.output.q_nb,
                 ins.q_nb,
                 sizeof(s_estimator.output.q_nb));
    s_estimator.output.initialized = s_estimator.initialized;
    s_estimator.output.mission_running = s_estimator.mission_running;
    EstimatorNoFusion_IrqUnlock(state);
}

void AppTask_Estimator(void *argument)
{
    (void)argument;
    (void)memset(&s_estimator, 0, sizeof(s_estimator));
    for (;;)
    {
        EstimatorNoFusion_OutputRefresh();
        vTaskDelay(pdMS_TO_TICKS(1U));
    }
}

SystemDeviceResult EstimatorTask_FreezeOrigins(void)
{
    return (s_estimator.mission_running == 0U) ?
        SYSTEM_DEVICE_OK : SYSTEM_DEVICE_BAD_STATE;
}

SystemDeviceResult EstimatorTask_InitializeMission(void)
{
    float q_nb[4];
    PlatformCriticalState state;

    SILVERSTAR_ASSERT(s_estimator.initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_estimator.mission_running <= 1U,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_estimator.mission_running != 0U)
    {
        return SYSTEM_DEVICE_ALREADY_MATCHED;
    }
    if (Ins_GetInitialAttitude(q_nb) == 0U)
    {
        return SYSTEM_DEVICE_NOT_READY;
    }
    state = EstimatorNoFusion_IrqLock();
    (void)memset(&s_estimator.output, 0, sizeof(s_estimator.output));
    (void)memset(&s_estimator.initial, 0, sizeof(s_estimator.initial));
    (void)memcpy(s_estimator.output.q_nb, q_nb,
                 sizeof(s_estimator.output.q_nb));
    s_estimator.output.position_update_result =
        NAV_KF_UPDATE_REJECTED_INVALID;
    s_estimator.output.velocity_update_result =
        NAV_KF_UPDATE_REJECTED_INVALID;
    s_estimator.output.baro_update_result = NAV_KF_UPDATE_REJECTED_INVALID;
    s_estimator.initial.valid = 1U;
    s_estimator.initialized = 1U;
    s_estimator.mission_running = 1U;
    s_estimator.output.initialized = 1U;
    s_estimator.output.mission_running = 1U;
    EstimatorNoFusion_IrqUnlock(state);
    EstimatorNoFusion_OutputRefresh();
    return SYSTEM_DEVICE_OK;
}

void EstimatorTask_RollbackMissionStart(void)
{
    EstimatorTask_AbortMission();
}

void EstimatorTask_AbortMission(void)
{
    PlatformCriticalState state = EstimatorNoFusion_IrqLock();

    s_estimator.initialized = 0U;
    s_estimator.mission_running = 0U;
    s_estimator.initial.valid = 0U;
    s_estimator.output.initialized = 0U;
    s_estimator.output.mission_running = 0U;
    EstimatorNoFusion_IrqUnlock(state);
}

uint8_t Estimator_GetInitialStateSnapshot(
    EstimatorInitialStateSnapshot *snapshot)
{
    PlatformCriticalState state;

    if (snapshot == NULL)
    {
        return 0U;
    }
    SILVERSTAR_ASSERT_OBJECT(snapshot, EstimatorInitialStateSnapshot,
                             SILVERSTAR_ASSERT_MODULE_APP);
    state = EstimatorNoFusion_IrqLock();
    *snapshot = s_estimator.initial;
    EstimatorNoFusion_IrqUnlock(state);
    return snapshot->valid;
}

uint8_t Estimator_GetLatestSnapshot(EstimatorOutputSnapshot *snapshot)
{
    PlatformCriticalState state;

    if (snapshot == NULL)
    {
        return 0U;
    }
    SILVERSTAR_ASSERT_OBJECT(snapshot, EstimatorOutputSnapshot,
                             SILVERSTAR_ASSERT_MODULE_APP);
    state = EstimatorNoFusion_IrqLock();
    *snapshot = s_estimator.output;
    EstimatorNoFusion_IrqUnlock(state);
    return snapshot->initialized;
}

SystemDeviceResult EstimatorTask_OriginsReset(void)
{
    return (s_estimator.mission_running == 0U) ?
        SYSTEM_DEVICE_OK : SYSTEM_DEVICE_BAD_STATE;
}

SystemDeviceResult EstimatorTask_GnssAlignmentStatusGet(
    SystemAlignmentGnssStatus *status)
{
    if (status == NULL)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(status, SystemAlignmentGnssStatus,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(status, 0, sizeof(*status));
    status->ready = 1U;
    status->state = SYSTEM_ALIGNMENT_COMPONENT_DISABLED;
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult EstimatorTask_BarometerAlignmentStatusGet(
    SystemAlignmentBarometerStatus *status)
{
    if (status == NULL)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(status, SystemAlignmentBarometerStatus,
                             SILVERSTAR_ASSERT_MODULE_APP);
    (void)memset(status, 0, sizeof(*status));
    status->ready = 1U;
    status->state = SYSTEM_ALIGNMENT_COMPONENT_DISABLED;
    return SYSTEM_DEVICE_OK;
}
