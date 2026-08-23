#include "sx1281_bus.h"

#include <stddef.h>

#include "project_resources.h"
#include "platform_gpio.h"
#include "platform_spi.h"
#include "platform_time.h"
#include "silverstar_assert.h"
#include "sx1281_config.h"

#define SX1281_BUSY_POLL_GUARD 1000000UL

static Sx1281BusStatus s_bus_status;

void Sx1281Bus_Init(void)
{
    s_bus_status.last_result = SX1281_BUS_OK;
    s_bus_status.spi_error_count = 0U;
    s_bus_status.spi_timeout_count = 0U;
    s_bus_status.busy_timeout_count = 0U;
}

void GpioWrite(PlatformGpioId id, uint32_t value)
{
    (void)PlatformGpio_Write(id, (uint8_t)(value != 0U));
}

uint8_t GpioRead(PlatformGpioId id)
{
    uint8_t value = 0U;

    (void)PlatformGpio_Read(id, &value);
    return value;
}

void SpiIn(const uint8_t *tx_buffer, uint16_t size)
{
    PlatformResult result = PlatformSpi_Write(PROJECT_RESOURCE_RADIO_SPI, tx_buffer,
                                               size, LORA_SPI_TIMEOUT_MS);

    if (result == PLATFORM_TIMEOUT)
    {
        s_bus_status.last_result = SX1281_BUS_SPI_TIMEOUT;
        s_bus_status.spi_timeout_count++;
    }
    else if (result != PLATFORM_OK)
    {
        s_bus_status.last_result = SX1281_BUS_SPI_ERROR;
        s_bus_status.spi_error_count++;
    }
    else
    {
        s_bus_status.last_result = SX1281_BUS_OK;
    }
}

void SpiInOut(const uint8_t *tx_buffer, uint8_t *rx_buffer, uint16_t size)
{
    PlatformResult result = PlatformSpi_Transfer(PROJECT_RESOURCE_RADIO_SPI, tx_buffer,
                                                  rx_buffer, size,
                                                  LORA_SPI_TIMEOUT_MS);

    if (result == PLATFORM_TIMEOUT)
    {
        s_bus_status.last_result = SX1281_BUS_SPI_TIMEOUT;
        s_bus_status.spi_timeout_count++;
    }
    else if (result != PLATFORM_OK)
    {
        s_bus_status.last_result = SX1281_BUS_SPI_ERROR;
        s_bus_status.spi_error_count++;
    }
    else
    {
        s_bus_status.last_result = SX1281_BUS_OK;
    }
}

uint8_t GpioWaitLow(PlatformGpioId id, uint32_t timeout_ms)
{
    uint32_t start_ms = PlatformTime_Ms();
    uint32_t guard;

    SILVERSTAR_ASSERT(id < PLATFORM_GPIO_COUNT,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_ENUM_RANGE);
    SILVERSTAR_ASSERT(timeout_ms > 0U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_TIME_INVARIANT);
    for (guard = 0U; guard < SX1281_BUSY_POLL_GUARD; guard++)
    {
        if (GpioRead(id) == 0U)
        {
            s_bus_status.last_result = SX1281_BUS_OK;
            return 1U;
        }
        if ((PlatformTime_Ms() - start_ms) >= timeout_ms)
        {
            s_bus_status.last_result = SX1281_BUS_BUSY_TIMEOUT;
            s_bus_status.busy_timeout_count++;
            return 0U;
        }
    }
    s_bus_status.last_result = SX1281_BUS_BUSY_TIMEOUT;
    s_bus_status.busy_timeout_count++;
    return 0U;
}

void Sx1281Bus_StatusGet(Sx1281BusStatus *status)
{
    if (status != NULL)
    {
        *status = s_bus_status;
    }
}
