from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.generator.render import GeneratedFiles_Render, MetadataFiles_Render
from silverstar_fccg.generator.source_graph import SourceGraph_Resolve
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.project.model import ProjectModel
from silverstar_fccg.project.validation import ProjectValidationResult, Project_Validate


class ProjectAssemblerError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlanOperation:
    operation: str
    target: str
    detail: str
    ownership: str
    dangerous: bool = False


@dataclass(frozen=True, slots=True)
class GenerationPlan:
    project_root: Path
    operations: tuple[PlanOperation, ...]
    validation: ProjectValidationResult
    new_project: bool

    @property
    def valid(self) -> bool:
        return self.validation.valid and not any(
            operation.operation == "CONFLICT" for operation in self.operations
        )

    @property
    def dangerous(self) -> bool:
        return any(operation.dangerous for operation in self.operations)


@dataclass(frozen=True, slots=True)
class ApplyResult:
    project_root: Path
    files_added: int
    files_modified: int
    component_files_preserved: int
    hardware_replaced: bool = False


class ProjectAssembler:
    HARDWARE_ROOT = "HardwareGenerated/STM32CubeMX"

    def __init__(
        self,
        workspace_policy: WorkspacePolicy,
        catalog: PluginCatalog,
    ) -> None:
        self.policy = workspace_policy
        self.catalog = catalog

    def Plan(self, model: ProjectModel, project_root: Path) -> GenerationPlan:
        destination = self.policy.Path_Resolve(project_root, allow_root=False)
        if destination.exists() and not destination.is_dir():
            raise ProjectAssemblerError(
                f"Project destination is not a directory: {destination}"
            )
        new_project = not destination.exists() or not any(destination.iterdir())
        if not new_project and not (destination / "SilverStar.ssproject").is_file():
            raise ProjectAssemblerError(
                "Existing destination is not an FCCG project (SilverStar.ssproject missing)"
            )
        validation = Project_Validate(model, self.catalog)
        if not validation.valid:
            return GenerationPlan(destination, (), validation, new_project)

        hardware_files = self._HardwareFiles_Get(model)
        desired, _ownership = self._DesiredFiles_Get(
            model, destination, hardware_files
        )
        managed_paths = set(desired)
        previous = self._Ownership_Load(destination) if not new_project else {}
        previous_components = previous.get("components", {})
        previous_active = set(previous.get("active_components", []))
        selected_components = set(model.ComponentIds_Get())
        operations: list[PlanOperation] = []

        for component_id in model.ComponentIds_Get():
            manifest = self.catalog.Component_Get(component_id)
            was_installed = component_id in previous_components
            for source in manifest.PayloadFiles_Get():
                relative = source.relative_to(manifest.payload_root).as_posix()
                target = destination.joinpath(*relative.split("/"))
                if self._ManagedPath_Is(relative, managed_paths):
                    operations.append(
                        PlanOperation(
                            "CONFLICT",
                            relative,
                            f"component {component_id} occupies an FCCG-managed path",
                            "component",
                        )
                    )
                elif new_project:
                    operations.append(
                        PlanOperation("ADD", relative, component_id, "component")
                    )
                elif was_installed:
                    operations.append(
                        PlanOperation(
                            "PRESERVE" if target.is_file() else "CONFLICT",
                            relative,
                            (
                                "project-owned source"
                                if target.is_file()
                                else "project-owned component file is missing; Apply will not restore it"
                            ),
                            "component",
                        )
                    )
                elif target.exists():
                    operations.append(
                        PlanOperation(
                            "CONFLICT",
                            relative,
                            f"new component {component_id} collides with an existing path",
                            "component",
                        )
                    )
                else:
                    operations.append(
                        PlanOperation("ADD", relative, component_id, "component")
                    )

        for component_id in sorted(previous_active - selected_components):
            modified = self._ComponentModified_Is(
                destination, previous_components.get(component_id, {})
            )
            detail = "component deactivated; project-owned source is retained"
            if modified:
                detail += " (local source changes detected)"
            operations.append(
                PlanOperation(
                    "DEACTIVATE",
                    component_id,
                    detail,
                    "component",
                    dangerous=True,
                )
            )

        previous_model = previous.get("model", {})
        if not new_project:
            for field_name, old_value, new_value in (
                ("MCU", previous_model.get("mcu", model.mcu), model.mcu),
                (
                    "target",
                    previous_model.get("target_profile", model.build.target_profile),
                    model.build.target_profile,
                ),
            ):
                if old_value != new_value:
                    operations.append(
                        PlanOperation(
                            "CHANGE",
                            field_name,
                            f"{old_value} -> {new_value}",
                            "project",
                            dangerous=True,
                        )
                    )

        previous_hashes = previous.get("managed_hashes", {})
        for relative, content in sorted(desired.items()):
            target = destination.joinpath(*relative.split("/"))
            dangerous = False
            detail = "FCCG-managed file"
            if not target.exists():
                operation = "ADD"
            elif target.is_file() and target.read_bytes() == content:
                operation = "UNCHANGED"
            elif target.is_file():
                operation = "MODIFY"
                if relative == ".eide/eide.yml":
                    current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                    previous_hash = previous_hashes.get(relative)
                    if previous_hash and current_hash != previous_hash:
                        dangerous = True
                        detail = (
                            "EIDE configuration was manually modified; applying will regenerate it"
                        )
            else:
                operation = "CONFLICT"
            operations.append(
                PlanOperation(
                    operation, relative, detail, "generated", dangerous=dangerous
                )
            )

        operations.extend(
            self._HardwareOperations_Get(
                model, destination, hardware_files, previous, new_project
            )
        )
        return GenerationPlan(
            destination, tuple(operations), validation, new_project
        )

    def Apply(
        self,
        model: ProjectModel,
        plan: GenerationPlan,
        *,
        confirm_dangerous: bool = False,
    ) -> ApplyResult:
        if not plan.valid:
            raise ProjectAssemblerError(
                "Cannot apply an invalid or conflicting generation plan"
            )
        if plan.dangerous and not confirm_dangerous:
            raise ProjectAssemblerError(
                "Dangerous operations require an explicit confirmation"
            )
        expected = self.Plan(model, plan.project_root)
        if (
            expected.operations != plan.operations
            or expected.new_project != plan.new_project
        ):
            raise ProjectAssemblerError(
                "Project state changed after planning; create a new plan"
            )
        if plan.new_project:
            return self._NewProject_Apply(model, plan.project_root)
        return self._ExistingProject_Apply(
            model, plan.project_root, replace_hardware=plan.dangerous
        )

    def _DesiredFiles_Get(
        self,
        model: ProjectModel,
        project_root: Path,
        hardware_files: dict[str, bytes] | None = None,
    ) -> tuple[dict[str, bytes], dict]:
        graph = SourceGraph_Resolve(model, self.catalog)
        desired = GeneratedFiles_Render(model, self.catalog, graph)
        desired.update(MetadataFiles_Render(model, self.catalog, graph))
        for relative in desired:
            try:
                self.policy.RelativePath_Validate(relative)
            except ValueError as error:
                raise ProjectAssemblerError(
                    f"Renderer produced an unsafe managed path: {relative!r}"
                ) from error
        previous = self._Ownership_Load(project_root)
        components = dict(previous.get("components", {}))
        components.update(model.component_provenance)
        hardware_files = hardware_files or {}
        hardware_hashes = {
            path: hashlib.sha256(content).hexdigest()
            for path, content in sorted(hardware_files.items())
        }
        managed_files = sorted((*desired.keys(), ".fccg/ownership.json"))
        ownership = {
            "format_version": 1,
            "active_components": list(model.ComponentIds_Get()),
            "components": components,
            "managed_files": managed_files,
            "managed_hashes": {
                path: hashlib.sha256(content).hexdigest()
                for path, content in sorted(desired.items())
            },
            "hardware": {
                "snapshot_id": (
                    model.hardware.snapshot_id
                    if model.hardware.mode == "custom"
                    else ""
                ),
                "files": hardware_hashes,
            },
            "model": {
                "mcu": model.mcu,
                "target_profile": model.build.target_profile,
            },
        }
        desired[".fccg/ownership.json"] = (
            json.dumps(ownership, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")
        return desired, ownership

    def _Ownership_Load(self, project_root: Path) -> dict:
        path = project_root / ".fccg" / "ownership.json"
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ProjectAssemblerError(
                f"Invalid project ownership metadata: {error}"
            ) from error
        if not isinstance(value, dict) or value.get("format_version") not in (0, 1):
            raise ProjectAssemblerError("Unsupported project ownership metadata")
        return value

    def _HardwareFiles_Get(self, model: ProjectModel) -> dict[str, bytes]:
        if model.hardware.mode != "custom":
            return {}
        snapshot_id = model.hardware.snapshot_id
        if not _Sha256_Is(snapshot_id):
            raise ProjectAssemblerError("Custom hardware snapshot id is invalid")
        snapshot = self.policy.Path_Resolve(
            self.policy.root
            / ".fccg"
            / "hardware_imports"
            / snapshot_id
            / "STM32CubeMX",
            allow_root=False,
        )
        if not snapshot.is_dir():
            raise ProjectAssemblerError(
                f"Custom hardware snapshot is unavailable: {snapshot_id}"
            )
        files: dict[str, bytes] = {}
        for source in sorted(snapshot.rglob("*")):
            if source.is_symlink():
                raise ProjectAssemblerError("Hardware snapshot contains a symlink")
            if not source.is_file():
                continue
            relative = source.relative_to(snapshot).as_posix()
            target = f"{self.HARDWARE_ROOT}/{relative}"
            self.policy.RelativePath_Validate(target)
            files[target] = source.read_bytes()
        return files

    def _HardwareOperations_Get(
        self,
        model: ProjectModel,
        destination: Path,
        hardware_files: dict[str, bytes],
        previous: dict,
        new_project: bool,
    ) -> list[PlanOperation]:
        previous_hardware = previous.get("hardware", {})
        previous_snapshot = str(previous_hardware.get("snapshot_id", ""))
        operations: list[PlanOperation] = []
        if model.hardware.mode != "custom":
            if previous_snapshot:
                operations.append(
                    PlanOperation(
                        "DEACTIVATE",
                        self.HARDWARE_ROOT,
                        "custom vendor snapshot retained but removed from the active source graph",
                        "hardware",
                        dangerous=True,
                    )
                )
            return operations
        if previous_snapshot and previous_snapshot != model.hardware.snapshot_id:
            return [
                PlanOperation(
                    "REPLACE_TREE",
                    self.HARDWARE_ROOT,
                    f"CubeMX snapshot {previous_snapshot[:12]} -> {model.hardware.snapshot_id[:12]}",
                    "hardware",
                    dangerous=True,
                )
            ]
        for relative, content in sorted(hardware_files.items()):
            target = destination.joinpath(*relative.split("/"))
            if new_project or not previous_snapshot:
                operation = "ADD" if not target.exists() else "CONFLICT"
                detail = "imported CubeMX vendor file"
            elif not target.is_file():
                operation = "CONFLICT"
                detail = "imported hardware file is missing; Apply will not restore it"
            else:
                operation = "PRESERVE"
                source_hash = hashlib.sha256(content).hexdigest()
                current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
                detail = (
                    "locally modified vendor file"
                    if source_hash != current_hash
                    else "imported CubeMX vendor file"
                )
            operations.append(
                PlanOperation(operation, relative, detail, "hardware")
            )
        return operations

    @staticmethod
    def _ManagedPath_Is(relative: str, managed_paths: set[str]) -> bool:
        return (
            relative in managed_paths
            or relative.startswith("Generated/")
            or relative.startswith(".fccg/")
            or relative.startswith(".vscode/")
            or relative.startswith(".eide/")
        )

    @staticmethod
    def _ComponentModified_Is(destination: Path, provenance: dict) -> bool:
        files = provenance.get("files", {}) if isinstance(provenance, dict) else {}
        for relative, expected_hash in files.items():
            target = destination.joinpath(*relative.split("/"))
            if not target.is_file():
                return True
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected_hash:
                return True
        return False

    def _NewProject_Apply(
        self, model: ProjectModel, destination: Path
    ) -> ApplyResult:
        if destination.exists() and any(destination.iterdir()):
            raise ProjectAssemblerError("New-project destination became non-empty")
        stage = self.policy.StagingDirectory_Create("project-")
        added = 0
        try:
            for component_id in model.ComponentIds_Get():
                manifest = self.catalog.Component_Get(component_id)
                for source in manifest.PayloadFiles_Get():
                    relative = source.relative_to(manifest.payload_root)
                    target = stage / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    added += 1
            hardware_files = self._HardwareFiles_Get(model)
            for relative, content in hardware_files.items():
                target = stage.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                added += 1
            desired, _ownership = self._DesiredFiles_Get(
                model, destination, hardware_files
            )
            for relative, content in desired.items():
                target = stage.joinpath(*relative.split("/"))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                added += 1
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                destination.rmdir()
            os.replace(stage, destination)
            return ApplyResult(destination, added, 0, 0)
        except Exception:
            if stage.exists():
                self.policy.Tree_Remove(stage)
            raise

    def _ExistingProject_Apply(
        self,
        model: ProjectModel,
        destination: Path,
        *,
        replace_hardware: bool,
    ) -> ApplyResult:
        hardware_files = self._HardwareFiles_Get(model)
        desired, _ownership = self._DesiredFiles_Get(
            model, destination, hardware_files
        )
        previous = self._Ownership_Load(destination)
        previous_components = previous.get("components", {})
        previous_snapshot = str(previous.get("hardware", {}).get("snapshot_id", ""))
        current_snapshot = (
            model.hardware.snapshot_id if model.hardware.mode == "custom" else ""
        )
        stage = self.policy.StagingDirectory_Create("apply-")
        staged_files = stage / "files"
        backup_files = stage / "backup"
        preserved = 0
        added = 0
        modified = 0
        copied_components: list[Path] = []
        applied_managed: list[tuple[Path, bool]] = []
        hardware_backup: Path | None = None
        hardware_target = destination / "HardwareGenerated" / "STM32CubeMX"
        hardware_was_replaced = False
        try:
            new_components = [
                component_id
                for component_id in model.ComponentIds_Get()
                if component_id not in previous_components
            ]
            for component_id in model.ComponentIds_Get():
                manifest = self.catalog.Component_Get(component_id)
                if component_id in previous_components:
                    preserved += len(manifest.PayloadFiles_Get())
                    continue
                for source in manifest.PayloadFiles_Get():
                    relative = source.relative_to(manifest.payload_root)
                    staged = staged_files / "components" / relative
                    staged.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, staged)

            managed_targets: list[tuple[Path, Path, bool]] = []
            for relative, content in desired.items():
                relative_path = Path(*relative.split("/"))
                staged = staged_files / "managed" / relative_path
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(content)
                target = self.policy.Path_Resolve(
                    destination / relative_path, allow_root=False
                )
                existed = target.is_file()
                if existed and target.read_bytes() == content:
                    continue
                managed_targets.append((target, staged, existed))
                if existed:
                    backup = backup_files / relative_path
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target, backup)
                    modified += 1
                else:
                    added += 1

            for component_id in new_components:
                manifest = self.catalog.Component_Get(component_id)
                for source in manifest.PayloadFiles_Get():
                    relative = source.relative_to(manifest.payload_root)
                    staged = staged_files / "components" / relative
                    target = self.policy.Path_Resolve(
                        destination / relative, allow_root=False
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(staged, target)
                    copied_components.append(target)
                    added += 1

            if current_snapshot and not previous_snapshot:
                for relative, content in hardware_files.items():
                    target = self.policy.Path_Resolve(
                        destination.joinpath(*relative.split("/")), allow_root=False
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    added += 1
            elif (
                current_snapshot
                and previous_snapshot != current_snapshot
                and replace_hardware
            ):
                staged_hardware = staged_files / "hardware"
                for relative, content in hardware_files.items():
                    suffix = Path(*relative.split("/")).relative_to(
                        Path("HardwareGenerated") / "STM32CubeMX"
                    )
                    target = staged_hardware / suffix
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                if hardware_target.exists():
                    hardware_backup = stage / "hardware-backup"
                    os.replace(hardware_target, hardware_backup)
                hardware_target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_hardware, hardware_target)
                hardware_was_replaced = True

            for target, staged, existed in managed_targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged, target)
                applied_managed.append((target, existed))
            return ApplyResult(
                destination,
                added,
                modified,
                preserved,
                hardware_replaced=hardware_was_replaced,
            )
        except Exception:
            for target, existed in reversed(applied_managed):
                if existed:
                    relative = target.relative_to(destination)
                    backup = backup_files / relative
                    if backup.exists():
                        os.replace(backup, target)
                else:
                    target.unlink(missing_ok=True)
            if hardware_was_replaced:
                if hardware_target.exists():
                    self.policy.Tree_Remove(hardware_target)
                if hardware_backup is not None and hardware_backup.exists():
                    os.replace(hardware_backup, hardware_target)
            for target in reversed(copied_components):
                target.unlink(missing_ok=True)
            raise
        finally:
            if stage.exists():
                self.policy.Tree_Remove(stage)


def _Sha256_Is(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)
