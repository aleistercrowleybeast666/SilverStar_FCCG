from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from silverstar_fccg.core.workspace import WorkspacePolicy


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


class PluginManifestError(ValueError):
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
class ResourceRequirement:
    name: str
    kind: str
    binding_macro: str = ""
    required: bool = True
    mode: ResourceMode = ResourceMode.EXCLUSIVE
    candidates: tuple[str, ...] = ()


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
    none_defines: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BoardContribution:
    source_kind: str
    compatible_mcus: tuple[str, ...]
    vendor: str
    provider: str
    verified: bool
    hardware_root: str


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
    capabilities_required: tuple[str, ...]
    build: BuildContribution
    payload_roots: tuple[str, ...]
    metadata: dict[str, Any]
    manifest_path: Path
    selection: SelectionContribution | None = None
    board: BoardContribution | None = None
    hardware_provider: HardwareProviderContribution | None = None
    environment: EnvironmentContribution | None = None
    source: str = "builtin"

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
        requirements.append(
            ResourceRequirement(
                name=name,
                kind=kind,
                binding_macro=binding_macro,
                required=_Boolean_Get(entry, "required", True),
                mode=mode,
                candidates=candidates,
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
    return BoardContribution(
        source_kind=source_kind,
        compatible_mcus=compatible_mcus,
        vendor=vendor,
        provider=provider,
        verified=_Boolean_Get(value, "verified", False),
        hardware_root=hardware_root,
    )


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
    capabilities_required = _StringTuple_Get(
        requires.get("capabilities", []), "requires.capabilities"
    )
    provides = _StringTuple_Get(data.get("provides", []), "provides")
    _CapabilityTuple_Validate(provides, "provides")
    _CapabilityTuple_Validate(capabilities_required, "requires.capabilities")
    build = _Build_Parse(data.get("build", {}))
    selection = _Selection_Parse(data.get("selection"))
    board = _Board_Parse(data.get("board"))
    hardware_provider = _HardwareProvider_Parse(data.get("hardware_provider"))
    environment = _Environment_Parse(data.get("environment"))

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
        capabilities_required=capabilities_required,
        build=build,
        payload_roots=payload_roots,
        metadata=dict(metadata),
        manifest_path=manifest_path.resolve(),
        selection=selection,
        board=board,
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
    return manifest


def PluginManifest_Load(path: Path, *, source: str = "builtin") -> PluginManifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PluginManifestError(
            f"Cannot read plugin manifest {path}: {error}"
        ) from error
    return PluginManifest_Parse(data, path, source=source)
