from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from collections import Counter
from typing import Any

from silverstar_fccg.hardware.inventory import CubeMxInventory_Parse, HardwareInventory
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import (
    ResourceMode,
    ResourceProvision,
    ResourceRequirement,
    ResourceRole,
    PluginManifest,
)
from silverstar_fccg.project.model import HardwareConfiguration, ProjectModel


@dataclass(frozen=True, slots=True)
class AssignedResource:
    requirement_key: str
    component_id: str
    requirement: ResourceRequirement
    provision: ResourceProvision
    role: ResourceRole | None = None


@dataclass(frozen=True, slots=True)
class ResourceAssignmentResult:
    assignments: tuple[AssignedResource, ...]
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True, slots=True)
class BoardCompatibilityResult:
    board_id: str
    compatible: bool
    missing: tuple[tuple[str, int], ...]
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResourceRequirementOption:
    key: str
    owner_id: str
    plugin_id: str
    kind: str
    display_names: dict[str, str]
    contract_summary: str
    required: bool
    mode: str
    assignment: str
    recommended_assignment: str
    candidates: tuple[str, ...]
    fixed: bool = False
    physical_resource: str = ""
    physical_details: str = ""


def ResourceRequirement_Key(component_id: str, requirement_name: str) -> str:
    return f"{component_id}:{requirement_name}"


def BoardHardwareInventory_Get(manifest: PluginManifest) -> HardwareInventory | None:
    if manifest.board is None or not manifest.board.ioc_file:
        return None
    ioc_path = manifest.package_root.joinpath(*manifest.board.ioc_file.split("/"))
    try:
        return CubeMxInventory_Parse(ioc_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as error:
        raise ValueError(f"Cannot read Board CubeMX inventory: {error}") from error


def BoardResourceProvisions_Get(
    manifest: PluginManifest,
) -> tuple[ResourceProvision, ...]:
    inventory = BoardHardwareInventory_Get(manifest)
    if (
        inventory is None
        or manifest.board is None
        or not manifest.board.connections_file
    ):
        return manifest.resource_provisions
    connection_path = manifest.package_root.joinpath(
        *manifest.board.connections_file.split("/")
    )
    try:
        data = json.loads(connection_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read Board connections: {error}") from error
    if (
        not isinstance(data, dict)
        or set(data) != {"format_version", "resources"}
        or data.get("format_version") != 1
        or not isinstance(data.get("resources"), dict)
    ):
        raise ValueError("Board connections.json has an invalid format")
    physical = {
        resource.resource_id: resource
        for resource in inventory.HardwareResources_Get()
    }
    result: list[ResourceProvision] = []
    connections = data["resources"]
    for provision in manifest.resource_provisions:
        entry = connections.get(provision.resource_id)
        if not isinstance(entry, dict) or set(entry) - {
            "physical",
            "fixed",
            "purpose",
        }:
            raise ValueError(
                f"Board connection is missing or invalid: {provision.resource_id}"
            )
        physical_id = entry.get("physical")
        if not isinstance(physical_id, str) or not physical_id:
            raise ValueError(
                f"Board connection has no physical resource: {provision.resource_id}"
            )
        actual = physical.get(physical_id)
        if actual is None:
            raise ValueError(
                f"Board connection {provision.resource_id} references unknown "
                f"IOC resource {physical_id}"
            )
        if actual.kind != provision.kind:
            raise ValueError(
                f"Board connection {provision.resource_id} kind mismatch: "
                f"{provision.kind} versus {actual.kind}"
            )
        metadata = {
            **actual.metadata,
            **provision.metadata,
            "physical_resource": physical_id,
            "connection_fixed": bool(entry.get("fixed", False)),
            "connection_purpose": str(entry.get("purpose", "")),
        }
        result.append(
            ResourceProvision(
                resource_id=provision.resource_id,
                kind=provision.kind,
                capabilities=provision.capabilities,
                reserved=provision.reserved,
                metadata=metadata,
            )
        )
    unknown = set(connections) - {item.resource_id for item in manifest.resource_provisions}
    if unknown:
        raise ValueError(
            "Board connections contain unknown aliases: " + ", ".join(sorted(unknown))
        )
    return tuple(result)


def _RequirementConstraintsErrors_Get(
    key: str,
    requirement: ResourceRequirement,
    provision: ResourceProvision,
) -> tuple[str, ...]:
    constraints = requirement.constraints
    electrical = requirement.electrical_constraints
    metadata = provision.metadata
    if (constraints or electrical) and "physical_resource" not in metadata:
        # Legacy third-party Board manifests have no .ioc-backed inventory.
        # They remain loadable, but cannot make a deep physical validation claim.
        return ()
    errors: list[str] = []

    def mismatch(field_name: str, expected: Any, actual: Any) -> None:
        errors.append(
            f"Resource contract mismatch for {key}: {field_name} requires "
            f"{expected}, got {actual}"
        )

    def dma_present(direction: str = "") -> bool:
        dma_values = metadata.get("dma", [])
        return isinstance(dma_values, list) and any(
            isinstance(item, dict)
            and bool(item.get("instance"))
            and (
                not direction
                or str(item.get("request", "")).upper().endswith(
                    "_" + direction.upper()
                )
            )
            for item in dma_values
        )

    def irq_enabled() -> bool:
        irq = metadata.get("irq", {})
        return isinstance(irq, dict) and irq.get("enabled") is True

    if "baud_rate" in constraints and metadata.get("baud_rate") != constraints["baud_rate"]:
        mismatch("baud_rate", constraints["baud_rate"], metadata.get("baud_rate"))
    if "mode" in constraints and str(metadata.get("mode", "")).casefold() != str(
        constraints["mode"]
    ).casefold():
        mismatch("mode", constraints["mode"], metadata.get("mode"))
    expected_signals = constraints.get("signals", [])
    actual_signals = {
        str(signal).casefold() for signal in metadata.get("pins", {})
    }
    if isinstance(expected_signals, list):
        missing = [
            str(signal)
            for signal in expected_signals
            if str(signal).casefold() not in actual_signals
        ]
        if missing:
            errors.append(
                f"Resource contract mismatch for {key}: missing signals "
                + ", ".join(missing)
            )
    if constraints.get("dma_rx_required") and not dma_present("rx"):
        errors.append(f"Resource contract mismatch for {key}: RX DMA is required")
    if constraints.get("dma_tx_required") and not dma_present("tx"):
        errors.append(f"Resource contract mismatch for {key}: TX DMA is required")
    if constraints.get("irq_required") and not irq_enabled():
        errors.append(f"Resource contract mismatch for {key}: enabled IRQ is required")

    uart = constraints.get("uart")
    if isinstance(uart, dict):
        actual_roles = {
            str(role).casefold() for role in metadata.get("pins", {})
        }
        missing_roles = {"rx", "tx"} - actual_roles
        if missing_roles:
            errors.append(
                f"Resource contract mismatch for {key}: UART is missing pin roles "
                + ", ".join(sorted(missing_roles))
            )
        actual_baud = metadata.get("baud_rate")
        baud = uart.get("baud", {})
        if isinstance(baud, dict):
            if "exact" in baud and actual_baud != baud["exact"]:
                mismatch("uart.baud.exact", baud["exact"], actual_baud)
            allowed = baud.get("allowed_values")
            if isinstance(allowed, list) and actual_baud not in allowed:
                mismatch("uart.baud.allowed_values", allowed, actual_baud)
        for field_name in ("word_length", "parity", "stop_bits"):
            if field_name in uart and str(metadata.get(field_name)).casefold() != str(
                uart[field_name]
            ).casefold():
                mismatch(
                    f"uart.{field_name}", uart[field_name], metadata.get(field_name)
                )
        if uart.get("rx_dma") and not dma_present("rx"):
            errors.append(f"Resource contract mismatch for {key}: UART RX DMA is required")
        if uart.get("tx_dma") and not dma_present("tx"):
            errors.append(f"Resource contract mismatch for {key}: UART TX DMA is required")
        if uart.get("irq") and not irq_enabled():
            errors.append(f"Resource contract mismatch for {key}: UART IRQ is required")

    spi = constraints.get("spi")
    if isinstance(spi, dict):
        actual_roles = {
            str(role).casefold() for role in metadata.get("pins", {})
        }
        missing_roles = {"miso", "mosi", "sck"} - actual_roles
        if missing_roles:
            errors.append(
                f"Resource contract mismatch for {key}: SPI is missing pin roles "
                + ", ".join(sorted(missing_roles))
            )
        actual_clock = metadata.get("clock_hz", 0)
        minimum_clock = spi.get("minimum_clock_hz")
        maximum_clock = spi.get("maximum_clock_hz")
        if isinstance(minimum_clock, int) and actual_clock < minimum_clock:
            mismatch("spi.minimum_clock_hz", f">={minimum_clock}", actual_clock)
        if isinstance(maximum_clock, int) and actual_clock > maximum_clock:
            mismatch("spi.maximum_clock_hz", f"<={maximum_clock}", actual_clock)
        for field_name in ("mode", "cpol", "cpha", "data_bits", "bit_order"):
            if field_name in spi and str(metadata.get(field_name)).casefold() != str(
                spi[field_name]
            ).casefold():
                mismatch(
                    f"spi.{field_name}", spi[field_name], metadata.get(field_name)
                )
        if spi.get("dma") and not dma_present():
            errors.append(f"Resource contract mismatch for {key}: SPI DMA is required")
        if spi.get("irq") and not irq_enabled():
            errors.append(f"Resource contract mismatch for {key}: SPI IRQ is required")

    i2c = constraints.get("i2c")
    if isinstance(i2c, dict):
        actual_roles = {
            str(role).casefold() for role in metadata.get("pins", {})
        }
        missing_roles = {"scl", "sda"} - actual_roles
        if missing_roles:
            errors.append(
                f"Resource contract mismatch for {key}: I2C is missing pin roles "
                + ", ".join(sorted(missing_roles))
            )
        actual_frequency = metadata.get("bus_frequency_hz", 0)
        maximum_frequency = i2c.get("maximum_bus_frequency_hz")
        if isinstance(maximum_frequency, int) and actual_frequency > maximum_frequency:
            mismatch(
                "i2c.maximum_bus_frequency_hz",
                f"<={maximum_frequency}",
                actual_frequency,
            )
        allowed_rates = i2c.get("allowed_rates_hz")
        if isinstance(allowed_rates, list) and actual_frequency not in allowed_rates:
            mismatch("i2c.allowed_rates_hz", allowed_rates, actual_frequency)
        if "address_mode" in i2c and metadata.get("address_mode") != i2c["address_mode"]:
            mismatch("i2c.address_mode", i2c["address_mode"], metadata.get("address_mode"))
        pin_electrical = metadata.get("pin_electrical", {})
        if i2c.get("required_pullup") and not (
            isinstance(pin_electrical, dict)
            and pin_electrical
            and all(
                isinstance(pin, dict)
                and pin.get("pull") == "up"
                and pin.get("output_type") in {"", "open_drain"}
                for pin in pin_electrical.values()
            )
        ):
            errors.append(
                f"Resource contract mismatch for {key}: I2C open-drain pull-up is required"
            )
        if i2c.get("dma") and not dma_present():
            errors.append(f"Resource contract mismatch for {key}: I2C DMA is required")
        if i2c.get("irq") and not irq_enabled():
            errors.append(f"Resource contract mismatch for {key}: I2C IRQ is required")

    pwm = constraints.get("pwm")
    if isinstance(pwm, dict):
        actual_frequency = metadata.get("frequency_hz", 0)
        actual_resolution = metadata.get("resolution_bits", 0)
        if "minimum_frequency_hz" in pwm and actual_frequency < pwm["minimum_frequency_hz"]:
            mismatch("pwm.minimum_frequency_hz", f">={pwm['minimum_frequency_hz']}", actual_frequency)
        if "maximum_frequency_hz" in pwm and actual_frequency > pwm["maximum_frequency_hz"]:
            mismatch("pwm.maximum_frequency_hz", f"<={pwm['maximum_frequency_hz']}", actual_frequency)
        if "minimum_resolution_bits" in pwm and actual_resolution < pwm["minimum_resolution_bits"]:
            mismatch("pwm.minimum_resolution_bits", f">={pwm['minimum_resolution_bits']}", actual_resolution)
        for field_name in ("polarity", "channel"):
            if field_name in pwm and metadata.get(field_name) != pwm[field_name]:
                mismatch(f"pwm.{field_name}", pwm[field_name], metadata.get(field_name))

    if electrical:
        expected_mode = electrical.get("mode")
        if expected_mode and provision.kind != expected_mode:
            mismatch("electrical.mode", expected_mode, provision.kind)
        for field_name in ("output_type", "pull", "speed", "exti_trigger"):
            if field_name in electrical and metadata.get(field_name) != electrical[field_name]:
                mismatch(
                    f"electrical.{field_name}",
                    electrical[field_name],
                    metadata.get(field_name),
                )
        if "alternate_function" in electrical and str(
            metadata.get("alternate_function", "")
        ).casefold() != str(electrical["alternate_function"]).casefold():
            mismatch(
                "electrical.alternate_function",
                electrical["alternate_function"],
                metadata.get("alternate_function"),
            )
        active_polarity = electrical.get("active_polarity", "high")
        safe_initial = electrical.get("safe_initial_level")
        expected_level = safe_initial
        if safe_initial == "inactive":
            expected_level = "low" if active_polarity == "high" else "high"
        elif safe_initial == "active":
            expected_level = active_polarity
        if expected_level and metadata.get("initial_level") != expected_level:
            mismatch(
                "electrical.safe_initial_level",
                expected_level,
                metadata.get("initial_level"),
            )
        if electrical.get("irq") and not irq_enabled():
            errors.append(f"Resource contract mismatch for {key}: GPIO IRQ is required")
        irq = metadata.get("irq", {})
        maximum_priority = electrical.get("maximum_irq_priority")
        if (
            isinstance(maximum_priority, int)
            and isinstance(irq, dict)
            and isinstance(irq.get("preempt_priority"), int)
            and irq["preempt_priority"] > maximum_priority
        ):
            mismatch(
                "electrical.maximum_irq_priority",
                f"<={maximum_priority}",
                irq["preempt_priority"],
            )
        if electrical.get("startup_glitch_free") and not metadata.get("locked"):
            errors.append(
                f"Resource contract mismatch for {key}: startup-safe GPIO must be locked in IOC"
            )
    return tuple(errors)


def _PhysicalDetails_Get(provision: ResourceProvision | None) -> str:
    if provision is None:
        return ""
    metadata = provision.metadata
    parts: list[str] = []
    physical = metadata.get("physical_resource")
    if physical:
        parts.append(str(physical))
    pins = metadata.get("pins")
    if isinstance(pins, dict) and pins:
        parts.append(
            ", ".join(f"{name.upper()}={pin}" for name, pin in sorted(pins.items()))
        )
    elif metadata.get("physical_pin"):
        parts.append(str(metadata["physical_pin"]))
    if metadata.get("baud_rate"):
        parts.append(f"baud={metadata['baud_rate']}")
    dma = metadata.get("dma")
    if isinstance(dma, list):
        streams = [
            str(item.get("instance"))
            for item in dma
            if isinstance(item, dict) and item.get("instance")
        ]
        if streams:
            parts.append("DMA=" + "/".join(streams))
    irq = metadata.get("irq")
    if isinstance(irq, dict) and irq.get("enabled"):
        parts.append(
            f"IRQ={irq.get('irq', '')}@{irq.get('preempt_priority', '?')}"
        )
    return " · ".join(parts)


def _RequirementContractSummary_Get(
    requirement: ResourceRequirement,
) -> str:
    parts = [requirement.kind]
    constraints = requirement.constraints
    uart = constraints.get("uart")
    if isinstance(uart, dict):
        baud = uart.get("baud", {})
        if isinstance(baud, dict) and "exact" in baud:
            parts.append(f"{baud['exact']} baud")
        if uart.get("rx_dma"):
            parts.append("RX DMA")
        if uart.get("tx_dma"):
            parts.append("TX DMA")
        if uart.get("irq"):
            parts.append("IRQ")
    spi = constraints.get("spi")
    if isinstance(spi, dict):
        if spi.get("mode"):
            parts.append(str(spi["mode"]))
        if spi.get("maximum_clock_hz"):
            parts.append(f"≤ {spi['maximum_clock_hz']} Hz")
    i2c = constraints.get("i2c")
    if isinstance(i2c, dict):
        if i2c.get("maximum_bus_frequency_hz"):
            parts.append(f"≤ {i2c['maximum_bus_frequency_hz']} Hz")
        if i2c.get("required_pullup"):
            parts.append("open-drain + pull-up")
    electrical = requirement.electrical_constraints
    for field_name in ("output_type", "pull", "exti_trigger"):
        if electrical.get(field_name):
            parts.append(str(electrical[field_name]))
    if electrical.get("safe_initial_level"):
        parts.append(f"safe={electrical['safe_initial_level']}")
    return " · ".join(parts)


def _ResourceRole_Get(
    owner_id: str,
    plugin_id: str,
    component_class: str,
    requirement_name: str,
    roles: dict[str, ResourceRole],
) -> ResourceRole | None:
    for key in (
        f"{owner_id}:{requirement_name}",
        f"{plugin_id}:{requirement_name}",
        f"{component_class}:{requirement_name}" if component_class else "",
    ):
        if key and key in roles:
            return roles[key]
    return None


def _RequirementOwners_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[tuple[str, str, PluginManifest], ...]:
    device_plugins = set(model.DevicePluginIds_Get())
    owners: list[tuple[str, str, PluginManifest]] = []
    for component_id in model.ComponentIds_Get():
        if component_id in device_plugins:
            continue
        owners.append(
            (component_id, component_id, catalog.Component_Get(component_id))
        )
    owners.extend(
        (
            instance.instance_id,
            instance.plugin,
            catalog.Component_Get(instance.plugin),
        )
        for instance in model.device_instances
    )
    return tuple(owners)


def _Candidates_Get(
    requirement: ResourceRequirement,
    role: ResourceRole | None,
    provisions: dict[str, ResourceProvision],
) -> tuple[str, ...]:
    role_candidates = role.candidates if role is not None else ()
    if requirement.candidates and role_candidates:
        allowed = set(role_candidates)
        return tuple(
            candidate
            for candidate in requirement.candidates
            if candidate in allowed
        )
    if requirement.candidates:
        return requirement.candidates
    if role_candidates:
        return role_candidates
    return tuple(
        resource_id
        for resource_id, provision in provisions.items()
        if provision.kind == requirement.kind
    )


def _Resource_AutoSelect(
    requirement: ResourceRequirement,
    role: ResourceRole | None,
    provisions: dict[str, ResourceProvision],
    claimed: dict[str, str],
) -> str:
    candidates = list(_Candidates_Get(requirement, role, provisions))
    if role is not None and role.default:
        candidates = [role.default, *(item for item in candidates if item != role.default)]
    for resource_id in candidates:
        provision = provisions.get(resource_id)
        if (
            provision is None
            or provision.kind != requirement.kind
            or provision.reserved
        ):
            continue
        if requirement.mode == ResourceMode.EXCLUSIVE and resource_id in claimed:
            continue
        return resource_id
    return ""


def ResourceAssignments_Resolve(
    model: ProjectModel,
    catalog: PluginCatalog,
    *,
    auto_assign: bool = False,
) -> ResourceAssignmentResult:
    provisions: dict[str, ResourceProvision] = {}
    roles: dict[str, ResourceRole] = {}
    board_conflicts = ()
    for component_id in model.ComponentIds_Get():
        manifest = catalog.Component_Get(component_id)
        component_provisions = (
            BoardResourceProvisions_Get(manifest)
            if component_id == model.board
            else manifest.resource_provisions
        )
        for provision in component_provisions:
            if provision.resource_id in provisions:
                return ResourceAssignmentResult(
                    (), (f"Duplicate provided resource id: {provision.resource_id}",)
                )
            provisions[provision.resource_id] = provision
        if component_id == model.board:
            roles = {role.key: role for role in manifest.resource_roles}
            board_conflicts = manifest.resource_conflicts
    if model.hardware.mode == "custom":
        for hardware_resource in model.hardware.resources:
            if hardware_resource.resource_id in provisions:
                return ResourceAssignmentResult(
                    (),
                    (
                        "Duplicate custom hardware resource id: "
                        f"{hardware_resource.resource_id}",
                    ),
                )
            provisions[hardware_resource.resource_id] = ResourceProvision(
                resource_id=hardware_resource.resource_id,
                kind=hardware_resource.kind,
                metadata=hardware_resource.metadata,
            )

    claimed: dict[str, str] = {}
    physical_claimed: dict[str, str] = {}
    assignments: list[AssignedResource] = []
    errors: list[str] = []
    for owner_id, plugin_id, manifest in _RequirementOwners_Get(model, catalog):
        for requirement in manifest.resource_requirements:
            key = ResourceRequirement_Key(owner_id, requirement.name)
            role = _ResourceRole_Get(
                owner_id,
                plugin_id,
                manifest.component_class,
                requirement.name,
                roles,
            )
            if role is not None and role.kind != requirement.kind:
                errors.append(
                    f"Board role kind mismatch for {key}: expected "
                    f"{requirement.kind}, got {role.kind}"
                )
                continue
            selected = model.resource_assignments.get(key, "")
            if not selected and auto_assign:
                selected = _Resource_AutoSelect(
                    requirement, role, provisions, claimed
                )
                if selected:
                    model.resource_assignments[key] = selected
            if not selected:
                if requirement.required:
                    errors.append(
                        f"Unassigned resource requirement: {key} ({requirement.kind})"
                    )
                continue
            provision = provisions.get(selected)
            if provision is None:
                errors.append(f"Unknown resource {selected} assigned to {key}")
                continue
            if provision.kind != requirement.kind:
                errors.append(
                    f"Resource kind mismatch for {key}: expected {requirement.kind}, "
                    f"got {provision.kind}"
                )
                continue
            candidates = _Candidates_Get(requirement, role, provisions)
            if candidates and selected not in candidates:
                errors.append(
                    f"Resource {selected} is not an allowed candidate for {key}"
                )
                continue
            if role is not None and role.fixed and selected != role.default:
                errors.append(
                    f"Fixed board role {role.key} must use {role.default}, got {selected}"
                )
                continue
            if provision.reserved:
                errors.append(f"Reserved resource {selected} cannot be assigned to {key}")
                continue
            if requirement.mode == ResourceMode.EXCLUSIVE and selected in claimed:
                errors.append(
                    f"Resource conflict: {selected} is assigned to "
                    f"{claimed[selected]} and {key}"
                )
                continue
            physical_resource = str(
                provision.metadata.get("physical_resource", "")
            )
            if (
                requirement.mode == ResourceMode.EXCLUSIVE
                and physical_resource
                and physical_resource in physical_claimed
            ):
                errors.append(
                    f"Physical resource conflict: {physical_resource} is assigned to "
                    f"{physical_claimed[physical_resource]} and {key}"
                )
                continue
            if requirement.mode == ResourceMode.EXCLUSIVE:
                claimed[selected] = key
                if physical_resource:
                    physical_claimed[physical_resource] = key
            errors.extend(
                _RequirementConstraintsErrors_Get(key, requirement, provision)
            )
            assignments.append(
                AssignedResource(key, owner_id, requirement, provision, role)
            )

    used = {assignment.provision.resource_id for assignment in assignments}
    for conflict in board_conflicts:
        conflict_set = set(conflict.resources)
        if conflict_set.issubset(used):
            detail = conflict.message or ", ".join(conflict.resources)
            errors.append(f"Board resource conflict: {detail}")
    dma_owners: dict[str, str] = {}
    for assignment in assignments:
        dma_values = assignment.provision.metadata.get("dma", [])
        if not isinstance(dma_values, list):
            continue
        for dma in dma_values:
            if not isinstance(dma, dict):
                continue
            instance = dma.get("instance")
            if not isinstance(instance, str) or not instance:
                continue
            previous = dma_owners.get(instance)
            if previous is not None and previous != assignment.requirement_key:
                errors.append(
                    f"DMA conflict: {instance} is used by {previous} and "
                    f"{assignment.requirement_key}"
                )
            else:
                dma_owners[instance] = assignment.requirement_key
    return ResourceAssignmentResult(tuple(assignments), tuple(errors))


def BoardCompatibility_Resolve(
    model: ProjectModel,
    catalog: PluginCatalog,
    board_id: str,
) -> BoardCompatibilityResult:
    board = catalog.Component_Get(board_id)
    if board.component_type != "board" or board.board is None:
        return BoardCompatibilityResult(
            board_id, False, (), ("Component is not a Board plugin",)
        )
    if model.mcu not in board.board.compatible_mcus:
        return BoardCompatibilityResult(
            board_id,
            False,
            (),
            (f"Board does not support selected MCU {model.mcu}",),
        )
    candidate = deepcopy(model)
    candidate.board = board_id
    candidate.hardware = HardwareConfiguration(
        mode="board_plugin",
        source_kind=board.board.source_kind,
    )
    candidate.resource_assignments = {}
    resolution = ResourceAssignments_Resolve(candidate, catalog, auto_assign=True)
    missing_counter: Counter[str] = Counter()
    for error in resolution.errors:
        if "Unassigned resource requirement:" not in error:
            continue
        kind_start = error.rfind("(")
        if kind_start >= 0 and error.endswith(")"):
            missing_counter[error[kind_start + 1 : -1]] += 1
    return BoardCompatibilityResult(
        board_id=board_id,
        compatible=resolution.valid,
        missing=tuple(sorted(missing_counter.items())),
        errors=resolution.errors,
    )


def ResourceRequirementOptions_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ResourceRequirementOption, ...]:
    provisions: dict[str, ResourceProvision] = {}
    roles: dict[str, ResourceRole] = {}
    for component_id in model.ComponentIds_Get():
        manifest = catalog.Component_Get(component_id)
        component_provisions = (
            BoardResourceProvisions_Get(manifest)
            if component_id == model.board
            else manifest.resource_provisions
        )
        provisions.update(
            {provision.resource_id: provision for provision in component_provisions}
        )
        if component_id == model.board:
            roles = {role.key: role for role in manifest.resource_roles}
    if model.hardware.mode == "custom":
        provisions.update(
            {
                resource.resource_id: ResourceProvision(
                    resource.resource_id, resource.kind, metadata=resource.metadata
                )
                for resource in model.hardware.resources
            }
        )
    options: list[ResourceRequirementOption] = []
    for owner_id, plugin_id, manifest in _RequirementOwners_Get(model, catalog):
        for requirement in manifest.resource_requirements:
            key = ResourceRequirement_Key(owner_id, requirement.name)
            role = _ResourceRole_Get(
                owner_id,
                plugin_id,
                manifest.component_class,
                requirement.name,
                roles,
            )
            options.append(
                ResourceRequirementOption(
                    key=key,
                    owner_id=owner_id,
                    plugin_id=plugin_id,
                    kind=requirement.kind,
                    display_names=dict(requirement.display_names),
                    contract_summary=_RequirementContractSummary_Get(requirement),
                    required=requirement.required,
                    mode=requirement.mode.value,
                    assignment=model.resource_assignments.get(key, ""),
                    recommended_assignment=(role.default if role is not None else ""),
                    candidates=_Candidates_Get(requirement, role, provisions),
                    fixed=bool(role is not None and role.fixed),
                    physical_resource=str(
                        provisions.get(
                            model.resource_assignments.get(key, ""),
                            ResourceProvision("", ""),
                        ).metadata.get("physical_resource", "")
                    ),
                    physical_details=_PhysicalDetails_Get(
                        provisions.get(
                            model.resource_assignments.get(key, "")
                        )
                    ),
                )
            )
    return tuple(options)
