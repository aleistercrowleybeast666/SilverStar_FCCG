#ifndef __PLATFORM_I2C_H
#define __PLATFORM_I2C_H

#include <stdint.h>

#include "platform_types.h"

typedef enum
{
    PLATFORM_I2C_1 = 0,
    PLATFORM_I2C_2,
    PLATFORM_I2C_3,
    PLATFORM_I2C_COUNT
} PlatformI2cId;

PlatformResult PlatformI2c_Write(PlatformI2cId id,
                                 uint16_t address_7bit,
                                 const uint8_t *data,
                                 uint16_t length,
                                 uint32_t timeout_ms);
PlatformResult PlatformI2c_Read(PlatformI2cId id,
                                uint16_t address_7bit,
                                uint8_t *data,
                                uint16_t length,
                                uint32_t timeout_ms);
PlatformResult PlatformI2c_MemoryWrite(PlatformI2cId id,
                                       uint16_t address_7bit,
                                       uint16_t memory_address,
                                       uint16_t memory_address_size,
                                       const uint8_t *data,
                                       uint16_t length,
                                       uint32_t timeout_ms);
PlatformResult PlatformI2c_MemoryRead(PlatformI2cId id,
                                      uint16_t address_7bit,
                                      uint16_t memory_address,
                                      uint16_t memory_address_size,
                                      uint8_t *data,
                                      uint16_t length,
                                      uint32_t timeout_ms);
PlatformResult PlatformI2c_WriteRead(PlatformI2cId id,
                                     uint16_t address_7bit,
                                     const uint8_t *tx_data,
                                     uint16_t tx_length,
                                     uint8_t *rx_data,
                                     uint16_t rx_length,
                                     uint32_t timeout_ms);

#endif /* __PLATFORM_I2C_H */
