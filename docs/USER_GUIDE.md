# User guide

## Create a project

Run `python main.py` and choose **New Project**. The one-step dialog asks only for project name, output directory, firmware version, and MCU. Configuration continues through the six main pages in this order:

```text
Project / MCU → Devices → Board & Hardware → Flight Configuration → Generate
```

When only one Core, OS, Protocol Bundle, or Development Environment is installed, FCCG selects it automatically.

## Select Devices first

Choose one installed Device per displayed class, such as JY901B, NEO-M9N, SX1281, and UART Console. The page shows their manifest-declared needs but does not ask for USART, SPI, GPIO pins, DMA streams, or pinmux. Future real `class=actuator` Devices appear through the same manifest mechanism.

## Existing Board flow

```text
Select existing Board plugin
        → Board compatibility is checked against MCU + Devices
        → resource defaults are auto-assigned
        → inspect only if “Advanced Resource Configuration” is needed
        → Generate Project
```

The Board selector keeps incompatible entries identifiable and explains missing resource kinds. Fixed roles cannot be changed; selectable roles show only legal candidates. Reserved resources and declared conflict groups are enforced. The verified SilverStar 0.5 Board needs no CubeMX interaction.

## STM32 custom hardware flow

Only an MCU with a compatible HardwareConfigurationProvider offers custom hardware. The current real implementation is STM32CubeMX for STM32.

```text
Select STM32 MCU
  → select Devices
  → configure peripherals in CubeMX and Generate Code
  → acknowledge the one-time custom-hardware risk warning
  → import the .ioc or complete generated directory
  → FCCG validates MCU/layout/HAL/CMSIS/startup/linker/peripherals/RTOS
  → Device resources are auto-mapped, then reviewed
  → generate and run build/hardware validation
  → optionally Export Board Plugin
```

FCCG does not edit `.ioc`, solve PLL/pinmux/DMA, install CubeMX, or replace CubeMX. A project containing CubeMX FreeRTOS/CMSIS-RTOS2 is rejected because SilverStar supplies its own official FreeRTOS component.

Imported files are copied under `HardwareGenerated/STM32CubeMX/` with a warning README. They are not official SilverStar hardware validation. Confirm clocks, DMA, interrupts, GPIO electrical levels, and power behavior. Importing a changed snapshot later requires a dangerous diff confirmation.

**Export Board Plugin** creates local `.ssplugin` data containing the Board manifest, mapping, provenance/docs, and dedicated hardware payload. Install it normally; a later project selects that Board and no longer needs a CubeMX import.

## Flight Configuration

Strategy controls are created from installed manifests. Current slots are Alignment, INS, Estimator, and Landing. Estimator supports **No fusion**, which removes KF6 sources from both Make and EIDE.

Mode controls are also manifest-driven. Calibration offers Existing/OneFace/SixFace. Deployment supports any combination of Apogee/vertical-velocity, Tilt, and Delay, including none. The collapsed Logging area edits enable, decimation, and periodic interval without creating a separate page.

## Generate and Apply

There is no Generate page and no mandatory Preview step. The global action runs Validate → Resolve → Plan → Apply. Ordinary logging/Mode changes apply directly. A concise diff confirmation appears for component deactivation, conflicts/local source concerns, MCU/target changes, manual EIDE overwrite, or HardwareGenerated replacement.

Component source copied from plugins is never overwritten by normal Apply. FCCG-managed glue and environment metadata are regenerated. Open or drag `SilverStar.ssproject` to restore a project.

## Plugins and Build

Plugins are declarative data. Installation validates/stages an archive and never executes its contents. Details expose IDs, manifests, provenance, and internals under the advanced Plugins page; normal configuration pages use localized names.

Build defaults to Build/Clean/Flash and tool status. Advanced controls expose tool paths, Host Tests, Architecture Check, Power of Ten, Static Analysis, and Artifact Check. Tool overrides remain project-local. Generated firmware builds independently with Make or native EIDE; no Python/FCCG runtime is required.

## Current limits

Only the STM32F407VET6/SilverStar 0.5 reference is fully firmware-build validated. Only STM32 has a manual hardware provider. No Guidance, Control, Control Allocation, actuator implementation, alternate MCU, or Keil environment is supplied. Flash/electrical validation requires actual target hardware and is not implied by generation.
