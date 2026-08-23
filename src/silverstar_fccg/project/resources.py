from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from collections import Counter

from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import (
    ResourceMode,
    ResourceProvision,
    ResourceRequirement,
    ResourceRole,
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
    kind: str
    required: bool
    mode: str
    assignment: str
    candidates: tuple[str, ...]


def ResourceRequirement_Key(component_id: str, requirement_name: str) -> str:
    return f"{component_id}:{requirement_name}"


def _ResourceRole_Get(
    component_id: str,
    component_class: str,
    requirement_name: str,
    roles: dict[str, ResourceRole],
) -> ResourceRole | None:
    for key in (
        f"{component_id}:{requirement_name}",
        f"{component_class}:{requirement_name}" if component_class else "",
    ):
        if key and key in roles:
            return roles[key]
    return None


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
        for provision in manifest.resource_provisions:
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
    assignments: list[AssignedResource] = []
    errors: list[str] = []
    for component_id in model.ComponentIds_Get():
        manifest = catalog.Component_Get(component_id)
        for requirement in manifest.resource_requirements:
            key = ResourceRequirement_Key(component_id, requirement.name)
            role = _ResourceRole_Get(
                component_id,
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
            if requirement.mode == ResourceMode.EXCLUSIVE:
                claimed[selected] = key
            assignments.append(
                AssignedResource(key, component_id, requirement, provision, role)
            )

    used = {assignment.provision.resource_id for assignment in assignments}
    for conflict in board_conflicts:
        conflict_set = set(conflict.resources)
        if conflict_set.issubset(used):
            detail = conflict.message or ", ".join(conflict.resources)
            errors.append(f"Board resource conflict: {detail}")
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
        provisions.update(
            {provision.resource_id: provision for provision in manifest.resource_provisions}
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
    for component_id in model.ComponentIds_Get():
        manifest = catalog.Component_Get(component_id)
        for requirement in manifest.resource_requirements:
            key = ResourceRequirement_Key(component_id, requirement.name)
            role = _ResourceRole_Get(
                component_id,
                manifest.component_class,
                requirement.name,
                roles,
            )
            options.append(
                ResourceRequirementOption(
                    key=key,
                    kind=requirement.kind,
                    required=requirement.required,
                    mode=requirement.mode.value,
                    assignment=model.resource_assignments.get(key, ""),
                    candidates=_Candidates_Get(requirement, role, provisions),
                )
            )
    return tuple(options)
