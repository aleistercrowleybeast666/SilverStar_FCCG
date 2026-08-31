#include <stdint.h>
#include <string.h>

#include "project_resources.h"
#include "platform_critical.h"
#include "platform_gpio.h"
#include "platform_time.h"
#include "sx1280.h"
#include "sx1281_bus.h"
#include "sx1281_device.h"
#include "test_common.h"

static uint32_t s_tick_ms;
static uint32_t s_irq_get_count;
static uint32_t s_packet_type_get_count;
static uint32_t s_rssi_get_count;
static uint32_t s_irq_clear_count;
static uint32_t s_set_rx_count;
static uint16_t s_raw_irq;
static uint8_t s_dio1_pending;

void SX1280Init(void) { }

RadioStatus_t SX1280GetStatus(void)
{
    RadioStatus_t status;

    status.Value = 0x20U;
    return status;
}

uint16_t SX1280GetFirmwareVersion(void) { return 0x1234U; }
void SX1280SetRegulatorMode(RadioRegulatorModes_t mode) { (void)mode; }
void SX1280SetStandby(RadioStandbyModes_t mode) { (void)mode; }
void SX1280SetPacketType(RadioPacketTypes_t type) { (void)type; }
void SX1280SetModulationParams(ModulationParams_t *params) { (void)params; }
void SX1280SetPacketParams(PacketParams_t *params) { (void)params; }
void SX1280SetRfFrequency(uint32_t frequency) { (void)frequency; }
void SX1280SetBufferBaseAddresses(uint8_t tx, uint8_t rx)
{
    (void)tx;
    (void)rx;
}
void SX1280SetTxParams(int8_t power, RadioRampTimes_t ramp)
{
    (void)power;
    (void)ramp;
}
void SX1280SetDioIrqParams(uint16_t irq, uint16_t dio1,
                           uint16_t dio2, uint16_t dio3)
{
    (void)irq;
    (void)dio1;
    (void)dio2;
    (void)dio3;
}
void SX1280SetRx(TickTime_t timeout)
{
    (void)timeout;
    s_set_rx_count++;
}
uint16_t SX1280GetIrqStatus(void)
{
    s_irq_get_count++;
    return s_raw_irq;
}
void SX1280ClearIrqStatus(uint16_t irq)
{
    (void)irq;
    s_irq_clear_count++;
    s_raw_irq = 0U;
}
RadioPacketTypes_t SX1280GetPacketType(void)
{
    s_packet_type_get_count++;
    return PACKET_TYPE_LORA;
}
int8_t SX1280GetRssiInst(void)
{
    s_rssi_get_count++;
    return -60;
}
uint8_t SX1280GetPayload(uint8_t *payload, uint8_t *size,
                         uint8_t maximum)
{
    (void)payload;
    (void)size;
    (void)maximum;
    return 1U;
}
void SX1280GetPacketStatus(PacketStatus_t *status)
{
    if (status != NULL) { (void)memset(status, 0, sizeof(*status)); }
}
void SX1280SendPayload(uint8_t *payload, uint8_t size, TickTime_t timeout)
{
    (void)payload;
    (void)size;
    (void)timeout;
}

void Sx1281Bus_Init(void) { }
void Sx1281Bus_StatusGet(Sx1281BusStatus *status)
{
    if (status != NULL) { (void)memset(status, 0, sizeof(*status)); }
}

uint32_t PlatformTime_Ms(void) { return s_tick_ms; }
uint64_t PlatformTime_Us(void) { return (uint64_t)s_tick_ms * 1000ULL; }
void PlatformTime_DelayMs(uint32_t delay_ms) { s_tick_ms += delay_ms; }
PlatformCriticalState PlatformCritical_Enter(void) { return 0U; }
void PlatformCritical_Exit(PlatformCriticalState state) { (void)state; }

PlatformResult PlatformGpio_Read(PlatformGpioId id, uint8_t *logical_high)
{
    if ((id >= PLATFORM_GPIO_COUNT) || (logical_high == NULL))
    {
        return PLATFORM_INVALID_ARGUMENT;
    }
    *logical_high = 0U;
    return PLATFORM_OK;
}

uint8_t PlatformGpio_IrqConsume(PlatformGpioId id)
{
    uint8_t pending;

    if (id != PROJECT_RESOURCE_RADIO_DIO1) { return 0U; }
    pending = s_dio1_pending;
    s_dio1_pending = 0U;
    return pending;
}

static void Test_CachedDiagnosticsDoNotReadSpi(void)
{
    LoraDiagSnapshot snapshot;
    LoraChipStatus chip;
    uint32_t irq_count;
    uint32_t packet_count;
    uint32_t rssi_count;

    TEST_CHECK(Lora_Init() == LORA_INIT_OK);
    Lora_StartRx();
    s_tick_ms = 100U;
    Lora_Process();
    irq_count = s_irq_get_count;
    packet_count = s_packet_type_get_count;
    rssi_count = s_rssi_get_count;
    Lora_GetDiagSnapshot(&snapshot);
    TEST_CHECK(Lora_ChipStatusGet(&chip) == LORA_DIAG_RESULT_OK);
    TEST_CHECK(s_irq_get_count == irq_count);
    TEST_CHECK(s_packet_type_get_count == packet_count);
    TEST_CHECK(s_rssi_get_count == rssi_count);
    TEST_CHECK(snapshot.rssi_inst_valid != 0U);
    TEST_CHECK(chip.verified != 0U);
}

static void Test_DioEventDrivesDirectIrqProcessing(void)
{
    LoraStats stats;
    uint32_t irq_count = s_irq_get_count;

    s_raw_irq = IRQ_RX_TX_TIMEOUT;
    s_dio1_pending = 1U;
    Lora_Process();
    Lora_GetStats(&stats);
    TEST_CHECK(s_irq_get_count == (irq_count + 1U));
    TEST_CHECK(s_irq_clear_count != 0U);
    TEST_CHECK(stats.rx_timeout_irq_count != 0U);
}

static void Test_OwnerControlTransaction(void)
{
    LoraControlResult result;
    uint32_t first_id;
    uint32_t second_id;
    uint32_t set_rx_before;

    TEST_CHECK(Lora_ControlSubmit(LORA_CONTROL_IRQ_CLEAR, 20U,
                                  &first_id) == LORA_CONTROL_SUBMIT_OK);
    TEST_CHECK(Lora_ControlSubmit(LORA_CONTROL_FORCE_RX_CONTINUOUS, 20U,
                                  &second_id) == LORA_CONTROL_SUBMIT_BUSY);
    s_raw_irq = IRQ_RX_DONE;
    Lora_Process();
    TEST_CHECK(Lora_ControlResultGet(first_id, &result) ==
               LORA_CONTROL_GET_COMPLETE);
    TEST_CHECK(result.result == LORA_DIAG_RESULT_OK);
    TEST_CHECK(result.raw_irq_before == IRQ_RX_DONE);
    TEST_CHECK(s_irq_clear_count != 0U);

    TEST_CHECK(Lora_IrqClear(NULL) == LORA_DIAG_RESULT_QUEUED);
    Lora_Process();
    TEST_CHECK(Lora_ControlSubmit(LORA_CONTROL_IRQ_CLEAR, 20U,
                                  &first_id) == LORA_CONTROL_SUBMIT_OK);
    Lora_Process();
    TEST_CHECK(Lora_ControlResultGet(first_id, &result) ==
               LORA_CONTROL_GET_COMPLETE);

    set_rx_before = s_set_rx_count;
    TEST_CHECK(Lora_ControlSubmit(LORA_CONTROL_FORCE_RX_CONTINUOUS, 10U,
                                  &first_id) == LORA_CONTROL_SUBMIT_OK);
    s_tick_ms += 11U;
    TEST_CHECK(Lora_ControlResultGet(first_id, &result) ==
               LORA_CONTROL_GET_COMPLETE);
    TEST_CHECK(result.result == LORA_DIAG_RESULT_TIMEOUT);
    TEST_CHECK(s_set_rx_count == set_rx_before);

    TEST_CHECK(Lora_ControlSubmit(LORA_CONTROL_FORCE_RX_CONTINUOUS, 20U,
                                  &second_id) == LORA_CONTROL_SUBMIT_OK);
    Lora_Process();
    TEST_CHECK(Lora_ControlResultGet(second_id, &result) ==
               LORA_CONTROL_GET_COMPLETE);
    TEST_CHECK(result.result == LORA_DIAG_RESULT_OK);
    TEST_CHECK(s_set_rx_count > set_rx_before);
}

int main(void)
{
    Test_CachedDiagnosticsDoNotReadSpi();
    Test_DioEventDrivesDirectIrqProcessing();
    Test_OwnerControlTransaction();
    return Test_Finish("sx1281_device");
}
