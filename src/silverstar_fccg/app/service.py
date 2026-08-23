from __future__ import annotations

from pathlib import Path

from silverstar_fccg.build.runner import BuildAction, BuildResult, BuildRunner
from silverstar_fccg.build.toolchain import ToolchainDetector, ToolchainResult
from silverstar_fccg.core.view_models import (
    BoardCompatibilityView,
    ComponentType,
    ComponentView,
    ResourceRequirementView,
)
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.generator.assembler import ApplyResult, GenerationPlan, ProjectAssembler
from silverstar_fccg.hardware import BoardPluginExporter, CubeMxImportResult, CubeMxImporter
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.installer import PluginInstaller
from silverstar_fccg.plugins.manifest import PluginManifest
from silverstar_fccg.project.model import ProjectModel, ProjectModel_Load
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
            name, reference_provenance=self.catalog.ReferenceProvenance_Get()
        )

    def Project_Open(self, path: Path) -> ProjectModel:
        project_file = path / "SilverStar.ssproject" if path.is_dir() else path
        return ProjectModel_Load(project_file.resolve())

    def GenerationPlan_Create(self, model: ProjectModel, project_root: Path) -> GenerationPlan:
        return self._Assembler_Get(project_root).Plan(model, project_root)

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
    ) -> BuildResult:
        runner = BuildRunner(self._OutputPolicy_Get(project_root))
        return runner.Run(model, project_root, action, token)

    def Resources_AutoAssign(self, model: ProjectModel) -> ResourceAssignmentResult:
        return ResourceAssignments_Resolve(model, self.catalog, auto_assign=True)

    def ResourceRequirementViews_Get(
        self, model: ProjectModel
    ) -> tuple[ResourceRequirementView, ...]:
        return tuple(
            ResourceRequirementView(
                kind=option.kind,
                name=option.key.rsplit(":", 1)[-1],
                key=option.key,
                assignment=option.assignment,
                candidates=option.candidates,
                required=option.required,
                mode=option.mode,
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
        return self.board_exporter.Plugin_Export(
            model,
            snapshot,
            output_path,
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
        self.policy.Path_Resolve(project_root, allow_root=False)
        return self.policy

    def _Assembler_Get(self, project_root: Path) -> ProjectAssembler:
        policy = self._OutputPolicy_Get(project_root)
        if policy is self.policy:
            return self.assembler
        return ProjectAssembler(policy, self.catalog)

    def ComponentViews_Get(self, language: str = "zh_CN") -> tuple[ComponentView, ...]:
        return tuple(
            self._ComponentView_Get(manifest, language)
            for manifest in self.catalog.All_Get()
        )

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
            description=manifest.description,
            source=manifest.source,
            status="installed" if manifest.source == "installed" else "available",
            dependencies=tuple(
                requirement.component_id for requirement in manifest.dependencies
            ),
            provides=manifest.provides,
            requirements=requirements,
            options={
                "selection_labels": (
                    manifest.selection.labels.get(language, {})
                    if manifest.selection is not None
                    else {}
                )
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
        )
