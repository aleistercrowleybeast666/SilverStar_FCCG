from __future__ import annotations

import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import silverstar_fccg.generator.assembler as assembler_module
from silverstar_fccg.app.service import FccgService
from silverstar_fccg.build.runner import BuildAction, BuildResult, BuildRunner
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.project.lifecycle import ProjectLifecycleState
from silverstar_fccg.project.logging import (
    LogPolicyLevel,
    ProtocolLogDefinitions_Get,
)
from silverstar_fccg.project.model import ProjectModel_Load


def test_first_save_materializes_a_ready_dry_runnable_project(
    tmp_path: Path, workspace_root: Path
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "LifecycleProject"
    model = service.ReferenceProject_Create("LifecycleProject")

    assert service.ProjectReadiness_Get(model, project_root).state == (
        ProjectLifecycleState.DRAFT
    )

    service.Project_Save(model, project_root)

    readiness = service.ProjectReadiness_Get(model, project_root)
    assert readiness.state == ProjectLifecycleState.READY
    assert not readiness.missing
    assert not readiness.stale
    for relative in (
        "SilverStar.ssproject",
        "Makefile",
        ".fccg/hardware-preparation.json",
        ".fccg/ownership.json",
        ".eide/eide.yml",
        ".vscode/tasks.json",
        "LifecycleProject.code-workspace",
        "Flight_Controller0.5.ioc",
        "startup_stm32f407xx.s",
        "STM32F407XX_FLASH.ld",
    ):
        assert (project_root / relative).is_file(), relative
    for relative in ("BuildSystem", "Generated", "Targets/SilverStar_F407"):
        assert (project_root / relative).is_dir(), relative
    for relative in ("Core", "Drivers", "FATFS"):
        assert (project_root / relative).is_dir(), relative
    assert not (project_root / "HardwareGenerated").exists()

    make = shutil.which(model.build.make_command)
    if make is None:
        pytest.skip(f"{model.build.make_command} is not available")
    dry_run = subprocess.run(
        (
            make,
            "-C",
            str(project_root),
            "-n",
            f"TARGET_PROFILE={model.build.target_profile}",
            "CONFIG=Debug",
            "all",
        ),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert dry_run.returncode == 0, dry_run.stdout + dry_run.stderr
    makefile_text = (project_root / "Makefile").read_text(encoding="utf-8")
    assert "CONFIG ?= Debug" in makefile_text
    assert "DEBUG_FLAGS := -g" in makefile_text
    assert "FCCG_PROGRESS|COMPILE|$<" in makefile_text
    assert "FCCG_PROGRESS|LINK|$@" in makefile_text


def test_readiness_detects_and_save_restores_a_missing_managed_file(
    tmp_path: Path, workspace_root: Path
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "ManagedReadiness"
    model = service.ReferenceProject_Create("ManagedReadiness")
    service.Project_Save(model, project_root)

    managed_file = project_root / ".vscode" / "settings.json"
    managed_file.unlink()
    readiness = service.ProjectReadiness_Get(model, project_root)
    assert readiness.state == ProjectLifecycleState.DIRTY
    assert ".vscode/settings.json" in readiness.missing

    service.Project_Save(model, project_root)
    assert managed_file.is_file()
    assert service.ProjectReadiness_Get(model, project_root).ready


def test_save_refreshes_managed_output_after_renderer_change(
    tmp_path: Path, workspace_root: Path, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "RendererRefresh"
    model = service.ReferenceProject_Create("RendererRefresh")
    service.Project_Save(model, project_root)
    settings_path = project_root / ".vscode" / "settings.json"
    original_settings = settings_path.read_bytes()
    original_renderer = assembler_module.MetadataFiles_Render

    def MetadataFiles_RenderChanged(*args, **kwargs):
        rendered = original_renderer(*args, **kwargs)
        rendered[".vscode/settings.json"] += b"\n"
        return rendered

    monkeypatch.setattr(
        assembler_module,
        "MetadataFiles_Render",
        MetadataFiles_RenderChanged,
    )

    result = service.Project_Save(model, project_root)

    assert result.files_modified >= 2
    assert settings_path.read_bytes() == original_settings + b"\n"
    assert service.ProjectReadiness_Get(model, project_root).ready


def test_verified_board_preparation_is_idempotent(
    tmp_path: Path, workspace_root: Path, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "PreparedBoard"
    model = service.ReferenceProject_Create("PreparedBoard")
    monkeypatch.setattr(
        type(service.hardware_importer),
        "Project_Import",
        lambda *_args, **_kwargs: pytest.fail(
            "verified Board preparation must not invoke CubeMX import/generation"
        ),
    )

    first = service.Project_HardwarePrepare(model, project_root)
    marker = project_root / ".fccg" / "hardware-preparation.json"
    marker_content = marker.read_bytes()
    second = service.Project_HardwarePrepare(model, project_root)

    assert first.files_added > 0
    assert second.files_added == 0
    assert second.files_modified == 0
    assert marker.read_bytes() == marker_content
    assert service.Project_HardwarePrepared_Is(model, project_root)


def test_first_save_publishes_project_descriptor_last(
    tmp_path: Path, workspace_root: Path, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "DescriptorLast"
    model = service.ReferenceProject_Create("DescriptorLast")
    published: list[Path] = []
    original_replace = assembler_module.os.replace

    def path_replace(source, destination) -> None:
        target = Path(destination)
        if target.parent == project_root:
            published.append(target)
        original_replace(source, destination)

    monkeypatch.setattr(assembler_module.os, "replace", path_replace)
    service.Project_Save(model, project_root)

    assert published
    assert published[-1] == project_root / "SilverStar.ssproject"
    assert service.ProjectReadiness_Get(model, project_root).ready


def test_build_auto_saves_dirty_mode_and_logging_configuration(
    tmp_path: Path, workspace_root: Path, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "BuildAutoSave"
    model = service.ReferenceProject_Create("BuildAutoSave")
    service.Project_Save(model, project_root)

    model.modes["deployment"] = ["ApogeeVerticalVelocity", "Tilt"]
    definitions = {
        definition.record: definition
        for definition in ProtocolLogDefinitions_Get(model, service.catalog)
    }
    optional = next(
        stream
        for stream in model.logging_streams
        if definitions[stream.record].level != LogPolicyLevel.REQUIRED
    )
    model.logging_streams = [
        replace(stream, enabled=False) if stream.record == optional.record else stream
        for stream in model.logging_streams
    ]

    def build_run(
        _runner: BuildRunner,
        current_model,
        current_root: Path,
        action: BuildAction,
        _token=None,
    ) -> BuildResult:
        saved = ProjectModel_Load(current_root / "SilverStar.ssproject")
        assert saved.modes["deployment"] == ["ApogeeVerticalVelocity", "Tilt"]
        assert not next(
            stream
            for stream in saved.logging_streams
            if stream.record == optional.record
        ).enabled
        assert service.ProjectReadiness_Get(current_model, current_root).ready
        return BuildResult(action, ("test-make", action.MakeTarget_Get()), 0, "ok\n")

    monkeypatch.setattr(BuildRunner, "Run", build_run)
    result = service.Build_Run(model, project_root, BuildAction.BUILD)
    assert result.succeeded


def test_all_advanced_actions_use_ensure_buildable_and_project_root(
    tmp_path: Path, workspace_root: Path, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "AdvancedActions"
    model = service.ReferenceProject_Create("AdvancedActions")
    service.Project_Save(model, project_root)
    actions = (
        BuildAction.HOST_TESTS,
        BuildAction.ARCHITECTURE_CHECK,
        BuildAction.POWER10_CHECK,
        BuildAction.STATIC_ANALYSIS,
        BuildAction.ARTIFACT_CHECK,
    )
    ensure_calls: list[Path] = []
    run_calls: list[tuple[Path, BuildAction]] = []
    original_ensure = service.Project_EnsureBuildable

    def ensure_buildable(current_model, current_root: Path, **kwargs):
        ensure_calls.append(current_root.resolve())
        return original_ensure(current_model, current_root, **kwargs)

    def build_run(
        _runner: BuildRunner,
        _model,
        current_root: Path,
        action: BuildAction,
        _token=None,
    ) -> BuildResult:
        run_calls.append((current_root.resolve(), action))
        return BuildResult(action, ("test-make", action.MakeTarget_Get()), 0, "ok\n")

    monkeypatch.setattr(service, "Project_EnsureBuildable", ensure_buildable)
    monkeypatch.setattr(BuildRunner, "Run", build_run)
    for action in actions:
        assert service.Build_Run(model, project_root, action).succeeded

    assert ensure_calls == [project_root.resolve()] * len(actions)
    assert run_calls == [(project_root.resolve(), action) for action in actions]
    makefile = (project_root / "Makefile").read_text(encoding="utf-8")
    assert "artifact-check: all" in makefile


def test_build_runner_starts_make_with_explicit_project_cwd(
    tmp_path: Path, workspace_root: Path, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "RunnerCwd"
    model = service.ReferenceProject_Create("RunnerCwd")
    service.Project_Save(model, project_root)
    calls: list[tuple[tuple[str, ...], Path]] = []

    class FakeStdout:
        def __init__(self) -> None:
            self._lines = iter(("checked\n", ""))

        def readline(self) -> str:
            return next(self._lines)

    class FakeProcess:
        def __init__(self) -> None:
            self.stdout = FakeStdout()

        def poll(self) -> int:
            return 0

        def wait(self) -> int:
            return 0

        def terminate(self) -> None:
            raise AssertionError("completed fake process must not be terminated")

    def process_start(command, **kwargs):
        calls.append((tuple(command), Path(kwargs["cwd"])))
        return FakeProcess()

    monkeypatch.setattr(subprocess, "Popen", process_start)
    runner = BuildRunner(WorkspacePolicy(project_root))
    for action in (
        BuildAction.HOST_TESTS,
        BuildAction.ARCHITECTURE_CHECK,
        BuildAction.POWER10_CHECK,
        BuildAction.STATIC_ANALYSIS,
        BuildAction.ARTIFACT_CHECK,
    ):
        assert runner.Run(model, project_root, action).succeeded

    assert [command[-1] for command, _root in calls] == [
        "host-tests",
        "architecture-check",
        "power10-check",
        "static-analysis",
        "artifact-check",
    ]
    assert all(root == project_root.resolve() for _command, root in calls)


def test_debug_and_release_commands_use_distinct_safe_make_configuration(
    tmp_path: Path, workspace_root: Path
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "BuildConfigurations"
    debug_model = service.ReferenceProject_Create("BuildConfigurations")
    service.Project_Save(debug_model, project_root)
    runner = BuildRunner(WorkspacePolicy(project_root))

    debug_command = runner.Command_Get(debug_model, BuildAction.BUILD)
    release_command = runner.Command_Get(debug_model, BuildAction.BUILD_RELEASE)
    assert "CONFIG=Debug" in debug_command
    assert "CONFIG=Release" in release_command
    assert debug_command != release_command

    makefile = (project_root / "Makefile").read_text(encoding="utf-8")
    assert "OPT := -Og" in makefile
    assert "DEBUG_FLAGS := -g3 -gdwarf-2" in makefile
    assert "OPT := -O2" in makefile
    assert "CONFIG must be Debug or Release" in makefile
    assert "NDEBUG" not in makefile
