# SilverStar_FCCG 当前进度

更新时间：2026-08-29（Asia/Shanghai）

状态：内部固件插件重构已完成。项目格式为 8，33 个 builtin 插件严格扫描通过；默认 SS0.5 工程的生成、增量保留、Release/Debug、Host Tests、架构、Power of Ten、静态分析和产物检查全部通过。外部参考固件始终只读。

## 本轮完成

- 原 `silverstar.protocol.reference_v0` 三协议 bundle 已退出生产目录，拆分为遥测、维护、日志三个独立且各自必选的 Protocol 插件。工程分别锁定 component、version、Profile 和 manifest SHA-256；格式 7 旧工程可确定性迁移并只写出格式 8。
- AIR M0、Serial Maintenance 0.0、SSLOG 0.0 的 C 源字节保持不变。Importer 会校验四个协议源码 hash，并在只读 reference snapshot 上重放 FCCG-owned overlays。
- `.ssdecoder` 从所选 Logging 插件合并 Record Catalog，并携带三协议、Core、Platform/Board/CubeMX、设备实例、算法、资源和日志语义；包仍只有五个数据文件，不含 Python、DLL、脚本或其他可执行代码。
- 设备页已删除 MCU 选择。已知 Board 或导入 CubeMX 的 `.ioc` 提供精确 part/family/package/core，FCCG 再按 exact 优先、priority/specificity 规则自动匹配一个已安装 MCU/Platform 插件；零候选和并列候选都会明确失败。
- Python renderer 不再写死 STM32F4 resource header/getter。F407 插件声明 Platform ABI、匹配规则、资源 collection/getter/struct contract、能力、限制和条件 backend；虚拟非 F4 fixture 证明同一 renderer 不依赖 F4 符号。
- FCCG-owned F407 overlay 实现阻塞式 7-bit I²C master/memory-register API、Classic CAN 2.0/bxCAN 单 owner API、固定频率普通 PWM permille duty API。三者均静态分配、参数检查、有界操作，并按真实分配裁剪。
- CubeMX inventory/resolver 已扩展 I²C、Classic CAN/FDCAN 区分和逐通道 PWM。它检查 Platform capability、I²C bus/address/composite device、CAN 单 owner、PWM channel 独占和同 TIM base-frequency 一致性。
- Source Graph 只从激活 backend 选择 Platform adapter 与准确 provider HAL source；EIDE 会排除同目录未激活 adapter，继续与 Make 使用同一真相。
- Device manifest 的 `device_category` 为严格命名空间。GUI 只把 `sensor.imu`/`sensor.gnss` 放入主要传感器，其余合法 `sensor.*` 自动进入其他传感器；link/storage/actuator/indicator 分组独立，拼写错误或未知 namespace 在扫描阶段拒绝。
- 每个指示器插件仍为 singleton，但 indicator 类允许多个不同角色；最终是否能同时启用仍由真实 GPIO resolver 决定。
- 每个 manifest 只保存稳定的 reference source kind/commit/snapshot digest；本机路径、导入时间和审计信息仅保留在 catalog provenance，不会造成生成工程无意义 stale。
- EIDE build-owned 字段再次合并时保持 EIDE 兼容缩进和长编译参数单行格式；未激活后端通过 `excludeList` 保持 Make/EIDE 源码图完全一致。

## 最终验收

默认工程：`tests/acceptance_internal_firmware_plugin_refactor_20260829/`。

- Python：`python -m compileall -q src main.py tools tests` 返回 0；两个不可访问的历史测试输出目录产生 `Can't list` 提示，但没有 Python 编译失败。
- 插件：33 个严格 manifest、45 个 builtin/schema JSON 文档成功加载；完整回归 `164 passed in 338.61s`。
- 生成：首次 499 files added；生成后、重载后、第二次应用后均 Ready；第二次计划为 468 `PRESERVE` + 31 `UNCHANGED`，没有改写用户组件源码。
- 默认 Source Graph：137 个唯一 C 源；I²C/CAN/PWM adapter 和无关 HAL I²C/CAN source 均为空。
- `.ssdecoder`：95,538 bytes，SHA-256 `5e5148244f71e936b2dbf3fd86562dd43596a4f5d4e917a4def33e8c98dc97b2`；三协议身份和 checksum 校验通过。
- Release：text 247,632 / data 1,160 / bss 116,688；BIN 248,792；ELF 2,627,188 bytes。
- Debug：text 261,224 / data 1,160 / bss 116,696；BIN 262,384；ELF 3,965,184 bytes。
- Host Tests：52 executables，8,784 checks，0 failures；8 个 compile-pass、16 个 expected compile rejection；Golden sample 通过。
- Architecture：250 checks，0 failures。
- Power of Ten：5,596 checks，92 个第一方 C 文件，2,073 个函数，通过。
- Arm GCC `-fanalyzer`：独立 StaticAnalysis tree 全量编译、链接、SIZE、HEX、BIN 通过。
- Artifact Check：FLASH 248,792；main SRAM 74,976；CCMRAM 42,872；heap reservation/runtime symbols 均为 0。
- 可选 F407 backend：Host mock 以 GCC C11 `-Werror -pedantic` 编译并运行边界测试通过；同一三份 backend 源以 Arm GNU 对 synthetic HAL contract 执行 `-fsyntax-only` 通过。

## 当前支持边界

- 当前完整固件生成/构建验证范围仍是 STM32F407VET6 + SS0.5 + STM32CubeMX；通用 Platform contract 不代表 H7/G4 或其他 MCU 已受支持。
- 默认 SS0.5 `.ioc` 没有 I²C/CAN/PWM 配置及相应可选 HAL 文件，因此这些 backend 正确地不进入默认工程。仍需用真实启用了各外设的自定义 CubeMX 工程补做硬件级 Arm build、板上和电气验证。
- I²C 不宣称通用 repeated-start；Classic CAN 不支持 CAN FD、router 或多 consumer；PWM 不支持 complementary/dead-time、动态频率、servo、Guidance、Control 或 Control Allocation。
- `.ssdecoder` 只提供声明式解码配置；FLP 的可信 container decoder 安装/导入与实际日志解析仍是后续集成工作。
- EIDE 原生 UI 编译、上传/烧录和硬件测试未自动执行；已验证的是 EIDE/Make Source Graph 一致性与生成 Make 工程。

## 工作区说明

外部参考固件 `C:/Users/chdxm/Desktop/stm32-1/Flight_Controller0.5` 只读核对前后均为 clean `main`、HEAD `cc0b377ded690556d037a412a55f87fe334c42d0`。FCCG 的 Platform/Protocol 扩展来源位于 `tools/reference_overlays/`，重新导入不会覆盖或伪装其所有权。
