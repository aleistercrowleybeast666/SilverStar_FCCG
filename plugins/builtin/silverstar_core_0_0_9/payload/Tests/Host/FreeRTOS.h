#ifndef __FREERTOS_H
#define __FREERTOS_H

#include <stdint.h>

typedef uint32_t TickType_t;

#define pdMS_TO_TICKS(milliseconds_) ((TickType_t)(milliseconds_))

#endif /* __FREERTOS_H */
