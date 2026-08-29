# 当前进度

日期：2026-08-30

状态：**Software Release Candidate / Pre-Hardware-Validation（内部软件候选版 / 硬件验证前）**。
本轮没有创建Tag、没有推送、没有发布，也没有声称已完成烧录、电气、台架或飞行验证。

## 已完成

- 工程格式升级为10；格式0–9可确定迁移并只写出格式10。
- 自定义CubeMX导入先读取真实MCU，再匹配唯一兼容Platform；不再隐式预锁F407。
- 36个builtin插件、48个builtin/schema JSON文档通过严格加载。
- 新增单实例`silverstar.device.storage.sd_sdio_fatfs`物理存储Device：
  - Device拥有`Devices/Storage/SdSdioFatFs`中的Storage/Log Sink实现；
  - Board只拥有已验证的SDIO/Time语义映射；
  - CubeMX拥有SDIO与FatFs App/Target glue；
  - MCU/Platform拥有受控FatFs core与HAL provider；
  - Source Graph只编译一个owner。
- 旧格式9生成工程保留原Board路径项目源码，但迁移会无冲突地新增Device路径；旧文件不覆盖、不删除、不参与构建。
- CubeMX FatFs门禁检查唯一对象/路径/Driver符号、App/Target、SDIO、RX/TX DMA、IRQ、版本与来源策略。
- HAL时间基准从生成源码动态识别handle、instance、IRQ、1 MHz counter与1 kHz tick；不在Python或renderer中固定TIM1，并拒绝SysTick、缺失/歧义、频率/IRQ错误以及与PWM复用。
- `module_providers`把CubeMX初始化/HAL/middleware provider和consumer wrapper分开；实际inventory与被选consumer共同决定激活，不做compile-all。
- I²C保持7-bit阻塞master与8/16-bit寄存器访问边界；PWM保持CubeMX拥有模式/极性/频率与安全端点；Classic CAN仍为`reserved`，普通consumer不能启用。
- Hardware Connection显示MCU、CubeMX/Firmware Package、HAL/CMSIS来源、Platform锁、时间基准、FatFs/SDIO与Storage有效性；中英文均由翻译键提供。

## 本轮实际验证

- Python：3.14.0；PySide6：6.10.1。
- `python -m pytest -q`：208 passed in 356.93s。
- `python -m compileall -q src tools main.py`：通过。
- 默认SS0.5新工程：首次503文件；二次规划471 `PRESERVE` + 32 `UNCHANGED`，0增删改，Ready；Source Graph 136个C源文件。
- 默认工程Release/Debug均通过；Host Tests为50个EXE、8754项检查、0失败、8个应通过编译门禁、16个预期编译拒绝。
- Architecture：250项、0失败。
- Power of Ten：5603项，92个第一方C文件，2074个函数，通过。
- Arm GCC `-fanalyzer`静态分析：通过。
- Artifact：通过；FLASH 250252/524288，主SRAM 77172/131072，CCMRAM 42872/65536，heap=0。
- 默认`.ssdecoder`：102035 bytes，SHA-256
  `67f2eb4f5c96ec28dcbe4ef2d0b22fbcb1c731a88163a596812c6dc92b7cb6cc`，仍只有5个声明式数据文件且不含可执行代码。
- 自定义CubeMX F407最终迁移后Release与Host Tests通过；二次规划1760 `PRESERVE` + 32 `UNCHANGED`，Ready。

完整命令、哈希、内存数据与限制见根目录`VALIDATION.md`。

## 只读参考

参考固件始终只读：`C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5`，clean `main`，
HEAD `cc0b377ded690556d037a412a55f87fe334c42d0`，提交主题
`完善同能力多实例与日志配置契约`。本轮只读取和复制到FCCG staged builtin payload，没有修改、构建、提交或推送参考固件。

## 剩余限制

- 完整固件构建验证范围仍只有STM32F407VET6 + SS0.5；H7/G4/其他MCU没有生产插件与验证结果。
- 软件`supported`不等于硬件`verified`。I²C外部上拉、PWM波形/安全电平、SD卡介质行为、烧录、台架与飞行必须后续实机验证。
- 当前没有普通CAN consumer，没有连续控制执行器、Guidance、Control、Control Allocation、Multi-EKF或传感器投票/故障切换。
- `.ssdecoder`仍是数据包；本轮没有实现可执行日志解析器、多版本解析插件或FLP导入。
- 当前Board/Environment没有声明已验证flash能力，因此GUI/Make/VS Code/EIDE不生成上传动作。
