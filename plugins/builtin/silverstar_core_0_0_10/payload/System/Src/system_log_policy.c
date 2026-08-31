#include "system_log_policy.h"

#include <stddef.h>
#include <string.h>

#include "platform_critical.h"
#include "project_log_config.h"
#include "silverstar_assert.h"

typedef struct
{
    SystemLogStreamConfig config;
    uint32_t emission_count;
} SystemLogStreamRuntime;

static SystemLogStreamRuntime s_streams[SSLOG_RECORD_COUNT];
static uint8_t s_initialized;
static uint8_t s_frozen;

static int16_t SystemLogPolicy_StreamIndexFind(
    FlightLogRecordType record_type)
{
    uint16_t index;

    for (index = 0U; index < SSLOG_RECORD_COUNT; index++)
    {
        if (s_streams[index].config.record_type == record_type)
        {
            return (int16_t)index;
        }
    }
    return -1;
}

void SystemLogPolicy_Init(void)
{
    const SystemLogStreamConfig *project_config;
    PlatformCriticalState state;
    uint16_t index;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_SYSTEM,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_frozen <= 1U,
                      SILVERSTAR_ASSERT_MODULE_SYSTEM,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    state = PlatformCritical_Enter();
    if (s_initialized != 0U)
    {
        PlatformCritical_Exit(state);
        return;
    }
    (void)memset(s_streams, 0, sizeof(s_streams));
    for (index = 0U; index < SSLOG_RECORD_COUNT; index++)
    {
        project_config = ProjectLogConfig_StreamByIndexGet(index);
        if (project_config != NULL)
        {
            s_streams[index].config = *project_config;
        }
    }
    s_frozen = 0U;
    s_initialized = 1U;
    PlatformCritical_Exit(state);
}

uint16_t SystemLogPolicy_StreamCountGet(void)
{
    SystemLogPolicy_Init();
    return SSLOG_RECORD_COUNT;
}

SystemDeviceResult SystemLogPolicy_StreamByIndexGet(
    uint16_t index, SystemLogStreamConfig *config)
{
    PlatformCriticalState state;

    if ((index >= SSLOG_RECORD_COUNT) || (config == NULL))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(config, SystemLogStreamConfig,
                             SILVERSTAR_ASSERT_MODULE_SYSTEM);
    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    *config = s_streams[index].config;
    PlatformCritical_Exit(state);
    return SYSTEM_DEVICE_OK;
}

SystemDeviceResult SystemLogPolicy_StreamGet(
    FlightLogRecordType record_type, SystemLogStreamConfig *config)
{
    PlatformCriticalState state;
    int16_t index;

    if (config == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    index = SystemLogPolicy_StreamIndexFind(record_type);
    if (index >= 0)
    {
        *config = s_streams[(uint16_t)index].config;
    }
    PlatformCritical_Exit(state);
    return (index >= 0) ? SYSTEM_DEVICE_OK :
                          SYSTEM_DEVICE_INVALID_ARGUMENT;
}

SystemDeviceResult SystemLogPolicy_StreamConfigure(
    const SystemLogStreamConfig *config)
{
    PlatformCriticalState state;
    uint8_t frozen;
    int16_t index;

    if ((config == NULL) || (config->decimation == 0U) ||
        (config->enabled > 1U) ||
        (config->policy > SSLOG_STREAM_POLICY_ONE_SHOT))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(config, SystemLogStreamConfig,
                             SILVERSTAR_ASSERT_MODULE_SYSTEM);
    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    index = SystemLogPolicy_StreamIndexFind(config->record_type);
    frozen = s_frozen;
    if ((index >= 0) && (frozen == 0U))
    {
        s_streams[(uint16_t)index].config = *config;
        s_streams[(uint16_t)index].emission_count = 0U;
    }
    PlatformCritical_Exit(state);
    if (index < 0) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    return (frozen == 0U) ? SYSTEM_DEVICE_OK : SYSTEM_DEVICE_BAD_STATE;
}

uint8_t SystemLogPolicy_IsEnabled(FlightLogRecordType record_type)
{
    SystemLogStreamConfig config;

    return (uint8_t)((SystemLogPolicy_StreamGet(record_type, &config) ==
                      SYSTEM_DEVICE_OK) && (config.enabled != 0U));
}

uint8_t SystemLogPolicy_ShouldEmit(FlightLogRecordType record_type)
{
    PlatformCriticalState state;
    uint8_t emit = 0U;
    int16_t index;

    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    index = SystemLogPolicy_StreamIndexFind(record_type);
    if ((index >= 0) &&
        (s_streams[(uint16_t)index].config.enabled != 0U))
    {
        const uint16_t decimation =
            s_streams[(uint16_t)index].config.decimation;
        emit = (uint8_t)((s_streams[(uint16_t)index].emission_count %
                            decimation) == 0U);
        s_streams[(uint16_t)index].emission_count++;
    }
    PlatformCritical_Exit(state);
    return emit;
}

void SystemLogPolicy_EmissionReset(void)
{
    PlatformCriticalState state;
    uint16_t index;

    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    for (index = 0U; index < SSLOG_RECORD_COUNT; index++)
    {
        s_streams[index].emission_count = 0U;
    }
    PlatformCritical_Exit(state);
}

uint8_t SystemLogPolicy_IsFrozen(void)
{
    uint8_t frozen;
    PlatformCriticalState state;

    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    frozen = s_frozen;
    PlatformCritical_Exit(state);
    return frozen;
}

void SystemLogPolicy_Freeze(void)
{
    PlatformCriticalState state;

    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    s_frozen = 1U;
    PlatformCritical_Exit(state);
}

void SystemLogPolicy_UnfreezeForRollback(void)
{
    PlatformCriticalState state;

    SystemLogPolicy_Init();
    state = PlatformCritical_Enter();
    s_frozen = 0U;
    PlatformCritical_Exit(state);
}
