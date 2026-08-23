#ifndef __PLATFORM_STM32F4_RESOURCES_H
#define __PLATFORM_STM32F4_RESOURCES_H

#include <stdint.h>

#include "platform_adc.h"
#include "platform_gpio.h"
#include "platform_spi.h"
#include "platform_uart.h"

typedef struct
{
    void *port;
    uint16_t pin;
    uint8_t irq_enabled;
} PlatformStm32f4GpioResource;

void *PlatformStm32f4Resource_UartHandleGet(PlatformUartId id);
void *PlatformStm32f4Resource_SpiHandleGet(PlatformSpiId id);
void *PlatformStm32f4Resource_AdcHandleGet(PlatformAdcId id);
uint8_t PlatformStm32f4Resource_GpioGet(
    PlatformGpioId id,
    PlatformStm32f4GpioResource *resource);

#endif /* __PLATFORM_STM32F4_RESOURCES_H */
