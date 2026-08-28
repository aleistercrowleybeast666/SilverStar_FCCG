#include "platform_i2c.h"

#include <stddef.h>

#include "platform_stm32f4_resources.h"
#include "stm32f4xx_hal.h"

static I2C_HandleTypeDef *PlatformI2c_HandleGet(PlatformI2cId id)
{
    return (I2C_HandleTypeDef *)PlatformStm32f4Resource_I2cHandleGet(id);
}

static uint8_t *PlatformI2c_HalBufferGet(const uint8_t *data)
{
    return (uint8_t *)(uintptr_t)data;
}

static PlatformResult PlatformI2c_ResultMap(HAL_StatusTypeDef result)
{
    if (result == HAL_OK) { return PLATFORM_OK; }
    if (result == HAL_TIMEOUT) { return PLATFORM_TIMEOUT; }
    if (result == HAL_BUSY) { return PLATFORM_BUSY; }
    return PLATFORM_IO_ERROR;
}

static uint8_t PlatformI2c_ArgumentsValid(uint16_t address_7bit,
                                          const void *data,
                                          uint16_t length,
                                          uint32_t timeout_ms)
{
    return ((address_7bit >= 0x08U) && (address_7bit <= 0x77U) &&
            (data != NULL) &&
            (length > 0U) && (timeout_ms > 0U)) ? 1U : 0U;
}

static uint16_t PlatformI2c_HalAddressGet(uint16_t address_7bit)
{
    return (uint16_t)(address_7bit << 1U);
}

static uint8_t PlatformI2c_MemoryAddressSizeValid(uint16_t size)
{
    return ((size == I2C_MEMADD_SIZE_8BIT) ||
            (size == I2C_MEMADD_SIZE_16BIT)) ? 1U : 0U;
}

static PlatformResult PlatformI2c_WriteReadValidate(
    I2C_HandleTypeDef *handle, uint16_t address_7bit,
    const uint8_t *tx_data, uint16_t tx_length,
    const uint8_t *rx_data, uint16_t rx_length, uint32_t timeout_ms)
{
    if ((handle == NULL) || (address_7bit < 0x08U) ||
        (address_7bit > 0x77U) || (tx_data == NULL) ||
        (rx_data == NULL) || (tx_length == 0U) ||
        (rx_length == 0U) || (timeout_ms == 0U))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    if ((tx_length != 1U) && (tx_length != 2U))
    {
        return PLATFORM_UNSUPPORTED;
    }
    return PLATFORM_OK;
}

static uint16_t PlatformI2c_MemoryAddressGet(
    const uint8_t *tx_data, uint16_t tx_length)
{
    if (tx_length == 1U) { return tx_data[0]; }
    return (uint16_t)(((uint16_t)tx_data[0] << 8U) |
                      (uint16_t)tx_data[1]);
}

PlatformResult PlatformI2c_Write(PlatformI2cId id,
                                 uint16_t address_7bit,
                                 const uint8_t *data,
                                 uint16_t length,
                                 uint32_t timeout_ms)
{
    I2C_HandleTypeDef *handle = PlatformI2c_HandleGet(id);

    if ((handle == NULL) ||
        (PlatformI2c_ArgumentsValid(address_7bit, data, length,
                                    timeout_ms) == 0U))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    return PlatformI2c_ResultMap(HAL_I2C_Master_Transmit(
        handle, PlatformI2c_HalAddressGet(address_7bit),
        PlatformI2c_HalBufferGet(data), length, timeout_ms));
}

PlatformResult PlatformI2c_Read(PlatformI2cId id,
                                uint16_t address_7bit,
                                uint8_t *data,
                                uint16_t length,
                                uint32_t timeout_ms)
{
    I2C_HandleTypeDef *handle = PlatformI2c_HandleGet(id);

    if ((handle == NULL) ||
        (PlatformI2c_ArgumentsValid(address_7bit, data, length,
                                    timeout_ms) == 0U))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    return PlatformI2c_ResultMap(HAL_I2C_Master_Receive(
        handle, PlatformI2c_HalAddressGet(address_7bit), data, length,
        timeout_ms));
}

PlatformResult PlatformI2c_MemoryWrite(
    PlatformI2cId id, uint16_t address_7bit,
    uint16_t memory_address, uint16_t memory_address_size,
    const uint8_t *data, uint16_t length, uint32_t timeout_ms)
{
    I2C_HandleTypeDef *handle = PlatformI2c_HandleGet(id);

    if ((handle == NULL) ||
        (PlatformI2c_MemoryAddressSizeValid(memory_address_size) == 0U) ||
        (PlatformI2c_ArgumentsValid(address_7bit, data, length,
                                    timeout_ms) == 0U))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    return PlatformI2c_ResultMap(HAL_I2C_Mem_Write(
        handle, PlatformI2c_HalAddressGet(address_7bit), memory_address,
        memory_address_size, PlatformI2c_HalBufferGet(data), length,
        timeout_ms));
}

PlatformResult PlatformI2c_MemoryRead(PlatformI2cId id,
                                      uint16_t address_7bit,
                                      uint16_t memory_address,
                                      uint16_t memory_address_size,
                                      uint8_t *data,
                                      uint16_t length,
                                      uint32_t timeout_ms)
{
    I2C_HandleTypeDef *handle = PlatformI2c_HandleGet(id);

    if ((handle == NULL) ||
        (PlatformI2c_MemoryAddressSizeValid(memory_address_size) == 0U) ||
        (PlatformI2c_ArgumentsValid(address_7bit, data, length,
                                    timeout_ms) == 0U))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    return PlatformI2c_ResultMap(HAL_I2C_Mem_Read(
        handle, PlatformI2c_HalAddressGet(address_7bit), memory_address,
        memory_address_size, data, length, timeout_ms));
}

PlatformResult PlatformI2c_WriteRead(
    PlatformI2cId id, uint16_t address_7bit,
    const uint8_t *tx_data, uint16_t tx_length,
    uint8_t *rx_data, uint16_t rx_length, uint32_t timeout_ms)
{
    I2C_HandleTypeDef *handle = PlatformI2c_HandleGet(id);
    uint16_t memory_address;
    uint16_t memory_address_size;
    PlatformResult validation;

    validation = PlatformI2c_WriteReadValidate(
        handle, address_7bit, tx_data, tx_length,
        rx_data, rx_length, timeout_ms);
    if (validation != PLATFORM_OK) { return validation; }
    memory_address = PlatformI2c_MemoryAddressGet(tx_data, tx_length);
    memory_address_size = (tx_length == 1U) ?
        I2C_MEMADD_SIZE_8BIT : I2C_MEMADD_SIZE_16BIT;
    return PlatformI2c_MemoryRead(
        id, address_7bit, memory_address, memory_address_size,
        rx_data, rx_length, timeout_ms);
}
