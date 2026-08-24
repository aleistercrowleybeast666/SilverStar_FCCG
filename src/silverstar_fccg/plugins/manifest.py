from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.core.errors import FccgError


PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][0-9A-Za-z.-]+)?$")
RESOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
RESOURCE_ROLE_PATTERN = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*:[a-z0-9]+(?:[._-][a-z0-9]+)*$"
)
BINDING_MACRO_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
DEFINE_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:=[A-Za-z0-9_+.,:/()|-]+)?$"
)
BUILD_TOKEN_PATTERN = re.compile(r"^[-A-Za-z0-9_+.,=:/]+$")
BUILD_PATH_PATTERN = re.compile(r"^[A-Za-z0-9_./+@-]+$")
TOOLCHAIN_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9_.+-]*$")
SELECTION_OPTION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

ALLOWED_PLUGIN_TYPES = frozenset(
    {
        "core",
        "mcu",
        "board",
        "device",
        "algorithm",
        "flight_logic",
        "os",
        "protocol_bundle",
        "hardware_configuration_provider",
        "development_environment",
    }
)
UTILITY_PLUGIN_TYPES = frozenset(
    {"hardware_configuration_provider", "development_environment"}
)
ALLOWED_BOARD_SOURCE_KINDS = frozenset(
    {"verified_builtin", "manual_import", "third_party"}
)
ALLOWED_PROVIDER_HANDLERS = frozenset({"stm32_cubemx"})
ALLOWED_ENVIRONMENT_RENDERERS = frozenset({"vscode_eide_gcc"})
ALLOWED_DEVICE_CARDINALITIES = frozenset({"single", "multiple"})


class PluginManifestError(FccgError):
    pass


class ResourceMode(StrEnum):
    EXCLUSIVE = "exclusive"
    SHARED = "shared"


class SelectionKind(StrEnum):
    STRATEGY = "strategy"
    MODE = "mode"


@dataclass(frozen=True, slots=True)
class ComponentRequirement:
    component_id: str
    optional: bool = False


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    capability: str
    purpose: str = "runtime"


@dataclass(frozen=True, slots=True)
class SelectionOptionRequirements:
    capabilities: tuple[CapabilityRequirement, ...] = ()
    components: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeviceInstancePolicy:
    project_max: int = 1
    same_plugin_multiple: bool = False
    multi_instance_ready: bool = False


@dataclass(frozen=True, slots=True)
class PhysicalDeviceContribution:
    vendor: str
    model: str
    chipset: str
    driver: str


@dataclass(frozen=True, slots=True)
class ResourceRequirement:
    name: str
    kind: str
    binding_macro: str = ""
    required: bool = True
    mode: ResourceMode = ResourceMode.EXCLUSIVE
    candidates: tuple[str, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    display_names: dict[str, str] = field(default_factory=dict)

    def DisplayName_Get(self, language: str) -> str:
        localized = self.display_names.get(language)
        return localized if localized else self.name.replace("_", " ")


@dataclass(frozen=True, slots=True)
class ResourceProvision:
    resource_id: str
    kind: str
    capabilities: tuple[str, ...] = ()
    reserved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ResourceRole:
    key: str
    kind: str
    default: str
    candidates: tuple[str, ...]
    fixed: bool = False


@dataclass(frozen=True, slots=True)
class ResourceConflict:
    resources: tuple[str, ...]
    message: str = ""


@dataclass(frozen=True, slots=True)
class SelectionContribution:
    kind: SelectionKind
    slot: str
    required: bool
    allow_none: bool
    allow_multiple: bool
    ui_order: int
    options: tuple[str, ...] = ()
    default: tuple[str, ...] = ()
    labels: dict[str, dict[str, str]] = field(default_factory=dict)
    option_requirements: dict[str, SelectionOptionRequirements] = field(
        default_factory=dict
    )
    none_defines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BoardContribution:
    source_kind: str
    compatible_mcus: tuple[str, ...]
    vendor: str
    provider: str
    verified: bool
    hardware_root: str
    ioc_file: str = ""
    connections_file: str = ""


@dataclass(frozen=True, slots=True)
class ProtocolContribution:
    logging_metadata: str
    maintenance_protocol_version: str
    firmware_version: str
    documentation_version: str


@dataclass(frozen=True, slots=True)
class HardwareProviderContribution:
    vendor: str
    handler: str
    accepted_inputs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EnvironmentContribution:
    renderer: str
    toolchain: str
    outputs: tuple[str, ...]
    tasks: tuple[str, ...]
    eide_native: bool


@dataclass(frozen=True, slots=True)
class BuildContribution:
    sources: tuple[str, ...] = ()
    asm_sources: tuple[str, ...] = ()
    include_dirs: tuple[str, ...] = ()
    defines: tuple[str, ...] = ()
    mcu_flags: tuple[str, ...] = ()
    specs: tuple[str, ...] = ()
    libraries: tuple[str, ...] = ()
    forced_includes: tuple[str, ...] = ()
    virtual_sources: tuple[str, ...] = ()
    exclude_sources: tuple[str, ...] = ()
    linker_script: str = ""
    toolchain_prefix: str = ""


@dataclass(frozen=True, slots=True)
class PluginManifest:
    schema_version: int
    component_id: str
    name: str
    component_type: str
    component_class: str
    version: str
    description: str
    dependencies: tuple[ComponentRequirement, ...]
    resource_requirements: tuple[ResourceRequirement, ...]
    resource_provisions: tuple[ResourceProvision, ...]
    resource_roles: tuple[ResourceRole, ...]
    resource_conflicts: tuple[ResourceConflict, ...]
    provides: tuple[str, ...]
    capability_requirements: tuple[CapabilityRequirement, ...]
    build: BuildContribution
    payload_roots: tuple[str, ...]
    metadata: dict[str, Any]
    manifest_path: Path
    instance_policy: DeviceInstancePolicy = DeviceInstancePolicy()
    physical_device: PhysicalDeviceContribution | None = None
    selection: SelectionContribution | None = None
    board: BoardContribution | None = None
    protocol: ProtocolContribution | None = None
    hardware_provider: HardwareProviderContribution | None = None
    environment: EnvironmentContribution | None = None
    source: str = "builtin"

    @property
    def capabilities_required(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                requirement.capability
                for requirement in self.capability_requirements
            )
        )

    @property
    def cardinality(self) -> str:
        return "multiple" if self.instance_policy.project_max > 1 else "single"

    @property
    def package_root(self) -> Path:
        return self.manifest_path.parent

    @property
    def payload_root(self) -> Path:
        return self.package_root / "payload"

    def DisplayName_Get(self, language: str) -> str:
        values = self.metadata.get("display_names", {})
        if isinstance(values, dict):
            localized = values.get(language)
            if isinstance(localized, str) and localized.strip():
                return localized
        return self.name

    def Description_Get(self, language: str) -> str:
        values = self.metadata.get("descriptions", {})
        if isinstance(values, dict):
            localized = values.get(language)
            if isinstance(localized, str) and localized.strip():
                return localized
        return self.description

    def PayloadFiles_Get(self) -> tuple[Path, ...]:
        files: list[Path] = []
        for root_name in self.payload_roots:
            root = self.payload_root.joinpath(*root_name.split("/"))
            if root.is_symlink():
                raise PluginManifestError(
                    f"Plugin payload root is a symlink: {root_name}"
                )
            if root.is_file():
                files.append(root)
            elif root.is_dir():
                for path in sorted(root.rglob("*")):
                    if path.is_symlink():
                        raise PluginManifestError(
                            f"Plugin payload contains a symlink: {path}"
                        )
                    if path.is_file():
                        files.append(path)
            else:
                raise PluginManifestError(f"Missing payload root: {root_name}")
        unique = {
            path.relative_to(self.payload_root).as_posix(): path for path in files
        }
        return tuple(unique[name] for name in sorted(unique))


def _StringTuple_Get(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(item, str) and bool(item) for item in value
    ):
        raise PluginManifestError(f"{field_name} must be an array of strings")
    if len(value) != len(set(value)):
        raise PluginManifestError(f"{field_name} contains duplicate values")
    return tuple(value)


def _Boolean_Get(data: dict[str, Any], field_name: str, default: bool) -> bool:
    if field_name not in data:
        return default
    value = data[field_name]
    if not isinstance(value, bool):
        raise PluginManifestError(f"{field_name} must be a boolean")
    return value


def _CapabilityTuple_Validate(values: tuple[str, ...], field_name: str) -> None:
    invalid = [value for value in values if not PLUGIN_ID_PATTERN.fullmatch(value)]
    if invalid:
        raise PluginManifestError(
            f"{field_name} contains invalid capability: {invalid[0]!r}"
        )


def _CapabilityRequirements_Parse(value: Any) -> tuple[CapabilityRequirement, ...]:
    if not isinstance(value, list):
        raise PluginManifestError("requires.capabilities must be an array")
    requirements: list[CapabilityRequirement] = []
    identities: set[tuple[str, str]] = set()
    for entry in value:
        if isinstance(entry, str):
            capability = entry
            purpose = "runtime"
        elif isinstance(entry, dict) and set(entry) == {"capability", "purpose"}:
            capability = entry.get("capability")
            purpose = entry.get("purpose")
        else:
            raise PluginManifestError(
                "requires.capabilities entries must be strings or "
                "capability/purpose objects"
            )
        if not isinstance(capability, str) or not PLUGIN_ID_PATTERN.fullmatch(
            capability
        ):
            raise PluginManifestError(
                f"requires.capabilities contains invalid capability: {capability!r}"
            )
        if not isinstance(purpose, str) or not PLUGIN_ID_PATTERN.fullmatch(purpose):
            raise PluginManifestError(
                f"requires.capabilities contains invalid purpose: {purpose!r}"
            )
        identity = (capability, purpose)
        if identity in identities:
            raise PluginManifestError(
                "requires.capabilities contains duplicate capability/purpose"
            )
        identities.add(identity)
        requirements.append(CapabilityRequirement(capability, purpose))
    return tuple(requirements)


def _InstancePolicy_Parse(
    value: Any, *, component_type: str, legacy_cardinality: Any
) -> DeviceInstancePolicy:
    if component_type != "device":
        if value is not None or legacy_cardinality is not None:
            raise PluginManifestError(
                "only device plugins may declare instance_policy/cardinality"
            )
        return DeviceInstancePolicy()
    if value is not None and legacy_cardinality is not None:
        raise PluginManifestError(
            "device plugin cannot declare both instance_policy and cardinality"
        )
    if value is None:
        if legacy_cardinality is None:
            raise PluginManifestError(
                "device plugin must declare instance_policy"
            )
        if legacy_cardinality not in ALLOWED_DEVICE_CARDINALITIES:
            raise PluginManifestError("cardinality must be single or multiple")
        return DeviceInstancePolicy(
            project_max=16 if legacy_cardinality == "multiple" else 1,
            same_plugin_multiple=False,
            multi_instance_ready=False,
        )
    if not isinstance(value, dict) or set(value) not in (
        {"project_max", "same_plugin_multiple"},
        {"project_max", "same_plugin_multiple", "multi_instance_ready"},
    ):
        raise PluginManifestError(
            "instance_policy must contain project_max, same_plugin_multiple "
            "and optionally multi_instance_ready"
        )
    project_max = value.get("project_max")
    same_plugin_multiple = value.get("same_plugin_multiple")
    multi_instance_ready = value.get("multi_instance_ready", False)
    if (
        isinstance(project_max, bool)
        or not isinstance(project_max, int)
        or not 1 <= project_max <= 64
    ):
        raise PluginManifestError(
            "instance_policy.project_max must be an integer from 1 to 64"
        )
    if not isinstance(same_plugin_multiple, bool):
        raise PluginManifestError(
            "instance_policy.same_plugin_multiple must be boolean"
        )
    if not isinstance(multi_instance_ready, bool):
        raise PluginManifestError(
            "instance_policy.multi_instance_ready must be boolean"
        )
    if project_max == 1 and same_plugin_multiple:
        raise PluginManifestError(
            "same_plugin_multiple cannot be true when project_max is 1"
        )
    if same_plugin_multiple and not multi_instance_ready:
        raise PluginManifestError(
            "same_plugin_multiple requires multi_instance_ready"
        )
    if project_max == 1 and multi_instance_ready:
        raise PluginManifestError(
            "multi_instance_ready cannot be true when project_max is 1"
        )
    return DeviceInstancePolicy(
        project_max, same_plugin_multiple, multi_instance_ready
    )


def _PhysicalDevice_Parse(
    value: Any, *, component_type: str
) -> PhysicalDeviceContribution | None:
    if value is None:
        if component_type == "device":
            raise PluginManifestError(
                "device plugin must declare physical_device"
            )
        return None
    if component_type != "device":
        raise PluginManifestError("only device plugins may declare physical_device")
    if not isinstance(value, dict) or set(value) != {
        "vendor",
        "model",
        "chipset",
        "driver",
    }:
        raise PluginManifestError(
            "physical_device must contain vendor, model, chipset and driver"
        )
    fields = tuple(value.get(name) for name in ("vendor", "model", "chipset", "driver"))
    if not all(isinstance(field_value, str) and field_value.strip() for field_value in fields):
        raise PluginManifestError("physical_device fields must be non-empty strings")
    return PhysicalDeviceContribution(*fields)


def _BuildTokens_Validate(
    values: tuple[str, ...], field_name: str, pattern: re.Pattern[str]
) -> None:
    invalid = [value for value in values if not pattern.fullmatch(value)]
    if invalid:
        raise PluginManifestError(
            f"{field_name} contains an unsafe token: {invalid[0]!r}"
        )


def _RelativePaths_Validate(paths: tuple[str, ...], field_name: str) -> None:
    policy = WorkspacePolicy(Path.cwd())
    for value in paths:
        try:
            policy.RelativePath_Validate(value)
        except ValueError as error:
            raise PluginManifestError(
                f"Invalid {field_name} path {value!r}"
            ) from error


def _Dependencies_Parse(requires: dict[str, Any]) -> tuple[ComponentRequirement, ...]:
    dependencies: list[ComponentRequirement] = []
    for entry in requires.get("components", []):
        if not isinstance(entry, dict) or set(entry) - {"id", "optional"}:
            raise PluginManifestError(
                "requires.components entries must contain id/optional"
            )
        dependency_id = entry.get("id")
        if not isinstance(dependency_id, str) or not PLUGIN_ID_PATTERN.fullmatch(
            dependency_id
        ):
            raise PluginManifestError(f"Invalid dependency id: {dependency_id!r}")
        dependencies.append(
            ComponentRequirement(
                dependency_id, _Boolean_Get(entry, "optional", False)
            )
        )
    ids = [dependency.component_id for dependency in dependencies]
    if len(ids) != len(set(ids)):
        raise PluginManifestError("requires.components contains duplicate ids")
    return tuple(dependencies)


def _ResourceRequirements_Parse(
    requires: dict[str, Any],
) -> tuple[ResourceRequirement, ...]:
    requirements: list[ResourceRequirement] = []
    for entry in requires.get("resources", []):
        if not isinstance(entry, dict):
            raise PluginManifestError("requires.resources entries must be objects")
        if set(entry) - {
            "name",
            "kind",
            "binding_macro",
            "required",
            "mode",
            "candidates",
            "constraints",
            "display_names",
        }:
            raise PluginManifestError("resource requirement contains unknown fields")
        name = entry.get("name")
        kind = entry.get("kind")
        if not isinstance(name, str) or not PLUGIN_ID_PATTERN.fullmatch(name):
            raise PluginManifestError(
                f"Invalid resource requirement name: {name!r}"
            )
        if not isinstance(kind, str) or not PLUGIN_ID_PATTERN.fullmatch(kind):
            raise PluginManifestError(f"Invalid resource kind: {kind!r}")
        try:
            mode = ResourceMode(entry.get("mode", "exclusive"))
        except ValueError as error:
            raise PluginManifestError(f"Invalid resource mode for {name}") from error
        candidates = _StringTuple_Get(
            entry.get("candidates", []), "resource candidates"
        )
        _BuildTokens_Validate(candidates, "resource candidates", RESOURCE_ID_PATTERN)
        binding_macro = entry.get("binding_macro", "")
        if not isinstance(binding_macro, str) or (
            binding_macro and not BINDING_MACRO_PATTERN.fullmatch(binding_macro)
        ):
            raise PluginManifestError(
                f"Invalid resource binding_macro for {name}: {binding_macro!r}"
            )
        constraints = entry.get("constraints", {})
        if not isinstance(constraints, dict):
            raise PluginManifestError(
                f"Resource constraints for {name} must be an object"
            )
        allowed_constraints = {
            "baud_rate",
            "mode",
            "signals",
            "dma_rx_required",
            "dma_tx_required",
            "irq_required",
        }
        unknown_constraints = set(constraints) - allowed_constraints
        if unknown_constraints:
            raise PluginManifestError(
                f"Resource constraints for {name} contain unknown fields: "
                + ", ".join(sorted(unknown_constraints))
            )
        baud_rate = constraints.get("baud_rate")
        if baud_rate is not None and (
            isinstance(baud_rate, bool)
            or not isinstance(baud_rate, int)
            or baud_rate < 1
        ):
            raise PluginManifestError(
                f"Resource baud_rate constraint for {name} must be a positive integer"
            )
        constraint_mode = constraints.get("mode")
        if constraint_mode is not None and (
            not isinstance(constraint_mode, str) or not constraint_mode
        ):
            raise PluginManifestError(
                f"Resource mode constraint for {name} must be a non-empty string"
            )
        signals = constraints.get("signals")
        if signals is not None:
            _StringTuple_Get(signals, f"resource signals for {name}")
            if len(signals) != len(set(signals)):
                raise PluginManifestError(
                    f"Resource signal constraints for {name} contain duplicates"
                )
        for flag in (
            "dma_rx_required",
            "dma_tx_required",
            "irq_required",
        ):
            if flag in constraints and not isinstance(constraints[flag], bool):
                raise PluginManifestError(
                    f"Resource {flag} constraint for {name} must be a boolean"
                )
        display_names = entry.get("display_names", {})
        if not isinstance(display_names, dict) or not all(
            isinstance(language, str)
            and bool(language)
            and isinstance(display_name, str)
            and bool(display_name.strip())
            for language, display_name in display_names.items()
        ):
            raise PluginManifestError(
                f"Resource display_names for {name} must map languages to text"
            )
        requirements.append(
            ResourceRequirement(
                name=name,
                kind=kind,
                binding_macro=binding_macro,
                required=_Boolean_Get(entry, "required", True),
                mode=mode,
                candidates=candidates,
                constraints=dict(constraints),
                display_names=dict(display_names),
            )
        )
    names = [requirement.name for requirement in requirements]
    if len(names) != len(set(names)):
        raise PluginManifestError("requires.resources contains duplicate names")
    return tuple(requirements)


def _Resources_Parse(
    data: Any,
) -> tuple[
    tuple[ResourceProvision, ...],
    tuple[ResourceRole, ...],
    tuple[ResourceConflict, ...],
]:
    resources = data if data is not None else {}
    if not isinstance(resources, dict) or set(resources) - {
        "provides",
        "roles",
        "conflicts",
    }:
        raise PluginManifestError(
            "resources must contain only provides, roles and conflicts"
        )
    provisions: list[ResourceProvision] = []
    for entry in resources.get("provides", []):
        if not isinstance(entry, dict):
            raise PluginManifestError("resources.provides entries must be objects")
        if set(entry) - {"id", "kind", "capabilities", "reserved", "metadata"}:
            raise PluginManifestError("provided resource contains unknown fields")
        resource_id = entry.get("id")
        kind = entry.get("kind")
        if not isinstance(resource_id, str) or not RESOURCE_ID_PATTERN.fullmatch(
            resource_id
        ):
            raise PluginManifestError(
                f"Invalid provided resource id: {resource_id!r}"
            )
        if not isinstance(kind, str) or not PLUGIN_ID_PATTERN.fullmatch(kind):
            raise PluginManifestError(f"Invalid provided resource kind: {kind!r}")
        metadata = entry.get("metadata", {})
        if not isinstance(metadata, dict):
            raise PluginManifestError("resource metadata must be an object")
        capabilities = _StringTuple_Get(
            entry.get("capabilities", []), "resource capabilities"
        )
        _CapabilityTuple_Validate(capabilities, "resource capabilities")
        provisions.append(
            ResourceProvision(
                resource_id=resource_id,
                kind=kind,
                capabilities=capabilities,
                reserved=_Boolean_Get(entry, "reserved", False),
                metadata=dict(metadata),
            )
        )
    provision_ids = [provision.resource_id for provision in provisions]
    if len(provision_ids) != len(set(provision_ids)):
        raise PluginManifestError("resources.provides contains duplicate ids")

    roles: list[ResourceRole] = []
    for entry in resources.get("roles", []):
        if not isinstance(entry, dict) or set(entry) - {
            "key",
            "kind",
            "default",
            "candidates",
            "fixed",
        }:
            raise PluginManifestError("resource role contains unknown fields")
        key = entry.get("key")
        kind = entry.get("kind")
        default = entry.get("default", "")
        candidates = _StringTuple_Get(
            entry.get("candidates", []), "resource role candidates"
        )
        if not isinstance(key, str) or not RESOURCE_ROLE_PATTERN.fullmatch(key):
            raise PluginManifestError(f"Invalid resource role key: {key!r}")
        if not isinstance(kind, str) or not PLUGIN_ID_PATTERN.fullmatch(kind):
            raise PluginManifestError(f"Invalid resource role kind: {kind!r}")
        if not isinstance(default, str) or (
            default and not RESOURCE_ID_PATTERN.fullmatch(default)
        ):
            raise PluginManifestError(f"Invalid resource role default: {default!r}")
        _BuildTokens_Validate(
            candidates, "resource role candidates", RESOURCE_ID_PATTERN
        )
        fixed = _Boolean_Get(entry, "fixed", False)
        if default and candidates and default not in candidates:
            raise PluginManifestError(
                f"Resource role {key} default is not in candidates"
            )
        if fixed and not default:
            raise PluginManifestError(
                f"Fixed resource role {key} must declare a default"
            )
        roles.append(ResourceRole(key, kind, default, candidates, fixed))
    role_keys = [role.key for role in roles]
    if len(role_keys) != len(set(role_keys)):
        raise PluginManifestError("resources.roles contains duplicate keys")

    conflicts: list[ResourceConflict] = []
    for entry in resources.get("conflicts", []):
        if not isinstance(entry, dict) or set(entry) - {"resources", "message"}:
            raise PluginManifestError("resource conflict contains unknown fields")
        conflict_resources = _StringTuple_Get(
            entry.get("resources", []), "resource conflict resources"
        )
        if len(conflict_resources) < 2:
            raise PluginManifestError(
                "resource conflict must contain at least two resources"
            )
        _BuildTokens_Validate(
            conflict_resources, "resource conflict resources", RESOURCE_ID_PATTERN
        )
        message = entry.get("message", "")
        if not isinstance(message, str):
            raise PluginManifestError("resource conflict message must be a string")
        conflicts.append(ResourceConflict(conflict_resources, message))
    return tuple(provisions), tuple(roles), tuple(conflicts)


def _Selection_Parse(value: Any) -> SelectionContribution | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "kind",
        "slot",
        "required",
        "allow_none",
        "allow_multiple",
        "ui_order",
        "options",
        "default",
        "labels",
        "option_requirements",
        "none_defines",
    }:
        raise PluginManifestError("selection contains unknown fields")
    try:
        kind = SelectionKind(value.get("kind"))
    except (TypeError, ValueError) as error:
        raise PluginManifestError("selection.kind is invalid") from error
    slot = value.get("slot")
    if not isinstance(slot, str) or not PLUGIN_ID_PATTERN.fullmatch(slot):
        raise PluginManifestError("selection.slot is invalid")
    ui_order = value.get("ui_order", 100)
    if (
        isinstance(ui_order, bool)
        or not isinstance(ui_order, int)
        or not 0 <= ui_order <= 10000
    ):
        raise PluginManifestError(
            "selection.ui_order must be an integer from 0 to 10000"
        )
    options = _StringTuple_Get(value.get("options", []), "selection.options")
    invalid_option = next(
        (option for option in options if not SELECTION_OPTION_PATTERN.fullmatch(option)),
        None,
    )
    if invalid_option is not None:
        raise PluginManifestError(f"Invalid selection option: {invalid_option!r}")
    default_value = value.get("default", [])
    if isinstance(default_value, str):
        default = (default_value,) if default_value else ()
    else:
        default = _StringTuple_Get(default_value, "selection.default")
    if any(option not in options for option in default):
        raise PluginManifestError("selection.default contains an unknown option")
    required = _Boolean_Get(value, "required", kind == SelectionKind.STRATEGY)
    allow_none = _Boolean_Get(value, "allow_none", not required)
    allow_multiple = _Boolean_Get(value, "allow_multiple", False)
    if kind == SelectionKind.STRATEGY and (options or default or allow_multiple):
        raise PluginManifestError(
            "strategy selection cannot declare options/default/allow_multiple"
        )
    if kind == SelectionKind.MODE and not options:
        raise PluginManifestError("mode selection must declare options")
    if not allow_multiple and len(default) > 1:
        raise PluginManifestError("single selection has more than one default")
    if not allow_none and not default and kind == SelectionKind.MODE:
        raise PluginManifestError(
            "mode selection that disallows none needs a default"
        )
    labels = value.get("labels", {})
    if not isinstance(labels, dict):
        raise PluginManifestError("selection.labels must be an object")
    normalized_labels: dict[str, dict[str, str]] = {}
    for language, language_values in labels.items():
        if not isinstance(language, str) or not isinstance(language_values, dict):
            raise PluginManifestError("selection.labels entries must be objects")
        if set(language_values) - set(options) or not all(
            isinstance(label, str) and bool(label.strip())
            for label in language_values.values()
        ):
            raise PluginManifestError("selection.labels contains invalid options")
        normalized_labels[language] = dict(language_values)
    option_requirements_value = value.get("option_requirements", {})
    if not isinstance(option_requirements_value, dict):
        raise PluginManifestError("selection.option_requirements must be an object")
    option_requirements: dict[str, SelectionOptionRequirements] = {}
    for option, requirements_value in option_requirements_value.items():
        if option not in options or not isinstance(requirements_value, dict):
            raise PluginManifestError(
                "selection.option_requirements contains an invalid option"
            )
        if set(requirements_value) - {"capabilities", "components"}:
            raise PluginManifestError(
                "selection.option_requirements contains unknown fields"
            )
        components = _StringTuple_Get(
            requirements_value.get("components", []),
            f"selection.option_requirements.{option}.components",
        )
        _BuildTokens_Validate(
            components,
            f"selection.option_requirements.{option}.components",
            PLUGIN_ID_PATTERN,
        )
        option_requirements[option] = SelectionOptionRequirements(
            capabilities=_CapabilityRequirements_Parse(
                requirements_value.get("capabilities", [])
            ),
            components=components,
        )
    none_defines = _StringTuple_Get(
        value.get("none_defines", []), "selection.none_defines"
    )
    _BuildTokens_Validate(none_defines, "selection.none_defines", DEFINE_PATTERN)
    return SelectionContribution(
        kind=kind,
        slot=slot,
        required=required,
        allow_none=allow_none,
        allow_multiple=allow_multiple,
        ui_order=ui_order,
        options=options,
        default=default,
        labels=normalized_labels,
        option_requirements=option_requirements,
        none_defines=none_defines,
    )


def _Board_Parse(value: Any) -> BoardContribution | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "source_kind",
        "compatible_mcus",
        "vendor",
        "provider",
        "verified",
        "hardware_root",
        "ioc_file",
        "connections_file",
    }:
        raise PluginManifestError("board contains unknown fields")
    source_kind = value.get("source_kind")
    if source_kind not in ALLOWED_BOARD_SOURCE_KINDS:
        raise PluginManifestError("board.source_kind is invalid")
    compatible_mcus = _StringTuple_Get(
        value.get("compatible_mcus", []), "board.compatible_mcus"
    )
    if not compatible_mcus or any(
        not PLUGIN_ID_PATTERN.fullmatch(item) for item in compatible_mcus
    ):
        raise PluginManifestError("board.compatible_mcus is invalid")
    vendor = value.get("vendor", "")
    provider = value.get("provider", "")
    hardware_root = value.get("hardware_root", "")
    ioc_file = value.get("ioc_file", "")
    connections_file = value.get("connections_file", "")
    if not isinstance(vendor, str) or not vendor:
        raise PluginManifestError("board.vendor must be a non-empty string")
    if not isinstance(provider, str) or (
        provider and not PLUGIN_ID_PATTERN.fullmatch(provider)
    ):
        raise PluginManifestError("board.provider is invalid")
    if not isinstance(hardware_root, str):
        raise PluginManifestError("board.hardware_root must be a string")
    if hardware_root:
        _RelativePaths_Validate((hardware_root,), "board.hardware_root")
    for field_name, relative_path in (
        ("board.ioc_file", ioc_file),
        ("board.connections_file", connections_file),
    ):
        if not isinstance(relative_path, str):
            raise PluginManifestError(f"{field_name} must be a string")
        if relative_path:
            _RelativePaths_Validate((relative_path,), field_name)
    return BoardContribution(
        source_kind=source_kind,
        compatible_mcus=compatible_mcus,
        vendor=vendor,
        provider=provider,
        verified=_Boolean_Get(value, "verified", False),
        hardware_root=hardware_root,
        ioc_file=ioc_file,
        connections_file=connections_file,
    )


def _Protocol_Parse(value: Any) -> ProtocolContribution | None:
    if value is None:
        return None
    expected = {
        "logging_metadata",
        "maintenance_protocol_version",
        "firmware_version",
        "documentation_version",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise PluginManifestError(
            "protocol must contain logging metadata and explicit version fields"
        )
    metadata_path = value.get("logging_metadata")
    if not isinstance(metadata_path, str) or not metadata_path:
        raise PluginManifestError("protocol.logging_metadata must be a path")
    _RelativePaths_Validate((metadata_path,), "protocol.logging_metadata")
    versions = tuple(
        value.get(field_name)
        for field_name in (
            "maintenance_protocol_version",
            "firmware_version",
            "documentation_version",
        )
    )
    if not all(
        isinstance(version, str) and VERSION_PATTERN.fullmatch(version)
        for version in versions
    ):
        raise PluginManifestError("protocol version fields are invalid")
    return ProtocolContribution(metadata_path, *versions)


def _HardwareProvider_Parse(value: Any) -> HardwareProviderContribution | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "vendor",
        "handler",
        "accepted_inputs",
    }:
        raise PluginManifestError("hardware_provider contains unknown fields")
    vendor = value.get("vendor")
    handler = value.get("handler")
    accepted_inputs = _StringTuple_Get(
        value.get("accepted_inputs", []), "hardware_provider.accepted_inputs"
    )
    if not isinstance(vendor, str) or not vendor:
        raise PluginManifestError(
            "hardware_provider.vendor must be a non-empty string"
        )
    if handler not in ALLOWED_PROVIDER_HANDLERS:
        raise PluginManifestError("hardware_provider.handler is not trusted")
    if not accepted_inputs:
        raise PluginManifestError(
            "hardware_provider.accepted_inputs must not be empty"
        )
    return HardwareProviderContribution(vendor, handler, accepted_inputs)


def _Environment_Parse(value: Any) -> EnvironmentContribution | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "renderer",
        "toolchain",
        "outputs",
        "tasks",
        "eide_native",
    }:
        raise PluginManifestError("environment contains unknown fields")
    renderer = value.get("renderer")
    toolchain = value.get("toolchain")
    if renderer not in ALLOWED_ENVIRONMENT_RENDERERS:
        raise PluginManifestError("environment.renderer is not supported")
    if not isinstance(toolchain, str) or not toolchain:
        raise PluginManifestError(
            "environment.toolchain must be a non-empty string"
        )
    outputs = _StringTuple_Get(value.get("outputs", []), "environment.outputs")
    tasks = _StringTuple_Get(value.get("tasks", []), "environment.tasks")
    _RelativePaths_Validate(outputs, "environment.outputs")
    return EnvironmentContribution(
        renderer=renderer,
        toolchain=toolchain,
        outputs=outputs,
        tasks=tasks,
        eide_native=_Boolean_Get(value, "eide_native", False),
    )


def _Build_Parse(value: Any) -> BuildContribution:
    data = value if value is not None else {}
    if not isinstance(data, dict) or set(data) - {
        "sources",
        "asm_sources",
        "include_dirs",
        "defines",
        "mcu_flags",
        "specs",
        "libraries",
        "forced_includes",
        "virtual_sources",
        "exclude_sources",
        "linker_script",
        "toolchain_prefix",
    }:
        raise PluginManifestError("build contains unknown fields")
    sources = _StringTuple_Get(data.get("sources", []), "build.sources")
    asm_sources = _StringTuple_Get(data.get("asm_sources", []), "build.asm_sources")
    include_dirs = _StringTuple_Get(data.get("include_dirs", []), "build.include_dirs")
    defines = _StringTuple_Get(data.get("defines", []), "build.defines")
    mcu_flags = _StringTuple_Get(data.get("mcu_flags", []), "build.mcu_flags")
    specs = _StringTuple_Get(data.get("specs", []), "build.specs")
    libraries = _StringTuple_Get(data.get("libraries", []), "build.libraries")
    forced_includes = _StringTuple_Get(
        data.get("forced_includes", []), "build.forced_includes"
    )
    virtual_sources = _StringTuple_Get(
        data.get("virtual_sources", []), "build.virtual_sources"
    )
    exclude_sources = _StringTuple_Get(
        data.get("exclude_sources", []), "build.exclude_sources"
    )
    linker_script = data.get("linker_script", "")
    toolchain_prefix = data.get("toolchain_prefix", "")
    if not isinstance(linker_script, str):
        raise PluginManifestError("build.linker_script must be a string")
    if not isinstance(toolchain_prefix, str) or not TOOLCHAIN_PREFIX_PATTERN.fullmatch(
        toolchain_prefix
    ):
        raise PluginManifestError("build.toolchain_prefix is invalid")
    path_values = (
        sources
        + asm_sources
        + include_dirs
        + forced_includes
        + virtual_sources
        + exclude_sources
    )
    _BuildTokens_Validate(path_values, "build paths", BUILD_PATH_PATTERN)
    _BuildTokens_Validate(defines, "build.defines", DEFINE_PATTERN)
    _BuildTokens_Validate(mcu_flags, "build.mcu_flags", BUILD_TOKEN_PATTERN)
    _BuildTokens_Validate(specs, "build.specs", BUILD_TOKEN_PATTERN)
    _BuildTokens_Validate(libraries, "build.libraries", BUILD_TOKEN_PATTERN)
    _RelativePaths_Validate(path_values, "build")
    if linker_script:
        _RelativePaths_Validate((linker_script,), "linker_script")
        _BuildTokens_Validate((linker_script,), "linker_script", BUILD_PATH_PATTERN)
    return BuildContribution(
        sources=sources,
        asm_sources=asm_sources,
        include_dirs=include_dirs,
        defines=defines,
        mcu_flags=mcu_flags,
        specs=specs,
        libraries=libraries,
        forced_includes=forced_includes,
        virtual_sources=virtual_sources,
        exclude_sources=exclude_sources,
        linker_script=linker_script,
        toolchain_prefix=toolchain_prefix,
    )


def PluginManifest_Parse(
    data: dict[str, Any], manifest_path: Path, *, source: str
) -> PluginManifest:
    if not isinstance(data, dict):
        raise PluginManifestError("plugin.json must contain a JSON object")
    required_fields = ("schema_version", "id", "name", "type", "version", "payload")
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise PluginManifestError(f"Missing manifest fields: {', '.join(missing)}")
    if data["schema_version"] != 0:
        raise PluginManifestError("Only plugin schema_version 0 is supported")
    allowed_top_level = {
        "schema_version",
        "id",
        "name",
        "type",
        "class",
        "version",
        "description",
        "requires",
        "resources",
        "provides",
        "build",
        "payload",
        "metadata",
        "selection",
        "board",
        "hardware_provider",
        "environment",
        "cardinality",
        "instance_policy",
        "physical_device",
        "protocol",
    }
    unknown = set(data) - allowed_top_level
    if unknown:
        raise PluginManifestError(
            f"Unknown manifest fields: {', '.join(sorted(unknown))}"
        )
    component_id = data["id"]
    if not isinstance(component_id, str) or not PLUGIN_ID_PATTERN.fullmatch(
        component_id
    ):
        raise PluginManifestError(f"Invalid plugin id: {component_id!r}")
    component_type = data["type"]
    if component_type not in ALLOWED_PLUGIN_TYPES:
        raise PluginManifestError(f"Unsupported plugin type: {component_type!r}")
    version = data["version"]
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise PluginManifestError(f"Invalid plugin version: {version!r}")
    for field_name in ("name", "description", "class"):
        if field_name in data and not isinstance(data[field_name], str):
            raise PluginManifestError(f"{field_name} must be a string")
    if not data["name"].strip():
        raise PluginManifestError("name must not be empty")
    metadata = data.get("metadata", {})
    if not isinstance(metadata, dict):
        raise PluginManifestError("metadata must be an object")
    for metadata_field in ("display_names", "descriptions"):
        localized_values = metadata.get(metadata_field, {})
        if not isinstance(localized_values, dict) or not all(
            isinstance(language, str)
            and bool(language)
            and isinstance(localized, str)
            and bool(localized.strip())
            for language, localized in localized_values.items()
        ):
            raise PluginManifestError(
                f"metadata.{metadata_field} must map languages to non-empty strings"
            )

    requires = data.get("requires", {})
    if not isinstance(requires, dict) or set(requires) - {
        "components",
        "resources",
        "capabilities",
    }:
        raise PluginManifestError("requires contains unknown fields")
    dependencies = _Dependencies_Parse(requires)
    resource_requirements = _ResourceRequirements_Parse(requires)
    resource_provisions, resource_roles, resource_conflicts = _Resources_Parse(
        data.get("resources", {})
    )
    capability_requirements = _CapabilityRequirements_Parse(
        requires.get("capabilities", [])
    )
    provides = _StringTuple_Get(data.get("provides", []), "provides")
    _CapabilityTuple_Validate(provides, "provides")
    build = _Build_Parse(data.get("build", {}))
    selection = _Selection_Parse(data.get("selection"))
    board = _Board_Parse(data.get("board"))
    hardware_provider = _HardwareProvider_Parse(data.get("hardware_provider"))
    environment = _Environment_Parse(data.get("environment"))
    protocol = _Protocol_Parse(data.get("protocol"))
    instance_policy = _InstancePolicy_Parse(
        data.get("instance_policy"),
        component_type=component_type,
        legacy_cardinality=data.get("cardinality"),
    )
    physical_device = _PhysicalDevice_Parse(
        data.get("physical_device"), component_type=component_type
    )

    if (component_type == "board") != (board is not None):
        raise PluginManifestError("board plugins must declare exactly one board block")
    if (component_type == "hardware_configuration_provider") != (
        hardware_provider is not None
    ):
        raise PluginManifestError(
            "hardware configuration provider plugins must declare hardware_provider"
        )
    if (component_type == "development_environment") != (environment is not None):
        raise PluginManifestError(
            "development environment plugins must declare environment"
        )
    if (component_type == "protocol_bundle") != (protocol is not None):
        raise PluginManifestError(
            "protocol_bundle plugins must declare exactly one protocol block"
        )
    if selection is not None and component_type not in {"algorithm", "flight_logic"}:
        raise PluginManifestError(
            "only algorithm/flight_logic plugins may select strategy/mode"
        )

    payload = data["payload"]
    if not isinstance(payload, dict) or set(payload) != {"roots"}:
        raise PluginManifestError("payload must contain only roots")
    payload_roots = _StringTuple_Get(payload.get("roots", []), "payload.roots")
    if not payload_roots and component_type not in UTILITY_PLUGIN_TYPES:
        raise PluginManifestError("payload.roots must not be empty")
    _RelativePaths_Validate(payload_roots, "payload")
    _BuildTokens_Validate(payload_roots, "payload.roots", BUILD_PATH_PATTERN)

    manifest = PluginManifest(
        schema_version=0,
        component_id=component_id,
        name=data["name"],
        component_type=component_type,
        component_class=str(data.get("class", "")),
        version=version,
        description=str(data.get("description", "")),
        dependencies=dependencies,
        resource_requirements=resource_requirements,
        resource_provisions=resource_provisions,
        resource_roles=resource_roles,
        resource_conflicts=resource_conflicts,
        provides=provides,
        capability_requirements=capability_requirements,
        build=build,
        payload_roots=payload_roots,
        metadata=dict(metadata),
        manifest_path=manifest_path.resolve(),
        instance_policy=instance_policy,
        physical_device=physical_device,
        selection=selection,
        board=board,
        protocol=protocol,
        hardware_provider=hardware_provider,
        environment=environment,
        source=source,
    )
    payload_files = {
        path.relative_to(manifest.payload_root).as_posix()
        for path in manifest.PayloadFiles_Get()
    }
    for build_path in (*build.sources, *build.asm_sources, *build.virtual_sources):
        if build_path not in payload_files:
            raise PluginManifestError(
                f"Build source is not supplied by payload roots: {build_path}"
            )
    for include_path in build.include_dirs:
        if not (manifest.payload_root / include_path).is_dir():
            raise PluginManifestError(
                f"Build include directory is missing: {include_path}"
            )
    for forced_include in build.forced_includes:
        if forced_include not in payload_files:
            raise PluginManifestError(
                f"Forced include is missing from payload: {forced_include}"
            )
    if build.linker_script and build.linker_script not in payload_files:
        raise PluginManifestError(
            f"Linker script is missing from payload: {build.linker_script}"
        )
    if protocol is not None and protocol.logging_metadata not in payload_files:
        raise PluginManifestError(
            "Protocol logging metadata is missing from payload: "
            f"{protocol.logging_metadata}"
        )
    if board is not None:
        for field_name, relative_path in (
            ("board.ioc_file", board.ioc_file),
            ("board.connections_file", board.connections_file),
        ):
            if not relative_path:
                continue
            target = manifest.package_root.joinpath(*relative_path.split("/"))
            try:
                target.relative_to(manifest.package_root)
            except ValueError as error:
                raise PluginManifestError(f"{field_name} leaves the plugin") from error
            if not target.is_file() or target.is_symlink():
                raise PluginManifestError(f"{field_name} is missing or unsafe")
    return manifest


def PluginManifest_Load(path: Path, *, source: str = "builtin") -> PluginManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PluginManifestError(
            f"Cannot read plugin manifest {path}: {error}"
        ) from error
    return PluginManifest_Parse(data, path, source=source)
