# 当前进度

日期：2026-09-01

状态：**SilverStar 0.0.10 Software Release Candidate / Pre-Hardware-Validation**。
本轮完成同型号多实例与最小故障切换基础，没有创建Release或Tag、没有推送，也没有修改
外部参考固件或SilverStar_FLP。当前`main`基准HEAD为
`f44f49e7e7163e4260a186d409fd1cdaa6f1ec1b`；本轮变更仍在工作区中。

## 本轮完成

- 官方JY901B、NEO-M9N、SX1281插件各支持最多4个同型号实例；GUI可新增/删除实例，稳定
  Device Instance顺序形成默认备用顺序，显式Canonical Source/Source Override仍决定主源。
- Manifest以通用`instance_resource_binding`声明每实例静态资源结构、accessor、数量符号和
  有界runtime context；每个实例的UART/SPI/GPIO/IRQ/时间资源独立解析，独占资源不可复用。
- JY901B、M9N与SX1281驱动及SX1280 HAL已context化，mutable parser/FIFO/状态/缓存不再
  singleton；生成代码仍只编译一份驱动源码，通过静态instance facade分派。
- 所有IMU/GNSS实例持续写Native日志。IMU只在校准/对准前选择并随后锁定；GNSS按基础
  liveness单向切换；AIR仅因当前本地transport连续10次真实TX timeout单向切换。成功发送
  清零计数，备用耗尽后仍在每个正常周期重试最后source，不做单次无限重试。
- Source-change继续复用现有EVENT Record，仅增加可恢复的old/new/reason语义；AIR M0、维护
  0.0、SSLOG 0.0、Record ID/layout、`.ssdecoder`/Project Semantics 1.1均未升级。

## 本轮实际验收摘要

- `python -m pytest -q`：289 passed in 524.38s（0:08:44）。
- `python -m compileall -q src main.py tools`：通过。
- 最终单实例与2×IMU+2×GNSS+2×Telemetry工程各生成518个文件；多实例Source Graph为
  138个C源文件+1个ASM。
- 多实例`.ssdecoder`：114272 bytes，SHA-256
  `cb735adfe49221ac61f3c3d35bd950668ab2c0f2634769222d98fdb91fb066c0`。
- 单实例/多实例Release与Debug均通过。Release多实例相对单实例增加592 bytes FLASH与
  14600 bytes data+bss；Debug增加1064 bytes FLASH与14600 bytes data+bss。
- Host Tests：56个可执行文件、9139项检查、0失败、8个compile-pass和16个预期拒绝；
  Architecture 255/255；Power of Ten 5895项；GCC `-fanalyzer`和Artifact Check均通过。
- 多实例Release产物：FLASH 261072/524288，main SRAM 91864/131072，CCMRAM
  42872/65536，heap为0。精确构建表和质量门禁见根目录`VALIDATION.md`。

## 只读参考

参考固件保持clean `main`：`cc0b377ded690556d037a412a55f87fe334c42d0`，snapshot digest
`7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`。导入器连续重建
结果确定，FCCG没有修改、格式化、构建、提交或推送该目录。

## 尚未完成

- 双IMU、双GNSS、双radio真实冗余硬件的电气、EMC、射频、HIL与飞行验证。
- I²C外部上拉及PWM波形、极性、安全电平的真实电气测试。
- 第二套真实硬件平台的双平台内部测试；当前合成H743 fixture不等于H7支持。
- 烧录、SD介质耐久、射频、执行器台架、HIL与飞行验证。
- 后续SilverStar_FLP：每次导入一个日志、严格匹配`.ssdecoder`、不兼容未发布旧日志，且
  离线算法比较不受机载算法清单限制。
