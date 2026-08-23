#include "app_tasks.h"

#include "FreeRTOS.h"
#include "task.h"
#include "telemetry_service.h"

void AppTask_Telemetry(void *argument)
{
    SystemDeviceResult init_result;

    (void)argument;
    init_result = TelemetryService_Init();

    for (;;)
    {
        if ((init_result == SYSTEM_DEVICE_OK) ||
            (init_result == SYSTEM_DEVICE_ALREADY_MATCHED))
        {
            TelemetryService_Process();
        }
        vTaskDelay(pdMS_TO_TICKS(1U));
    }
}
