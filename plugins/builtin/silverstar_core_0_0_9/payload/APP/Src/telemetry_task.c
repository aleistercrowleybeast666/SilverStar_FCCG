#include "app_tasks.h"

#include "FreeRTOS.h"
#include "task.h"
#include "diagnostic_log.h"
#include "silverstar_assert.h"
#include "system_time.h"
#include "telemetry_service.h"

void AppTask_Telemetry(void *argument)
{
    static DiagnosticLogPeriodicState telemetry_log_state;
    SystemDeviceResult init_result;

    (void)argument;
    init_result = TelemetryService_Init();
    SILVERSTAR_ASSERT(init_result <= SYSTEM_DEVICE_NOT_PRESENT,
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    SILVERSTAR_ASSERT((init_result != SYSTEM_DEVICE_INVALID_ARGUMENT) &&
                      (init_result != SYSTEM_DEVICE_BAD_STATE),
                      SILVERSTAR_ASSERT_MODULE_APP,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);

    for (;;)
    {
        if ((init_result == SYSTEM_DEVICE_OK) ||
            (init_result == SYSTEM_DEVICE_ALREADY_MATCHED))
        {
            TelemetryService_Process();
        }
        DiagnosticLog_TelemetryProcess(
            &telemetry_log_state, SystemTime_GetMonotonicUs());
        vTaskDelay(pdMS_TO_TICKS(1U));
    }
}
