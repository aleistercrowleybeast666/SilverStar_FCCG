#ifndef __HW_H__
#define __HW_H__

#include <stdint.h>
#include "project_resources.h"
#include "platform_gpio.h"
#include "sx1280.h"

#define RADIO_NSS          PROJECT_RESOURCE_RADIO_NSS
#define RADIO_BUSY         PROJECT_RESOURCE_RADIO_BUSY
#define RADIO_RESET        PROJECT_RESOURCE_RADIO_RESET
#define RADIO_DIO1         PROJECT_RESOURCE_RADIO_DIO1

void GpioWrite(PlatformGpioId id, uint32_t value);
uint8_t GpioRead(PlatformGpioId id);
uint8_t GpioWaitLow(PlatformGpioId id, uint32_t timeout_ms);

void SpiIn(const uint8_t *tx_buffer, uint16_t size);
void SpiInOut(const uint8_t *tx_buffer, uint8_t *rx_buffer, uint16_t size);

#endif
