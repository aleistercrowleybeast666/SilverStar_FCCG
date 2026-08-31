# 当前进度

日期：2026-08-31

状态：**SilverStar 0.0.10 Software Release Candidate / Pre-Hardware-Validation**。
本轮没有创建 Release 或 Tag，也没有修改外部参考固件或 SilverStar_FLP。按用户最后指令，
代码将以 `修改测试与文档，完成基础功能` 提交并推送；不可变 commit hash 在提交完成后由
`git rev-parse HEAD` 获取并在最终交接中报告。

## 已冻结

- FCCG应用、新工程平台身份、生成固件、Embedded Core和官方SilverStar builtin发布列车
  统一为0.0.10；AIR M0、维护/日志0.0、`.ssdecoder`/project-semantics 1.1、FreeRTOS 11.3.0、
  SS0.5和STM32F407VET6保持独立版本。
- 纯相对路径校验不再依赖进程cwd；真实文件写入仍禁止以文件系统根为授权区。
- Build Target Profile由匹配的MCU/Platform插件声明并作为工程完整性锁保存；当前已验证值为
  `SilverStar_F407`。合成H743仅用于架构测试，不构成产品支持。
- 校准只显示单面/六面且默认空选；空选确定性进入NONE/READY单位校正。启用日志时
  `CALIBRATION_RESULT`仍为必须快照，Record ID/layout和SSLOG 0.0不变。
- 三协议8种组合、校准4种选择、默认F407生成/增量、`.ssdecoder` 1.1与统一Source Graph已复核。

## 本轮实际验收摘要

- `python -m pytest -q`：276 passed in 478.64s（0:07:58）。
- `python -m compileall -q src main.py tools`：通过。
- 默认工程首次生成504个文件；二次生成0新增、0修改、472个工程自有文件保持，Ready且无
  missing/stale；Source Graph为136个C源文件+1个ASM。
- 默认`.ssdecoder`：102390 bytes，SHA-256
  `696d09226fc8a574602514e342667b46e7cf4e707c1f580740b62640927482d3`。
- Release/Debug、Host Tests、Architecture、Power of Ten、GCC `-fanalyzer` Static Analysis和
  Artifact Check全部通过；精确命令、内存、计数和哈希见根目录`VALIDATION.md`。
- 8种Telemetry/Maintenance/Logging组合的16个Release/Debug构建及任务函数/栈/TCB符号审计
  全部通过；4种校准选择完成代表性编译，默认空选另完成完整Host Tests。

## 只读参考

参考固件保持clean `main`：`cc0b377ded690556d037a412a55f87fe334c42d0`，snapshot digest
`7998cace3e609d4e0c3f16f8d9e4cdf531f3f82939670638d4fe4d02f3c4e942`。导入器连续重建
结果确定，FCCG没有修改、格式化、构建、提交或推送该目录。

## 尚未完成

- I²C外部上拉及PWM波形、极性、安全电平的真实电气测试。
- 第二套真实硬件平台的双平台内部测试；当前合成H743 fixture不等于H7支持。
- 烧录、SD介质耐久、射频、执行器台架、HIL与飞行验证。
- 后续SilverStar_FLP：每次导入一个日志、严格匹配`.ssdecoder`、不兼容未发布旧日志，且
  离线算法比较不受机载算法清单限制。
