#include "platform_i2c.h"

PlatformResult PlatformI2c_Write(PlatformI2cId id,
                                 uint16_t address,
                                 const uint8_t *data,
                                 uint16_t length,
                                 uint32_t timeout_ms)
{
    (void)id;
    (void)address;
    (void)data;
    (void)length;
    (void)timeout_ms;
    return PLATFORM_UNSUPPORTED;
}

PlatformResult PlatformI2c_Read(PlatformI2cId id,
                                uint16_t address,
                                uint8_t *data,
                                uint16_t length,
                                uint32_t timeout_ms)
{
    (void)id;
    (void)address;
    (void)data;
    (void)length;
    (void)timeout_ms;
    return PLATFORM_UNSUPPORTED;
}

PlatformResult PlatformI2c_WriteRead(PlatformI2cId id,
                                     uint16_t address,
                                     const uint8_t *tx_data,
                                     uint16_t tx_length,
                                     uint8_t *rx_data,
                                     uint16_t rx_length,
                                     uint32_t timeout_ms)
{
    (void)id;
    (void)address;
    (void)tx_data;
    (void)tx_length;
    (void)rx_data;
    (void)rx_length;
    (void)timeout_ms;
    return PLATFORM_UNSUPPORTED;
}
