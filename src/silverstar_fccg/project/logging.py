from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from silverstar_fccg.project.model import LogStreamConfig, ProjectModel
from silverstar_fccg.project.capabilities import CapabilityResolution_Resolve
from silverstar_fccg.core.errors import FccgError

if TYPE_CHECKING:
    from silverstar_fccg.plugins.catalog import PluginCatalog
    from silverstar_fccg.plugins.manifest import PluginManifest


class LogMetadataError(FccgError):
    pass


class LogPolicyLevel(StrEnum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


@dataclass(frozen=True, slots=True)
class LogRecordDefinition:
    record: str
    name: str
    record_id: str
    version: int
    payload_size: int
    default_stream: LogStreamConfig
    level: LogPolicyLevel
    capabilities_required: tuple[str, ...] = ()
    recordable_capabilities_required: tuple[str, ...] = ()
    components_required: tuple[str, ...] = ()
    strategy_slots_required: tuple[str, ...] = ()
    display_names: dict[str, str] = field(default_factory=dict)

    def DisplayName_Get(self, language: str) -> str:
        return self.display_names.get(language, self.name).replace("_", " ")


@dataclass(frozen=True, slots=True)
class LogAvailability:
    available: bool
    reason_code: str = ""
    missing: tuple[str, ...] = ()


def _StringTuple_Get(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(
        isinstance(item, str) and bool(item) for item in value
    ):
        raise LogMetadataError(f"{field_name} must be an array of strings")
    return tuple(value)


def ProtocolLogMetadataPath_Get(manifest: PluginManifest) -> Path:
    if manifest.protocol is None:
        raise LogMetadataError(
            f"Protocol plugin {manifest.component_id} has no logging metadata"
        )
    path = manifest.payload_root.joinpath(
        *manifest.protocol.logging_metadata.split("/")
    ).resolve()
    try:
        path.relative_to(manifest.payload_root.resolve())
    except ValueError as error:
        raise LogMetadataError("Protocol logging metadata leaves its payload") from error
    if not path.is_file() or path.is_symlink():
        raise LogMetadataError(f"Protocol logging metadata is unsafe: {path}")
    return path


def ProtocolLogDefinitions_Load(path: Path) -> tuple[LogRecordDefinition, ...]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LogMetadataError(f"Cannot read logging metadata: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise LogMetadataError("Logging metadata must contain a records array")
    fccg = data.get("fccg", {})
    if not isinstance(fccg, dict):
        raise LogMetadataError("Logging metadata fccg block must be an object")
    record_policies = fccg.get("records", {})
    if not isinstance(record_policies, dict):
        raise LogMetadataError("Logging metadata fccg.records must be an object")

    definitions: list[LogRecordDefinition] = []
    seen: set[str] = set()
    for index, entry in enumerate(data["records"]):
        if not isinstance(entry, dict):
            raise LogMetadataError(f"Logging record {index} must be an object")
        record = entry.get("enum")
        name = entry.get("name")
        record_id = entry.get("id")
        version = entry.get("version")
        payload_size = entry.get("payload_size")
        stream = entry.get("default_stream")
        if (
            not isinstance(record, str)
            or not record.startswith("FLIGHT_LOG_RECORD_")
            or record in seen
            or not isinstance(name, str)
            or not isinstance(record_id, str)
            or isinstance(version, bool)
            or not isinstance(version, int)
            or isinstance(payload_size, bool)
            or not isinstance(payload_size, int)
            or not isinstance(stream, dict)
        ):
            raise LogMetadataError(f"Logging record {index} is invalid")
        enabled = stream.get("enabled")
        policy = stream.get("policy")
        decimation = stream.get("decimation", 1)
        period_us = stream.get("period_us", 0)
        if (
            not isinstance(enabled, bool)
            or not isinstance(policy, str)
            or isinstance(decimation, bool)
            or not isinstance(decimation, int)
            or decimation < 1
            or isinstance(period_us, bool)
            or not isinstance(period_us, int)
            or period_us < 0
        ):
            raise LogMetadataError(f"Default stream for {record} is invalid")
        policy_data = record_policies.get(record, {})
        if not isinstance(policy_data, dict) or set(policy_data) - {
            "level",
            "requires",
            "display_names",
        }:
            raise LogMetadataError(f"FCCG policy for {record} must be an object")
        fallback_level = "recommended" if enabled else "optional"
        try:
            level = LogPolicyLevel(policy_data.get("level", fallback_level))
        except ValueError as error:
            raise LogMetadataError(f"FCCG policy level for {record} is invalid") from error
        requirements = policy_data.get("requires", {})
        if not isinstance(requirements, dict) or set(requirements) - {
            "capabilities",
            "recordable_capabilities",
            "components",
            "strategy_slots",
        }:
            raise LogMetadataError(f"FCCG requirements for {record} are invalid")
        display_names = policy_data.get("display_names", {})
        if not isinstance(display_names, dict) or not all(
            language in {"zh_CN", "en_US"}
            and isinstance(display_name, str)
            and bool(display_name.strip())
            for language, display_name in display_names.items()
        ):
            raise LogMetadataError(f"FCCG display names for {record} are invalid")
        definitions.append(
            LogRecordDefinition(
                record=record,
                name=name,
                record_id=record_id,
                version=version,
                payload_size=payload_size,
                default_stream=LogStreamConfig(
                    record,
                    enabled,
                    policy.upper(),
                    decimation,
                    period_us,
                ),
                level=level,
                capabilities_required=_StringTuple_Get(
                    requirements.get("capabilities"),
                    f"{record}.requires.capabilities",
                ),
                recordable_capabilities_required=_StringTuple_Get(
                    requirements.get("recordable_capabilities"),
                    f"{record}.requires.recordable_capabilities",
                ),
                components_required=_StringTuple_Get(
                    requirements.get("components"),
                    f"{record}.requires.components",
                ),
                strategy_slots_required=_StringTuple_Get(
                    requirements.get("strategy_slots"),
                    f"{record}.requires.strategy_slots",
                ),
                display_names=dict(display_names),
            )
        )
        seen.add(record)
    if not definitions:
        raise LogMetadataError("Logging metadata declares no records")
    unknown_policies = set(record_policies) - seen
    if unknown_policies:
        raise LogMetadataError(
            "FCCG policy references unknown records: "
            + ", ".join(sorted(unknown_policies))
        )
    return tuple(definitions)


def ProtocolLogDefinitions_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[LogRecordDefinition, ...]:
    if len(model.protocol_bundles) != 1:
        raise LogMetadataError("Exactly one protocol bundle must be selected")
    manifest = catalog.Component_Get(model.protocol_bundles[0])
    return ProtocolLogDefinitions_Load(ProtocolLogMetadataPath_Get(manifest))


def ProjectCapabilities_Get(model: ProjectModel, catalog: PluginCatalog) -> set[str]:
    capabilities: set[str] = set()
    device_plugins = set(model.DevicePluginIds_Get())
    for component_id in model.ComponentIds_Get():
        if component_id in device_plugins:
            continue
        try:
            capabilities.update(catalog.Component_Get(component_id).provides)
        except ValueError:
            continue
    resolution = CapabilityResolution_Resolve(model, catalog)
    for enabled in resolution.enabled_by_instance.values():
        capabilities.update(enabled)
    return capabilities


def ProjectRecordableOutputs_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[set[str], dict[str, str]]:
    """Return enabled raw outputs and explicit device-output disable reasons."""
    enabled: set[str] = set()
    disabled_reasons: dict[str, str] = {}
    for instance in model.device_instances:
        manifest = catalog.Component_Get(instance.plugin)
        values = manifest.metadata.get("recordable_outputs", {})
        if not isinstance(values, dict):
            continue
        for capability, configuration in values.items():
            if not isinstance(capability, str) or not isinstance(configuration, dict):
                continue
            if configuration.get("enabled") is True:
                enabled.add(capability)
                disabled_reasons.pop(capability, None)
            elif capability not in enabled:
                reason_code = configuration.get("reason_code", "")
                if isinstance(reason_code, str) and reason_code:
                    disabled_reasons[capability] = reason_code
    return enabled, disabled_reasons


def LogAvailability_Get(
    definition: LogRecordDefinition,
    model: ProjectModel,
    catalog: PluginCatalog,
) -> LogAvailability:
    selected = set(model.ComponentIds_Get())
    capabilities = ProjectCapabilities_Get(model, catalog)
    recordable, disabled_recordable = ProjectRecordableOutputs_Get(model, catalog)
    missing_capabilities = tuple(
        value for value in definition.capabilities_required if value not in capabilities
    )
    if missing_capabilities:
        return LogAvailability(
            False, "logging.unavailable.capability", missing_capabilities
        )
    missing_recordable = tuple(
        value
        for value in definition.recordable_capabilities_required
        if value not in recordable
    )
    if missing_recordable:
        reason_codes = tuple(
            dict.fromkeys(
                disabled_recordable.get(value, "")
                for value in missing_recordable
                if disabled_recordable.get(value, "")
            )
        )
        return LogAvailability(
            False,
            (
                reason_codes[0]
                if len(reason_codes) == 1
                else "logging.unavailable.recordable"
            ),
            missing_recordable,
        )
    missing_components = tuple(
        value for value in definition.components_required if value not in selected
    )
    if missing_components:
        return LogAvailability(
            False, "logging.unavailable.component", missing_components
        )
    missing_slots = tuple(
        value
        for value in definition.strategy_slots_required
        if not model.strategies.get(value)
    )
    if missing_slots:
        return LogAvailability(False, "logging.unavailable.strategy", missing_slots)
    return LogAvailability(True)


def LoggingProfile_Reconcile(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[LogRecordDefinition, ...]:
    definitions = ProtocolLogDefinitions_Get(model, catalog)
    current = {stream.record: stream for stream in model.logging_streams}
    reconciled: list[LogStreamConfig] = []
    for definition in definitions:
        stream = current.get(definition.record, definition.default_stream)
        availability = LogAvailability_Get(definition, model, catalog)
        enabled = stream.enabled
        if not availability.available:
            enabled = False
        elif definition.level == LogPolicyLevel.REQUIRED:
            enabled = True
        reconciled.append(
            LogStreamConfig(
                record=definition.record,
                enabled=enabled,
                policy=stream.policy,
                decimation=stream.decimation,
                period_us=stream.period_us,
            )
        )
    model.logging_streams = reconciled
    return definitions
