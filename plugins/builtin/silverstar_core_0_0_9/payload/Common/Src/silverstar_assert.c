#include "silverstar_assert.h"

#include <stddef.h>

static volatile SilverStarAssertFaultRecord s_assert_fault;

void SilverStarAssert_Check(uint8_t condition,
                            SilverStarAssertModuleId module_id,
                            const char *file_name,
                            uint32_t line,
                            SilverStarAssertReasonId reason_id)
{
    if (condition == 0U)
    {
        SilverStarAssert_Fail(module_id, file_name, line, reason_id);
    }
}

void SilverStarAssert_ObjectCheck(const volatile void *object,
                                  uint32_t alignment,
                                  SilverStarAssertModuleId module_id,
                                  const char *file_name,
                                  uint32_t line)
{
    uintptr_t address;

    SilverStarAssert_Check((uint8_t)(object != NULL), module_id, file_name,
                           line, SILVERSTAR_ASSERT_REASON_NULL_POINTER);
    address = (uintptr_t)object;
    SilverStarAssert_Check(
        (uint8_t)((alignment != 0U) && ((address % alignment) == 0U)),
        module_id, file_name, line,
        SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
}

SILVERSTAR_NORETURN void SilverStarAssert_Fail(
    SilverStarAssertModuleId module_id,
    const char *file_name,
    uint32_t line,
    SilverStarAssertReasonId reason_id)
{
    s_assert_fault.file_name = file_name;
    s_assert_fault.timestamp_us = 0U;
    s_assert_fault.line = line;
    s_assert_fault.sequence++;
    s_assert_fault.module_id = module_id;
    s_assert_fault.reason_id = reason_id;
    s_assert_fault.timestamp_valid = 0U;
    s_assert_fault.active = 1U;
    __sync_synchronize();
    __builtin_trap();
    for (;;)
    {
        /* Deterministic fail-stop if a debugger resumes after the trap. */
    }
}

uint8_t SilverStarAssert_FaultedGet(void)
{
    return s_assert_fault.active;
}

uint8_t SilverStarAssert_FaultRecordGet(SilverStarAssertFaultRecord *record)
{
    if (record == NULL)
    {
        return 0U;
    }
    record->file_name = s_assert_fault.file_name;
    record->timestamp_us = s_assert_fault.timestamp_us;
    record->line = s_assert_fault.line;
    record->sequence = s_assert_fault.sequence;
    record->module_id = s_assert_fault.module_id;
    record->reason_id = s_assert_fault.reason_id;
    record->timestamp_valid = s_assert_fault.timestamp_valid;
    record->active = s_assert_fault.active;
    return record->active;
}
