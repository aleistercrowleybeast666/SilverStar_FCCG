from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import PluginManifest, SelectionKind
from silverstar_fccg.project.capabilities import (
    CapabilityResolution,
    CapabilitySourceOverrides_Reconcile,
)
from silverstar_fccg.project.logging import LoggingProfile_Reconcile
from silverstar_fccg.project.model import ProjectModel
from silverstar_fccg.project.model import HardwareConfiguration
from silverstar_fccg.project.resources import (
    ResourceAssignmentResult,
    ResourceAssignments_Resolve,
    ResourceRequirementOptions_Get,
)
from silverstar_fccg.project.validation import (
    ProjectValidationResult,
    Project_EditValidate,
)


@dataclass(frozen=True, slots=True)
class SelectionAvailability:
    available: bool
    missing_capabilities: tuple[str, ...] = ()
    missing_components: tuple[str, ...] = ()
    reason_code: str = ""


@dataclass(frozen=True, slots=True)
class ConfigurationNotice:
    code: str
    slot: str = ""
    component_id: str = ""
    count: int = 0


@dataclass(frozen=True, slots=True)
class ProjectConfigurationResult:
    model: ProjectModel
    capability_resolution: CapabilityResolution
    resource_resolution: ResourceAssignmentResult
    strategy_availability: dict[str, SelectionAvailability]
    mode_availability: dict[tuple[str, str], SelectionAvailability]
    edit_validation: ProjectValidationResult
    notices: tuple[ConfigurationNotice, ...] = ()
    retained_assignments: int = 0
    cleared_assignments: int = 0
    pending_assignments: int = 0


def PhysicalCapabilities_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> frozenset[str]:
    return frozenset(
        capability
        for instance in model.device_instances
        for capability in catalog.Component_Get(instance.plugin).provides
    )


def _SelectedComponentIdsForStrategy_Get(
    model: ProjectModel, slot: str, component_id: str
) -> tuple[str, ...]:
    candidate = deepcopy(model)
    candidate.strategies[slot] = component_id
    return candidate.ComponentIds_Get()


def _LogicalCapabilities_Get(
    component_ids: tuple[str, ...], catalog: PluginCatalog
) -> frozenset[str]:
    return frozenset(
        capability
        for component_id in component_ids
        for capability in catalog.Component_Get(component_id).provides
    )


def _ManifestAvailability_Get(
    manifest: PluginManifest,
    component_ids: tuple[str, ...],
    catalog: PluginCatalog,
    *,
    additional_capabilities: tuple[str, ...] = (),
    additional_components: tuple[str, ...] = (),
) -> SelectionAvailability:
    selected = set(component_ids)
    capabilities = set(_LogicalCapabilities_Get(component_ids, catalog))
    required_components = tuple(
        dict.fromkeys(
            (
                requirement.component_id
                for requirement in manifest.dependencies
                if not requirement.optional
            )
        )
    ) + tuple(additional_components)
    missing_components = tuple(
        component_id
        for component_id in dict.fromkeys(required_components)
        if component_id not in selected
    )
    required_capabilities = tuple(
        dict.fromkeys(
            (
                requirement.capability
                for requirement in manifest.capability_requirements
            )
        )
    ) + tuple(additional_capabilities)
    missing_capabilities = tuple(
        capability
        for capability in dict.fromkeys(required_capabilities)
        if capability not in capabilities
    )
    compatible_mcus = manifest.metadata.get("compatible_mcus", [])
    incompatible_mcu = (
        isinstance(compatible_mcus, list)
        and bool(compatible_mcus)
        and McuCompatibilityMissing_Is(component_ids, compatible_mcus)
    )
    if incompatible_mcu:
        missing_components = (*missing_components, "mcu.compatibility")
    if missing_capabilities:
        reason_code = "selection.unavailable.capability"
    elif missing_components:
        reason_code = "selection.unavailable.component"
    else:
        reason_code = ""
    return SelectionAvailability(
        available=not missing_capabilities and not missing_components,
        missing_capabilities=missing_capabilities,
        missing_components=missing_components,
        reason_code=reason_code,
    )


def McuCompatibilityMissing_Is(
    component_ids: tuple[str, ...], compatible_mcus: list[object]
) -> bool:
    compatible = {value for value in compatible_mcus if isinstance(value, str)}
    return not compatible.intersection(component_ids)


def StrategyAvailabilities_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> dict[str, SelectionAvailability]:
    values: dict[str, SelectionAvailability] = {}
    for slot in catalog.SelectionSlots_Get(SelectionKind.STRATEGY.value):
        for manifest in catalog.SelectionSlot_Get(slot):
            component_ids = _SelectedComponentIdsForStrategy_Get(
                model, slot, manifest.component_id
            )
            values[manifest.component_id] = _ManifestAvailability_Get(
                manifest, component_ids, catalog
            )
    return values


def ModeOptionAvailabilities_Get(
    model: ProjectModel, catalog: PluginCatalog
) -> dict[tuple[str, str], SelectionAvailability]:
    component_ids = model.ComponentIds_Get()
    values: dict[tuple[str, str], SelectionAvailability] = {}
    for component_id in model.base_components:
        manifest = catalog.Component_Get(component_id)
        selection = manifest.selection
        if selection is None or selection.kind != SelectionKind.MODE:
            continue
        for option in selection.options:
            requirements = selection.option_requirements.get(option)
            values[(selection.slot, option)] = _ManifestAvailability_Get(
                manifest,
                component_ids,
                catalog,
                additional_capabilities=(
                    tuple(
                        requirement.capability
                        for requirement in requirements.capabilities
                    )
                    if requirements is not None
                    else ()
                ),
                additional_components=(
                    requirements.components if requirements is not None else ()
                ),
            )
    return values


def _Strategies_Reconcile(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ConfigurationNotice, ...]:
    notices: list[ConfigurationNotice] = []
    slot_count = len(catalog.SelectionSlots_Get(SelectionKind.STRATEGY.value))
    for _pass in range(max(1, slot_count + 1)):
        changed = False
        availability = StrategyAvailabilities_Get(model, catalog)
        for slot in catalog.SelectionSlots_Get(SelectionKind.STRATEGY.value):
            selected = model.strategies.get(slot)
            if selected is None:
                continue
            selected_availability = availability.get(selected)
            if selected_availability is not None and selected_availability.available:
                continue
            legal = [
                manifest.component_id
                for manifest in catalog.SelectionSlot_Get(slot)
                if availability.get(
                    manifest.component_id, SelectionAvailability(False)
                ).available
            ]
            if len(legal) == 1:
                model.strategies[slot] = legal[0]
                notices.append(
                    ConfigurationNotice(
                        "configuration.strategy_auto_selected",
                        slot=slot,
                        component_id=legal[0],
                    )
                )
            else:
                model.strategies[slot] = None
                notices.append(
                    ConfigurationNotice(
                        (
                            "configuration.strategy_reselect"
                            if legal
                            else "configuration.strategy_unsupported"
                        ),
                        slot=slot,
                        component_id=selected,
                    )
                )
            changed = True
        if not changed:
            break
    return tuple(notices)


def _Modes_Reconcile(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ConfigurationNotice, ...]:
    availability = ModeOptionAvailabilities_Get(model, catalog)
    notices: list[ConfigurationNotice] = []
    for slot, values in tuple(model.modes.items()):
        retained = [
            option
            for option in values
            if availability.get((slot, option), SelectionAvailability(False)).available
        ]
        if retained != values:
            model.modes[slot] = retained
            notices.append(
                ConfigurationNotice(
                    "configuration.mode_options_removed",
                    slot=slot,
                    count=len(values) - len(retained),
                )
            )
    return tuple(notices)


def _Hardware_Reconcile(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ConfigurationNotice, ...]:
    if model.hardware.mode == "unselected":
        model.board = ""
        model.resource_assignments = {}
        return ()
    reset = False
    if model.hardware.mode == "board_plugin":
        if not model.board:
            reset = True
        else:
            board = catalog.Component_Get(model.board)
            reset = (
                board.board is None
                or model.mcu not in board.board.compatible_mcus
            )
    elif model.hardware.mode == "custom":
        mcu = catalog.Component_Get(model.mcu)
        provider = (
            catalog.Component_Get(model.hardware.provider)
            if model.hardware.provider
            else None
        )
        expected_mcu = str(mcu.metadata.get("mcu_model", mcu.name))
        reset = (
            provider is None
            or provider.hardware_provider is None
            or provider.hardware_provider.vendor
            != str(mcu.metadata.get("vendor", ""))
            or bool(model.hardware.mcu and model.hardware.mcu != expected_mcu)
        )
    if not reset:
        return ()
    model.board = ""
    model.hardware = HardwareConfiguration()
    model.resource_assignments = {}
    return (ConfigurationNotice("configuration.hardware_reset"),)


def _ResourceAssignments_Reconcile(
    model: ProjectModel, catalog: PluginCatalog
) -> tuple[ResourceAssignmentResult, int, int, int]:
    previous = dict(model.resource_assignments)
    options = ResourceRequirementOptions_Get(model, catalog)
    valid_options = {option.key: option for option in options}
    if model.hardware.mode == "unselected":
        model.resource_assignments = {}
    else:
        retained: dict[str, str] = {}
        for key, assignment in previous.items():
            option = valid_options.get(key)
            if option is None or not assignment:
                continue
            if assignment not in option.candidates:
                continue
            retained[key] = assignment
        model.resource_assignments = retained
    result = ResourceAssignments_Resolve(model, catalog, auto_assign=True)
    retained_count = sum(
        1
        for key, assignment in previous.items()
        if model.resource_assignments.get(key) == assignment
    )
    cleared_count = sum(
        1
        for key, assignment in previous.items()
        if assignment and model.resource_assignments.get(key) != assignment
    )
    required_keys = {option.key for option in options if option.required}
    pending_count = sum(
        1 for key in required_keys if not model.resource_assignments.get(key)
    )
    return result, retained_count, cleared_count, pending_count


def ProjectConfiguration_Reconcile(
    model: ProjectModel, catalog: PluginCatalog
) -> ProjectConfigurationResult:
    candidate = deepcopy(model)
    notices = [*_Hardware_Reconcile(candidate, catalog)]
    notices.extend(_Strategies_Reconcile(candidate, catalog))
    notices.extend(_Modes_Reconcile(candidate, catalog))
    capability_resolution = CapabilitySourceOverrides_Reconcile(candidate, catalog)
    (
        resource_resolution,
        retained,
        cleared,
        pending,
    ) = _ResourceAssignments_Reconcile(candidate, catalog)
    LoggingProfile_Reconcile(candidate, catalog)
    edit_validation = Project_EditValidate(candidate, catalog)
    return ProjectConfigurationResult(
        model=candidate,
        capability_resolution=capability_resolution,
        resource_resolution=resource_resolution,
        strategy_availability=StrategyAvailabilities_Get(candidate, catalog),
        mode_availability=ModeOptionAvailabilities_Get(candidate, catalog),
        edit_validation=edit_validation,
        notices=tuple(notices),
        retained_assignments=retained,
        cleared_assignments=cleared,
        pending_assignments=pending,
    )
