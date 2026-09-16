# SilverStar_FCCG Documentation

本目录分成两层：

1. **FCCG软件文档**：本目录根部，描述配置器、插件、工程模型、生成器、构建和GUI；
2. **SilverStar平台规范**：[`platform/`](platform/)，描述飞控接口、状态机、算法、AIR/维护/SSLOG和验证要求。

## FCCG软件文档
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`PLUGIN_FORMAT.md`](PLUGIN_FORMAT.md)
- [`PROJECT_FORMAT.md`](PROJECT_FORMAT.md)
- [`GENERATED_CODE.md`](GENERATED_CODE.md)
- [`BUILD.md`](BUILD.md)
- [`COMPONENTS.md`](COMPONENTS.md)
- [`USER_GUIDE.md`](USER_GUIDE.md)
- [`CURRENT_PROGRESS.md`](CURRENT_PROGRESS.md)
- [飞前日志策略](PREFLIGHT_LOGGING.md)
- [`GUI_STYLE_GUIDE.md`](GUI_STYLE_GUIDE.md)

## 共同协议契约
- [`AIR_CALIBRATION_CONTRACT.md`](AIR_CALIBRATION_CONTRACT.md)

当前平台版本为 SilverStar 0.0.10；AIR仍为M0，Maintenance/SSLOG仍为0.0，`.ssdecoder`/Project Semantics为1.2（拒绝1.1）。

GUI规范同时参见[CXYL Python GUI Style Guide](CXYL_Python_GUI_STYLE_GUIDE.md)。完整平台条目见[文档清单](platform/details/DOCUMENT_LIST.md)，实际验收快照见[VALIDATION](../VALIDATION.md)。

## Algorithm configuration contract

Pure INS/KF6 实际参数、单位、P0/Q/R 转换与 decoder 1.2 边界见[算法参数契约](ALGORITHM_PARAMETERS.md)。默认值保留旧算法数值行为；公式、时序与融合策略不变。
