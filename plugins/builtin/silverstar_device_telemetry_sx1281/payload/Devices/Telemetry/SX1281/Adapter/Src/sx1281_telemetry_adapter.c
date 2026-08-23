#include "system_version.h"
#include "system_telemetry_transport_if.h"

#include <limits.h>
#include <stddef.h>
#include <string.h>

#include "air_protocol.h"
#include "platform_critical.h"
#include "platform_time.h"
#include "silverstar_assert.h"
#include "sx1281_config.h"
#include "sx1281_bus.h"
#include "sx1281_device.h"

_Static_assert(AIR_MAX_FRAME_LEN <= LORA_MAX_PAYLOAD_LEN,
               "AIR_MAX_FRAME_LEN exceeds the SX1281 transport MTU");

static volatile uint8_t s_initialized;
static volatile uint8_t s_started;
static SystemTelemetryHealth s_health;
static SystemDeviceIoDiagnostics s_io_diagnostics;
static LoraStats s_previous_stats;
static Sx1281BusStatus s_previous_bus_status;

static void Sx1281Transport_IoDiagnosticsUpdate(
    const LoraStats *stats,
    const Sx1281BusStatus *bus_status)
{
    if (bus_status == NULL) { return; }
    s_io_diagnostics.transport_error_count = bus_status->spi_error_count;
    s_io_diagnostics.spi_error_count = bus_status->spi_error_count;
    s_io_diagnostics.spi_timeout_count = bus_status->spi_timeout_count;
    s_io_diagnostics.busy_timeout_count = bus_status->busy_timeout_count;
    s_io_diagnostics.timeout_count = bus_status->spi_timeout_count +
        bus_status->busy_timeout_count;
    if (stats != NULL)
    {
        s_io_diagnostics.integrity_error_count = stats->rx_crc_error;
    }
}

static uint32_t Sx1281Transport_IrqLock(void)
{
    return PlatformCritical_Enter();
}

static void Sx1281Transport_IrqUnlock(uint32_t primask)
{
    PlatformCritical_Exit(primask);
}

static SystemDeviceResult Sx1281Transport_Init(void)
{
    LoraInitResult init_result;
    LoraChipStatus chip_status;
    Sx1281BusStatus bus_status;
    uint32_t primask;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_started <= 1U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_initialized != 0U) { return SYSTEM_DEVICE_ALREADY_MATCHED; }
    primask = Sx1281Transport_IrqLock();
    (void)memset(&s_health, 0, sizeof(s_health));
    (void)memset(&s_previous_stats, 0, sizeof(s_previous_stats));
    (void)memset(&s_previous_bus_status, 0, sizeof(s_previous_bus_status));
    (void)memset(&s_io_diagnostics, 0, sizeof(s_io_diagnostics));
    s_io_diagnostics.supported_mask = SYSTEM_DEVICE_IO_VALID_TRANSPORT |
        SYSTEM_DEVICE_IO_VALID_INTEGRITY_ERRORS |
        SYSTEM_DEVICE_IO_VALID_TIMEOUTS |
        SYSTEM_DEVICE_IO_VALID_TRANSPORT_ERRORS |
        SYSTEM_DEVICE_IO_VALID_SPI_ERRORS |
        SYSTEM_DEVICE_IO_VALID_SPI_TIMEOUTS |
        SYSTEM_DEVICE_IO_VALID_BUSY_TIMEOUTS;
    s_io_diagnostics.valid_mask = s_io_diagnostics.supported_mask;
    s_io_diagnostics.transport_type = SYSTEM_DEVICE_TRANSPORT_SPI;
    s_io_diagnostics.owner = SYSTEM_DEVICE_IO_OWNER_SELF;
    Sx1281Transport_IrqUnlock(primask);
    init_result = Lora_Init();
    Sx1281Bus_StatusGet(&bus_status);
    Sx1281Transport_IoDiagnosticsUpdate(NULL, &bus_status);
    if (init_result != LORA_INIT_OK)
    {
        return ((bus_status.busy_timeout_count != 0U) ||
                (bus_status.spi_timeout_count != 0U)) ?
            SYSTEM_DEVICE_TIMEOUT : SYSTEM_DEVICE_IO_ERROR;
    }
    if ((Lora_ChipStatusGet(&chip_status) != LORA_DIAG_RESULT_OK) ||
        (chip_status.verified == 0U))
    {
        return SYSTEM_DEVICE_VERIFY_FAILED;
    }
    primask = Sx1281Transport_IrqLock();
    s_initialized = 1U;
    s_health.initialized = 1U;
    s_health.healthy = 1U;
    s_previous_bus_status = bus_status;
    Sx1281Transport_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_Start(void)
{
    Sx1281BusStatus before;
    Sx1281BusStatus after;
    uint32_t primask;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_started <= 1U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_initialized == 0U) { return SYSTEM_DEVICE_NOT_READY; }
    if (s_started != 0U) { return SYSTEM_DEVICE_ALREADY_MATCHED; }
    Sx1281Bus_StatusGet(&before);
    Lora_StartRx();
    Sx1281Bus_StatusGet(&after);
    if ((after.spi_error_count != before.spi_error_count) ||
        (after.spi_timeout_count != before.spi_timeout_count) ||
        (after.busy_timeout_count != before.busy_timeout_count))
    {
        return ((after.busy_timeout_count != before.busy_timeout_count) ||
                (after.spi_timeout_count != before.spi_timeout_count)) ?
            SYSTEM_DEVICE_TIMEOUT : SYSTEM_DEVICE_IO_ERROR;
    }
    primask = Sx1281Transport_IrqLock();
    s_started = 1U;
    s_health.started = 1U;
    Sx1281Transport_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_Stop(void)
{
    uint32_t primask = Sx1281Transport_IrqLock();

    s_started = 0U;
    s_health.started = 0U;
    Sx1281Transport_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_Send(const uint8_t *data,
                                                uint16_t length)
{
    LoraTxEnqueueResult result;

    if ((data == NULL) || (length == 0U) ||
        (length > LORA_MAX_PAYLOAD_LEN) || (length > UINT8_MAX))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    if (s_started == 0U) { return SYSTEM_DEVICE_NOT_READY; }
    result = Lora_TxEnqueue(data, (uint8_t)length);
    if (result == LORA_TX_ENQUEUE_OK) { return SYSTEM_DEVICE_OK; }
    if (result == LORA_TX_ENQUEUE_QUEUE_FULL) { return SYSTEM_DEVICE_NOT_READY; }
    if (result == LORA_TX_ENQUEUE_NOT_INIT) { return SYSTEM_DEVICE_OFFLINE; }
    return SYSTEM_DEVICE_INVALID_ARGUMENT;
}

static SystemDeviceResult Sx1281Transport_Receive(uint8_t *data,
                                                  uint16_t capacity,
                                                  uint16_t *length)
{
    uint8_t packet_length = 0U;
    uint8_t packet[LORA_MAX_PAYLOAD_LEN];
    int8_t rssi = 0;
    int8_t snr = 0;
    LoraRxDequeueResult result;
    uint32_t primask;

    if ((data == NULL) || (length == NULL) || (capacity == 0U))
    {
        return SYSTEM_DEVICE_INVALID_ARGUMENT;
    }
    SILVERSTAR_ASSERT_OBJECT(data, uint8_t, SILVERSTAR_ASSERT_MODULE_DEVICE);
    *length = 0U;
    result = Lora_RxDequeue(packet, &packet_length, &rssi, &snr);
    if (result == LORA_RX_DEQUEUE_EMPTY) { return SYSTEM_DEVICE_NOT_READY; }
    if (result != LORA_RX_DEQUEUE_OK) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    if (packet_length > capacity)
    {
        primask = Sx1281Transport_IrqLock();
        s_health.receive_error_count++;
        Sx1281Transport_IrqUnlock(primask);
        return SYSTEM_DEVICE_IO_ERROR;
    }
    (void)memcpy(data, packet, packet_length);
    *length = packet_length;
    primask = Sx1281Transport_IrqLock();
    s_health.last_rssi_dbm = rssi;
    s_health.last_snr_q4 = (int8_t)(snr * 4);
    Sx1281Transport_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

static void Sx1281Transport_HealthStatsApply(
    SystemTelemetryHealth *health,
    const LoraStats *stats,
    const LoraStats *previous_stats,
    uint64_t now_us)
{
    SILVERSTAR_ASSERT_OBJECT(health, SystemTelemetryHealth,
                             SILVERSTAR_ASSERT_MODULE_DEVICE);
    SILVERSTAR_ASSERT_OBJECT(stats, LoraStats,
                             SILVERSTAR_ASSERT_MODULE_DEVICE);
    if (stats->tx_ok != previous_stats->tx_ok)
    {
        health->last_transmit_timestamp_us = now_us;
    }
    if (stats->rx_ok != previous_stats->rx_ok)
    {
        health->last_receive_timestamp_us = now_us;
    }
    health->transmit_packet_count = stats->tx_ok;
    health->receive_packet_count = stats->rx_ok;
    health->transmit_error_count = stats->tx_timeout + stats->tx_dropped;
    health->receive_error_count = stats->rx_timeout + stats->rx_error +
                                  stats->rx_dropped;
    health->integrity_error_count = stats->rx_crc_error;
    health->last_rssi_dbm = stats->last_rx_rssi;
    health->last_snr_q4 = (int8_t)(stats->last_rx_snr * 4);
}

static void Sx1281Transport_Process(void)
{
    LoraStats stats;
    LoraStats previous_stats;
    LoraChipStatus chip_status;
    Sx1281BusStatus bus_status;
    Sx1281BusStatus previous_bus_status;
    SystemTelemetryHealth health;
    uint64_t now_us;
    uint32_t primask;

    SILVERSTAR_ASSERT(s_initialized <= 1U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    SILVERSTAR_ASSERT(s_started <= 1U,
                      SILVERSTAR_ASSERT_MODULE_DEVICE,
                      SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
    if (s_started == 0U) { return; }
    (void)memset(&chip_status, 0, sizeof(chip_status));
    Lora_Process();
    Lora_GetStats(&stats);
    now_us = PlatformTime_Us();
    primask = Sx1281Transport_IrqLock();
    previous_stats = s_previous_stats;
    previous_bus_status = s_previous_bus_status;
    health = s_health;
    Sx1281Transport_IrqUnlock(primask);
    Sx1281Transport_HealthStatsApply(
        &health, &stats, &previous_stats, now_us);
    Sx1281Bus_StatusGet(&bus_status);
    if (Lora_ChipStatusGet(&chip_status) != LORA_DIAG_RESULT_OK)
    {
        chip_status.verified = 0U;
    }
    health.online = (uint8_t)((health.last_receive_timestamp_us != 0U) &&
        (now_us >= health.last_receive_timestamp_us) &&
        ((now_us - health.last_receive_timestamp_us) <=
         ((uint64_t)LORA_REMOTE_ONLINE_TIMEOUT_MS * 1000ULL)));
    health.healthy = (uint8_t)((chip_status.verified != 0U) &&
        (bus_status.spi_error_count == previous_bus_status.spi_error_count) &&
        (bus_status.spi_timeout_count ==
         previous_bus_status.spi_timeout_count) &&
        (bus_status.busy_timeout_count ==
         previous_bus_status.busy_timeout_count));
    primask = Sx1281Transport_IrqLock();
    Sx1281Transport_IoDiagnosticsUpdate(&stats, &bus_status);
    s_health = health;
    s_previous_stats = stats;
    s_previous_bus_status = bus_status;
    Sx1281Transport_IrqUnlock(primask);
}

static SystemDeviceResult Sx1281Transport_GetInfo(SystemDeviceInfo *info)
{
    if (info == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    info->device_name = "SX1281 Telemetry Transport";
    info->model_name = "E28-2G4M12SX / SX1281";
    info->driver_version = SILVERSTAR_PRODUCT_STRING;
    info->capability_mask = SYSTEM_TELEM_CAP_TX |
                            SYSTEM_TELEM_CAP_RX |
                            SYSTEM_TELEM_CAP_PACKET_BOUNDARY |
                            SYSTEM_TELEM_CAP_LINK_CRC |
                            SYSTEM_TELEM_CAP_RSSI |
                            SYSTEM_TELEM_CAP_SNR;
    info->configuration_mask = 0U;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_GetCapabilities(uint32_t *mask)
{
    SystemDeviceInfo info;

    if (mask == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)Sx1281Transport_GetInfo(&info);
    *mask = info.capability_mask;
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_GetHealth(SystemTelemetryHealth *health)
{
    uint32_t primask;

    if (health == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    primask = Sx1281Transport_IrqLock();
    *health = s_health;
    Sx1281Transport_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_GetIoDiagnostics(
    SystemDeviceIoDiagnostics *diagnostics)
{
    uint32_t primask;

    if (diagnostics == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    primask = Sx1281Transport_IrqLock();
    *diagnostics = s_io_diagnostics;
    Sx1281Transport_IrqUnlock(primask);
    return SYSTEM_DEVICE_OK;
}

static SystemDeviceResult Sx1281Transport_SelfTest(
    SystemDeviceSelfTestResult *result)
{
    if (result == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    (void)memset(result, 0, sizeof(*result));
    result->unsupported_mask = 1U;
    return SYSTEM_DEVICE_UNSUPPORTED;
}

static SystemDeviceResult Sx1281Transport_GetMtu(uint16_t *mtu)
{
    if (mtu == NULL) { return SYSTEM_DEVICE_INVALID_ARGUMENT; }
    *mtu = LORA_MAX_PAYLOAD_LEN;
    return SYSTEM_DEVICE_OK;
}

const char *SystemTelemetry_NameGet(void) { return "SX1281 Transport"; }
SystemDeviceResult SystemTelemetry_Init(void) { return Sx1281Transport_Init(); }
SystemDeviceResult SystemTelemetry_Start(void) { return Sx1281Transport_Start(); }
SystemDeviceResult SystemTelemetry_Stop(void) { return Sx1281Transport_Stop(); }
SystemDeviceResult SystemTelemetry_Send(const uint8_t *data, uint16_t length)
{ return Sx1281Transport_Send(data, length); }
SystemDeviceResult SystemTelemetry_Receive(uint8_t *data,
                                           uint16_t capacity,
                                           uint16_t *length)
{ return Sx1281Transport_Receive(data, capacity, length); }
void SystemTelemetry_Process(void) { Sx1281Transport_Process(); }
SystemDeviceResult SystemTelemetry_InfoGet(SystemDeviceInfo *info)
{ return Sx1281Transport_GetInfo(info); }
SystemDeviceResult SystemTelemetry_CapabilitiesGet(uint32_t *mask)
{ return Sx1281Transport_GetCapabilities(mask); }
SystemDeviceResult SystemTelemetry_HealthGet(SystemTelemetryHealth *health)
{ return Sx1281Transport_GetHealth(health); }
SystemDeviceResult SystemTelemetry_IoDiagnosticsGet(
    SystemDeviceIoDiagnostics *diagnostics)
{ return Sx1281Transport_GetIoDiagnostics(diagnostics); }
SystemDeviceResult SystemTelemetry_SelfTestRun(
    SystemDeviceSelfTestResult *result)
{ return Sx1281Transport_SelfTest(result); }
SystemDeviceResult SystemTelemetry_MtuGet(uint16_t *mtu)
{ return Sx1281Transport_GetMtu(mtu); }
