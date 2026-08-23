#ifndef __PLATFORM_GPIO_H
#define __PLATFORM_GPIO_H

#include <stdint.h>

#include "platform_types.h"

typedef enum
{
    PLATFORM_GPIO_0 = 0,
    PLATFORM_GPIO_1,
    PLATFORM_GPIO_2,
    PLATFORM_GPIO_3,
    PLATFORM_GPIO_4,
    PLATFORM_GPIO_5,
    PLATFORM_GPIO_6,
    PLATFORM_GPIO_7,
    PLATFORM_GPIO_8,
    PLATFORM_GPIO_COUNT
} PlatformGpioId;

PlatformResult PlatformGpio_Write(PlatformGpioId id, uint8_t logical_high);
PlatformResult PlatformGpio_Read(PlatformGpioId id, uint8_t *logical_high);
uint8_t PlatformGpio_IrqConsume(PlatformGpioId id);

#endif /* __PLATFORM_GPIO_H */
