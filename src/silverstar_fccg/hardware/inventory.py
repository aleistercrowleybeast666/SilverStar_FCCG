from __future__ import annotations

import json
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
    output_type: str = ""
    speed: str = ""
    exti_trigger: str = ""
    locked: bool = False
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
        # HardwareConfiguration is persisted as strict JSON.  Normalize tuple
        # fields here so a freshly detected inventory is byte-semantically
        # identical to the same inventory after save/reload.
        return json.loads(json.dumps(asdict(self), ensure_ascii=False))

    def HardwareResources_Get(self) -> tuple[HardwareResource, ...]:
        resources: list[HardwareResource] = []
        groups = (
            (self.uarts, "platform_uart.h", "huart"),
            (self.spis, "platform_spi.h", "hspi"),
            (self.i2cs, "platform_i2c.h", "hi2c"),
            (self.adcs, "platform_adc.h", "hadc"),
            (self.timers, "platform_timer.h", "htim"),
            (self.pwms, "platform_pwm.h", "htim"),
            (self.cans, "platform_can.h", ""),
        )
        kind_indexes: dict[str, int] = {}
        for peripherals, header, handle_prefix in groups:
            for peripheral in peripherals:
                index = kind_indexes.get(peripheral.kind, 0)
                kind_indexes[peripheral.kind] = index + 1
                handle_instance = str(
                    peripheral.settings.get("timer_instance", peripheral.instance)
                )
                suffix_match = re.search(r"(\d+)$", handle_instance)
                suffix = suffix_match.group(1) if suffix_match else str(index + 1)
                effective_handle_prefix = handle_prefix
                if peripheral.kind == "can_classic":
                    effective_handle_prefix = "hcan"
                elif peripheral.kind == "can_fd":
                    effective_handle_prefix = "hfdcan"
                c_id_kind = {
                    "can_classic": "CAN",
                    "can_fd": "FDCAN",
                }.get(peripheral.kind, peripheral.kind.upper())
                metadata = {
                    "c_id": f"PLATFORM_{c_id_kind}_{index + 1}",
                    "header": header,
                    "handle": f"{effective_handle_prefix}{suffix}",
                    "logical_index": index,
                    "peripheral": peripheral.instance,
                    "physical_resource": peripheral.instance,
                    "pins": dict(peripheral.pins),
                    "pin_electrical": {
                        role: {
                            "pin": pin.pin,
                            "signal": pin.signal,
                            "mode": pin.mode,
                            "alternate_function": (
                                pin.alternate_function or pin.signal
                            ),
                            "pull": pin.pull,
                            "output_type": pin.output_type,
                            "speed": pin.speed,
                        }
                        for role, physical_pin in peripheral.pins.items()
                        for pin in self.pins
                        if pin.pin == physical_pin
                    },
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
            irq = None
            if pin.exti_line is not None:
                if pin.exti_line <= 4:
                    irq_name = f"EXTI{pin.exti_line}_IRQn"
                elif pin.exti_line <= 9:
                    irq_name = "EXTI9_5_IRQn"
                else:
                    irq_name = "EXTI15_10_IRQn"
                irq = next(
                    (item for item in self.nvic if item.irq == irq_name), None
                )
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
                        "mode": kind,
                        "pin_mode": pin.mode,
                        "alternate_function": pin.alternate_function,
                        "pull": pin.pull,
                        "output_type": pin.output_type,
                        "speed": pin.speed,
                        "output_default": pin.output_default,
                        "initial_level": pin.output_default,
                        "exti_trigger": pin.exti_trigger,
                        "locked": pin.locked,
                        "exti_line": pin.exti_line,
                        "irq": asdict(irq) if irq is not None else {},
                        "irq_enabled": int(
                            irq is not None and irq.enabled
                        ),
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


def _Pull_Normalize(value: str) -> str:
    upper = value.upper()
    if "PULLUP" in upper:
        return "up"
    if "PULLDOWN" in upper:
        return "down"
    return "none"


def _OutputType_Normalize(value: str, signal: str) -> str:
    upper = value.upper()
    if "OD" in upper or "OPEN_DRAIN" in upper:
        return "open_drain"
    if signal.upper().startswith("I2C"):
        return "open_drain"
    if signal == "GPIO_Output" or "PP" in upper or "PUSH_PULL" in upper:
        return "push_pull"
    return ""


def _Speed_Normalize(value: str, signal: str) -> str:
    upper = value.upper()
    if "VERY_HIGH" in upper:
        return "very_high"
    if "HIGH" in upper:
        return "high"
    if "MEDIUM" in upper:
        return "medium"
    return "low" if signal == "GPIO_Output" else ""


def _Level_Normalize(value: str, signal: str) -> str:
    upper = value.upper()
    if "SET" in upper or upper in {"HIGH", "1"}:
        return "high"
    if "RESET" in upper or upper in {"LOW", "0"}:
        return "low"
    return "low" if signal == "GPIO_Output" else ""


def _ExtiTrigger_Normalize(value: str, signal: str) -> str:
    upper = f"{value} {signal}".upper()
    if "RISING_FALLING" in upper or "BOTH" in upper:
        return "both"
    if "FALLING" in upper:
        return "falling"
    if "EXTI" in upper or "GPXTI" in upper or "RISING" in upper:
        return "rising"
    return ""


def _FrequencyHz_Parse(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    text = str(value).strip()
    try:
        return max(0, int(text, 0))
    except ValueError:
        pass
    match = re.fullmatch(
        r"([0-9]+(?:\.[0-9]+)?)\s*([kKmM]?)\s*(?:bits?/s|hz)?",
        text,
        re.IGNORECASE,
    )
    if match is None:
        return 0
    scale = {"": 1, "k": 1_000, "m": 1_000_000}[match.group(2).casefold()]
    return int(round(float(match.group(1)) * scale))


def _MacroInteger_Get(value: Any, default: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    text = str(value).strip()
    try:
        return int(text, 0)
    except ValueError:
        match = re.search(r"(\d+)(?:TQ|BIT)?$", text, re.IGNORECASE)
        return int(match.group(1)) if match else default


def _TimerClockHz_Get(instance: str, values: dict[str, str]) -> int:
    number = _MacroInteger_Get(instance)
    bus = "APB2" if number in {1, 8, 9, 10, 11} else "APB1"
    for key in (
        f"RCC.{bus}TimFreq_Value",
        f"RCC.{bus}TimerFreq_Value",
        f"RCC.{bus}TIMFreq_Value",
    ):
        frequency = _FrequencyHz_Parse(values.get(key, ""))
        if frequency > 0:
            return frequency
    bus_frequency = _FrequencyHz_Parse(values.get(f"RCC.{bus}Freq_Value", ""))
    if bus_frequency <= 0:
        return 0
    divider = values.get(f"RCC.{bus}CLKDivider", "")
    return bus_frequency if divider.upper().endswith("DIV1") else bus_frequency * 2


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
        settings["word_length"] = _Integer_Get(
            re.sub(
                r"\D",
                "",
                values.get(prefix + "WordLength", "8"),
            )
            or "8"
        )
        parity = values.get(prefix + "Parity", "none").casefold()
        settings["parity"] = (
            "none" if "none" in parity else "even" if "even" in parity else "odd"
        )
        stop_bits = values.get(prefix + "StopBits", "1")
        settings["stop_bits"] = (
            2.0 if "2" in stop_bits else 1.5 if "1_5" in stop_bits else 1.0
        )
    elif kind == "spi":
        raw_mode = values.get(prefix + "Mode", values.get(prefix + "VirtualType", ""))
        settings["mode"] = "master" if "MASTER" in raw_mode.upper() else "slave"
        settings["clock_hz"] = _FrequencyHz_Parse(
            values.get(prefix + "CalculateBaudRate", "")
        )
        polarity = values.get(prefix + "CLKPolarity", "SPI_POLARITY_LOW").upper()
        phase = values.get(prefix + "CLKPhase", "SPI_PHASE_1EDGE").upper()
        first_bit = values.get(prefix + "FirstBit", "SPI_FIRSTBIT_MSB").upper()
        data_size = values.get(prefix + "DataSize", "SPI_DATASIZE_8BIT")
        data_bits_match = re.search(r"(\d+)", data_size)
        settings["cpol"] = "high" if "HIGH" in polarity else "low"
        settings["cpha"] = "2edge" if "2EDGE" in phase else "1edge"
        settings["data_bits"] = (
            int(data_bits_match.group(1)) if data_bits_match else 8
        )
        settings["bit_order"] = "lsb" if "LSB" in first_bit else "msb"
    elif kind == "i2c":
        settings["bus_frequency_hz"] = _FrequencyHz_Parse(
            values.get(
                prefix + "CalculateClockFrequency",
                values.get(prefix + "ClockSpeed", "0"),
            )
        )
        settings["address_mode"] = (
            "10bit"
            if "10BIT" in values.get(prefix + "AddressingMode", "").upper()
            else "7bit"
        )
        settings["own_address"] = _MacroInteger_Get(
            values.get(prefix + "OwnAddress1", "0")
        )
    elif kind in {"can_classic", "can_fd"}:
        raw_mode = values.get(prefix + "Mode", "")
        settings["mode"] = raw_mode.casefold().removeprefix("can_mode_")
        settings["can_kind"] = "bxcan" if kind == "can_classic" else "fdcan"
        settings["frame_format"] = "classic" if kind == "can_classic" else "fd"
        prescaler = _MacroInteger_Get(
            values.get(prefix + "Prescaler", values.get(prefix + "NominalPrescaler", "0"))
        )
        segment1 = _MacroInteger_Get(
            values.get(prefix + "TimeSeg1", values.get(prefix + "NominalTimeSeg1", "0"))
        )
        segment2 = _MacroInteger_Get(
            values.get(prefix + "TimeSeg2", values.get(prefix + "NominalTimeSeg2", "0"))
        )
        clock_hz = _FrequencyHz_Parse(
            values.get(
                prefix + "ClockFrequency",
                values.get("RCC.APB1Freq_Value", "0"),
            )
        )
        calculated = _FrequencyHz_Parse(
            values.get(
                prefix + "CalculateBaudRate",
                values.get(prefix + "NominalBitRate", "0"),
            )
        )
        if calculated <= 0 and all(value > 0 for value in (clock_hz, prescaler, segment1, segment2)):
            calculated = clock_hz // (prescaler * (1 + segment1 + segment2))
        settings.update(
            {
                "clock_hz": clock_hz,
                "nominal_bitrate": calculated,
                "prescaler": prescaler,
                "time_segment_1": segment1,
                "time_segment_2": segment2,
                "sync_jump_width": _MacroInteger_Get(
                    values.get(prefix + "SyncJumpWidth", "0")
                ),
                "automatic_bus_off": (
                    "ENABLE" in values.get(prefix + "AutoBusOff", "").upper()
                ),
                "auto_retransmission": (
                    "DISABLE"
                    not in values.get(prefix + "AutoRetransmission", "").upper()
                ),
            }
        )
    dma_items = tuple(item for item in dmas if item.request.startswith(instance + "_"))
    irq_names = {f"{instance}_IRQn", f"{instance}1_IRQn"}
    irq = next(
        (
            item
            for item in nvic
            if item.irq in irq_names or item.irq.startswith(instance + "_")
        ),
        None,
    )
    return PeripheralInventory(
        instance,
        kind,
        pin_map,
        _CaseInsensitiveKeys_Normalize(settings),
        dma_items,
        irq,
    )


def _CaseInsensitiveKeys_Normalize(values: dict[str, Any]) -> dict[str, Any]:
    """Keep inventory JSON consumable by case-insensitive PowerShell parsers.

    CubeMX commonly emits fields such as ``Mode`` while FCCG adds a normalized
    ``mode`` field.  JSON permits both, but Windows PowerShell 5 rejects that
    object.  Keep the normalized lower-case spelling and retain the raw value
    under a deterministic ``cubemx_`` name.
    """
    groups: dict[str, list[tuple[str, Any]]] = {}
    for key, value in values.items():
        groups.setdefault(key.casefold(), []).append((key, value))
    reserved = {key.casefold() for key in values}
    result: dict[str, Any] = {}
    for entries in groups.values():
        preferred = next(
            (entry for entry in entries if entry[0] == entry[0].casefold()),
            entries[0],
        )
        result[preferred[0]] = preferred[1]
        for key, value in entries:
            if key == preferred[0]:
                continue
            candidate = f"cubemx_{key}"
            suffix = 2
            while candidate.casefold() in reserved or any(
                candidate.casefold() == existing.casefold()
                for existing in result
            ):
                candidate = f"cubemx_{key}_{suffix}"
                suffix += 1
            result[candidate] = value
    return result


def _Pwm_Get(
    pin: PinInventory,
    values: dict[str, str],
    pins: tuple[PinInventory, ...],
    dmas: tuple[DmaInventory, ...],
    nvic: tuple[NvicInventory, ...],
) -> PeripheralInventory:
    match = re.fullmatch(r"(TIM\d+)_CH(\d+)", pin.signal)
    if match is None:
        raise ValueError(f"Unsupported PWM signal: {pin.signal}")
    timer, channel_text = match.groups()
    channel = int(channel_text)
    base = _Peripheral_Get(timer, "pwm", values, pins, dmas, nvic)
    prefix = timer + "."
    prescaler = _MacroInteger_Get(values.get(prefix + "Prescaler", "0"))
    period = _MacroInteger_Get(values.get(prefix + "Period", "0"))
    timer_clock_hz = _TimerClockHz_Get(timer, values)
    frequency_hz = 0
    if timer_clock_hz > 0 and prescaler >= 0 and period >= 0:
        divisor = (prescaler + 1) * (period + 1)
        frequency_hz = timer_clock_hz // divisor if divisor > 0 else 0
    polarity_raw = values.get(
        prefix + f"OCPolarity_{channel}",
        values.get(prefix + f"OCPolarity_CH{channel}", "TIM_OCPOLARITY_HIGH"),
    )
    active_high = "LOW" not in polarity_raw.upper()
    settings = {
        **base.settings,
        "timer_instance": timer,
        "channel": channel,
        "channel_token": f"TIM_CHANNEL_{channel}",
        "prescaler": prescaler,
        "period_counts": period + 1,
        "timer_clock_hz": timer_clock_hz,
        "frequency_hz": frequency_hz,
        "resolution_bits": max(1, (period + 1).bit_length() - 1),
        "polarity": "active_high" if active_high else "active_low",
        "active_high": int(active_high),
        "safe_state": "inactive",
        "safe_inactive_compare": 0,
        "physical_resource": f"{timer}:CH{channel}",
    }
    return PeripheralInventory(
        instance=f"{timer}_CH{channel}",
        kind="pwm",
        pins={"out": pin.pin},
        settings=settings,
        dma=base.dma,
        irq=base.irq,
    )


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
        mode_value = values.get(
            f"{pin}.GPIO_ModeDefaultEXTI",
            values.get(f"{pin}.GPIO_Mode", values.get(f"{pin}.Mode", "")),
        )
        output_type_value = values.get(
            f"{pin}.GPIO_ModeDefaultOutputPP",
            values.get(f"{pin}.GPIO_OutputType", mode_value),
        )
        output_default_value = values.get(f"{pin}.PinState", "")
        pins.append(
            PinInventory(
                pin=pin,
                signal=signal,
                label=values.get(f"{pin}.GPIO_Label", ""),
                mode=mode_value,
                alternate_function=values.get(
                    f"{pin}.GPIO_AF",
                    values.get(
                        f"{pin}.GPIO_AFName",
                        values.get(f"{pin}.GPIO_AFValue", ""),
                    ),
                ),
                pull=_Pull_Normalize(values.get(f"{pin}.GPIO_PuPd", "")),
                output_default=_Level_Normalize(output_default_value, signal),
                output_type=_OutputType_Normalize(output_type_value, signal),
                speed=_Speed_Normalize(
                    values.get(f"{pin}.GPIO_Speed", ""), signal
                ),
                exti_trigger=_ExtiTrigger_Normalize(mode_value, signal),
                locked=values.get(f"{pin}.Locked", "false").casefold()
                == "true",
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
    pwms = tuple(
        _Pwm_Get(pin, values, pin_values, dmas, nvic)
        for pin in sorted(pin_values, key=lambda item: _NaturalKey_Get(item.signal))
        if re.fullmatch(r"TIM\d+_CH\d+", pin.signal)
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
        cans=(
            *group(("CAN",), "can_classic"),
            *group(("FDCAN",), "can_fd"),
        ),
        dmas=dmas,
        nvic=nvic,
        clocks=clocks,
        peripherals=peripherals,
        issues=tuple(issues),
    )
