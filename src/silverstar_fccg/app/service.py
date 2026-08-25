from __future__ import annotations

import json
import os
from collections.abc import Callable
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

from silverstar_fccg.build.runner import (
    BuildAction,
    BuildProgress,
    BuildResult,
    BuildRunner,
)
from silverstar_fccg.build.toolchain import ToolchainDetector, ToolchainResult
from silverstar_fccg.core.view_models import (
    BoardCompatibilityView,
    CapabilityUsageView,
    ComponentType,
    ComponentView,
    DeviceInstanceView,
    ResourceRequirementView,
)
from silverstar_fccg.core.errors import FccgError
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.generator.assembler import ApplyResult, GenerationPlan, ProjectAssembler
from silverstar_fccg.generator.hardware_preparation import (
    HardwarePreparationFingerprint_Get,
)
from silverstar_fccg.hardware import BoardPluginExporter, CubeMxImportResult, CubeMxImporter
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.installer import PluginInstaller
from silverstar_fccg.plugins.manifest import PluginManifest
from silverstar_fccg.project.model import (
    HardwareConfiguration,
    ProjectModel,
    ProjectModel_Load,
)
from silverstar_fccg.project.capabilities import (
    CapabilityKind_Get,
    CapabilityResolution,
    CapabilityResolution_Resolve,
    CapabilitySourceOverrides_Reconcile,
    Capability_UserSelectable_Is,
)
from silverstar_fccg.project.configuration import (
    ProjectConfigurationResult,
    ProjectConfiguration_Reconcile,
)
from silverstar_fccg.project.lifecycle import (
    ProjectReadiness,
    ProjectReadiness_Inspect,
)
from silverstar_fccg.project.logging import LoggingProfile_Reconcile
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.resources import (
    BoardCompatibility_Resolve,
    ResourceAssignmentResult,
    ResourceAssignments_Resolve,
    ResourceRequirementOptions_Get,
)


class FccgService:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.policy = WorkspacePolicy(self.workspace_root)
        self.catalog = PluginCatalog(
            self.workspace_root / "plugins" / "builtin",
            self.workspace_root / "plugins" / "installed",
        )
        self.catalog.Scan()
        self.installer = PluginInstaller(
            self.policy,
            self.workspace_root / "plugins" / "installed",
            self.catalog,
        )
        self.assembler = ProjectAssembler(self.policy, self.catalog)
        self.build_runner = BuildRunner(self.policy)
        self.toolchain_detector = ToolchainDetector()
        self.hardware_importer = CubeMxImporter(self.policy)
        self.board_exporter = BoardPluginExporter(self.policy)

    def ReferenceProject_Create(self, name: str) -> ProjectModel:
        return ReferenceProject_Create(
            name,
            reference_provenance=self.catalog.ReferenceProvenance_Get(),
            catalog=self.catalog,
        )

    def ProjectDraft_Create(self, name: str) -> ProjectModel:
        model = self.ReferenceProject_Create(name)
        model.board = ""
        provider = self.HardwareProviderForMcu_Get(model.mcu)
        model.hardware = (
            HardwareConfiguration(
                mode="custom",
                source_kind="manual_import",
                provider=provider,
            )
            if provider
            else HardwareConfiguration()
        )
        model.resource_assignments = {}
        return self.ProjectConfiguration_Reconcile(model).model

    def Project_Open(self, path: Path) -> ProjectModel:
        project_file = path / "SilverStar.ssproject" if path.is_dir() else path
        return ProjectModel_Load(project_file.resolve())

    def Project_Save(
        self,
        model: ProjectModel,
        project_root: Path,
        *,
        confirm_dangerous: bool = False,
    ) -> ApplyResult:
        """Validate and materialize a complete, buildable project."""
        return self.Project_EnsureBuildable(
            model,
            project_root,
            confirm_dangerous=confirm_dangerous,
        )

    def ProjectReadiness_Get(
        self, model: ProjectModel, project_root: Path
    ) -> ProjectReadiness:
        policy = self._OutputPolicy_Get(project_root)
        return ProjectReadiness_Inspect(model, policy.root, self.catalog)

    def Project_EnsureBuildable(
        self,
        model: ProjectModel,
        project_root: Path,
        *,
        confirm_dangerous: bool = False,
    ) -> ApplyResult:
        policy = self._OutputPolicy_Get(project_root)
        configuration = self.ProjectConfiguration_Reconcile(model)
        candidate = configuration.model
        resources = configuration.resource_resolution
        if not resources.valid:
            raise FccgError(
                "error.resource_assignment_incomplete",
                {"count": len(resources.errors)},
                "\n".join(resources.errors),
            )

        assembler = self._Assembler_Get(policy.root)
        plan = assembler.Plan(candidate, policy.root)
        if not plan.valid:
            details = [
                f"[{issue.code}] {issue.message}"
                for issue in plan.validation.issues
            ]
            details.extend(
                f"{operation.target}: {operation.detail}"
                for operation in plan.operations
                if operation.operation == "CONFLICT"
            )
            raise FccgError(
                "error.project_validation_failed",
                {"count": len(plan.validation.issues)},
                "\n".join(details),
            )
        if plan.dangerous and not confirm_dangerous:
            raise FccgError(
                "error.dangerous_confirmation_required",
                {},
                "\n".join(
                    f"{operation.target}: {operation.detail}"
                    for operation in plan.operations
                    if operation.dangerous
                ),
            )
        result = assembler.Apply(
            candidate,
            plan,
            confirm_dangerous=confirm_dangerous,
        )
        final_readiness = ProjectReadiness_Inspect(candidate, policy.root, self.catalog)
        if not final_readiness.ready:
            details = (
                *(f"missing: {path}" for path in final_readiness.missing),
                *(f"stale: {path}" for path in final_readiness.stale),
            )
            raise FccgError(
                "error.project_not_ready",
                {},
                "\n".join(details) or final_readiness.technical_detail,
            )
        self._ProjectModel_Commit(model, candidate)
        return result

    def Project_HardwarePrepare(
        self,
        model: ProjectModel,
        project_root: Path,
        *,
        confirm_dangerous: bool = False,
    ) -> ApplyResult:
        """Prepare verified/imported hardware through the same atomic save path."""
        return self.Project_EnsureBuildable(
            model,
            project_root,
            confirm_dangerous=confirm_dangerous,
        )

    def Project_HardwarePrepared_Is(
        self, model: ProjectModel, project_root: Path
    ) -> bool:
        policy = self._OutputPolicy_Get(project_root)
        marker = policy.root / ".fccg" / "hardware-preparation.json"
        if not marker.is_file():
            return False
        try:
            value = json.loads(marker.read_text(encoding="utf-8"))
            if value.get("fingerprint") != HardwarePreparationFingerprint_Get(
                model, self.catalog
            ):
                return False
            if model.hardware.mode == "board_plugin":
                board = self.catalog.Component_Get(model.board)
                return all(
                    (policy.root / source.relative_to(board.payload_root)).is_file()
                    for source in board.PayloadFiles_Get()
                )
            return (policy.root / ProjectAssembler.HARDWARE_ROOT).is_dir()
        except (OSError, ValueError, TypeError, AttributeError):
            return False

    def Project_SaveAs(
        self,
        model: ProjectModel,
        source_root: Path | None,
        destination_root: Path,
        *,
        confirm_dangerous: bool = False,
    ) -> Path:
        source = source_root.resolve() if source_root is not None else None
        destination = destination_root.resolve(strict=False)
        CapabilitySourceOverrides_Reconcile(model, self.catalog)
        LoggingProfile_Reconcile(model, self.catalog)
        resources = ResourceAssignments_Resolve(
            model, self.catalog, auto_assign=True
        )
        if not resources.valid:
            raise FccgError(
                "error.resource_assignment_incomplete",
                {"count": len(resources.errors)},
                "\n".join(resources.errors),
            )
        if source is not None:
            try:
                destination.relative_to(source)
            except ValueError:
                pass
            else:
                raise FccgError(
                    "error.save_as_nested",
                    {},
                    "Save As destination cannot be inside the source project",
                )
            try:
                source.relative_to(destination)
            except ValueError:
                pass
            else:
                raise FccgError(
                    "error.save_as_nested",
                    {},
                    "Save As source cannot be inside the destination project",
                )
        policy = self._OutputPolicy_Get(destination)
        policy.Directory_Ensure(policy.root)
        if any(policy.root.iterdir()):
            raise FccgError(
                "error.save_as_destination_not_empty",
                {"path": str(policy.root)},
                f"Save As destination is not empty: {policy.root}",
            )
        staging = policy.Path_Resolve(policy.root / ".fccg-save-as-staging")
        policy.Directory_Ensure(staging)
        excluded_directories = {
            "build",
            "__pycache__",
            ".pytest_cache",
            ".cache",
            ".mypy_cache",
            ".ruff_cache",
            ".fccg-save-as-staging",
        }
        excluded_suffixes = {
            ".o",
            ".d",
            ".elf",
            ".hex",
            ".bin",
            ".map",
            ".lst",
            ".pyc",
            ".su",
            ".gcda",
            ".gcno",
        }
        try:
            staged_project = policy.Directory_Ensure(staging / "project")
            if source is not None and (source / "SilverStar.ssproject").is_file():
                for current_name, directory_names, file_names in os.walk(
                    source, topdown=True, followlinks=False
                ):
                    current = Path(current_name)
                    kept_directories: list[str] = []
                    for directory_name in sorted(directory_names):
                        source_path = current / directory_name
                        relative = source_path.relative_to(source)
                        if (
                            directory_name in excluded_directories
                            or (
                                len(relative.parts) > 1
                                and relative.parts[0] == ".fccg"
                                and relative.parts[1]
                                in {"cache", "staging", "tmp"}
                            )
                        ):
                            continue
                        if source_path.is_symlink():
                            raise FccgError(
                                "error.save_as_symlink",
                                {"path": str(relative)},
                                f"Save As refuses source symlink: {source_path}",
                            )
                        kept_directories.append(directory_name)
                        policy.Directory_Ensure(staged_project / relative)
                    directory_names[:] = kept_directories
                    for file_name in sorted(file_names):
                        source_path = current / file_name
                        relative = source_path.relative_to(source)
                        if source_path.is_symlink():
                            raise FccgError(
                                "error.save_as_symlink",
                                {"path": str(relative)},
                                f"Save As refuses source symlink: {source_path}",
                            )
                        if source_path.suffix.casefold() not in excluded_suffixes:
                            policy.File_Copy(
                                source_path, staged_project / relative
                            )

            readiness = ProjectReadiness_Inspect(
                model, staged_project, self.catalog
            )
            if not readiness.ready:
                staged_assembler = ProjectAssembler(
                    self.policy,
                    self.catalog,
                    WorkspacePolicy(staged_project),
                )
                staged_plan = staged_assembler.Plan(model, staged_project)
                if not staged_plan.valid:
                    raise FccgError(
                        "error.project_validation_failed",
                        {"count": len(staged_plan.validation.issues)},
                        "\n".join(
                            f"[{issue.code}] {issue.message}"
                            for issue in staged_plan.validation.issues
                        ),
                    )
                if staged_plan.dangerous and not confirm_dangerous:
                    raise FccgError(
                        "error.dangerous_confirmation_required",
                        {},
                        "\n".join(
                            f"{operation.target}: {operation.detail}"
                            for operation in staged_plan.operations
                            if operation.dangerous
                        ),
                    )
                staged_assembler.Apply(
                    model,
                    staged_plan,
                    confirm_dangerous=confirm_dangerous,
                )
                readiness = ProjectReadiness_Inspect(
                    model, staged_project, self.catalog
                )
            if not readiness.ready:
                raise FccgError(
                    "error.project_not_ready",
                    {},
                    "\n".join((*readiness.missing, *readiness.stale)),
                )

            moved: list[Path] = []
            try:
                for staged_path in sorted(
                    staged_project.iterdir(),
                    key=lambda item: (
                        item.name == "SilverStar.ssproject",
                        item.name,
                    ),
                ):
                    target = policy.root / staged_path.name
                    staged_path.replace(target)
                    moved.append(target)
            except Exception:
                for target in reversed(moved):
                    if target.is_dir():
                        policy.Tree_Remove(target)
                    else:
                        target.unlink(missing_ok=True)
                raise
            policy.Tree_Remove(staging)
        except Exception:
            if staging.exists():
                policy.Tree_Remove(staging)
            raise
        return policy.root

    def GenerationPlan_Create(self, model: ProjectModel, project_root: Path) -> GenerationPlan:
        selected_root = Path(project_root).resolve(strict=False)
        return self._Assembler_Get(selected_root).Plan(model, selected_root)

    def GenerationPlan_Apply(
        self,
        model: ProjectModel,
        plan: GenerationPlan,
        *,
        confirm_dangerous: bool = False,
    ) -> ApplyResult:
        return self._Assembler_Get(plan.project_root).Apply(
            model, plan, confirm_dangerous=confirm_dangerous
        )

    def Plugin_Install(self, archive_path: Path) -> PluginManifest:
        return self.installer.Install(archive_path)

    def Plugin_Get(self, component_id: str) -> PluginManifest:
        return self.catalog.Component_Get(component_id)

    def Plugin_Remove(self, component_id: str) -> PluginManifest:
        return self.installer.Remove(component_id)

    def Plugins_Refresh(self) -> None:
        self.catalog.Scan()

    def PluginDocumentationRoot_Get(self, component_id: str) -> Path:
        manifest = self.catalog.Component_Get(component_id)
        package_root = manifest.package_root.resolve()
        documentation_root = (package_root / "docs").resolve()
        try:
            documentation_root.relative_to(package_root)
        except ValueError as error:
            raise ValueError(
                f"Plugin documentation path escaped its package: {component_id}"
            ) from error
        if not documentation_root.is_dir():
            raise ValueError(f"Plugin has no documentation directory: {component_id}")
        return documentation_root

    def Toolchains_Detect(
        self, tool_paths: dict[str, str] | None = None
    ) -> tuple[ToolchainResult, ...]:
        return self.toolchain_detector.Detect(tool_paths)

    def Build_Run(
        self,
        model: ProjectModel,
        project_root: Path,
        action: BuildAction,
        token=None,
        *,
        confirm_dangerous: bool = False,
        line_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[BuildProgress], None] | None = None,
        ensure_buildable: bool = True,
    ) -> BuildResult:
        if ensure_buildable:
            self.Project_EnsureBuildable(
                model,
                project_root,
                confirm_dangerous=confirm_dangerous,
            )
        runner = BuildRunner(self._OutputPolicy_Get(project_root))
        if line_callback is None and progress_callback is None:
            return runner.Run(model, project_root, action, token)
        return runner.Run(
            model,
            project_root,
            action,
            token,
            line_callback=line_callback,
            progress_callback=progress_callback,
        )

    def Resources_AutoAssign(self, model: ProjectModel) -> ResourceAssignmentResult:
        return ResourceAssignments_Resolve(model, self.catalog, auto_assign=True)

    def ResourceRequirementViews_Get(
        self, model: ProjectModel, language: str = "zh_CN"
    ) -> tuple[ResourceRequirementView, ...]:
        resolution = ResourceAssignments_Resolve(
            model, self.catalog, auto_assign=False
        )
        return tuple(
            ResourceRequirementView(
                kind=option.kind,
                name=option.key.rsplit(":", 1)[-1],
                key=option.key,
                display_name=(
                    f"{self.catalog.Component_Get(option.plugin_id).DisplayName_Get(language)}"
                    f" · {option.display_names.get(language, option.key.rsplit(':', 1)[-1].replace('_', ' '))}"
                ),
                contract_summary=option.contract_summary,
                assignment=option.assignment,
                recommended_assignment=option.recommended_assignment,
                candidates=option.candidates,
                required=option.required,
                mode=option.mode,
                fixed=option.fixed,
                physical_resource=option.physical_resource,
                physical_details=option.physical_details,
                pending_hardware_confirmation=(
                    not option.candidates
                    and model.hardware.mode != "board_plugin"
                    and not model.hardware.snapshot_id
                ),
                validation_error="\n".join(
                    error for error in resolution.errors if option.key in error
                ),
            )
            for option in ResourceRequirementOptions_Get(model, self.catalog)
        )

    def CubeMxProject_Import(
        self,
        input_path: Path,
        model: ProjectModel,
        *,
        risk_acknowledged: bool,
    ) -> CubeMxImportResult:
        mcu = self.catalog.Component_Get(model.mcu)
        expected_mcu = str(mcu.metadata.get("mcu_model", mcu.name))
        providers = [
            component
            for component in self.catalog.Type_Get("hardware_configuration_provider")
            if component.hardware_provider is not None
            and component.hardware_provider.vendor == str(mcu.metadata.get("vendor", ""))
        ]
        if len(providers) != 1:
            raise ValueError("Selected MCU requires exactly one compatible hardware provider")
        return self.hardware_importer.Project_Import(
            input_path,
            expected_mcu=expected_mcu,
            provider_id=providers[0].component_id,
            risk_acknowledged=risk_acknowledged,
        )

    def HardwareProviderForMcu_Get(self, mcu_id: str) -> str:
        mcu = self.catalog.Component_Get(mcu_id)
        vendor = str(mcu.metadata.get("vendor", ""))
        providers = [
            component.component_id
            for component in self.catalog.Type_Get("hardware_configuration_provider")
            if component.hardware_provider is not None
            and component.hardware_provider.vendor == vendor
        ]
        return providers[0] if len(providers) == 1 else ""

    def CustomBoardPlugin_Export(
        self,
        model: ProjectModel,
        output_path: Path,
        *,
        component_id: str,
        name: str,
    ) -> Path:
        snapshot = self.hardware_importer.SnapshotRoot_Get(
            model.hardware.snapshot_id
        )
        output = Path(output_path).resolve(strict=False)
        exporter = BoardPluginExporter(
            self.policy, WorkspacePolicy(output.parent)
        )
        return exporter.Plugin_Export(
            model,
            snapshot,
            output,
            component_id=component_id,
            name=name,
        )

    def BoardCompatibilities_Get(
        self, model: ProjectModel, *, language: str = "zh_CN"
    ) -> tuple[BoardCompatibilityView, ...]:
        views: list[BoardCompatibilityView] = []
        for board in self.catalog.Type_Get("board"):
            result = BoardCompatibility_Resolve(model, self.catalog, board.component_id)
            missing = ", ".join(
                f"{kind} ×{count}" for kind, count in result.missing
            )
            views.append(
                BoardCompatibilityView(
                    component_id=board.component_id,
                    name=board.DisplayName_Get(language),
                    compatible=result.compatible,
                    missing_text=missing,
                    detail="; ".join(result.errors),
                )
            )
        return tuple(sorted(views, key=lambda view: (not view.compatible, view.name)))

    def _OutputPolicy_Get(self, project_root: Path) -> WorkspacePolicy:
        selected = Path(project_root)
        if selected.exists() and selected.is_symlink():
            raise FccgError(
                "error.project_output_symlink",
                {"path": str(selected)},
                f"A project output directory cannot be a symlink: {selected}",
            )
        return WorkspacePolicy(selected.resolve(strict=False))

    def _Assembler_Get(self, project_root: Path) -> ProjectAssembler:
        policy = self._OutputPolicy_Get(project_root)
        return ProjectAssembler(self.policy, self.catalog, policy)

    def ComponentViews_Get(self, language: str = "zh_CN") -> tuple[ComponentView, ...]:
        return tuple(
            self._ComponentView_Get(manifest, language)
            for manifest in self.catalog.All_Get()
        )

    def CapabilityResolution_Get(
        self, model: ProjectModel, *, reconcile: bool = False
    ) -> CapabilityResolution:
        if reconcile:
            return CapabilitySourceOverrides_Reconcile(model, self.catalog)
        return CapabilityResolution_Resolve(model, self.catalog)

    def ProjectConfiguration_Reconcile(
        self, model: ProjectModel
    ) -> ProjectConfigurationResult:
        return ProjectConfiguration_Reconcile(model, self.catalog)

    def DeviceInstanceViews_Get(
        self, model: ProjectModel, language: str = "zh_CN"
    ) -> tuple[DeviceInstanceView, ...]:
        resolution = CapabilityResolution_Resolve(model, self.catalog)
        return tuple(
            DeviceInstanceView(
                instance_id=instance.instance_id,
                plugin_id=instance.plugin,
                name=self.catalog.Component_Get(instance.plugin).DisplayName_Get(
                    language
                ),
                component_class=self.catalog.Component_Get(
                    instance.plugin
                ).component_class,
                provides=self.catalog.Component_Get(instance.plugin).provides,
                consumed=resolution.ConsumedCapabilitiesForInstance_Get(
                    instance.instance_id
                ),
                unused=resolution.unused_by_instance.get(instance.instance_id, ()),
                enabled=resolution.EnabledCapabilitiesForInstance_Get(
                    instance.instance_id
                ),
                unqualified=tuple(
                    str(capability)
                    for capability in self.catalog.Component_Get(
                        instance.plugin
                    ).metadata.get("unqualified_capabilities", {})
                ),
                required=bool(
                    resolution.required_by_instance.get(instance.instance_id, ())
                ),
                required_capabilities=resolution.required_by_instance.get(
                    instance.instance_id, ()
                ),
                project_max=self.catalog.Component_Get(
                    instance.plugin
                ).instance_policy.project_max,
                same_plugin_multiple=self.catalog.Component_Get(
                    instance.plugin
                ).instance_policy.same_plugin_multiple,
                multi_instance_ready=self.catalog.Component_Get(
                    instance.plugin
                ).instance_policy.multi_instance_ready,
            )
            for instance in model.device_instances
        )

    def CapabilityUsageViews_Get(
        self, model: ProjectModel, language: str = "zh_CN"
    ) -> tuple[CapabilityUsageView, ...]:
        resolution = CapabilityResolution_Resolve(model, self.catalog)
        instance_names = {
            instance.instance_id: self.catalog.Component_Get(
                instance.plugin
            ).DisplayName_Get(language)
            for instance in model.device_instances
        }
        providers_by_capability: dict[str, list[tuple[str, str]]] = {}
        ordered_capabilities: list[str] = []
        for instance in model.device_instances:
            manifest = self.catalog.Component_Get(instance.plugin)
            for capability in manifest.provides:
                if not Capability_UserSelectable_Is(capability):
                    continue
                if capability not in ordered_capabilities:
                    ordered_capabilities.append(capability)
                providers_by_capability.setdefault(capability, []).append(
                    (instance.instance_id, instance_names[instance.instance_id])
                )
        for requirement in resolution.requirements:
            if (
                Capability_UserSelectable_Is(requirement.capability)
                and requirement.capability not in ordered_capabilities
            ):
                ordered_capabilities.append(requirement.capability)

        routes_by_capability = {
            capability: tuple(
                route
                for route in resolution.routes
                if route.requirement.capability == capability
            )
            for capability in ordered_capabilities
        }
        choices = {choice.capability: choice for choice in resolution.choices}
        requirements_by_capability = {
            capability: tuple(
                requirement
                for requirement in resolution.requirements
                if requirement.capability == capability
            )
            for capability in ordered_capabilities
        }
        views: list[CapabilityUsageView] = []
        for capability in ordered_capabilities:
            routes = routes_by_capability[capability]
            requirements = requirements_by_capability[capability]
            source_id = routes[0].provider.instance_id if routes else ""
            consumer_names = tuple(
                dict.fromkeys(
                    self.catalog.Component_Get(
                        requirement.consumer_component
                    ).DisplayName_Get(language)
                    for requirement in requirements
                )
            )
            choice = choices.get(capability)
            views.append(
                CapabilityUsageView(
                    capability=capability,
                    kind=CapabilityKind_Get(capability).value,
                    source_instance_id=source_id,
                    source_name=instance_names.get(source_id, ""),
                    used=bool(routes),
                    missing=bool(requirements) and not routes and choice is None,
                    ambiguous=bool(choice is not None and choice.requires_selection),
                    consumers=consumer_names,
                    purposes=tuple(
                        dict.fromkeys(
                            requirement.purpose for requirement in requirements
                        )
                    ),
                    providers=tuple(providers_by_capability.get(capability, ())),
                )
            )
        return tuple(views)

    @staticmethod
    def _ComponentView_Get(
        manifest: PluginManifest, language: str = "zh_CN"
    ) -> ComponentView:
        requirements = tuple(
            ResourceRequirementView(
                kind=requirement.kind,
                name=requirement.name,
                candidates=requirement.candidates,
                required=requirement.required,
                mode=requirement.mode.value,
            )
            for requirement in manifest.resource_requirements
        )
        return ComponentView(
            component_id=manifest.component_id,
            name=manifest.DisplayName_Get(language),
            component_type=ComponentType(manifest.component_type),
            version=manifest.version,
            component_class=manifest.component_class,
            description=manifest.Description_Get(language),
            source=manifest.source,
            status="installed" if manifest.source == "installed" else "available",
            dependencies=tuple(
                requirement.component_id for requirement in manifest.dependencies
            ),
            provides=manifest.provides,
            requirements=requirements,
            options={
                "device_category": str(
                    manifest.metadata.get("device_category", "")
                ),
                "logical_device": manifest.metadata.get("logical_device") is True,
                "selection_labels": (
                    manifest.selection.labels.get(language, {})
                    if manifest.selection is not None
                    else {}
                )
                ,
                "selection_option_requirements": (
                    {
                        option: {
                            "capabilities": tuple(
                                requirement.capability
                                for requirement in requirements.capabilities
                            ),
                            "components": requirements.components,
                        }
                        for option, requirements in manifest.selection.option_requirements.items()
                    }
                    if manifest.selection is not None
                    else {}
                ),
                "selection_parameters": (
                    {
                        option: tuple(
                            {
                                "id": parameter.parameter_id,
                                "type": parameter.value_type,
                                "default": parameter.default,
                                "minimum": parameter.minimum,
                                "maximum": parameter.maximum,
                                "unit": parameter.unit,
                                "generated_symbol": parameter.generated_symbol,
                                "generated_scale": parameter.generated_scale,
                                "display_name": parameter.DisplayName_Get(language),
                            }
                            for parameter in parameters
                        )
                        for option, parameters in manifest.selection.parameters.items()
                    }
                    if manifest.selection is not None
                    else {}
                ),
            },
            selection_kind=(
                manifest.selection.kind.value if manifest.selection is not None else ""
            ),
            selection_slot=(manifest.selection.slot if manifest.selection is not None else ""),
            selection_options=(manifest.selection.options if manifest.selection is not None else ()),
            selection_default=(manifest.selection.default if manifest.selection is not None else ()),
            allow_none=(manifest.selection.allow_none if manifest.selection is not None else False),
            allow_multiple=(manifest.selection.allow_multiple if manifest.selection is not None else False),
            ui_order=(manifest.selection.ui_order if manifest.selection is not None else 100),
            board_source_kind=(manifest.board.source_kind if manifest.board is not None else ""),
            board_verified=(manifest.board.verified if manifest.board is not None else False),
            compatible_mcus=(manifest.board.compatible_mcus if manifest.board is not None else ()),
            cardinality=manifest.cardinality,
            project_max=manifest.instance_policy.project_max,
            same_plugin_multiple=manifest.instance_policy.same_plugin_multiple,
            multi_instance_ready=manifest.instance_policy.multi_instance_ready,
            vendor=str(manifest.metadata.get("vendor", "")),
            physical_vendor=(
                manifest.physical_device.vendor
                if manifest.physical_device is not None
                else ""
            ),
            physical_model=(
                manifest.physical_device.model
                if manifest.physical_device is not None
                else ""
            ),
            chipset=(
                manifest.physical_device.chipset
                if manifest.physical_device is not None
                else ""
            ),
            driver=(
                manifest.physical_device.driver
                if manifest.physical_device is not None
                else ""
            ),
        )

    @staticmethod
    def _ProjectModel_Commit(target: ProjectModel, source: ProjectModel) -> None:
        for model_field in fields(ProjectModel):
            setattr(target, model_field.name, deepcopy(getattr(source, model_field.name)))
