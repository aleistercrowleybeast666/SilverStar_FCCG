from __future__ import annotations

from dataclasses import dataclass
import re

from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import SelectionKind
from silverstar_fccg.project.model import ProjectModel, ProjectModelError, ProjectModel_Parse
from silverstar_fccg.project.reference import ReferenceLogStreams_Get
from silverstar_fccg.project.resources import ResourceAssignments_Resolve


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    level: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ProjectValidationResult:
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


def _ComponentType_Validate(
    catalog: PluginCatalog,
    component_id: str,
    expected_type: str,
    issues: list[ValidationIssue],
) -> None:
    try:
        manifest = catalog.Component_Get(component_id)
    except ValueError as error:
        issues.append(ValidationIssue("error", "missing_component", str(error)))
        return
    if manifest.component_type != expected_type:
        issues.append(
            ValidationIssue(
                "error",
                "component_type",
                f"{component_id} is {manifest.component_type}, expected {expected_type}",
            )
        )


def _Strategies_Validate(
    model: ProjectModel,
    catalog: PluginCatalog,
    issues: list[ValidationIssue],
) -> None:
    declared_slots = set(catalog.SelectionSlots_Get(SelectionKind.STRATEGY.value))
    selected_slots = set(model.strategies)
    for slot in sorted(selected_slots - declared_slots):
        issues.append(
            ValidationIssue(
                "error", "strategy_slot", f"Unknown strategy slot: {slot}"
            )
        )
    for slot in sorted(declared_slots - selected_slots):
        candidates = catalog.SelectionSlot_Get(slot)
        if any(
            component.selection is not None and component.selection.required
            for component in candidates
        ):
            issues.append(
                ValidationIssue(
                    "error", "strategy_required", f"Strategy slot {slot} is required"
                )
            )
    for slot, component_id in sorted(model.strategies.items()):
        candidates = catalog.SelectionSlot_Get(slot)
        if component_id is None:
            if not candidates or not all(
                component.selection is not None
                and component.selection.allow_none
                and not component.selection.required
                for component in candidates
            ):
                issues.append(
                    ValidationIssue(
                        "error",
                        "strategy_none",
                        f"Strategy slot {slot} does not allow None",
                    )
                )
            continue
        try:
            manifest = catalog.Component_Get(component_id)
        except ValueError as error:
            issues.append(ValidationIssue("error", "missing_component", str(error)))
            continue
        selection = manifest.selection
        if (
            selection is None
            or selection.kind != SelectionKind.STRATEGY
            or selection.slot != slot
        ):
            issues.append(
                ValidationIssue(
                    "error",
                    "strategy_component",
                    f"{component_id} does not implement strategy slot {slot}",
                )
            )


def _Modes_Validate(
    model: ProjectModel,
    catalog: PluginCatalog,
    issues: list[ValidationIssue],
) -> None:
    owners = {
        manifest.selection.slot: manifest
        for component_id in model.base_components
        for manifest in (catalog.Component_Get(component_id),)
        if manifest.selection is not None
        and manifest.selection.kind == SelectionKind.MODE
    }
    for slot in sorted(set(model.modes) - set(owners)):
        issues.append(
            ValidationIssue("error", "mode_slot", f"Unknown active mode slot: {slot}")
        )
    for slot, manifest in owners.items():
        selection = manifest.selection
        assert selection is not None
        values = model.modes.get(slot, [])
        unknown = set(values) - set(selection.options)
        if unknown:
            issues.append(
                ValidationIssue(
                    "error",
                    "mode_option",
                    f"Mode slot {slot} contains unknown options: {', '.join(sorted(unknown))}",
                )
            )
        if not selection.allow_multiple and len(values) > 1:
            issues.append(
                ValidationIssue(
                    "error", "mode_multiple", f"Mode slot {slot} is not multi-select"
                )
            )
        if not selection.allow_none and not values:
            issues.append(
                ValidationIssue(
                    "error", "mode_required", f"Mode slot {slot} requires a selection"
                )
            )


def _Hardware_Validate(
    model: ProjectModel,
    catalog: PluginCatalog,
    issues: list[ValidationIssue],
) -> None:
    mcu = catalog.Component_Get(model.mcu)
    mcu_vendor = str(mcu.metadata.get("vendor", ""))
    if model.hardware.mode == "board_plugin":
        board = catalog.Component_Get(model.board)
        if board.board is None:
            issues.append(
                ValidationIssue("error", "board_manifest", "Board metadata is missing")
            )
            return
        if model.mcu not in board.board.compatible_mcus:
            issues.append(
                ValidationIssue(
                    "error",
                    "board_mcu",
                    f"Board {model.board} is not compatible with MCU {model.mcu}",
                )
            )
        if board.board.source_kind != "verified_builtin":
            issues.append(
                ValidationIssue(
                    "warning",
                    "board_unverified",
                    f"Board {model.board} is not an official verified builtin",
                )
            )
        return
    provider = catalog.Component_Get(model.hardware.provider)
    if provider.hardware_provider is None:
        issues.append(
            ValidationIssue(
                "error", "hardware_provider", "Hardware provider metadata is missing"
            )
        )
        return
    if provider.hardware_provider.vendor != mcu_vendor:
        issues.append(
            ValidationIssue(
                "error",
                "hardware_vendor",
                f"Provider vendor {provider.hardware_provider.vendor} does not match MCU vendor {mcu_vendor}",
            )
        )
    expected_mcu = re.sub(
        r"[^A-Z0-9]", "", str(mcu.metadata.get("mcu_model", "")).upper()
    )
    imported_mcu = re.sub(r"[^A-Z0-9]", "", model.hardware.mcu.upper())
    if expected_mcu and not (
        imported_mcu == expected_mcu
        or (len(imported_mcu) >= 11 and expected_mcu.startswith(imported_mcu[:11]))
    ):
        issues.append(
            ValidationIssue(
                "error",
                "hardware_mcu",
                f"Imported CubeMX MCU {model.hardware.mcu} does not match {expected_mcu}",
            )
        )
    hardware_prefix = "HardwareGenerated/STM32CubeMX/"
    if any(
        not path.startswith(hardware_prefix)
        for path in (*model.hardware.build_sources, *model.hardware.asm_sources, *model.hardware.include_dirs)
    ):
        issues.append(
            ValidationIssue(
                "error",
                "hardware_path",
                "Custom hardware build paths must remain below HardwareGenerated/STM32CubeMX",
            )
        )
    if not model.hardware.risk_acknowledged:
        issues.append(
            ValidationIssue(
                "error",
                "hardware_risk",
                "Custom hardware risk acknowledgement is required",
            )
        )
    issues.append(
        ValidationIssue(
            "warning",
            "hardware_manual",
            "Custom hardware is not officially hardware-validated by SilverStar",
        )
    )


def Project_Validate(model: ProjectModel, catalog: PluginCatalog) -> ProjectValidationResult:
    issues: list[ValidationIssue] = []
    try:
        ProjectModel_Parse(model.Dictionary_Get())
    except ProjectModelError as error:
        return ProjectValidationResult(
            (ValidationIssue("error", "project_model", str(error)),)
        )
    raw_components = [model.core, model.mcu, model.board, model.os]
    raw_components.extend(model.devices)
    raw_components.extend(model.base_components)
    raw_components.extend(
        component_id
        for component_id in model.strategies.values()
        if component_id is not None
    )
    raw_components.extend(model.protocol_bundles)
    raw_components.append(model.development_environment)
    if model.hardware.mode == "custom":
        raw_components.append(model.hardware.provider)
    raw_components = [component_id for component_id in raw_components if component_id]
    if len(raw_components) != len(set(raw_components)):
        issues.append(
            ValidationIssue(
                "error", "duplicate_component", "A component is selected twice"
            )
        )

    for expected_type, component_id in (
        ("core", model.core),
        ("mcu", model.mcu),
        ("os", model.os),
        ("development_environment", model.development_environment),
    ):
        _ComponentType_Validate(catalog, component_id, expected_type, issues)
    if model.hardware.mode == "board_plugin":
        _ComponentType_Validate(catalog, model.board, "board", issues)
    else:
        _ComponentType_Validate(
            catalog,
            model.hardware.provider,
            "hardware_configuration_provider",
            issues,
        )
    for component_id in model.devices:
        _ComponentType_Validate(catalog, component_id, "device", issues)
    for component_id in model.base_components:
        try:
            component_type = catalog.Component_Get(component_id).component_type
        except ValueError as error:
            issues.append(ValidationIssue("error", "missing_component", str(error)))
            continue
        if component_type not in {"algorithm", "flight_logic"}:
            issues.append(
                ValidationIssue(
                    "error",
                    "component_type",
                    f"{component_id} cannot be a base flight component",
                )
            )
    for component_id in model.protocol_bundles:
        _ComponentType_Validate(
            catalog, component_id, "protocol_bundle", issues
        )
    _Strategies_Validate(model, catalog, issues)
    _Modes_Validate(model, catalog, issues)
    try:
        mcu_manifest = catalog.Component_Get(model.mcu)
        environment_manifest = catalog.Component_Get(model.development_environment)
        supported_environments = tuple(
            mcu_manifest.metadata.get("supported_environments", [])
        )
        if (
            supported_environments
            and model.development_environment not in supported_environments
        ):
            issues.append(
                ValidationIssue(
                    "error",
                    "environment_mcu",
                    "Selected development environment is not supported by the MCU plugin",
                )
            )
        if environment_manifest.environment is None:
            issues.append(
                ValidationIssue(
                    "error",
                    "environment_manifest",
                    "Development environment renderer metadata is missing",
                )
            )
    except ValueError as error:
        issues.append(ValidationIssue("error", "environment_catalog", str(error)))
    try:
        _Hardware_Validate(model, catalog, issues)
    except ValueError as error:
        issues.append(ValidationIssue("error", "hardware_catalog", str(error)))

    component_ids = model.ComponentIds_Get()
    for error in catalog.DependencyErrors_Get(component_ids):
        issues.append(ValidationIssue("error", "dependency", error))
    for path, owners in catalog.PathConflicts_Get(component_ids).items():
        issues.append(
            ValidationIssue(
                "error", "payload_conflict", f"{path} is owned by {', '.join(owners)}"
            )
        )
    try:
        resource_result = ResourceAssignments_Resolve(model, catalog)
    except ValueError as error:
        issues.append(ValidationIssue("error", "resource_catalog", str(error)))
    else:
        for error in resource_result.errors:
            issues.append(ValidationIssue("error", "resource", error))
    if not model.logging_streams:
        issues.append(
            ValidationIssue(
                "error", "logging", "No SSLOG stream policy is configured"
            )
        )
    expected_records = tuple(stream.record for stream in ReferenceLogStreams_Get())
    actual_records = tuple(stream.record for stream in model.logging_streams)
    if actual_records != expected_records:
        issues.append(
            ValidationIssue(
                "error",
                "logging_records",
                "The SSLOG record table must match the selected protocol bundle order",
            )
        )
    if model.build.target_profile != "SilverStar_F407":
        issues.append(
            ValidationIssue(
                "error", "target", "Only SilverStar_F407 is currently validated"
            )
        )
    return ProjectValidationResult(tuple(issues))
