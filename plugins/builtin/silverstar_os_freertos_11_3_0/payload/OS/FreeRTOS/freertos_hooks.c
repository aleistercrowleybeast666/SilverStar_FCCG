#include "FreeRTOS.h"
#include "task.h"

#include "platform_memory.h"
#include "silverstar_assert.h"

static StaticTask_t s_idle_task_control;
static PLATFORM_CPU_FAST_BSS StackType_t
    s_idle_task_stack[configMINIMAL_STACK_SIZE];

void vApplicationGetIdleTaskMemory(
    StaticTask_t **task_control,
    StackType_t **stack,
    configSTACK_DEPTH_TYPE *stack_words)
{
    if ((task_control == NULL) || (stack == NULL) || (stack_words == NULL))
    {
        return;
    }
    *task_control = &s_idle_task_control;
    *stack = s_idle_task_stack;
    *stack_words = configMINIMAL_STACK_SIZE;
}

void vApplicationStackOverflowHook(TaskHandle_t task, char *task_name)
{
    (void)task;
    (void)task_name;
    taskDISABLE_INTERRUPTS();
    SilverStarAssert_Fail(SILVERSTAR_ASSERT_MODULE_OS, __FILE__,
                          (uint32_t)__LINE__,
                          SILVERSTAR_ASSERT_REASON_STATE_INVARIANT);
}
