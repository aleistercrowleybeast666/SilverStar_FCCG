#ifndef __LOGGER_TASK_H
#define __LOGGER_TASK_H
#include <stdint.h>
#include "system_device_types.h"

typedef struct
{
    uint64_t max_iteration_us;
    uint32_t serialized_count;
    uint8_t io_fault;
} LoggerTaskDiagnostics;

SystemDeviceResult LoggerTask_DiagnosticsGet(LoggerTaskDiagnostics *diagnostics);
#endif /* __LOGGER_TASK_H */
