/*
  ______                              _
 / _____)             _              | |
( (____  _____ ____ _| |_ _____  ____| |__
 \____ \| ___ |    (_   _) ___ |/ ___)  _ \
 _____) ) ____| | | || |_| ____( (___| | | |
(______/|_____)_|_|_| \__)_____)\____)_| |_|
    (C)2016 Semtech

Description: Handling of the node configuration protocol

License: Revised BSD License, see LICENSE.TXT file include in the project

Maintainer: Miguel Luis, Matthieu Verdy and Benjamin Boulet
*/
#include "hw.h"
#include "sx1280-hal.h"
#include "platform_critical.h"
#include "platform_time.h"
#include "sx1281_config.h"
#include <string.h>

/*!
 * \brief Define the size of tx and rx hal buffers
 *
 * The Tx and Rx hal buffers are used for SPI communication to
 * store data to be sent/receive to/from the chip.
 *
 * \warning The application must ensure the maximal useful size to be much lower
 *          than the MAX_HAL_BUFFER_SIZE
 */
#define MAX_HAL_BUFFER_SIZE   0xFFF

static uint8_t halTxBuffer[MAX_HAL_BUFFER_SIZE] = {0x00};
static uint8_t halRxBuffer[MAX_HAL_BUFFER_SIZE] = {0x00};

/*!
 * \brief Used to block execution waiting for low state on radio busy pin.
 *        Essentially used in SPI communications
 */
void SX1280HalWaitOnBusy( void )
{
    ( void )GpioWaitLow( RADIO_BUSY, LORA_BUSY_TIMEOUT_MS );
}

void SX1280HalInit( void )
{
    SX1280HalReset( );
}

void SX1280HalReset( void )
{
    PlatformTime_DelayMs( 20U );
    GpioWrite( RADIO_RESET, 0U );
    PlatformTime_DelayMs( 50U );
    GpioWrite( RADIO_RESET, 1U );
    PlatformTime_DelayMs( 20U );
}

void SX1280HalClearInstructionRam( void )
{
    uint16_t remain = IRAM_SIZE;
    uint16_t addr = IRAM_START_ADDRESS;
    uint16_t chunk;
    uint16_t halSize;

    while( remain > 0 )
    {
        /* 预留前3字节给命令和地址 */
        chunk = remain;
        if( chunk > ( MAX_HAL_BUFFER_SIZE - 3U ) )
        {
            chunk = ( MAX_HAL_BUFFER_SIZE - 3U );
        }

        halTxBuffer[0] = RADIO_WRITE_REGISTER;
        halTxBuffer[1] = ( addr >> 8 ) & 0x00FF;
        halTxBuffer[2] = addr & 0x00FF;

        memset( &halTxBuffer[3], 0x00, chunk );
        halSize = ( uint16_t )( chunk + 3U );

        SX1280HalWaitOnBusy( );

        GpioWrite( RADIO_NSS, 0U );
        SpiIn( halTxBuffer, halSize );
        GpioWrite( RADIO_NSS, 1U );

        SX1280HalWaitOnBusy( );

        addr = ( uint16_t )( addr + chunk );
        remain = ( uint16_t )( remain - chunk );
    }
}

void SX1280HalWakeup( void )
{
    PlatformCriticalState critical_state = PlatformCritical_Enter( );

    GpioWrite( RADIO_NSS, 0U );

    uint16_t halSize = 2;
    halTxBuffer[0] = RADIO_GET_STATUS;
    halTxBuffer[1] = 0x00;
    SpiIn( halTxBuffer, halSize );

    GpioWrite( RADIO_NSS, 1U );

    // Wait for chip to be ready.
    SX1280HalWaitOnBusy( );

    PlatformCritical_Exit( critical_state );
}

void SX1280HalWriteCommand( RadioCommands_t command, uint8_t *buffer, uint16_t size )
{
    uint16_t halSize  = size + 1;
    SX1280HalWaitOnBusy( );

    GpioWrite( RADIO_NSS, 0U );

    halTxBuffer[0] = command;
    memcpy( halTxBuffer + 1, ( uint8_t * )buffer, size * sizeof( uint8_t ) );

    SpiIn( halTxBuffer, halSize );

    GpioWrite( RADIO_NSS, 1U );

    if( command != RADIO_SET_SLEEP )
    {
        SX1280HalWaitOnBusy( );
    }
}

void SX1280HalReadCommand( RadioCommands_t command, uint8_t *buffer, uint16_t size )
{
    uint16_t halSize = 2 + size;
    halTxBuffer[0] = command;
    halTxBuffer[1] = 0x00;
    for( uint16_t index = 0; index < size; index++ )
    {
        halTxBuffer[2+index] = 0x00;
    }

    SX1280HalWaitOnBusy( );

    GpioWrite( RADIO_NSS, 0U );

    SpiInOut( halTxBuffer, halRxBuffer, halSize );

    memcpy( buffer, halRxBuffer + 2, size );

    GpioWrite( RADIO_NSS, 1U );

    SX1280HalWaitOnBusy( );
}

void SX1280HalWriteRegisters( uint16_t address, uint8_t *buffer, uint16_t size )
{
    uint16_t halSize = size + 3;
    halTxBuffer[0] = RADIO_WRITE_REGISTER;
    halTxBuffer[1] = ( address & 0xFF00 ) >> 8;
    halTxBuffer[2] = address & 0x00FF;
    memcpy( halTxBuffer + 3, buffer, size );

    SX1280HalWaitOnBusy( );

    GpioWrite( RADIO_NSS, 0U );

    SpiIn( halTxBuffer, halSize );

    GpioWrite( RADIO_NSS, 1U );

    SX1280HalWaitOnBusy( );
}

void SX1280HalWriteRegister( uint16_t address, uint8_t value )
{
    SX1280HalWriteRegisters( address, &value, 1 );
}

void SX1280HalReadRegisters( uint16_t address, uint8_t *buffer, uint16_t size )
{
    uint16_t halSize = 4 + size;
    halTxBuffer[0] = RADIO_READ_REGISTER;
    halTxBuffer[1] = ( address & 0xFF00 ) >> 8;
    halTxBuffer[2] = address & 0x00FF;
    halTxBuffer[3] = 0x00;
    for( uint16_t index = 0; index < size; index++ )
    {
        halTxBuffer[4+index] = 0x00;
    }

    SX1280HalWaitOnBusy( );

    GpioWrite( RADIO_NSS, 0U );

    SpiInOut( halTxBuffer, halRxBuffer, halSize );

    memcpy( buffer, halRxBuffer + 4, size );

    GpioWrite( RADIO_NSS, 1U );

    SX1280HalWaitOnBusy( );
}

uint8_t SX1280HalReadRegister( uint16_t address )
{
    uint8_t data;

    SX1280HalReadRegisters( address, &data, 1 );

    return data;
}

void SX1280HalWriteBuffer( uint8_t offset, uint8_t *buffer, uint8_t size )
{
    uint16_t halSize = size + 2;
    halTxBuffer[0] = RADIO_WRITE_BUFFER;
    halTxBuffer[1] = offset;
    memcpy( halTxBuffer + 2, buffer, size );

    SX1280HalWaitOnBusy( );

    GpioWrite( RADIO_NSS, 0U );

    SpiIn( halTxBuffer, halSize );

    GpioWrite( RADIO_NSS, 1U );

    SX1280HalWaitOnBusy( );
}

void SX1280HalReadBuffer( uint8_t offset, uint8_t *buffer, uint8_t size )
{
    uint16_t halSize = size + 3;
    halTxBuffer[0] = RADIO_READ_BUFFER;
    halTxBuffer[1] = offset;
    halTxBuffer[2] = 0x00;
    for( uint16_t index = 0; index < size; index++ )
    {
        halTxBuffer[3+index] = 0x00;
    }

    SX1280HalWaitOnBusy( );

    GpioWrite( RADIO_NSS, 0U );

    SpiInOut( halTxBuffer, halRxBuffer, halSize );

    memcpy( buffer, halRxBuffer + 3, size );

    GpioWrite( RADIO_NSS, 1U );

    SX1280HalWaitOnBusy( );
}

uint8_t SX1280HalGetDioStatus( void )
{
	uint8_t Status = GpioRead( RADIO_BUSY );
	
#if( RADIO_DIO1_ENABLE )
	Status |= (GpioRead( RADIO_DIO1 ) << 1);
#endif
#if( RADIO_DIO2_ENABLE )
	Status |= (GpioRead( RADIO_DIO2_GPIO_Port, RADIO_DIO2_Pin ) << 2);
#endif
#if( RADIO_DIO3_ENABLE )
	Status |= (GpioRead( RADIO_DIO3_GPIO_Port, RADIO_DIO3_Pin ) << 3);
#endif
#if( !RADIO_DIO1_ENABLE && !RADIO_DIO2_ENABLE && !RADIO_DIO3_ENABLE )
#error "Please define a DIO" 
#endif
	
	return Status;
}
