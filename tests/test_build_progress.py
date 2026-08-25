from __future__ import annotations

from pathlib import Path

from silverstar_fccg.build.runner import (
    BuildAction,
    BuildProgress,
    BuildRunner,
)
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.project.model import ProjectModel_Save
from silverstar_fccg.project.reference import ReferenceProject_Create


def _BuildRoot_Create(tmp_path: Path):
    root = tmp_path / "BuildProgress"
    root.mkdir()
    model = ReferenceProject_Create("BuildProgress")
    policy = WorkspacePolicy(root)
    ProjectModel_Save(model, root / "SilverStar.ssproject", policy)
    (root / "Makefile").write_text(
        "# SilverStar authoritative build entry\n.PHONY: all\nall:\n\t@echo ok\n",
        encoding="utf-8",
    )
    return root, model, BuildRunner(policy)


def test_validation_build_uses_release_without_project_state(
    tmp_path: Path,
) -> None:
    _root, model, runner = _BuildRoot_Create(tmp_path)

    command = runner.Command_Get(model, BuildAction.BUILD)

    assert "CONFIG=Release" in command
    assert command[-1] == "all"
    assert "configuration" not in model.Dictionary_Get()["build"]


def test_dry_run_plans_incremental_steps_and_streams_live_progress(
    tmp_path: Path, monkeypatch
) -> None:
    root, model, runner = _BuildRoot_Create(tmp_path)
    calls: list[tuple[str, ...]] = []
    dry_lines = [
        'echo "FCCG_PROGRESS|COMPILE|APP/Src/one.c"\n',
        'echo "FCCG_PROGRESS|LINK|build/app.elf"\n',
        'echo "FCCG_PROGRESS|SIZE|build/app.elf"\n',
        'echo "FCCG_PROGRESS|HEX|build/app.hex"\n',
        'echo "FCCG_PROGRESS|BIN|build/app.bin"\n',
    ]
    actual_lines = [
        "FCCG_PROGRESS|COMPILE|APP/Src/one.c\n",
        "compiler output\n",
        "FCCG_PROGRESS|LINK|build/app.elf\n",
        "FCCG_PROGRESS|SIZE|build/app.elf\n",
        "FCCG_PROGRESS|HEX|build/app.hex\n",
        "FCCG_PROGRESS|BIN|build/app.bin\n",
    ]

    def process_run(command, _root, _environment, _token, line_callback=None):
        calls.append(tuple(command))
        lines = dry_lines if "-n" in command else actual_lines
        if line_callback is not None:
            for line in lines:
                line_callback(line)
        return 0, list(lines)

    monkeypatch.setattr(BuildRunner, "_Process_Run", staticmethod(process_run))
    live_lines: list[str] = []
    progress: list[BuildProgress] = []

    result = runner.Run(
        model,
        root,
        BuildAction.BUILD,
        line_callback=live_lines.append,
        progress_callback=progress.append,
    )

    assert result.succeeded
    assert result.plan.total_steps == 5
    assert result.plan.compile_steps == 1
    assert result.completed_steps == 5
    assert calls[0][1] == "-n"
    assert live_lines == ["compiler output"]
    assert progress[0].stage == "PLAN"
    assert [item.stage for item in progress[1:-1]] == [
        "COMPILE",
        "LINK",
        "SIZE",
        "HEX",
        "BIN",
    ]
    assert progress[-1].stage == "COMPLETE"
    assert progress[-1].completed_steps == progress[-1].total_steps == 5
