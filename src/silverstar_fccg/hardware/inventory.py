from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from silverstar_fccg.project.model import HardwareResource


@dataclass(frozen=True, slots=True)
class PinInventory:
    pin: str
    signal: str
    label: str = ""
    mode: str = ""
    alternate_function: str = ""
    pull: str = ""
    output_default: str = ""
    exti_line: int | None = None


@dataclass(frozen=True, slots=True)
class DmaInventory:
    request: str
    instance: str
    direction: str = ""
    mode: str = ""
    priority: str = ""
    channel: str = ""


@dataclass(frozen=True, slots=True)
class NvicInventory:
    irq: str
    enabled: bool
    preempt_priority: int | None = None
    sub_priority: int | None = None


@dataclass(frozen=True, slots=True)
class PeripheralInventory:
    instance: str
    kind: str
    pins: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    dma: tuple[DmaInventory, ...] = ()
    irq: NvicInventory | None = None


@dataclass(frozen=True, slots=True)
class HardwareInventory:
    mcu_part: str
    mcu_family: str
    package: str
    core: str
    pins: tuple[PinInventory, ...]
    uarts: tuple[PeripheralInventory, ...]
    spis: tuple[PeripheralInventory, ...]
    i2cs: tuple[PeripheralInventory, ...]
    adcs: tuple[PeripheralInventory, ...]
    timers: tuple[PeripheralInventory, ...]
    pwms: tuple[PeripheralInventory, ...]
    cans: tuple[PeripheralInventory, ...]
    dmas: tuple[DmaInventory, ...]
    nvic: tuple[NvicInventory, ...]
    clocks: dict[str, Any]
    peripherals: tuple[str, ...]
    issues: tuple[str, ...] = ()

    def Dictionary_Get(self) -> dict[str, Any]:
        return asdict(self)

    def HardwareResources_Get(self) -> tuple[HardwareResource, ...]:
        resources: list[HardwareResource] = []
        groups = (
            (self.uarts, "platform_uart.h", "huart"),
            (self.spis, "platform_spi.h", "hspi"),
            (self.i2cs, "platform_i2c.h", "hi2c"),
            (self.adcs, "platform_adc.h", "hadc"),
            (self.timers, "platform_timer.h", "htim"),
            (self.pwms, "platform_pwm.h", "htim"),
            (self.cans, "platform_can.h", "hcan"),
        )
        kind_indexes: dict[str, int] = {}
        for peripherals, header, handle_prefix in groups:
            for peripheral in peripherals:
                index = kind_indexes.get(peripheral.kind, 0)
                kind_indexes[peripheral.kind] = index + 1
                suffix_match = re.search(r"(\d+)", peripheral.instance)
                suffix = suffix_match.group(1) if suffix_match else str(index + 1)
                metadata = {
                    "c_id": f"PLATFORM_{peripheral.kind.upper()}_{index + 1}",
                    "header": header,
                    "handle": f"{handle_prefix}{suffix}",
                    "logical_index": index,
                    "peripheral": peripheral.instance,
                    "physical_resource": peripheral.instance,
                    "pins": dict(peripheral.pins),
                    **dict(peripheral.settings),
                    "dma": [asdict(item) for item in peripheral.dma],
                }
                if peripheral.irq is not None:
                    metadata["irq"] = asdict(peripheral.irq)
                    metadata["irq_enabled"] = int(peripheral.irq.enabled)
                resources.append(
                    HardwareResource(peripheral.instance, peripheral.kind, metadata)
                )

        gpio_pins = tuple(
            pin
            for pin in self.pins
            if pin.signal in {"GPIO_Input", "GPIO_Output"}
            or "EXTI" in pin.signal.upper()
            or "GPXTI" in pin.signal.upper()
        )
        for index, pin in enumerate(sorted(gpio_pins, key=lambda value: value.pin)):
            if "EXTI" in pin.signal.upper() or "GPXTI" in pin.signal.upper():
                kind = "gpio_interrupt"
            elif pin.signal == "GPIO_Output":
                kind = "gpio_output"
            else:
                kind = "gpio_input"
            label = pin.label or pin.pin
            resource_id = re.sub(r"[^A-Za-z0-9_.-]", "_", label)
            macro = re.sub(r"[^A-Za-z0-9_]", "_", label)
            resources.append(
                HardwareResource(
                    resource_id,
                    kind,
                    {
                        "c_id": f"PLATFORM_GPIO_{index}",
                        "header": "platform_gpio.h",
                        "port": f"{macro}_GPIO_Port",
                        "pin": f"{macro}_Pin",
                        "logical_index": index,
                        "physical_pin": pin.pin,
                        "physical_resource": f"{pin.pin} ({pin.signal})",
                        "label": label,
                        "signal": pin.signal,
                        "mode": pin.mode,
                        "alternate_function": pin.alternate_function,
                        "pull": pin.pull,
                        "output_default": pin.output_default,
                        "exti_line": pin.exti_line,
                        "irq_enabled": int(kind == "gpio_interrupt"),
                    },
                )
            )
        if any(
            item.startswith(("SDIO", "SDMMC")) for item in self.peripherals
        ):
            resources.append(
                HardwareResource(
                    "SDIO",
                    "sdio",
                    {
                        "c_id": "PLATFORM_SDIO_1",
                        "physical_resource": "SDIO",
                    },
                )
            )
        resources.append(
            HardwareResource(
                "SYSTEM_TIME",
                "time",
                {
                    "c_id": "PLATFORM_TIME_1",
                    "physical_resource": "system timebase",
                },
            )
        )
        return tuple(resources)


def CubeMxValues_Parse(ioc_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in ioc_text.splitlines():
        if "=" not in raw_line or raw_line.lstrip().startswith("#"):
            continue
        key, value = raw_line.split("=", 1)
        values[key.strip().replace("\\#", "#")] = (
            value.strip().replace("\\:", ":").replace("\\#", "#")
        )
    return values


def _NaturalKey_Get(value: str) -> tuple[str, int, str]:
    match = re.search(r"(\d+)$", value)
    return (
        re.sub(r"\d+$", "", value),
        int(match.group(1)) if match else -1,
        value,
    )


def _Integer_Get(value: str) -> int | str:
    try:
        return int(value, 0)
    except ValueError:
        return value


def _PinSignalParts_Get(signal: str, instance: str) -> str:
    if signal.startswith(instance + "_"):
        return signal[len(instance) + 1 :].casefold()
    return signal.casefold()


def _Dma_Get(values: dict[str, str]) -> tuple[DmaInventory, ...]:
    requests = sorted(
        {
            value
            for key, value in values.items()
            if re.fullmatch(r"Dma\.Request\d+", key)
        },
        key=_NaturalKey_Get,
    )
    result: list[DmaInventory] = []
    for request in requests:
        prefix = f"Dma.{request}."
        indexes = {
            key[len(prefix) :].split(".", 1)[0]
            for key in values
            if key.startswith(prefix) and "." in key[len(prefix) :]
        }
        for index in sorted(indexes, key=lambda value: int(value) if value.isdigit() else 0):
            item_prefix = f"{prefix}{index}."
            result.append(
                DmaInventory(
                    request=request,
                    instance=values.get(item_prefix + "Instance", ""),
                    direction=values.get(item_prefix + "Direction", ""),
                    mode=values.get(item_prefix + "Mode", ""),
                    priority=values.get(item_prefix + "Priority", ""),
                    channel=values.get(item_prefix + "Channel", ""),
                )
            )
    return tuple(result)


def _Nvic_Get(values: dict[str, str]) -> tuple[NvicInventory, ...]:
    result: list[NvicInventory] = []
    for key, value in sorted(values.items()):
        if not key.startswith("NVIC.") or not key.endswith("IRQn"):
            continue
        parts = value.split(":")
        enabled = bool(parts and parts[0].casefold() == "true")
        preempt = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        sub = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
        result.append(NvicInventory(key[len("NVIC.") :], enabled, preempt, sub))
    return tuple(result)


def _Peripheral_Get(
    instance: str,
    kind: str,
    values: dict[str, str],
    pins: tuple[PinInventory, ...],
    dmas: tuple[DmaInventory, ...],
    nvic: tuple[NvicInventory, ...],
) -> PeripheralInventory:
    pin_map = {
        _PinSignalParts_Get(pin.signal, instance): pin.pin
        for pin in pins
        if pin.signal.startswith(instance + "_")
        or (kind == "adc" and pin.signal.startswith("ADCx_"))
    }
    settings: dict[str, Any] = {}
    prefix = instance + "."
    for key, value in values.items():
        if not key.startswith(prefix):
            continue
        name = key[len(prefix) :]
        if name in {"IPParameters"} or name.endswith("Parameters"):
            continue
        settings[name] = _Integer_Get(value)
    if kind == "uart":
        settings["baud_rate"] = _Integer_Get(values.get(prefix + "BaudRate", "0"))
        settings["mode"] = values.get(prefix + "VirtualMode", "")
    elif kind == "spi":
        raw_mode = values.get(prefix + "Mode", values.get(prefix + "VirtualType", ""))
        settings["mode"] = "master" if "MASTER" in raw_mode.upper() else "slave"
        settings["baud_rate"] = values.get(prefix + "CalculateBaudRate", "")
    elif kind == "i2c":
        settings["speed"] = _Integer_Get(
            values.get(prefix + "Timing", values.get(prefix + "ClockSpeed", "0"))
        )
    dma_items = tuple(item for item in dmas if item.request.startswith(instance + "_"))
    irq_names = {f"{instance}_IRQn", f"{instance}1_IRQn"}
    irq = next((item for item in nvic if item.irq in irq_names), None)
    return PeripheralInventory(instance, kind, pin_map, settings, dma_items, irq)


def CubeMxInventory_Parse(ioc_text: str) -> HardwareInventory:
    values = CubeMxValues_Parse(ioc_text)
    peripherals = tuple(
        sorted(
            {
                value
                for key, value in values.items()
                if re.fullmatch(r"Mcu\.IP\d+", key)
            },
            key=_NaturalKey_Get,
        )
    )
    pins: list[PinInventory] = []
    for key, signal in values.items():
        if not key.endswith(".Signal"):
            continue
        pin = key[: -len(".Signal")]
        if not re.fullmatch(r"P[A-K][0-9]+(?:-[A-Z0-9_]+)?", pin):
            continue
        exti_match = re.search(r"(?:GPXTI|EXTI)(\d+)", signal, re.IGNORECASE)
        pins.append(
            PinInventory(
                pin=pin,
                signal=signal,
                label=values.get(f"{pin}.GPIO_Label", ""),
                mode=values.get(f"{pin}.Mode", ""),
                alternate_function=values.get(
                    f"{pin}.GPIO_AF",
                    values.get(
                        f"{pin}.GPIO_AFName",
                        values.get(f"{pin}.GPIO_AFValue", ""),
                    ),
                ),
                pull=values.get(f"{pin}.GPIO_PuPd", ""),
                output_default=values.get(f"{pin}.PinState", ""),
                exti_line=int(exti_match.group(1)) if exti_match else None,
            )
        )
    pin_values = tuple(sorted(pins, key=lambda value: value.pin))
    dmas = _Dma_Get(values)
    nvic = _Nvic_Get(values)

    def group(prefixes: tuple[str, ...], kind: str) -> tuple[PeripheralInventory, ...]:
        return tuple(
            _Peripheral_Get(item, kind, values, pin_values, dmas, nvic)
            for item in peripherals
            if item.startswith(prefixes)
        )

    timers = group(("TIM", "LPTIM"), "timer")
    pwm_instances = {
        signal.split("_", 1)[0]
        for signal in (pin.signal for pin in pin_values)
        if re.match(r"TIM\d+_CH\d+", signal)
    }
    pwms = tuple(
        _Peripheral_Get(item, "pwm", values, pin_values, dmas, nvic)
        for item in sorted(pwm_instances, key=_NaturalKey_Get)
    )
    clock_prefixes = ("RCC.", "Clock.")
    clocks = {
        key: _Integer_Get(value)
        for key, value in sorted(values.items())
        if key.startswith(clock_prefixes)
        and (
            "Freq" in key
            or key.endswith("Source")
            or key.endswith("VALUE")
            or key.endswith("Divider")
        )
    }
    issues: list[str] = []
    if not dmas:
        issues.append("inventory.dma_missing")
    if not nvic:
        issues.append("inventory.nvic_missing")
    if not pin_values:
        issues.append("inventory.pinout_missing")
    return HardwareInventory(
        mcu_part=values.get(
            "Mcu.CPN", values.get("Mcu.Name", values.get("ProjectManager.DeviceId", ""))
        ),
        mcu_family=values.get("Mcu.Family", ""),
        package=values.get("Mcu.Package", ""),
        core=values.get(
            "Mcu.Core",
            values.get("Mcu.CPU", values.get("Mcu.UserName", "")),
        ),
        pins=pin_values,
        uarts=group(("USART", "UART", "LPUART"), "uart"),
        spis=group(("SPI",), "spi"),
        i2cs=group(("I2C",), "i2c"),
        adcs=group(("ADC",), "adc"),
        timers=timers,
        pwms=pwms,
        cans=group(("CAN", "FDCAN"), "can"),
        dmas=dmas,
        nvic=nvic,
        clocks=clocks,
        peripherals=peripherals,
        issues=tuple(issues),
    )
