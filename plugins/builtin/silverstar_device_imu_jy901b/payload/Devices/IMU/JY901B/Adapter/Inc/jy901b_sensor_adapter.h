#ifndef __JY901B_SENSOR_ADAPTER_H
#define __JY901B_SENSOR_ADAPTER_H

#include "system_imu_if.h"
#include "jy901b_device.h"

SystemDeviceResult Jy901bAdapter_SharedInit(void);
SystemDeviceResult Jy901bAdapter_SharedStart(void);
SystemDeviceResult Jy901bAdapter_SharedStop(void);
void Jy901bAdapter_SharedProcess(void);
SystemDeviceResult Jy901bAdapter_SharedHealthGet(SystemDeviceHealth *health);
SystemDeviceResult Jy901bAdapter_FrameHealthGet(IMUFrameType frame_type,
                                                 SystemDeviceHealth *health);
SystemDeviceResult Jy901bAdapter_SharedSnapshotGet(IMUData *snapshot);
SystemDeviceResult Jy901bAdapter_ConfigAccessCheck(void);
SystemDeviceResult Jy901bAdapter_AlgorithmStage(IMUAlgorithm algorithm);
SystemDeviceResult Jy901bAdapter_OutputRateValueGet(uint16_t rate_hz,
                                                     IMUOutputRate *value);

#endif /* __JY901B_SENSOR_ADAPTER_H */
