#include "platform_time.h"

#include "platform_critical.h"
#include "silverstar_assert.h"
#include "stm32f4xx_hal.h"

extern TIM_HandleTypeDef htim1;

static uint8_t s_initialized;
static uint32_t s_last_tick_ms;
static uint64_t s_tick_epoch_ms;
static uint64_t s_last_monotonic_us;

PlatformResult PlatformTime_Init(void)
{
    PlatformCriticalState state = PlatformCritical_Enter();

    s_initialized = 0U;
    s_last_tick_ms = 0U;
    s_tick_epoch_ms = 0ULL;
    s_last_monotonic_us = 0ULL;
    PlatformCritical_Exit(state);
    return PLATFORM_OK;
}

uint32_t PlatformTime_Ms(void)
{
    return HAL_GetTick();
}

uint64_t PlatformTime_Us(void)
{
    PlatformCriticalState state;
    uint32_t tick_ms;
    uint32_t counter_us = 0U;
    uint8_t update_pending = 0U;
    uint64_t timestamp_us;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_PLATFORM,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    state = PlatformCritical_Enter();
    tick_ms = HAL_GetTick();
    if (htim1.Instance != NULL)
    {
        counter_us = __HAL_TIM_GET_COUNTER(&htim1);
        if (__HAL_TIM_GET_FLAG(&htim1, TIM_FLAG_UPDATE) != RESET)
        {
            update_pending = 1U;
            counter_us = __HAL_TIM_GET_COUNTER(&htim1);
        }
    }
    if (update_pending != 0U)
    {
        tick_ms++;
    }
    if (s_initialized == 0U)
    {
        s_initialized = 1U;
        s_last_tick_ms = tick_ms;
    }
    else if (tick_ms < s_last_tick_ms)
    {
        s_tick_epoch_ms += (1ULL << 32);
    }
    s_last_tick_ms = tick_ms;
    timestamp_us = ((s_tick_epoch_ms + tick_ms) * 1000ULL) + counter_us;
    if (timestamp_us < s_last_monotonic_us)
    {
        timestamp_us = s_last_monotonic_us;
    }
    SILVERSTAR_ASSERT(timestamp_us >= s_last_monotonic_us,
                      SILVERSTAR_ASSERT_MODULE_PLATFORM,
                      SILVERSTAR_ASSERT_REASON_TIME_INVARIANT);
    s_last_monotonic_us = timestamp_us;
    PlatformCritical_Exit(state);
    return timestamp_us;
}

void PlatformTime_DelayMs(uint32_t delay_ms)
{
    HAL_Delay(delay_ms);
}
