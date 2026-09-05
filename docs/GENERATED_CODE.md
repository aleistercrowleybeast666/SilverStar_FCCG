# Generated Code and Project Ownership

## Output model
生成项目是独立源码工程，生成后可脱离FCCG构建。

```text
<Project>/
  SilverStar.ssproject
  Generated/
  APP/ / System/ / Algorithm/ / Devices/ ...   project-owned component sources
  HardwareGenerated/STM32CubeMX/
  Makefile / Targets/
  .vscode/ / .eide/
  <Project>.ssdecoder                 only when logging enabled
```

## Ownership
- Component payload首次物化后归项目所有，普通Generate不覆盖；
- `Generated/`、descriptor、build/editor metadata由FCCG管理；
- 禁用组件可保留文件但离开SourceGraph；
- `.ssdecoder`只在Logging启用时存在，Logging None时FCCG安全移除自己管理的decoder artifacts。

## Generated glue
包含：resource binding、device instance facade、capability routes、protocol selection、feature macros、project semantics、decoder identity等。Generated不包含运行期动态插件。

## Verified Board
Board插件的`connections.json`决定logical ID；`.ioc`/generated header只解析physical alias。生成后Platform Resource Closure Check验证Project assignment→logical ID→Board alias→physical symbol→platform table完全闭合。

## `.ssdecoder`
固定成员：`manifest.json`、`record_catalog.json`、`project_semantics.json`、`checksums.sha256`、`README.md`。它是纯数据ZIP，不执行代码。Package/semantics当前为1.1，SSLOG container为0.0。

完整`docs/platform/`留在FCCG仓库，不复制到每个生成工程；生成工程摘要继续使用既有README/配置摘要机制。Calibration行为见[共同契约](AIR_CALIBRATION_CONTRACT.md)。
