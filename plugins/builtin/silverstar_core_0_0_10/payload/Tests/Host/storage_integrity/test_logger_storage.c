/* Real LoggerBus -> LoggerTask -> LogSink -> Storage -> FatFs -> diskio.
 * Only time, RTOS scheduling and the SD card are Host models. */
#define main Fixture_DiskMain
#define vTaskDelay Fixture_BaseDelay
#define xQueueReceive Fixture_BaseReceive
#include "test_storage_integrity.c"
#undef main
#undef vTaskDelay
#undef xQueueReceive
#include <setjmp.h>
#include "app_tasks.h"
#include "logger_bus.h"
#include "logger_task.h"
#include "platform_critical.h"
#include "system_log_policy.h"
#include "system_storage_if.h"
#include "system_startup.h"
#include "system_user_config.h"

FATFS SDFatFS;
char SDPath[4];
static jmp_buf s_exit;
static uint8_t s_running;
static uint8_t s_in_producer;
static uint8_t s_overflow_test;
static uint8_t s_startup_overflow_test;
static uint8_t s_burst_done;
static uint8_t s_final_armed;
static uint32_t s_produced;
static uint64_t s_next_production_us;
static uint64_t s_clock_us;
static uint64_t s_start_us;
static uint64_t s_production_begin_us;
static uint64_t s_production_end_us;
static uint32_t s_start_accepted;
static SystemStartupReport s_startup;

PlatformCriticalState PlatformCritical_Enter(void) { return 0U; }
void PlatformCritical_Exit(PlatformCriticalState state) { (void)state; }
uint64_t PlatformTime_Us(void) { return s_clock_us + (uint64_t)s_ticks * 1000ULL; }
uint64_t SystemTime_GetMonotonicUs(void) { s_clock_us += 20ULL; return PlatformTime_Us(); }
const SystemStartupReport *SystemStartup_GetReport(void) { return &s_startup; }

static LoggerBusResult Fixture_RecordPush(uint32_t index, uint64_t now)
{
    FlightLogRecord record;
    memset(&record, 0, sizeof(record));
    /* Every required record appears before START; native sensor mix follows.
     * Caller RAM is overwritten on return to verify queue copy ownership. */
    if (index == 5U) { return LoggerBus_AlignmentResultPush(now, &record.payload.alignment_result); }
    if (index == 6U) { return LoggerBus_CalibrationResultPush(now, &record.payload.calibration_result); }
    if (index == 7U || index == 1000U) { return LoggerBus_MissionConfigPush(now); }
    if (index == 8U) { return LoggerBus_InitialStatePush(now, &record.payload.initial_state); }
    if (index == 1001U)
    { return LoggerBus_EventPush(now, FLIGHT_LOG_EVENT_MISSION_START, 0U, 0U); }
    if ((index % 1000U) == 9U)
    {
        record.payload.stats.logger_queue_overflow_count = LoggerBus_OverflowCountGet();
        return LoggerBus_StatsPush(now, &record.payload.stats);
    }
    if (index > 11U && index % 31U == 0U)
    { return LoggerBus_EstimatorPush(now, index, &record.payload.estimator); }
    switch (index % 5U)
    {
        case 0U: return LoggerBus_ImuNativePush(now, index, &record.payload.imu_native);
        case 1U: return LoggerBus_ImuCorrectedPush(now, index, &record.payload.imu_corrected);
        case 2U: return LoggerBus_GnssNativePush(now, index, &record.payload.gnss_native);
        case 3U: return LoggerBus_BaroNativePush(now, index, &record.payload.baro_native);
        default: return LoggerBus_HardwareQuaternionNativePush(now, index, &record.payload.hw_quat_native);
    }
}

static void Fixture_Produce(void)
{
    uint64_t now;
    if (!s_running || s_in_producer) { return; }
    s_in_producer = 1U;
    now = PlatformTime_Us();
    while (s_produced < TEST_RECORD_COUNT && now >= s_next_production_us)
    {
        LoggerBusResult result;
        if (s_produced == 0U) { s_production_begin_us = now; }
        if (s_produced == 1000U)
        {
            LoggerBusDiagnostics diagnostics;
            s_start_us = now;
            (void)LoggerBus_DiagnosticsGet(&diagnostics);
            s_start_accepted = diagnostics.accepted_count;
        }
        result = Fixture_RecordPush(s_produced++, s_next_production_us);
        if (result != LOGGER_BUS_RESULT_OK && result != LOGGER_BUS_RESULT_FULL) { abort(); }
        s_next_production_us += s_produced < 1000U ? 10000ULL : 2000ULL;
        s_production_end_us = now;
    }
    if (s_overflow_test && !s_burst_done && s_produced > 1001U)
    {
        /* Deliberate finite overload, separate from normal rate/SD latency. */
        for (unsigned index = 0U; index < 500U; index++)
        { (void)LoggerBus_EventPush(now, FLIGHT_LOG_EVENT_SAMPLE_GAP, index, 0U); }
        for (unsigned index = 0U; index < 100U; index++)
        {
            FlightLogEstimatorRecord estimator = {0};
            (void)LoggerBus_EstimatorPush(now, index, &estimator);
        }
        s_burst_done = 1U;
    }
    if (s_produced == TEST_RECORD_COUNT && LoggerBus_Count() == 0U && !s_final_armed)
    {
        FlightLogStatsRecord stats = {0};
        stats.logger_queue_overflow_count = LoggerBus_OverflowCountGet();
        if (LoggerBus_StatsPush(now, &stats) != LOGGER_BUS_RESULT_OK) { abort(); }
        /* Time already exceeds the normal landing grace deadline. */
        if (LoggerBus_FinalizationArm(1ULL) != LOGGER_BUS_RESULT_OK) { abort(); }
        s_final_armed = 1U;
    }
    s_in_producer = 0U;
}

void vTaskDelay(TickType_t ticks)
{
    Fixture_BaseDelay(ticks);
    Fixture_Produce();
    if (s_running && LoggerBus_FinalizationStateGet() == LOGGER_BUS_FINALIZATION_FINALIZED)
    { longjmp(s_exit, 1); }
    if (s_running && PlatformTime_Us() > 300000000ULL)
    {
        fprintf(stderr, "Logger exceeded the simulated completion deadline\n");
        s_failures++;
        longjmp(s_exit, 2);
    }
}

BaseType_t xQueueReceive(QueueHandle_t queue, void *data, TickType_t ticks)
{
    BaseType_t result = Fixture_BaseReceive(queue, data, ticks);
    Fixture_Produce();
    return result;
}

static int Test_Writer(const char *output)
{
    LoggerBusDiagnostics bus;
    LoggerTaskDiagnostics task;
    SystemStorageHealth storage;
    FILE *exported;
    uint8_t buffer[513];
    UINT read;
    CHECK(LoggerBus_Init() == LOGGER_BUS_RESULT_OK);
    for (uint16_t index = 0U; index < SystemLogPolicy_StreamCountGet(); index++)
    {
        SystemLogStreamConfig config;
        CHECK(SystemLogPolicy_StreamByIndexGet(index, &config) == SYSTEM_DEVICE_OK);
        config.enabled = 1U;
        config.decimation = 1U;
        CHECK(SystemLogPolicy_StreamConfigure(&config) == SYSTEM_DEVICE_OK);
    }
    s_startup.completed = 1U;
    s_startup.passed = 1U;
    if (s_startup_overflow_test)
    {
        for (unsigned index = 0U; index < 200U; index++)
        { (void)LoggerBus_EventPush(PlatformTime_Us(), FLIGHT_LOG_EVENT_BOOT, index, 0U); }
    }
    s_next_production_us = PlatformTime_Us() + 10000ULL;
    s_running = 1U;
    if (setjmp(s_exit) == 0) { AppTask_Logger(NULL); }
    s_running = 0U;
    CHECK(s_failures == 0U);
    CHECK(LoggerBus_DiagnosticsGet(&bus) == LOGGER_BUS_RESULT_OK);
    CHECK(LoggerTask_DiagnosticsGet(&task) == SYSTEM_DEVICE_OK && task.io_fault == 0U);
    CHECK(SystemStorage_HealthGet(&storage) == SYSTEM_DEVICE_OK && storage.error_count == 0U);
    CHECK(bus.normal_count == 0U && bus.estimator_count == 0U);
    CHECK(bus.accepted_count == bus.dequeued_count);
    CHECK(s_overflow_test ? bus.overflow_count > 0U : bus.overflow_count == 0U);
    CHECK(f_mount(NULL, "0:", 0U) == FR_OK);
    CHECK(f_mount(&s_fs, "0:", 1U) == FR_OK);
    CHECK(f_open(&s_file, "0:/SS0000.BIN", FA_READ) == FR_OK);
    CHECK(f_size(&s_file) == storage.bytes_written);
    exported = fopen(output, "wb");
    CHECK(exported != NULL);
    do
    {
        CHECK(f_read(&s_file, buffer + 1U, 512U, &read) == FR_OK);
        CHECK(fwrite(buffer + 1U, 1U, read, exported) == read);
    } while (read != 0U);
    CHECK(fclose(exported) == 0 && f_close(&s_file) == FR_OK);
    printf("LOGGER_STORAGE accepted=%lu drops=%lu hwm=%u/%u max_write_us=%llu max_sync_us=%llu max_iteration_us=%llu\n",
        (unsigned long)bus.accepted_count, (unsigned long)bus.overflow_count,
        bus.normal_high_water, bus.estimator_high_water,
        (unsigned long long)storage.max_write_latency_us,
        (unsigned long long)storage.max_sync_latency_us,
        (unsigned long long)task.max_iteration_us);
    printf("LOGGER_RATE pre_records=1000 pre_us=%llu post_records=39000 post_us=%llu pre_accepted=%lu\n",
        (unsigned long long)(s_start_us - s_production_begin_us),
        (unsigned long long)(s_production_end_us - s_start_us), (unsigned long)s_start_accepted);
    return 1;
}

int main(int argc, char **argv)
{
    if (argc != 2 && argc != 3) { return 2; }
    if (argc == 3)
    {
        s_overflow_test = 1U;
        s_startup_overflow_test = (uint8_t)(strcmp(argv[2], "startup-overflow") == 0);
    }
    if (FATFS_LinkDriver(&SD_Driver, SDPath) != 0U) { return 3; }
    if (f_mkfs(SDPath, FM_FAT | FM_SFD, 512U, s_work, sizeof(s_work)) != FR_OK) { return 4; }
    if (f_mount(&s_fs, SDPath, 1U) != FR_OK) { return 5; }
    return Test_Writer(argv[1]) ? 0 : 1;
}
