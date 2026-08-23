#include "sx1281_device.h"

#include <string.h>

#include "project_resources.h"
#include "silverstar_assert.h"
#include "platform_critical.h"
#include "platform_gpio.h"
#include "platform_time.h"
#include "sx1280.h"
#include "sx1281_bus.h"

typedef struct
{
    uint8_t len;
    uint8_t data[LORA_MAX_PAYLOAD_LEN];
} LoraTxPacket;

typedef struct
{
    uint8_t len;
    int8_t rssi;
    int8_t snr;
    uint8_t data[LORA_MAX_PAYLOAD_LEN];
} LoraRxPacket;

typedef enum
{
    LoraControlStateIdle = 0U,
    LoraControlStateSubmitted,
    LoraControlStateActive,
    LoraControlStateComplete
} LoraControlState;

typedef struct
{
    LoraControlState state;
    LoraControlOperation operation;
    uint32_t transaction_id;
    uint32_t next_transaction_id;
    uint32_t submitted_ms;
    uint32_t timeout_ms;
    uint8_t auto_release;
    LoraControlResult result;
} LoraControlTransaction;

static volatile uint8_t s_tx_done_flag = 0U;
static volatile uint8_t s_rx_done_flag = 0U;
static volatile uint8_t s_tx_timeout_flag = 0U;
static volatile uint8_t s_rx_timeout_flag = 0U;
static volatile uint8_t s_rx_error_flag = 0U;
static volatile IrqErrorCode_t s_rx_error_code = IRQ_HEADER_ERROR_CODE;

static volatile uint8_t s_inited = 0U;
static volatile uint8_t s_tx_busy = 0U;
static volatile uint8_t s_radio_in_rx = 0U;

static uint8_t s_rx_tmp_buf[LORA_MAX_PAYLOAD_LEN];
static PacketStatus_t s_pkt_status;
static ModulationParams_t s_mod_params;
static PacketParams_t s_pkt_params;
static LoraStats s_stats;
static LoraDiagSnapshot s_diag;
static uint16_t s_diag_counted_raw_irq = 0U;
static LoraChipStatus s_chip_status;
static LoraControlTransaction s_control_transaction;
static uint32_t s_diag_last_refresh_ms;
static uint8_t s_cached_busy_gpio;
static uint8_t s_cached_dio1_gpio;

#define LORA_DIAG_REFRESH_PERIOD_MS 100U
#define LORA_CONTROL_DEFAULT_TIMEOUT_MS 250U

static LoraTxPacket s_tx_queue[LORA_TX_QUEUE_DEPTH];
static uint8_t s_tx_head = 0U;
static uint8_t s_tx_tail = 0U;
static uint8_t s_tx_count = 0U;

static LoraRxPacket s_rx_queue[LORA_RX_QUEUE_DEPTH];
static uint8_t s_rx_head = 0U;
static uint8_t s_rx_tail = 0U;
static uint8_t s_rx_count = 0U;

static void Lora_OnTxDone(void);
static void Lora_OnRxDone(void);
static void Lora_OnTxTimeout(void);
static void Lora_OnRxTimeout(void);
static void Lora_OnRxError(IrqErrorCode_t errCode);
static void Lora_DiagRecordIrq(uint16_t raw_irq);
static void Lora_DiagSetDioIrqParams(uint16_t irq_mask,
                                     uint16_t dio1_mask,
                                     uint16_t dio2_mask,
                                     uint16_t dio3_mask);
static void Lora_ControlProcess(void);
static void Lora_IrqProcess(uint16_t raw_irq);
static LoraControlSubmitResult Lora_ControlSubmitInternal(
    LoraControlOperation operation,
    uint32_t timeout_ms,
    uint8_t auto_release,
    uint32_t *transaction_id);
static LoraDiagResult Lora_ForceRxContinuousDirect(void);

static PlatformCriticalState Lora_IrqLock(void)
{
    return PlatformCritical_Enter();
}

static void Lora_IrqUnlock(PlatformCriticalState state)
{
    PlatformCritical_Exit(state);
}

static void Lora_SetRadioState(LoraRadioState state)
{
    uint32_t primask;

    primask = Lora_IrqLock();
    s_stats.radio_state = state;
    Lora_IrqUnlock(primask);
}

static void Lora_LastRxRecord(uint8_t len, int8_t rssi, int8_t snr)
{
    uint32_t primask;

    primask = Lora_IrqLock();
    s_stats.last_rx_len = len;
    s_stats.last_rx_rssi = rssi;
    s_stats.last_rx_snr = snr;
    s_stats.last_rx_type = (len > 0U) ? s_rx_tmp_buf[0] : 0U;
    Lora_IrqUnlock(primask);
}

static void Lora_StatsIncrement(uint32_t *counter)
{
    uint32_t primask;

    if (counter == 0)
    {
        return;
    }

    primask = Lora_IrqLock();
    (*counter)++;
    Lora_IrqUnlock(primask);
}

static void Lora_DiagRecordSetRx(void)
{
    uint32_t primask;
    uint32_t tick_ms = PlatformTime_Ms();

    primask = Lora_IrqLock();
    s_diag.setrx_count++;
    s_diag.rx_start_count++;
    s_diag.last_setrx_ms = tick_ms;
    Lora_IrqUnlock(primask);
}

static void Lora_DiagRecordSetTx(void)
{
    uint32_t primask;
    uint32_t tick_ms = PlatformTime_Ms();

    primask = Lora_IrqLock();
    s_diag.settx_count++;
    s_diag.last_settx_ms = tick_ms;
    Lora_IrqUnlock(primask);
}

static void Lora_DiagRecordTxStart(void)
{
    uint32_t primask;

    primask = Lora_IrqLock();
    s_diag.tx_start_count++;
    Lora_IrqUnlock(primask);
}

static void Lora_DiagTimeoutRecord(uint16_t raw_irq,
                                   uint8_t *is_tx_irq,
                                   uint8_t *is_rx_irq)
{
    if ((raw_irq & IRQ_RX_TX_TIMEOUT) == 0U)
    {
        return;
    }
    if ((s_tx_busy != 0U) || (s_stats.radio_state == LORA_RADIO_STATE_TX))
    {
        s_diag.tx_timeout_count++;
        *is_tx_irq = 1U;
    }
    else
    {
        s_diag.rx_timeout_count++;
        *is_rx_irq = 1U;
    }
}

static void Lora_DiagRecordIrq(uint16_t raw_irq)
{
    uint32_t primask;
    uint32_t tick_ms;
    uint8_t is_tx_irq = 0U;
    uint8_t is_rx_irq = 0U;

    if (raw_irq == 0U)
    {
        return;
    }

    SILVERSTAR_ASSERT_OBJECT(&s_diag, LoraDiagSnapshot,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    tick_ms = PlatformTime_Ms();
    primask = Lora_IrqLock();

    s_diag.last_raw_irq = raw_irq;
    s_diag.last_irq_ms = tick_ms;
    s_diag.has_last_irq = 1U;

    if ((raw_irq & IRQ_TX_DONE) != 0U)
    {
        s_diag.tx_done_count++;
        is_tx_irq = 1U;
    }
    if ((raw_irq & IRQ_RX_DONE) != 0U)
    {
        s_diag.rx_done_count++;
        is_rx_irq = 1U;
    }
    if ((raw_irq & IRQ_CRC_ERROR) != 0U)
    {
        s_diag.rx_crc_count++;
        s_diag.rx_error_count++;
        is_rx_irq = 1U;
    }
    if ((raw_irq & IRQ_HEADER_ERROR) != 0U)
    {
        s_diag.rx_header_count++;
        s_diag.rx_error_count++;
        is_rx_irq = 1U;
    }
    Lora_DiagTimeoutRecord(raw_irq, &is_tx_irq, &is_rx_irq);

    if (is_rx_irq != 0U)
    {
        s_diag.last_rx_irq_ms = tick_ms;
        s_diag.has_last_rx_irq = 1U;
    }
    if (is_tx_irq != 0U)
    {
        s_diag.last_tx_irq_ms = tick_ms;
        s_diag.has_last_tx_irq = 1U;
    }

    Lora_IrqUnlock(primask);
}

static void Lora_DiagSetDioIrqParams(uint16_t irq_mask,
                                     uint16_t dio1_mask,
                                     uint16_t dio2_mask,
                                     uint16_t dio3_mask)
{
    uint32_t primask;

    SX1280SetDioIrqParams(irq_mask, dio1_mask, dio2_mask, dio3_mask);

    primask = Lora_IrqLock();
    s_diag.irq_mask = irq_mask;
    s_diag.dio1_mask = dio1_mask;
    s_diag.dio2_mask = dio2_mask;
    s_diag.dio3_mask = dio3_mask;
    Lora_IrqUnlock(primask);
}

static void Lora_LoadDefaultConfig(void)
{
    memset(&s_mod_params, 0, sizeof(s_mod_params));
    memset(&s_pkt_params, 0, sizeof(s_pkt_params));
    memset(&s_pkt_status, 0, sizeof(s_pkt_status));

    s_mod_params.PacketType = PACKET_TYPE_LORA;
    s_mod_params.Params.LoRa.SpreadingFactor = LORA_CFG_SF;
    s_mod_params.Params.LoRa.Bandwidth = LORA_CFG_BW;
    s_mod_params.Params.LoRa.CodingRate = LORA_CFG_CR;

    s_pkt_params.PacketType = PACKET_TYPE_LORA;
    s_pkt_params.Params.LoRa.PreambleLength = LORA_CFG_PREAMBLE_LEN;
    s_pkt_params.Params.LoRa.HeaderType = LORA_CFG_HEADER_TYPE;
    s_pkt_params.Params.LoRa.CrcMode = LORA_CFG_CRC_MODE;
    s_pkt_params.Params.LoRa.InvertIQ = LORA_CFG_IQ_MODE;
    s_pkt_params.Params.LoRa.PayloadLength = LORA_MAX_PAYLOAD_LEN;
}

static void Lora_ClearRuntimeState(void)
{
    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    s_tx_done_flag = 0U;
    s_rx_done_flag = 0U;
    s_tx_timeout_flag = 0U;
    s_rx_timeout_flag = 0U;
    s_rx_error_flag = 0U;
    s_rx_error_code = IRQ_HEADER_ERROR_CODE;

    s_tx_busy = 0U;
    s_radio_in_rx = 0U;

    s_tx_head = 0U;
    s_tx_tail = 0U;
    s_tx_count = 0U;

    s_rx_head = 0U;
    s_rx_tail = 0U;
    s_rx_count = 0U;

    memset(&s_stats, 0, sizeof(s_stats));
    memset(&s_diag, 0, sizeof(s_diag));
    memset(&s_chip_status, 0, sizeof(s_chip_status));
    memset(&s_control_transaction, 0, sizeof(s_control_transaction));
    s_diag_last_refresh_ms = 0U;
    s_cached_busy_gpio = 0U;
    s_cached_dio1_gpio = 0U;
    s_diag_counted_raw_irq = 0U;
    Lora_SetRadioState(LORA_RADIO_STATE_NOT_INIT);
}

static uint8_t Lora_TxQueuePush(const uint8_t *data, uint8_t len)
{
    uint32_t primask;

    if ((data == 0) || (len == 0) || (len > LORA_MAX_PAYLOAD_LEN))
    {
        return 0U;
    }

    SILVERSTAR_ASSERT_OBJECT(data, uint8_t,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    primask = Lora_IrqLock();

    if (s_tx_count >= LORA_TX_QUEUE_DEPTH)
    {
        Lora_IrqUnlock(primask);
        return 0U;
    }

    s_tx_queue[s_tx_head].len = len;
    memcpy(s_tx_queue[s_tx_head].data, data, len);

    s_tx_head++;
    if (s_tx_head >= LORA_TX_QUEUE_DEPTH)
    {
        s_tx_head = 0U;
    }

    s_tx_count++;
    Lora_IrqUnlock(primask);
    return 1U;
}

static uint8_t Lora_TxQueuePushFront(const uint8_t *data, uint8_t len)
{
    uint32_t primask;

    if ((data == 0) || (len == 0) || (len > LORA_MAX_PAYLOAD_LEN))
    {
        return 0U;
    }

    SILVERSTAR_ASSERT_OBJECT(data, uint8_t,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    primask = Lora_IrqLock();

    if (s_tx_count >= LORA_TX_QUEUE_DEPTH)
    {
        Lora_IrqUnlock(primask);
        return 0U;
    }

    if (s_tx_tail == 0U)
    {
        s_tx_tail = (uint8_t)(LORA_TX_QUEUE_DEPTH - 1U);
    }
    else
    {
        s_tx_tail--;
    }

    s_tx_queue[s_tx_tail].len = len;
    memcpy(s_tx_queue[s_tx_tail].data, data, len);
    s_tx_count++;

    Lora_IrqUnlock(primask);
    return 1U;
}

static uint8_t Lora_TxQueuePop(LoraTxPacket *pkt)
{
    uint32_t primask;

    if (pkt == 0)
    {
        return 0U;
    }

    SILVERSTAR_ASSERT_OBJECT(pkt, LoraTxPacket,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    primask = Lora_IrqLock();

    if (s_tx_count == 0)
    {
        Lora_IrqUnlock(primask);
        return 0U;
    }

    *pkt = s_tx_queue[s_tx_tail];

    s_tx_tail++;
    if (s_tx_tail >= LORA_TX_QUEUE_DEPTH)
    {
        s_tx_tail = 0U;
    }

    s_tx_count--;
    Lora_IrqUnlock(primask);
    return 1U;
}

static uint8_t Lora_RxQueuePush(const uint8_t *data, uint8_t len, int8_t rssi, int8_t snr)
{
    uint32_t primask;

    if ((data == 0) || (len == 0) || (len > LORA_MAX_PAYLOAD_LEN))
    {
        return 0U;
    }

    SILVERSTAR_ASSERT_OBJECT(data, uint8_t,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    primask = Lora_IrqLock();

    if (s_rx_count >= LORA_RX_QUEUE_DEPTH)
    {
        Lora_IrqUnlock(primask);
        return 0U;
    }

    s_rx_queue[s_rx_head].len = len;
    s_rx_queue[s_rx_head].rssi = rssi;
    s_rx_queue[s_rx_head].snr = snr;
    memcpy(s_rx_queue[s_rx_head].data, data, len);

    s_rx_head++;
    if (s_rx_head >= LORA_RX_QUEUE_DEPTH)
    {
        s_rx_head = 0U;
    }

    s_rx_count++;
    Lora_IrqUnlock(primask);
    return 1U;
}

static uint8_t Lora_RxQueuePop(LoraRxPacket *pkt)
{
    uint32_t primask;

    if (pkt == 0)
    {
        return 0U;
    }

    SILVERSTAR_ASSERT_OBJECT(pkt, LoraRxPacket,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    primask = Lora_IrqLock();

    if (s_rx_count == 0)
    {
        Lora_IrqUnlock(primask);
        return 0U;
    }

    *pkt = s_rx_queue[s_rx_tail];

    s_rx_tail++;
    if (s_rx_tail >= LORA_RX_QUEUE_DEPTH)
    {
        s_rx_tail = 0U;
    }

    s_rx_count--;
    Lora_IrqUnlock(primask);
    return 1U;
}

static void Lora_TryStartNextTx(void)
{
    LoraTxPacket pkt;

    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((s_inited == 0) || (s_tx_busy != 0))
    {
        return;
    }

    if (Lora_TxQueuePop(&pkt) == 0)
    {
        return;
    }

    s_pkt_params.Params.LoRa.PayloadLength = pkt.len;
    SX1280SetPacketParams(&s_pkt_params);
    Lora_DiagSetDioIrqParams(LORA_TX_IRQ_MASK, LORA_TX_IRQ_MASK, IRQ_RADIO_NONE, IRQ_RADIO_NONE);
    Lora_DiagRecordTxStart();
    SX1280SendPayload(pkt.data, pkt.len,
                      (TickTime_t){ LORA_TX_TIMEOUT_STEP,
                                    LORA_TX_TIMEOUT_COUNT });
    Lora_DiagRecordSetTx();

    s_tx_busy = 1U;
    s_radio_in_rx = 0U;
    Lora_SetRadioState(LORA_RADIO_STATE_TX);
}

LoraConfigResult Lora_ApplyDefaultConfig(void)
{
    Sx1281BusStatus before;
    Sx1281BusStatus after;

    Sx1281Bus_StatusGet(&before);
    SX1280SetPacketType(PACKET_TYPE_LORA);
    SX1280SetModulationParams(&s_mod_params);
    SX1280SetPacketParams(&s_pkt_params);
    SX1280SetRfFrequency(LORA_RF_FREQUENCY_HZ);
    SX1280SetBufferBaseAddresses(0x00, 0x00);
    SX1280SetTxParams(LORA_TX_OUTPUT_POWER_DBM, RADIO_RAMP_02_US);
    Sx1281Bus_StatusGet(&after);
    return ((after.spi_error_count != before.spi_error_count) ||
            (after.busy_timeout_count != before.busy_timeout_count)) ?
        LORA_CONFIG_PORT_ERROR : LORA_CONFIG_OK;
}

LoraInitResult Lora_Init(void)
{
    RadioStatus_t radio_status;
    Sx1281BusStatus bus_status;

    SILVERSTAR_ASSERT_OBJECT(&s_chip_status, LoraChipStatus,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    Sx1281Bus_Init();
    Lora_LoadDefaultConfig();
    Lora_ClearRuntimeState();

    SX1280Init();
    SX1280SetRegulatorMode(USE_LDO);
    SX1280SetStandby(STDBY_RC);
    if (Lora_ApplyDefaultConfig() != LORA_CONFIG_OK)
    {
        return LORA_INIT_PORT_ERROR;
    }

    s_chip_status.firmware_version = SX1280GetFirmwareVersion();
    radio_status = SX1280GetStatus();
    s_chip_status.status_value = radio_status.Value;
    Sx1281Bus_StatusGet(&bus_status);
    if ((bus_status.spi_error_count != 0U) ||
        (bus_status.busy_timeout_count != 0U))
    {
        return LORA_INIT_PORT_ERROR;
    }
    if ((s_chip_status.firmware_version == 0x0000U) ||
        (s_chip_status.firmware_version == 0xFFFFU) ||
        (s_chip_status.status_value == 0x00U) ||
        (s_chip_status.status_value == 0xFFU))
    {
        return LORA_INIT_CHIP_NOT_FOUND;
    }
    s_chip_status.verified = 1U;

    s_inited = 1U;
    Lora_SetRadioState(LORA_RADIO_STATE_READY);

    return LORA_INIT_OK;
}

void Lora_StartRx(void)
{
    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_inited == 0)
    {
        return;
    }

    s_pkt_params.Params.LoRa.PayloadLength = LORA_MAX_PAYLOAD_LEN;
    SX1280SetPacketParams(&s_pkt_params);
    Lora_DiagSetDioIrqParams(LORA_RX_IRQ_MASK, LORA_RX_IRQ_MASK, IRQ_RADIO_NONE, IRQ_RADIO_NONE);
    SX1280SetRx(RX_TX_CONTINUOUS);
    Lora_DiagRecordSetRx();

    s_radio_in_rx = 1U;
    if (s_tx_busy != 0)
    {
        Lora_SetRadioState(LORA_RADIO_STATE_TX);
    }
    else
    {
        Lora_SetRadioState(LORA_RADIO_STATE_RX);
    }
}

LoraTxEnqueueResult Lora_TxEnqueue(const uint8_t *data, uint8_t len)
{
    if (s_inited == 0)
    {
        return LORA_TX_ENQUEUE_NOT_INIT;
    }

    if ((data == 0) || (len == 0) || (len > LORA_MAX_PAYLOAD_LEN))
    {
        return LORA_TX_ENQUEUE_BAD_PARAM;
    }

    if (Lora_TxQueuePush(data, len) == 0)
    {
        Lora_StatsIncrement(&s_stats.tx_dropped);
        return LORA_TX_ENQUEUE_QUEUE_FULL;
    }

    return LORA_TX_ENQUEUE_OK;
}

LoraTxEnqueueResult Lora_TxEnqueuePriority(const uint8_t *data, uint8_t len)
{
    if (s_inited == 0)
    {
        return LORA_TX_ENQUEUE_NOT_INIT;
    }

    if ((data == 0) || (len == 0) || (len > LORA_MAX_PAYLOAD_LEN))
    {
        return LORA_TX_ENQUEUE_BAD_PARAM;
    }

    if (Lora_TxQueuePushFront(data, len) == 0)
    {
        Lora_StatsIncrement(&s_stats.tx_dropped);
        return LORA_TX_ENQUEUE_QUEUE_FULL;
    }

    return LORA_TX_ENQUEUE_OK;
}

static void Lora_IrqProcess(uint16_t raw_irq)
{
    SILVERSTAR_ASSERT_OBJECT(&s_diag, LoraDiagSnapshot,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((raw_irq & IRQ_TX_DONE) != 0U)
    {
        Lora_OnTxDone();
    }
    if ((raw_irq & IRQ_RX_DONE) != 0U)
    {
        if ((raw_irq & IRQ_CRC_ERROR) != 0U)
        {
            Lora_OnRxError(IRQ_CRC_ERROR_CODE);
        }
        else if ((raw_irq & IRQ_HEADER_ERROR) != 0U)
        {
            Lora_OnRxError(IRQ_HEADER_ERROR_CODE);
        }
        else
        {
            Lora_OnRxDone();
        }
    }
    else if ((raw_irq & IRQ_CRC_ERROR) != 0U)
    {
        Lora_OnRxError(IRQ_CRC_ERROR_CODE);
    }
    else if ((raw_irq & IRQ_HEADER_ERROR) != 0U)
    {
        Lora_OnRxError(IRQ_HEADER_ERROR_CODE);
    }
    if ((raw_irq & IRQ_RX_TX_TIMEOUT) != 0U)
    {
        if (s_tx_busy != 0U)
        {
            Lora_OnTxTimeout();
        }
        else
        {
            Lora_OnRxTimeout();
        }
    }
}

static void Lora_RawIrqProcess(void)
{
    uint16_t raw_irq = 0U;
    uint32_t primask;

    SILVERSTAR_ASSERT_OBJECT(&s_diag, LoraDiagSnapshot,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((PlatformGpio_IrqConsume(PROJECT_RESOURCE_RADIO_DIO1) != 0U) ||
        (s_tx_busy != 0U))
    {
        raw_irq = SX1280GetIrqStatus();
    }
    primask = Lora_IrqLock();
    s_diag.raw_irq = raw_irq;
    Lora_IrqUnlock(primask);
    if (raw_irq != 0U)
    {
        Lora_DiagRecordIrq(raw_irq);
        Lora_IrqProcess(raw_irq);
        SX1280ClearIrqStatus(raw_irq);
        s_diag_counted_raw_irq = raw_irq;
    }
    else
    {
        s_diag_counted_raw_irq = 0U;
    }
}

static void Lora_DiagnosticsRefresh(void)
{
    RadioStatus_t radio_status;
    uint8_t busy_gpio = 0U;
    uint8_t dio1_gpio = 0U;
    uint8_t packet_runtime;
    int16_t rssi_inst;
    uint32_t primask;

    SILVERSTAR_ASSERT_OBJECT(&s_chip_status, LoraChipStatus,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((PlatformTime_Ms() - s_diag_last_refresh_ms) <
        LORA_DIAG_REFRESH_PERIOD_MS)
    {
        return;
    }
    radio_status = SX1280GetStatus();
    packet_runtime = (uint8_t)SX1280GetPacketType();
    rssi_inst = (int16_t)SX1280GetRssiInst();
    (void)PlatformGpio_Read(PROJECT_RESOURCE_RADIO_BUSY, &busy_gpio);
    (void)PlatformGpio_Read(PROJECT_RESOURCE_RADIO_DIO1, &dio1_gpio);
    primask = Lora_IrqLock();
    s_chip_status.status_value = radio_status.Value;
    s_chip_status.verified = (uint8_t)((radio_status.Value != 0x00U) &&
                                      (radio_status.Value != 0xFFU));
    s_diag.packet_runtime = packet_runtime;
    s_diag.rssi_inst = rssi_inst;
    s_diag.rssi_inst_valid = 1U;
    s_cached_busy_gpio = busy_gpio;
    s_cached_dio1_gpio = dio1_gpio;
    s_diag_last_refresh_ms = PlatformTime_Ms();
    Lora_IrqUnlock(primask);
}

static void Lora_TxCompletionProcess(void)
{
    if (s_tx_done_flag != 0U)
    {
        s_tx_done_flag = 0U;
        s_tx_busy = 0U;
        Lora_StatsIncrement(&s_stats.tx_ok);
        Lora_SetRadioState(LORA_RADIO_STATE_READY);
    }
    if (s_tx_timeout_flag != 0U)
    {
        s_tx_timeout_flag = 0U;
        s_tx_busy = 0U;
        Lora_StatsIncrement(&s_stats.tx_timeout);
        Lora_SetRadioState(LORA_RADIO_STATE_READY);
    }
}

static void Lora_RxCompletionProcess(void)
{
    uint8_t size = 0U;
    int8_t rssi;
    int8_t snr;

    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_rx_done_flag == 0U)
    {
        return;
    }
    s_rx_done_flag = 0U;
    if (SX1280GetPayload(s_rx_tmp_buf, &size, LORA_MAX_PAYLOAD_LEN) == 0)
    {
        SX1280GetPacketStatus(&s_pkt_status);
        rssi = s_pkt_status.Params.LoRa.RssiPkt;
        snr = s_pkt_status.Params.LoRa.SnrPkt;
        Lora_LastRxRecord(size, rssi, snr);
        if (Lora_RxQueuePush(s_rx_tmp_buf, size, rssi, snr) != 0U)
        {
            Lora_StatsIncrement(&s_stats.rx_ok);
        }
        else
        {
            Lora_StatsIncrement(&s_stats.rx_dropped);
        }
    }
    else
    {
        Lora_StatsIncrement(&s_stats.rx_dropped);
    }
    Lora_SetRadioState(LORA_RADIO_STATE_READY);
}

static void Lora_RxErrorProcess(void)
{
    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_rx_timeout_flag != 0U)
    {
        s_rx_timeout_flag = 0U;
        Lora_StatsIncrement(&s_stats.rx_timeout);
        Lora_SetRadioState(LORA_RADIO_STATE_READY);
    }
    if (s_rx_error_flag != 0U)
    {
        s_rx_error_flag = 0U;
        Lora_StatsIncrement(&s_stats.rx_error);
        if (s_rx_error_code == IRQ_CRC_ERROR_CODE)
        {
            Lora_StatsIncrement(&s_stats.rx_crc_error);
        }
        Lora_SetRadioState(LORA_RADIO_STATE_READY);
    }
}

void Lora_Process(void)
{
    if (s_inited == 0)
    {
        return;
    }

    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    Lora_ControlProcess();
    Lora_RawIrqProcess();
    Lora_DiagnosticsRefresh();
    Lora_TxCompletionProcess();
    Lora_RxCompletionProcess();
    Lora_RxErrorProcess();
    if (s_tx_busy == 0)
    {
        Lora_TryStartNextTx();
        if ((s_tx_busy == 0) && (s_radio_in_rx == 0))
        {
            Lora_StartRx();
        }
    }
}

LoraRxDequeueResult Lora_RxDequeue(uint8_t *data, uint8_t *len, int8_t *rssi, int8_t *snr)
{
    LoraRxPacket pkt;

    if ((data == 0) || (len == 0))
    {
        return LORA_RX_DEQUEUE_BAD_PARAM;
    }

    SILVERSTAR_ASSERT_OBJECT(data, uint8_t,
        SILVERSTAR_ASSERT_MODULE_DEVICE);

    if (Lora_RxQueuePop(&pkt) == 0)
    {
        return LORA_RX_DEQUEUE_EMPTY;
    }

    memcpy(data, pkt.data, pkt.len);
    *len = pkt.len;

    if (rssi != 0)
    {
        *rssi = pkt.rssi;
    }

    if (snr != 0)
    {
        *snr = pkt.snr;
    }

    return LORA_RX_DEQUEUE_OK;
}

void Lora_GetStats(LoraStats *stats)
{
    uint32_t primask;

    if (stats == 0)
    {
        return;
    }

    primask = Lora_IrqLock();
    *stats = s_stats;
    Lora_IrqUnlock(primask);
}

void Lora_GetDebugSnapshot(LoraDebugSnapshot *snapshot)
{
    uint32_t primask;

    if (snapshot == 0)
    {
        return;
    }

    primask = Lora_IrqLock();
    snapshot->initialized = s_inited;
    snapshot->tx_queue_count = s_tx_count;
    snapshot->rx_queue_count = s_rx_count;
    snapshot->stats = s_stats;
    snapshot->busy_gpio = s_cached_busy_gpio;
    snapshot->dio1_gpio = s_cached_dio1_gpio;
    Lora_IrqUnlock(primask);
}

void Lora_GetDiagSnapshot(LoraDiagSnapshot *snapshot)
{
    uint32_t primask;

    if (snapshot == 0)
    {
        return;
    }

    primask = Lora_IrqLock();
    *snapshot = s_diag;
    Lora_IrqUnlock(primask);
}

LoraDiagResult Lora_IrqClear(uint16_t *raw_before)
{
    uint32_t transaction_id;
    LoraControlSubmitResult result;

    if (raw_before != 0)
    {
        *raw_before = 0U;
    }
    result = Lora_ControlSubmitInternal(LORA_CONTROL_IRQ_CLEAR,
                                        LORA_CONTROL_DEFAULT_TIMEOUT_MS,
                                        1U,
                                        &transaction_id);
    (void)transaction_id;
    if (result == LORA_CONTROL_SUBMIT_OK)
    {
        return LORA_DIAG_RESULT_QUEUED;
    }
    return (result == LORA_CONTROL_SUBMIT_BUSY) ? LORA_DIAG_RESULT_BUSY :
                                                  LORA_DIAG_RESULT_NOT_INIT;
}

static LoraDiagResult Lora_ForceRxContinuousDirect(void)
{
    uint32_t primask;

    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_inited == 0U)
    {
        return LORA_DIAG_RESULT_NOT_INIT;
    }

    SX1280SetStandby(STDBY_RC);
    SX1280ClearIrqStatus(IRQ_RADIO_ALL);
    s_diag_counted_raw_irq = 0U;

    primask = Lora_IrqLock();
    s_tx_done_flag = 0U;
    s_rx_done_flag = 0U;
    s_tx_timeout_flag = 0U;
    s_rx_timeout_flag = 0U;
    s_rx_error_flag = 0U;
    s_tx_busy = 0U;
    s_radio_in_rx = 0U;
    Lora_IrqUnlock(primask);

    s_pkt_params.Params.LoRa.PayloadLength = LORA_MAX_PAYLOAD_LEN;
    SX1280SetPacketParams(&s_pkt_params);
    Lora_DiagSetDioIrqParams(LORA_RX_IRQ_MASK, LORA_RX_IRQ_MASK, IRQ_RADIO_NONE, IRQ_RADIO_NONE);
    SX1280SetRx(RX_TX_CONTINUOUS);
    Lora_DiagRecordSetRx();

    primask = Lora_IrqLock();
    s_radio_in_rx = 1U;
    Lora_IrqUnlock(primask);
    Lora_SetRadioState(LORA_RADIO_STATE_RX);

    return LORA_DIAG_RESULT_OK;
}

void Lora_ClearStats(void)
{
    LoraRadioState state;
    uint32_t primask;

    primask = Lora_IrqLock();
    state = s_stats.radio_state;
    memset(&s_stats, 0, sizeof(s_stats));
    s_stats.radio_state = state;
    Lora_IrqUnlock(primask);
}

LoraBusyState Lora_IsBusy(void)
{
    uint8_t busy;
    uint32_t primask;

    primask = Lora_IrqLock();
    busy = ((s_tx_busy != 0) || (s_tx_count > 0U)) ? 1U : 0U;
    Lora_IrqUnlock(primask);

    if (busy != 0)
    {
        return LORA_BUSY_ACTIVE;
    }

    return LORA_BUSY_IDLE;
}

LoraDiagResult Lora_ChipStatusGet(LoraChipStatus *status)
{
    uint32_t primask;

    SILVERSTAR_ASSERT_OBJECT(&s_stats, LoraStats,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if ((status == 0) || (s_inited == 0U))
    {
        return LORA_DIAG_RESULT_NOT_INIT;
    }
    primask = Lora_IrqLock();
    *status = s_chip_status;
    Lora_IrqUnlock(primask);
    return LORA_DIAG_RESULT_OK;
}

LoraDiagResult Lora_ForceRxContinuous(void)
{
    uint32_t transaction_id;
    LoraControlSubmitResult result = Lora_ControlSubmitInternal(
        LORA_CONTROL_FORCE_RX_CONTINUOUS,
        LORA_CONTROL_DEFAULT_TIMEOUT_MS,
        1U,
        &transaction_id);

    (void)transaction_id;
    if (result == LORA_CONTROL_SUBMIT_OK)
    {
        return LORA_DIAG_RESULT_QUEUED;
    }
    return (result == LORA_CONTROL_SUBMIT_BUSY) ? LORA_DIAG_RESULT_BUSY :
                                                  LORA_DIAG_RESULT_NOT_INIT;
}

LoraControlSubmitResult Lora_ControlSubmit(LoraControlOperation operation,
                                           uint32_t timeout_ms,
                                           uint32_t *transaction_id)
{
    return Lora_ControlSubmitInternal(operation, timeout_ms, 0U,
                                      transaction_id);
}

static LoraControlSubmitResult Lora_ControlSubmitInternal(
    LoraControlOperation operation,
    uint32_t timeout_ms,
    uint8_t auto_release,
    uint32_t *transaction_id)
{
    uint32_t primask;
    uint32_t now_ms;

    if ((transaction_id == 0) || (timeout_ms == 0U) ||
        ((operation != LORA_CONTROL_IRQ_CLEAR) &&
         (operation != LORA_CONTROL_FORCE_RX_CONTINUOUS)))
    {
        return LORA_CONTROL_SUBMIT_BAD_PARAM;
    }
    SILVERSTAR_ASSERT_OBJECT(transaction_id, uint32_t,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (s_inited == 0U) { return LORA_CONTROL_SUBMIT_NOT_INIT; }
    now_ms = PlatformTime_Ms();
    primask = Lora_IrqLock();
    if (((s_control_transaction.state == LoraControlStateSubmitted) ||
         (s_control_transaction.state == LoraControlStateComplete)) &&
        ((now_ms - s_control_transaction.submitted_ms) >=
         s_control_transaction.timeout_ms))
    {
        s_control_transaction.state = LoraControlStateIdle;
    }
    if (s_control_transaction.state != LoraControlStateIdle)
    {
        Lora_IrqUnlock(primask);
        return LORA_CONTROL_SUBMIT_BUSY;
    }
    s_control_transaction.next_transaction_id++;
    if (s_control_transaction.next_transaction_id == 0U)
    {
        s_control_transaction.next_transaction_id = 1U;
    }
    s_control_transaction.transaction_id =
        s_control_transaction.next_transaction_id;
    s_control_transaction.operation = operation;
    s_control_transaction.submitted_ms = now_ms;
    s_control_transaction.timeout_ms = timeout_ms;
    s_control_transaction.auto_release = auto_release;
    s_control_transaction.state = LoraControlStateSubmitted;
    *transaction_id = s_control_transaction.transaction_id;
    Lora_IrqUnlock(primask);
    return LORA_CONTROL_SUBMIT_OK;
}

LoraControlGetResult Lora_ControlResultGet(uint32_t transaction_id,
                                           LoraControlResult *result)
{
    uint32_t primask;

    if ((transaction_id == 0U) || (result == 0))
    {
        return LORA_CONTROL_GET_BAD_PARAM;
    }
    SILVERSTAR_ASSERT_OBJECT(result, LoraControlResult,
        SILVERSTAR_ASSERT_MODULE_DEVICE);
    primask = Lora_IrqLock();
    if ((s_control_transaction.state == LoraControlStateIdle) ||
        (s_control_transaction.transaction_id != transaction_id))
    {
        Lora_IrqUnlock(primask);
        return LORA_CONTROL_GET_NOT_FOUND;
    }
    if ((s_control_transaction.state == LoraControlStateSubmitted) &&
        ((PlatformTime_Ms() - s_control_transaction.submitted_ms) >=
         s_control_transaction.timeout_ms))
    {
        s_control_transaction.result.transaction_id = transaction_id;
        s_control_transaction.result.result = LORA_DIAG_RESULT_TIMEOUT;
        s_control_transaction.result.raw_irq_before = 0U;
        s_control_transaction.state = LoraControlStateComplete;
    }
    if (s_control_transaction.state != LoraControlStateComplete)
    {
        Lora_IrqUnlock(primask);
        return LORA_CONTROL_GET_PENDING;
    }
    *result = s_control_transaction.result;
    s_control_transaction.state = LoraControlStateIdle;
    Lora_IrqUnlock(primask);
    return LORA_CONTROL_GET_COMPLETE;
}

static void Lora_ControlProcess(void)
{
    LoraControlOperation operation;
    LoraControlResult result;
    uint32_t primask;

    SILVERSTAR_ASSERT_OBJECT(&s_control_transaction,
        LoraControlTransaction, SILVERSTAR_ASSERT_MODULE_DEVICE);
    primask = Lora_IrqLock();
    if (s_control_transaction.state != LoraControlStateSubmitted)
    {
        Lora_IrqUnlock(primask);
        return;
    }
    if ((PlatformTime_Ms() - s_control_transaction.submitted_ms) >=
        s_control_transaction.timeout_ms)
    {
        s_control_transaction.result.transaction_id =
            s_control_transaction.transaction_id;
        s_control_transaction.result.result = LORA_DIAG_RESULT_TIMEOUT;
        s_control_transaction.result.raw_irq_before = 0U;
        s_control_transaction.state =
            (s_control_transaction.auto_release != 0U) ?
                LoraControlStateIdle : LoraControlStateComplete;
        Lora_IrqUnlock(primask);
        return;
    }
    operation = s_control_transaction.operation;
    result.transaction_id = s_control_transaction.transaction_id;
    result.raw_irq_before = 0U;
    s_control_transaction.state = LoraControlStateActive;
    Lora_IrqUnlock(primask);

    if (operation == LORA_CONTROL_IRQ_CLEAR)
    {
        result.raw_irq_before = SX1280GetIrqStatus();
        SX1280ClearIrqStatus(IRQ_RADIO_ALL);
        s_diag_counted_raw_irq = 0U;
        result.result = LORA_DIAG_RESULT_OK;
    }
    else
    {
        result.result = Lora_ForceRxContinuousDirect();
    }

    primask = Lora_IrqLock();
    s_control_transaction.result = result;
    s_control_transaction.state =
        (s_control_transaction.auto_release != 0U) ?
            LoraControlStateIdle : LoraControlStateComplete;
    Lora_IrqUnlock(primask);
}

static void Lora_OnTxDone(void)
{
    Lora_StatsIncrement(&s_stats.tx_irq_count);
    s_tx_done_flag = 1U;
    s_radio_in_rx = 0U;
}

static void Lora_OnRxDone(void)
{
    Lora_StatsIncrement(&s_stats.rx_irq_count);
    s_rx_done_flag = 1U;
    s_radio_in_rx = 0U;
}

static void Lora_OnTxTimeout(void)
{
    Lora_StatsIncrement(&s_stats.tx_timeout_irq_count);
    s_tx_timeout_flag = 1U;
    s_radio_in_rx = 0U;
}

static void Lora_OnRxTimeout(void)
{
    Lora_StatsIncrement(&s_stats.rx_timeout_irq_count);
    s_rx_timeout_flag = 1U;
    s_radio_in_rx = 0U;
}

static void Lora_OnRxError(IrqErrorCode_t errCode)
{
    Lora_StatsIncrement(&s_stats.rx_error_irq_count);
    s_rx_error_code = errCode;
    s_rx_error_flag = 1U;
    s_radio_in_rx = 0U;
}
