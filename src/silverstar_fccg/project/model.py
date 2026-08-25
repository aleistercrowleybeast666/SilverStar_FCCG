from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.core.errors import FccgError


PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,79}$")
PROJECT_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
COMPONENT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
SELECTION_SLOT_PATTERN = COMPONENT_ID_PATTERN
SELECTION_OPTION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
FIRMWARE_VERSION_PATTERN = re.compile(
    r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][0-9A-Za-z.-]+)?$"
)
LOG_RECORD_PATTERN = re.compile(r"^FLIGHT_LOG_RECORD_[A-Z0-9_]+$")
RESOURCE_KEY_PATTERN = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*:[a-z0-9]+(?:[._-][a-z0-9]+)*$"
)
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DEVICE_INSTANCE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TOOLCHAIN_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_.+-]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
RELATIVE_FILE_PATTERN = re.compile(r"^[A-Za-z0-9_./+@-]+$")

PROJECT_FORMAT_VERSION = 6
DEFAULT_PROTOCOL_PROFILES = {
    "telemetry": "air.compact.v0",
    "maintenance": "maintenance.v0_0",
    "logging": "sslog0",
}
DEFAULT_MODE_PARAMETERS = {
    "deployment": {
        "ApogeeVerticalVelocity": {
            "vertical_velocity_threshold": -2.0,
        },
        "Tilt": {
            "tilt_threshold": 45.0,
        },
        "Delay": {
            "delay": 60.0,
        },
    }
}
HARDWARE_MODES = frozenset({"unselected", "board_plugin", "custom"})
BOARD_SOURCE_KINDS = frozenset(
    {"unselected", "verified_builtin", "manual_import", "third_party"}
)


class ProjectModelError(FccgError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    name: str
    firmware_version: str = "0.0.9"
    build_target: str = "SilverStar_0_0_9"


@dataclass(frozen=True, slots=True)
class DeviceInstance:
    instance_id: str
    plugin: str


@dataclass(frozen=True, slots=True)
class BuildOptions:
    target_profile: str = "SilverStar_F407"
    make_command: str = "mingw32-make"
    toolchain_prefix: str = "arm-none-eabi-"
    gcc_path: str = ""
    flash_command: str = ""
    eide_mode: str = "native"
    tool_paths: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LogStreamConfig:
    record: str
    enabled: bool
    policy: str
    decimation: int = 1
    period_us: int = 0


@dataclass(frozen=True, slots=True)
class HardwareResource:
    resource_id: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HardwareConfiguration:
    mode: str = "unselected"
    source_kind: str = "unselected"
    provider: str = ""
    snapshot_id: str = ""
    ioc_file: str = ""
    mcu: str = ""
    capabilities: tuple[str, ...] = ()
    inventory: dict[str, Any] = field(default_factory=dict)
    resources: tuple[HardwareResource, ...] = ()
    build_sources: tuple[str, ...] = ()
    asm_sources: tuple[str, ...] = ()
    include_dirs: tuple[str, ...] = ()
    defines: tuple[str, ...] = ()
    linker_script: str = ""
    source_digest: str = ""
    source_label: str = ""
    risk_acknowledged: bool = False
    assignment_fingerprint: str = ""


@dataclass(slots=True)
class ProjectModel:
    identity: ProjectIdentity
    core: str
    mcu: str
    board: str
    os: str
    device_instances: list[DeviceInstance] = field(default_factory=list)
    base_components: list[str] = field(default_factory=list)
    strategies: dict[str, str | None] = field(default_factory=dict)
    modes: dict[str, list[str]] = field(default_factory=dict)
    mode_parameters: dict[str, dict[str, dict[str, float | int]]] = field(
        default_factory=lambda: deepcopy(DEFAULT_MODE_PARAMETERS)
    )
    protocol_bundles: list[str] = field(default_factory=list)
    protocol_profiles: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_PROTOCOL_PROFILES)
    )
    development_environment: str = ""
    hardware: HardwareConfiguration = field(default_factory=HardwareConfiguration)
    resource_assignments: dict[str, str] = field(default_factory=dict)
    capability_source_overrides: dict[str, str] = field(default_factory=dict)
    logging_streams: list[LogStreamConfig] = field(default_factory=list)
    build: BuildOptions = field(default_factory=BuildOptions)
    generated_glue: list[str] = field(
        default_factory=lambda: [
            "project_bindings",
            "project_capability_routes",
            "platform_resources",
            "project_resources",
            "project_log_config",
            "project_metadata",
            "project_flight_config",
            "project_sources",
        ]
    )
    component_provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    reference_provenance: dict[str, Any] = field(default_factory=dict)
    format_version: int = PROJECT_FORMAT_VERSION

    def ComponentIds_Get(self) -> tuple[str, ...]:
        ordered = [self.core, self.mcu, self.board, self.os]
        ordered.extend(self.DevicePluginIds_Get())
        ordered.extend(self.base_components)
        ordered.extend(
            component_id
            for _slot, component_id in sorted(self.strategies.items())
            if component_id is not None
        )
        ordered.extend(self.protocol_bundles)
        ordered.append(self.development_environment)
        if self.hardware.mode == "custom":
            ordered.append(self.hardware.provider)
        return tuple(dict.fromkeys(component_id for component_id in ordered if component_id))

    def DevicePluginIds_Get(self) -> tuple[str, ...]:
        return tuple(instance.plugin for instance in self.device_instances)

    def DeviceInstance_Get(self, instance_id: str) -> DeviceInstance | None:
        for instance in self.device_instances:
            if instance.instance_id == instance_id:
                return instance
        return None

    def Dictionary_Get(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "project": {
                "name": self.identity.name,
                "firmware_version": self.identity.firmware_version,
                "build_target": self.identity.build_target,
            },
            "components": {
                "core": self.core,
                "mcu": self.mcu,
                "board": self.board,
                "os": self.os,
                "devices": [
                    {
                        "instance_id": instance.instance_id,
                        "plugin": instance.plugin,
                    }
                    for instance in self.device_instances
                ],
                "base": list(self.base_components),
                "strategies": dict(sorted(self.strategies.items())),
                "protocol_bundles": list(self.protocol_bundles),
                "development_environment": self.development_environment,
            },
            "modes": {
                slot: list(selection)
                for slot, selection in sorted(self.modes.items())
            },
            "mode_parameters": {
                slot: {
                    option: dict(sorted(parameters.items()))
                    for option, parameters in sorted(options.items())
                }
                for slot, options in sorted(self.mode_parameters.items())
            },
            "protocol_profiles": dict(sorted(self.protocol_profiles.items())),
            "hardware": {
                "mode": self.hardware.mode,
                "source_kind": self.hardware.source_kind,
                "provider": self.hardware.provider,
                "snapshot_id": self.hardware.snapshot_id,
                "ioc_file": self.hardware.ioc_file,
                "mcu": self.hardware.mcu,
                "capabilities": list(self.hardware.capabilities),
                "inventory": self.hardware.inventory,
                "resources": [
                    {
                        "id": resource.resource_id,
                        "kind": resource.kind,
                        "metadata": resource.metadata,
                    }
                    for resource in self.hardware.resources
                ],
                "build_sources": list(self.hardware.build_sources),
                "asm_sources": list(self.hardware.asm_sources),
                "include_dirs": list(self.hardware.include_dirs),
                "defines": list(self.hardware.defines),
                "linker_script": self.hardware.linker_script,
                "source_digest": self.hardware.source_digest,
                "source_label": self.hardware.source_label,
                "risk_acknowledged": self.hardware.risk_acknowledged,
                "assignment_fingerprint": self.hardware.assignment_fingerprint,
            },
            "resources": dict(sorted(self.resource_assignments.items())),
            "capability_sources": dict(
                sorted(self.capability_source_overrides.items())
            ),
            "logging": {
                "streams": [
                    {
                        "record": stream.record,
                        "enabled": stream.enabled,
                        "policy": stream.policy,
                        "decimation": stream.decimation,
                        "period_us": stream.period_us,
                    }
                    for stream in self.logging_streams
                ]
            },
            "build": {
                "target_profile": self.build.target_profile,
                "make_command": self.build.make_command,
                "toolchain_prefix": self.build.toolchain_prefix,
                "gcc_path": self.build.gcc_path,
                "flash_command": self.build.flash_command,
                "eide_mode": self.build.eide_mode,
                "tool_paths": dict(sorted(self.build.tool_paths.items())),
            },
            "generated_glue": list(self.generated_glue),
            "component_provenance": self.component_provenance,
            "reference_provenance": self.reference_provenance,
        }


def _Object_Require(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProjectModelError(f"{name} must be an object")
    return data


def _String_Require(
    data: dict[str, Any], name: str, *, allow_empty: bool = False
) -> str:
    value = data.get(name)
    if not isinstance(value, str) or (not allow_empty and not value):
        qualifier = "a string" if allow_empty else "a non-empty string"
        raise ProjectModelError(f"{name} must be {qualifier}")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ProjectModelError(f"{name} contains control characters")
    return value


def _StringList_Require(
    data: dict[str, Any], name: str, *, allow_empty_items: bool = False
) -> list[str]:
    value = data.get(name, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and (allow_empty_items or bool(item)) for item in value
    ):
        raise ProjectModelError(f"{name} must be an array of strings")
    if len(value) != len(set(value)):
        raise ProjectModelError(f"{name} contains duplicate values")
    return list(value)


def _ComponentId_Validate(value: str, name: str, *, allow_empty: bool = False) -> None:
    if value == "" and allow_empty:
        return
    if not COMPONENT_ID_PATTERN.fullmatch(value):
        raise ProjectModelError(f"Invalid {name}: {value!r}")


def _ProjectV0_Migrate(root: dict[str, Any]) -> dict[str, Any]:
    components = _Object_Require(root.get("components"), "components")
    algorithms = list(components.get("algorithms", []))
    flight_logic = list(components.get("flight_logic", []))
    strategies: dict[str, str | None] = {}
    base: list[str] = [
        "silverstar.algorithm.common",
        "silverstar.algorithm.alignment.common",
    ]
    for component_id in algorithms:
        if ".alignment." in component_id:
            strategies["alignment"] = component_id
        elif ".ins." in component_id:
            strategies["ins"] = component_id
        elif ".estimator." in component_id:
            strategies["estimator"] = component_id
        else:
            base.append(component_id)
    for component_id in flight_logic:
        if ".landing." in component_id:
            strategies["landing"] = component_id
        else:
            base.append(component_id)
    migrated = {
        "format_version": 2,
        "project": root.get("project"),
        "components": {
            "core": components.get("core"),
            "mcu": components.get("mcu"),
            "board": components.get("board", ""),
            "os": components.get("os"),
            "devices": components.get("devices", []),
            "base": list(dict.fromkeys(base)),
            "strategies": strategies,
            "protocol_bundles": components.get("protocol_bundles", []),
            "development_environment": "silverstar.environment.vscode_eide_gcc",
        },
        "modes": {
            "calibration": ["Existing"],
            "deployment": ["ApogeeVerticalVelocity"],
        },
        "hardware": {
            "mode": "board_plugin",
            "source_kind": "verified_builtin",
            "provider": "",
            "snapshot_id": "",
            "ioc_file": "",
            "mcu": "",
            "capabilities": [],
            "inventory": {},
            "resources": [],
            "build_sources": [],
            "asm_sources": [],
            "include_dirs": [],
            "defines": [],
            "linker_script": "",
            "source_digest": "",
            "source_label": "",
            "risk_acknowledged": False,
        },
        "resources": root.get("resources", {}),
        "logging": root.get("logging", {"streams": []}),
        "build": dict(root.get("build", {})),
        "generated_glue": root.get("generated_glue", []),
        "component_provenance": root.get("component_provenance", {}),
        "reference_provenance": {},
    }
    migrated["build"]["eide_mode"] = "native"
    return migrated


def _ProjectV1_Migrate(root: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(root)
    migrated["format_version"] = 2
    hardware = _Object_Require(migrated.get("hardware"), "hardware")
    hardware.setdefault("inventory", {})
    return migrated


def _LegacyDeviceClass_Get(plugin_id: str) -> str:
    marker = ".device."
    suffix = plugin_id.split(marker, 1)[1] if marker in plugin_id else "device"
    component_class = suffix.split(".", 1)[0]
    return "maintenance" if component_class == "console" else component_class


def _ProjectV2_Migrate(root: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(root)
    components = _Object_Require(migrated.get("components"), "components")
    legacy_devices = components.get("devices", [])
    if not isinstance(legacy_devices, list) or not all(
        isinstance(plugin_id, str) and plugin_id for plugin_id in legacy_devices
    ):
        raise ProjectModelError("components.devices must be an array of component ids")
    class_counts: dict[str, int] = {}
    instance_by_plugin: dict[str, str] = {}
    instances: list[dict[str, str]] = []
    for plugin_id in legacy_devices:
        component_class = _LegacyDeviceClass_Get(plugin_id)
        index = class_counts.get(component_class, 0)
        class_counts[component_class] = index + 1
        instance_id = f"{component_class}{index}"
        instance_by_plugin[plugin_id] = instance_id
        instances.append({"instance_id": instance_id, "plugin": plugin_id})
    components["devices"] = instances
    resources = _Object_Require(migrated.get("resources"), "resources")
    migrated["resources"] = {
        (
            f"{instance_by_plugin[owner]}:{requirement}"
            if owner in instance_by_plugin
            else key
        ): resource_id
        for key, resource_id in resources.items()
        for owner, separator, requirement in (key.partition(":"),)
        if separator
    }
    generated_glue = migrated.get("generated_glue", [])
    if isinstance(generated_glue, list) and "project_capability_routes" not in generated_glue:
        generated_glue.append("project_capability_routes")
    migrated["capability_sources"] = {}
    migrated["format_version"] = 3
    return migrated


def _ProjectV3_Migrate(root: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(root)
    migrated["capability_selections"] = {}
    migrated["format_version"] = 4
    return migrated


def _ProjectV4_Migrate(root: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(root)
    migrated.pop("capability_selections", None)
    build = _Object_Require(migrated.get("build"), "build")
    build.pop("configuration", None)
    migrated["format_version"] = 5
    return migrated


def _ProjectV5_Migrate(root: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(root)
    migrated["mode_parameters"] = deepcopy(DEFAULT_MODE_PARAMETERS)
    migrated["protocol_profiles"] = dict(DEFAULT_PROTOCOL_PROFILES)
    hardware = _Object_Require(migrated.get("hardware"), "hardware")
    hardware["assignment_fingerprint"] = ""
    generated_glue = migrated.get("generated_glue", [])
    if (
        isinstance(generated_glue, list)
        and "project_flight_config" not in generated_glue
    ):
        generated_glue.append("project_flight_config")
    migrated["format_version"] = PROJECT_FORMAT_VERSION
    return migrated


def _DeviceInstances_Parse(value: Any) -> list[DeviceInstance]:
    if not isinstance(value, list):
        raise ProjectModelError("components.devices must be an array")
    instances: list[DeviceInstance] = []
    instance_ids: set[str] = set()
    for entry_value in value:
        entry = _Object_Require(entry_value, "device instance")
        if set(entry) != {"instance_id", "plugin"}:
            raise ProjectModelError(
                "device instance must contain instance_id and plugin"
            )
        instance_id = _String_Require(entry, "instance_id")
        plugin = _String_Require(entry, "plugin")
        if not DEVICE_INSTANCE_ID_PATTERN.fullmatch(instance_id):
            raise ProjectModelError(f"Invalid device instance id: {instance_id!r}")
        _ComponentId_Validate(plugin, "device plugin")
        if instance_id in instance_ids:
            raise ProjectModelError(f"Duplicate device instance id: {instance_id}")
        instance_ids.add(instance_id)
        instances.append(DeviceInstance(instance_id, plugin))
    return instances


def _Components_Parse(data: Any) -> tuple[
    str,
    str,
    str,
    str,
    list[DeviceInstance],
    list[str],
    dict[str, str | None],
    list[str],
    str,
]:
    components = _Object_Require(data, "components")
    expected = {
        "core",
        "mcu",
        "board",
        "os",
        "devices",
        "base",
        "strategies",
        "protocol_bundles",
        "development_environment",
    }
    if set(components) != expected:
        raise ProjectModelError("components has missing or unknown fields")
    core = _String_Require(components, "core")
    mcu = _String_Require(components, "mcu")
    board = _String_Require(components, "board", allow_empty=True)
    os_component = _String_Require(components, "os")
    device_instances = _DeviceInstances_Parse(components.get("devices"))
    base = _StringList_Require(components, "base")
    protocol_bundles = _StringList_Require(components, "protocol_bundles")
    environment = _String_Require(components, "development_environment")
    for name, value, allow_empty in (
        ("core component", core, False),
        ("mcu component", mcu, False),
        ("board component", board, True),
        ("os component", os_component, False),
        ("development environment", environment, False),
    ):
        _ComponentId_Validate(value, name, allow_empty=allow_empty)
    for component_id in (
        *(instance.plugin for instance in device_instances),
        *base,
        *protocol_bundles,
    ):
        _ComponentId_Validate(component_id, "component id")
    strategy_data = _Object_Require(components.get("strategies"), "strategies")
    strategies: dict[str, str | None] = {}
    for slot, component_id in strategy_data.items():
        if not isinstance(slot, str) or not SELECTION_SLOT_PATTERN.fullmatch(slot):
            raise ProjectModelError(f"Invalid strategy slot: {slot!r}")
        if component_id is not None:
            if not isinstance(component_id, str):
                raise ProjectModelError(f"Strategy {slot} must be a component id or null")
            _ComponentId_Validate(component_id, f"strategy {slot}")
        strategies[slot] = component_id
    return (
        core,
        mcu,
        board,
        os_component,
        device_instances,
        base,
        strategies,
        protocol_bundles,
        environment,
    )


def _Modes_Parse(value: Any) -> dict[str, list[str]]:
    data = _Object_Require(value, "modes")
    modes: dict[str, list[str]] = {}
    for slot, selection_value in data.items():
        if not isinstance(slot, str) or not SELECTION_SLOT_PATTERN.fullmatch(slot):
            raise ProjectModelError(f"Invalid mode slot: {slot!r}")
        wrapper = {"selection": selection_value}
        selection = _StringList_Require(wrapper, "selection")
        invalid = next(
            (
                option
                for option in selection
                if not SELECTION_OPTION_PATTERN.fullmatch(option)
            ),
            None,
        )
        if invalid is not None:
            raise ProjectModelError(f"Invalid mode option: {invalid!r}")
        modes[slot] = selection
    return modes


def _ModeParameters_Parse(
    value: Any,
) -> dict[str, dict[str, dict[str, float | int]]]:
    data = _Object_Require(value, "mode_parameters")
    result: dict[str, dict[str, dict[str, float | int]]] = {}
    for slot, options_value in data.items():
        if not isinstance(slot, str) or not SELECTION_SLOT_PATTERN.fullmatch(slot):
            raise ProjectModelError(f"Invalid mode parameter slot: {slot!r}")
        options = _Object_Require(
            options_value, f"mode_parameters.{slot}"
        )
        normalized_options: dict[str, dict[str, float | int]] = {}
        for option, parameters_value in options.items():
            if (
                not isinstance(option, str)
                or not SELECTION_OPTION_PATTERN.fullmatch(option)
            ):
                raise ProjectModelError(
                    f"Invalid mode parameter option: {option!r}"
                )
            parameters = _Object_Require(
                parameters_value, f"mode_parameters.{slot}.{option}"
            )
            normalized_parameters: dict[str, float | int] = {}
            for parameter_id, parameter_value in parameters.items():
                if (
                    not isinstance(parameter_id, str)
                    or not COMPONENT_ID_PATTERN.fullmatch(parameter_id)
                ):
                    raise ProjectModelError(
                        f"Invalid mode parameter id: {parameter_id!r}"
                    )
                if (
                    isinstance(parameter_value, bool)
                    or not isinstance(parameter_value, (int, float))
                    or not math.isfinite(float(parameter_value))
                ):
                    raise ProjectModelError(
                        f"Mode parameter {slot}.{option}.{parameter_id} "
                        "must be a finite number"
                    )
                normalized_parameters[parameter_id] = parameter_value
            normalized_options[option] = normalized_parameters
        result[slot] = normalized_options
    return result


def _ProtocolProfiles_Parse(value: Any) -> dict[str, str]:
    data = _Object_Require(value, "protocol_profiles")
    result: dict[str, str] = {}
    for category, profile_id in data.items():
        if (
            not isinstance(category, str)
            or not COMPONENT_ID_PATTERN.fullmatch(category)
            or not isinstance(profile_id, str)
            or not COMPONENT_ID_PATTERN.fullmatch(profile_id)
        ):
            raise ProjectModelError(
                "protocol_profiles must map category ids to profile ids"
            )
        result[category] = profile_id
    return result


def _Hardware_Parse(value: Any, *, board: str) -> HardwareConfiguration:
    data = _Object_Require(value, "hardware")
    expected = {
        "mode",
        "source_kind",
        "provider",
        "snapshot_id",
        "ioc_file",
        "mcu",
        "capabilities",
        "inventory",
        "resources",
        "build_sources",
        "asm_sources",
        "include_dirs",
        "defines",
        "linker_script",
        "source_digest",
        "source_label",
        "risk_acknowledged",
        "assignment_fingerprint",
    }
    if set(data) != expected:
        raise ProjectModelError("hardware has missing or unknown fields")
    mode = _String_Require(data, "mode")
    source_kind = _String_Require(data, "source_kind")
    provider = _String_Require(data, "provider", allow_empty=True)
    snapshot_id = _String_Require(data, "snapshot_id", allow_empty=True)
    ioc_file = _String_Require(data, "ioc_file", allow_empty=True)
    mcu = _String_Require(data, "mcu", allow_empty=True)
    source_digest = _String_Require(data, "source_digest", allow_empty=True)
    source_label = _String_Require(data, "source_label", allow_empty=True)
    assignment_fingerprint = _String_Require(
        data, "assignment_fingerprint", allow_empty=True
    )
    capabilities = tuple(_StringList_Require(data, "capabilities"))
    inventory = _Object_Require(data.get("inventory"), "hardware inventory")
    resources_value = data.get("resources")
    if not isinstance(resources_value, list):
        raise ProjectModelError("hardware.resources must be an array")
    resources: list[HardwareResource] = []
    resource_ids: set[str] = set()
    for entry_value in resources_value:
        entry = _Object_Require(entry_value, "hardware resource")
        if set(entry) != {"id", "kind", "metadata"}:
            raise ProjectModelError("hardware resource has missing or unknown fields")
        resource_id = _String_Require(entry, "id")
        kind = _String_Require(entry, "kind")
        metadata = _Object_Require(entry.get("metadata"), "hardware resource metadata")
        if not RESOURCE_ID_PATTERN.fullmatch(resource_id):
            raise ProjectModelError(f"Invalid hardware resource id: {resource_id!r}")
        if not COMPONENT_ID_PATTERN.fullmatch(kind):
            raise ProjectModelError(f"Invalid hardware resource kind: {kind!r}")
        if resource_id in resource_ids:
            raise ProjectModelError(f"Duplicate hardware resource: {resource_id}")
        resource_ids.add(resource_id)
        resources.append(HardwareResource(resource_id, kind, dict(metadata)))
    build_sources = tuple(_StringList_Require(data, "build_sources"))
    asm_sources = tuple(_StringList_Require(data, "asm_sources"))
    include_dirs = tuple(_StringList_Require(data, "include_dirs"))
    defines = tuple(_StringList_Require(data, "defines"))
    linker_script = _String_Require(data, "linker_script", allow_empty=True)
    for field_name, paths in (
        ("hardware.build_sources", build_sources),
        ("hardware.asm_sources", asm_sources),
        ("hardware.include_dirs", include_dirs),
    ):
        for path in paths:
            if (
                not RELATIVE_FILE_PATTERN.fullmatch(path)
                or path.startswith("/")
                or ".." in Path(path).parts
            ):
                raise ProjectModelError(f"{field_name} contains an invalid path")
    if linker_script and (
        not RELATIVE_FILE_PATTERN.fullmatch(linker_script)
        or linker_script.startswith("/")
        or ".." in Path(linker_script).parts
    ):
        raise ProjectModelError("hardware.linker_script is invalid")
    if not all(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:=[A-Za-z0-9_+.,:/()-]+)?", define)
        for define in defines
    ):
        raise ProjectModelError("hardware.defines contains an invalid token")
    risk_acknowledged = data.get("risk_acknowledged")
    if not isinstance(risk_acknowledged, bool):
        raise ProjectModelError("hardware.risk_acknowledged must be boolean")
    if mode not in HARDWARE_MODES:
        raise ProjectModelError("hardware.mode is invalid")
    if source_kind not in BOARD_SOURCE_KINDS:
        raise ProjectModelError("hardware.source_kind is invalid")
    _ComponentId_Validate(provider, "hardware provider", allow_empty=True)
    if snapshot_id and not SHA256_PATTERN.fullmatch(snapshot_id):
        raise ProjectModelError("hardware.snapshot_id is invalid")
    if source_digest and not SHA256_PATTERN.fullmatch(source_digest):
        raise ProjectModelError("hardware.source_digest is invalid")
    if assignment_fingerprint and not SHA256_PATTERN.fullmatch(
        assignment_fingerprint
    ):
        raise ProjectModelError("hardware.assignment_fingerprint is invalid")
    if ioc_file and (
        not RELATIVE_FILE_PATTERN.fullmatch(ioc_file)
        or ioc_file.startswith("/")
        or ".." in Path(ioc_file).parts
    ):
        raise ProjectModelError("hardware.ioc_file is invalid")
    if mode == "unselected":
        if board or provider or snapshot_id or ioc_file or mcu or source_digest:
            raise ProjectModelError("unselected hardware must not contain a selection")
        if source_kind != "unselected":
            raise ProjectModelError("unselected hardware requires unselected source_kind")
    if mode == "board_plugin" and not board:
        raise ProjectModelError("board_plugin hardware requires a board component")
    if mode == "custom":
        if board:
            raise ProjectModelError("custom hardware must not select a board plugin")
        if not provider:
            raise ProjectModelError("custom hardware requires a provider")
    return HardwareConfiguration(
        mode=mode,
        source_kind=source_kind,
        provider=provider,
        snapshot_id=snapshot_id,
        ioc_file=ioc_file,
        mcu=mcu,
        capabilities=capabilities,
        inventory=dict(inventory),
        resources=tuple(resources),
        build_sources=build_sources,
        asm_sources=asm_sources,
        include_dirs=include_dirs,
        defines=defines,
        linker_script=linker_script,
        source_digest=source_digest,
        source_label=source_label,
        risk_acknowledged=risk_acknowledged,
        assignment_fingerprint=assignment_fingerprint,
    )


def _Logging_Parse(value: Any) -> list[LogStreamConfig]:
    logging_data = _Object_Require(value, "logging")
    if set(logging_data) != {"streams"}:
        raise ProjectModelError("logging must contain only streams")
    streams_data = logging_data.get("streams", [])
    if not isinstance(streams_data, list):
        raise ProjectModelError("logging.streams must be an array")
    streams: list[LogStreamConfig] = []
    seen_records: set[str] = set()
    valid_policies = {"EVERY", "DECIMATION", "PERIODIC", "EVENT", "ONE_SHOT"}
    for entry_value in streams_data:
        entry = _Object_Require(entry_value, "logging stream")
        if set(entry) != {"record", "enabled", "policy", "decimation", "period_us"}:
            raise ProjectModelError("logging stream has missing or unknown fields")
        record = _String_Require(entry, "record")
        if not LOG_RECORD_PATTERN.fullmatch(record):
            raise ProjectModelError(f"Invalid logging record: {record!r}")
        if record in seen_records:
            raise ProjectModelError(f"Duplicate logging stream: {record}")
        seen_records.add(record)
        policy = _String_Require(entry, "policy")
        if policy not in valid_policies:
            raise ProjectModelError(f"Invalid logging policy for {record}: {policy}")
        decimation = entry.get("decimation")
        period_us = entry.get("period_us")
        if isinstance(decimation, bool) or not isinstance(decimation, int) or not 1 <= decimation <= 65535:
            raise ProjectModelError(f"Invalid decimation for {record}")
        if isinstance(period_us, bool) or not isinstance(period_us, int) or not 0 <= period_us <= 0xFFFFFFFF:
            raise ProjectModelError(f"Invalid period_us for {record}")
        enabled = entry.get("enabled")
        if not isinstance(enabled, bool):
            raise ProjectModelError(f"enabled must be boolean for {record}")
        streams.append(LogStreamConfig(record, enabled, policy, decimation, period_us))
    return streams


def _Build_Parse(value: Any) -> BuildOptions:
    data = _Object_Require(value, "build")
    expected = {
        "target_profile",
        "make_command",
        "toolchain_prefix",
        "gcc_path",
        "flash_command",
        "eide_mode",
        "tool_paths",
    }
    if set(data) != expected:
        raise ProjectModelError("build has missing or unknown fields")
    target_profile = _String_Require(data, "target_profile")
    if not PROJECT_TOKEN_PATTERN.fullmatch(target_profile):
        raise ProjectModelError(f"Invalid target profile: {target_profile!r}")
    toolchain_prefix = _String_Require(data, "toolchain_prefix")
    eide_mode = _String_Require(data, "eide_mode")
    if not TOOLCHAIN_PREFIX_PATTERN.fullmatch(toolchain_prefix):
        raise ProjectModelError("build.toolchain_prefix is invalid")
    if eide_mode != "native":
        raise ProjectModelError("Only EIDE native mode is supported")
    tool_paths = _Object_Require(data.get("tool_paths"), "build.tool_paths")
    allowed_tool_ids = {
        "compiler",
        "objcopy",
        "size",
        "make",
        "host_gcc",
        "debugger",
        "static_analyzer",
        "cubemx",
        "eide_builder",
    }
    if set(tool_paths) - allowed_tool_ids:
        raise ProjectModelError("build.tool_paths contains unknown tool ids")
    if not all(
        isinstance(path, str)
        and bool(path)
        and not any(ord(character) < 32 or ord(character) == 127 for character in path)
        for path in tool_paths.values()
    ):
        raise ProjectModelError("build.tool_paths must map tool ids to non-empty paths")
    return BuildOptions(
        target_profile=target_profile,
        make_command=_String_Require(data, "make_command"),
        toolchain_prefix=toolchain_prefix,
        gcc_path=_String_Require(data, "gcc_path", allow_empty=True),
        flash_command=_String_Require(data, "flash_command", allow_empty=True),
        eide_mode=eide_mode,
        tool_paths=dict(tool_paths),
    )


def _Provenance_Parse(value: Any) -> dict[str, dict[str, Any]]:
    provenance = _Object_Require(value, "component_provenance")
    for component_id, entry_value in provenance.items():
        if not isinstance(component_id, str) or not COMPONENT_ID_PATTERN.fullmatch(
            component_id
        ):
            raise ProjectModelError(
                "component_provenance contains an invalid component id"
            )
        entry = _Object_Require(entry_value, f"component_provenance.{component_id}")
        expected = {"version", "source", "manifest_id", "payload_digest", "files"}
        if set(entry) != expected or entry.get("manifest_id") != component_id:
            raise ProjectModelError(
                f"component_provenance.{component_id} has missing or invalid fields"
            )
        version = entry.get("version")
        digest = entry.get("payload_digest")
        if not isinstance(version, str) or not FIRMWARE_VERSION_PATTERN.fullmatch(version):
            raise ProjectModelError(
                f"component_provenance.{component_id} has an invalid version"
            )
        if entry.get("source") not in ("builtin", "installed"):
            raise ProjectModelError(
                f"component_provenance.{component_id} has an invalid source"
            )
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ProjectModelError(
                f"component_provenance.{component_id} has an invalid payload digest"
            )
        files = _Object_Require(entry.get("files"), f"component_provenance.{component_id}.files")
        if not all(
            isinstance(path, str)
            and bool(path)
            and isinstance(file_digest, str)
            and SHA256_PATTERN.fullmatch(file_digest)
            for path, file_digest in files.items()
        ):
            raise ProjectModelError(
                f"component_provenance.{component_id}.files is invalid"
            )
    return dict(provenance)


def ProjectModel_Parse(data: dict[str, Any]) -> ProjectModel:
    root = _Object_Require(data, "project file")
    if root.get("format_version") == 0:
        root = _ProjectV0_Migrate(root)
    if root.get("format_version") == 1:
        root = _ProjectV1_Migrate(root)
    if root.get("format_version") == 2:
        root = _ProjectV2_Migrate(root)
    if root.get("format_version") == 3:
        root = _ProjectV3_Migrate(root)
    if root.get("format_version") == 4:
        root = _ProjectV4_Migrate(root)
    if root.get("format_version") == 5:
        root = _ProjectV5_Migrate(root)
    required_root = {
        "format_version",
        "project",
        "components",
        "modes",
        "mode_parameters",
        "protocol_profiles",
        "hardware",
        "resources",
        "capability_sources",
        "logging",
        "build",
        "generated_glue",
        "component_provenance",
        "reference_provenance",
    }
    if set(root) != required_root:
        missing = required_root - set(root)
        unknown = set(root) - required_root
        details = [
            *(f"missing {name}" for name in sorted(missing)),
            *(f"unknown {name}" for name in sorted(unknown)),
        ]
        raise ProjectModelError("Project fields are invalid: " + ", ".join(details))
    if root.get("format_version") != PROJECT_FORMAT_VERSION:
        raise ProjectModelError(
            f"Only project format_version {PROJECT_FORMAT_VERSION} is supported"
        )
    project_data = _Object_Require(root.get("project"), "project")
    if set(project_data) != {"name", "firmware_version", "build_target"}:
        raise ProjectModelError(
            "project must contain name, firmware_version and build_target"
        )
    name = _String_Require(project_data, "name")
    firmware_version = _String_Require(project_data, "firmware_version")
    build_target = _String_Require(project_data, "build_target")
    if not PROJECT_NAME_PATTERN.fullmatch(name) or name.strip() != name:
        raise ProjectModelError(f"Invalid project name: {name!r}")
    if not FIRMWARE_VERSION_PATTERN.fullmatch(firmware_version):
        raise ProjectModelError(f"Invalid firmware version: {firmware_version!r}")
    if not PROJECT_TOKEN_PATTERN.fullmatch(build_target):
        raise ProjectModelError(f"Invalid build target: {build_target!r}")
    (
        core,
        mcu,
        board,
        os_component,
        device_instances,
        base,
        strategies,
        protocol_bundles,
        environment,
    ) = _Components_Parse(root.get("components"))
    modes = _Modes_Parse(root.get("modes"))
    mode_parameters = _ModeParameters_Parse(root.get("mode_parameters"))
    protocol_profiles = _ProtocolProfiles_Parse(root.get("protocol_profiles"))
    hardware = _Hardware_Parse(root.get("hardware"), board=board)
    resources = _Object_Require(root.get("resources"), "resources")
    if not all(
        isinstance(key, str)
        and RESOURCE_KEY_PATTERN.fullmatch(key)
        and isinstance(resource_id, str)
        and RESOURCE_ID_PATTERN.fullmatch(resource_id)
        for key, resource_id in resources.items()
    ):
        raise ProjectModelError(
            "resources must map requirement keys to resource ids"
        )
    capability_sources = _Object_Require(
        root.get("capability_sources"), "capability_sources"
    )
    instance_ids = {instance.instance_id for instance in device_instances}
    if not all(
        isinstance(capability, str)
        and COMPONENT_ID_PATTERN.fullmatch(capability)
        and isinstance(instance_id, str)
        and instance_id in instance_ids
        for capability, instance_id in capability_sources.items()
    ):
        raise ProjectModelError(
            "capability_sources must map capabilities to selected device instances"
        )
    generated_wrapper = {"generated_glue": root.get("generated_glue")}
    generated_glue = _StringList_Require(generated_wrapper, "generated_glue")
    if any(not PROJECT_TOKEN_PATTERN.fullmatch(value) for value in generated_glue):
        raise ProjectModelError("generated_glue contains an invalid identifier")
    reference_provenance = _Object_Require(
        root.get("reference_provenance"), "reference_provenance"
    )
    return ProjectModel(
        identity=ProjectIdentity(name, firmware_version, build_target),
        core=core,
        mcu=mcu,
        board=board,
        os=os_component,
        device_instances=device_instances,
        base_components=base,
        strategies=strategies,
        modes=modes,
        mode_parameters=mode_parameters,
        protocol_bundles=protocol_bundles,
        protocol_profiles=protocol_profiles,
        development_environment=environment,
        hardware=hardware,
        resource_assignments=dict(resources),
        capability_source_overrides=dict(capability_sources),
        logging_streams=_Logging_Parse(root.get("logging")),
        build=_Build_Parse(root.get("build")),
        generated_glue=generated_glue,
        component_provenance=_Provenance_Parse(root.get("component_provenance")),
        reference_provenance=dict(reference_provenance),
        format_version=PROJECT_FORMAT_VERSION,
    )


def ProjectModel_Load(path: Path) -> ProjectModel:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProjectModelError(f"Cannot read project file {path}: {error}") from error
    return ProjectModel_Parse(data)


def ProjectModel_Save(model: ProjectModel, path: Path, policy: WorkspacePolicy) -> Path:
    serialized = json.dumps(
        model.Dictionary_Get(), ensure_ascii=False, indent=2, sort_keys=False
    ) + "\n"
    return policy.Text_AtomicWrite(path, serialized)
