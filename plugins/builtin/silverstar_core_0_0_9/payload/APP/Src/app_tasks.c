#include "app_tasks.h"


#include "silverstar_assert.h"
#include <stddef.h>
#include <string.h>

#include "FreeRTOS.h"
#include "app_task_config.h"
#include "estimator_bus.h"
#include "imu_sample_bus.h"
#include "logger_bus.h"
#include "platform_memory.h"
#include "system_alignment.h"
#include "system_calibration.h"
#include "system_inertial.h"
#include "task.h"

typedef struct
{
    StaticTask_t control;
    uint32_t stack_words;
    TaskHandle_t handle;
} AppTaskStorage;

static PLATFORM_CPU_FAST_BSS StackType_t
    s_device_stack[APP_TASK_STACK_DEVICE_WORDS];
static PLATFORM_CPU_FAST_BSS StackType_t
    s_ins_stack[APP_TASK_STACK_INS_WORDS];
static PLATFORM_CPU_FAST_BSS StackType_t
    s_estimator_stack[APP_TASK_STACK_ESTIMATOR_WORDS];
static PLATFORM_CPU_FAST_BSS StackType_t
    s_flight_stack[APP_TASK_STACK_FLIGHT_WORDS];
static PLATFORM_CPU_FAST_BSS StackType_t
    s_logger_stack[APP_TASK_STACK_LOGGER_WORDS];
static PLATFORM_CPU_FAST_BSS StackType_t
    s_serial_stack[APP_TASK_STACK_SERIAL_WORDS];
static PLATFORM_CPU_FAST_BSS StackType_t
    s_telemetry_stack[APP_TASK_STACK_TELEMETRY_WORDS];

static AppTaskStorage s_tasks[SYSTEM_TASK_STACK_COUNT] =
{
    [SYSTEM_TASK_STACK_DEVICE] = {
        .stack_words = APP_TASK_STACK_DEVICE_WORDS
    },
    [SYSTEM_TASK_STACK_INS] = {
        .stack_words = APP_TASK_STACK_INS_WORDS
    },
    [SYSTEM_TASK_STACK_ESTIMATOR] = {
        .stack_words = APP_TASK_STACK_ESTIMATOR_WORDS
    },
    [SYSTEM_TASK_STACK_FLIGHT] = {
        .stack_words = APP_TASK_STACK_FLIGHT_WORDS
    },
    [SYSTEM_TASK_STACK_LOGGER] = {
        .stack_words = APP_TASK_STACK_LOGGER_WORDS
    },
    [SYSTEM_TASK_STACK_SERIAL] = {
        .stack_words = APP_TASK_STACK_SERIAL_WORDS
    },
    [SYSTEM_TASK_STACK_RADIO] = {
        .stack_words = APP_TASK_STACK_TELEMETRY_WORDS
    }
};

static TaskHandle_t AppTasks_DeviceCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_DEVICE];

    storage->handle = xTaskCreateStatic(
        AppTask_Device, "Device", APP_TASK_STACK_DEVICE_WORDS, NULL,
        APP_PRIORITY_DEVICE, s_device_stack, &storage->control);
    return storage->handle;
}

static TaskHandle_t AppTasks_InsCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_INS];

    storage->handle = xTaskCreateStatic(
        AppTask_Ins, "INS", APP_TASK_STACK_INS_WORDS, NULL,
        APP_PRIORITY_INS, s_ins_stack, &storage->control);
    return storage->handle;
}

static TaskHandle_t AppTasks_EstimatorCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_ESTIMATOR];

    storage->handle = xTaskCreateStatic(
        AppTask_Estimator, "Estimator", APP_TASK_STACK_ESTIMATOR_WORDS, NULL,
        APP_PRIORITY_ESTIMATOR, s_estimator_stack, &storage->control);
    return storage->handle;
}

static TaskHandle_t AppTasks_FlightCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_FLIGHT];

    storage->handle = xTaskCreateStatic(
        AppTask_Flight, "Flight", APP_TASK_STACK_FLIGHT_WORDS, NULL,
        APP_PRIORITY_FLIGHT, s_flight_stack, &storage->control);
    return storage->handle;
}

static TaskHandle_t AppTasks_LoggerCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_LOGGER];

    storage->handle = xTaskCreateStatic(
        AppTask_Logger, "Logger", APP_TASK_STACK_LOGGER_WORDS, NULL,
        APP_PRIORITY_LOGGER, s_logger_stack, &storage->control);
    return storage->handle;
}

static TaskHandle_t AppTasks_SerialCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_SERIAL];

    storage->handle = xTaskCreateStatic(
        AppTask_Serial, "Serial", APP_TASK_STACK_SERIAL_WORDS, NULL,
        APP_PRIORITY_SERIAL, s_serial_stack, &storage->control);
    return storage->handle;
}

static TaskHandle_t AppTasks_TelemetryCreate(void)
{
    AppTaskStorage *storage = &s_tasks[SYSTEM_TASK_STACK_RADIO];

    storage->handle = xTaskCreateStatic(
        AppTask_Telemetry, "Telemetry", APP_TASK_STACK_TELEMETRY_WORDS, NULL,
        APP_PRIORITY_TELEMETRY, s_telemetry_stack, &storage->control);
    return storage->handle;
}

AppTasksInitResult AppTasks_Init(void)
{
    SILVERSTAR_ASSERT(s_tasks[SYSTEM_TASK_STACK_DEVICE].stack_words ==
                      APP_TASK_STACK_DEVICE_WORDS,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_tasks[SYSTEM_TASK_STACK_RADIO].stack_words ==
                      APP_TASK_STACK_TELEMETRY_WORDS,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SystemCalibration_Init();
    SystemAlignment_Init();
    if ((SystemInertial_Init() != SYSTEM_DEVICE_OK) ||
        (ImuSampleBus_Init() != IMU_SAMPLE_BUS_RESULT_OK) ||
        (EstimatorBus_Init() != ESTIMATOR_BUS_RESULT_OK) ||
        (LoggerBus_Init() != LOGGER_BUS_RESULT_OK))
    {
        return AppTasksInitResult_BusInitFailed;
    }

    if ((AppTasks_DeviceCreate() == NULL) ||
        (AppTasks_InsCreate() == NULL) ||
        (AppTasks_EstimatorCreate() == NULL) ||
        (AppTasks_FlightCreate() == NULL) ||
        (AppTasks_LoggerCreate() == NULL) ||
        (AppTasks_SerialCreate() == NULL) ||
        (AppTasks_TelemetryCreate() == NULL))
    {
        return AppTasksInitResult_TaskCreateFailed;
    }
    return AppTasksInitResult_Ok;
}

SystemDeviceResult SystemTaskStack_SnapshotGet(
    SystemTaskStackSnapshot *snapshot)
{
    uint32_t index;

    if (snapshot == NULL)
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    (void)memset(snapshot, 0, sizeof(*snapshot));
    for (index = 0U; index < (uint32_t)SYSTEM_TASK_STACK_COUNT; index++)
    {
        const AppTaskStorage *storage = &s_tasks[index];

        SILVERSTAR_ASSERT_OBJECT(snapshot, SystemTaskStackSnapshot,
                                 SILVERSTAR_ASSERT_MODULE_APP);
        snapshot->task[index].allocation_words = storage->stack_words;
        if (storage->handle != NULL)
        {
            snapshot->task[index].high_water_mark_words =
                (uint32_t)uxTaskGetStackHighWaterMark(storage->handle);
            snapshot->valid_mask |= (1UL << index);
        }
    }
    return SYSTEM_DEVICE_OK;
}
