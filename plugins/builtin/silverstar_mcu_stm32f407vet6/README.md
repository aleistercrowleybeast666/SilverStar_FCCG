# STM32F407VET6

Declarative SilverStar_FCCG builtin `mcu` plugin.

Reference baseline: `main` at `cc0b377ded690556d037a412a55f87fe334c42d0`. Reference-derived files retain the recorded snapshot provenance; FCCG-owned overlays are replayed from `tools/reference_overlays/` and are identified separately in `metadata.source_origins`. Plugin payload is data and is never executed.

This MCU/Platform plugin declares automatic CubeMX matching, the Platform resource-binding ABI, and conditionally selected I2C, Classic CAN, and PWM backends. Production validation remains limited to STM32F407VET6/SS0.5.
