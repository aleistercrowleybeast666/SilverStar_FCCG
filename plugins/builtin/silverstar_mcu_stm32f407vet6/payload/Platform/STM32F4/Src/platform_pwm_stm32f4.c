#include "platform_pwm.h"

#include <stddef.h>

#include "platform_stm32f4_resources.h"
#include "stm32f4xx_hal.h"

typedef struct
{
    TIM_HandleTypeDef *handle;
    uint32_t channel;
    uint32_t safe_inactive_compare;
    uint32_t frequency_hz;
    uint16_t resolution_bits;
    uint16_t duty_permille;
    uint8_t active_high;
    uint8_t started;
    uint8_t loaded;
} PlatformPwmContext;

static PlatformPwmContext s_pwm[PLATFORM_PWM_COUNT];

static uint8_t PlatformPwm_ContextLoad(
    PlatformPwmId id, PlatformPwmContext *context)
{
    PlatformStm32f4PwmResource resource;

    if (PlatformStm32f4Resource_PwmGet(id, &resource) == 0U)
    {
        return 0U;
    }
    context->handle = (TIM_HandleTypeDef *)resource.handle;
    context->channel = resource.channel;
    context->safe_inactive_compare = resource.safe_inactive_compare;
    context->frequency_hz = resource.frequency_hz;
    context->resolution_bits = resource.resolution_bits;
    context->active_high = resource.active_high;
    context->loaded = 1U;
    return (context->handle != NULL) ? 1U : 0U;
}

static PlatformPwmContext *PlatformPwm_ContextGet(PlatformPwmId id)
{
    PlatformPwmContext *context;

    if ((uint32_t)id >= (uint32_t)PLATFORM_PWM_COUNT) { return NULL; }
    context = &s_pwm[id];
    if ((context->loaded == 0U) &&
        (PlatformPwm_ContextLoad(id, context) == 0U)) { return NULL; }
    return (context->handle != NULL) ? context : NULL;
}

static PlatformResult PlatformPwm_ResultMap(HAL_StatusTypeDef result)
{
    if (result == HAL_OK) { return PLATFORM_OK; }
    if (result == HAL_TIMEOUT) { return PLATFORM_TIMEOUT; }
    if (result == HAL_BUSY) { return PLATFORM_BUSY; }
    return PLATFORM_IO_ERROR;
}

PlatformResult PlatformPwm_Start(PlatformPwmId id)
{
    PlatformPwmContext *context = PlatformPwm_ContextGet(id);
    HAL_StatusTypeDef result;

    if (context == NULL) { return PLATFORM_INVALID_ARGUMENT; }
    result = HAL_TIM_PWM_Start(context->handle, context->channel);
    if (result == HAL_OK) { context->started = 1U; }
    return PlatformPwm_ResultMap(result);
}

PlatformResult PlatformPwm_Stop(PlatformPwmId id)
{
    PlatformPwmContext *context = PlatformPwm_ContextGet(id);
    HAL_StatusTypeDef result;

    if (context == NULL) { return PLATFORM_INVALID_ARGUMENT; }
    result = HAL_TIM_PWM_Stop(context->handle, context->channel);
    if (result == HAL_OK) { context->started = 0U; }
    return PlatformPwm_ResultMap(result);
}

PlatformResult PlatformPwm_DutyPermilleSet(
    PlatformPwmId id,
    uint16_t duty_permille)
{
    PlatformPwmContext *context = PlatformPwm_ContextGet(id);
    uint64_t timer_counts;
    uint32_t compare;

    if ((context == NULL) ||
        (duty_permille > PLATFORM_PWM_DUTY_PERMILLE_MAX))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    timer_counts = (uint64_t)context->handle->Init.Period + 1ULL;
    compare = (uint32_t)((timer_counts * duty_permille) /
                         PLATFORM_PWM_DUTY_PERMILLE_MAX);
    __HAL_TIM_SET_COMPARE(context->handle, context->channel, compare);
    context->duty_permille = duty_permille;
    return PLATFORM_OK;
}

PlatformResult PlatformPwm_SafeInactiveSet(PlatformPwmId id)
{
    PlatformPwmContext *context = PlatformPwm_ContextGet(id);

    if (context == NULL) { return PLATFORM_INVALID_ARGUMENT; }
    __HAL_TIM_SET_COMPARE(context->handle, context->channel,
                          context->safe_inactive_compare);
    context->duty_permille = 0U;
    return PlatformPwm_Stop(id);
}

PlatformResult PlatformPwm_DiagnosticsGet(
    PlatformPwmId id,
    PlatformPwmDiagnostics *diagnostics)
{
    PlatformPwmContext *context = PlatformPwm_ContextGet(id);

    if ((context == NULL) || (diagnostics == NULL))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    diagnostics->frequency_hz = context->frequency_hz;
    diagnostics->resolution_bits = context->resolution_bits;
    diagnostics->active_high = context->active_high;
    diagnostics->started = context->started;
    diagnostics->duty_permille = context->duty_permille;
    return PLATFORM_OK;
}
