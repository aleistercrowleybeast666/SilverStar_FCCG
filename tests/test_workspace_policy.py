from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import silverstar_fccg.core.workspace as workspace_module
from silverstar_fccg.core.workspace import (
    WorkspacePolicy,
    WorkspacePolicyError,
    _WindowsDirectoryInheritance_Enable,
)


def test_workspace_policy_rejects_escape_and_unsafe_portable_paths(tmp_path: Path) -> None:
    policy = WorkspacePolicy(tmp_path)
    assert policy.Path_Resolve("inside/file.txt") == (tmp_path / "inside/file.txt").resolve()
    with pytest.raises(WorkspacePolicyError):
        policy.Path_Resolve("../outside.txt")
    with pytest.raises(WorkspacePolicyError):
        policy.Path_Resolve(tmp_path.parent / "outside.txt")
    for value in (
        "../escape",
        "/absolute",
        "C:/drive",
        "a\\b",
        "NUL.txt",
        "trailing.",
        "control\nname",
        "alternate:stream",
        "a/./b",
        "a//b",
    ):
        with pytest.raises(WorkspacePolicyError):
            policy.RelativePath_Validate(value)


def test_workspace_staging_and_atomic_write_remain_inside_root(tmp_path: Path) -> None:
    policy = WorkspacePolicy(tmp_path)
    staging = policy.StagingDirectory_Create("test-")
    assert staging.is_relative_to(tmp_path.resolve())
    path = policy.Text_AtomicWrite("state/value.txt", "stable\n")
    assert path.read_text(encoding="utf-8") == "stable\n"


def test_windows_staging_permission_fix_enables_parent_inheritance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def run_stub(
        arguments: list[str], **options: object
    ) -> subprocess.CompletedProcess[str]:
        captured["arguments"] = arguments
        captured["options"] = options
        return subprocess.CompletedProcess(arguments, 0, "processed", "")

    monkeypatch.setattr(workspace_module.subprocess, "run", run_stub)
    staging = tmp_path / "staging"
    _WindowsDirectoryInheritance_Enable(staging)

    assert captured["arguments"] == [
        "icacls",
        str(staging),
        "/inheritance:e",
    ]
    options = captured["options"]
    assert isinstance(options, dict)
    assert options["check"] is False
    assert options["capture_output"] is True


def test_windows_staging_permission_fix_reports_icacls_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def run_stub(
        arguments: list[str], **_options: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(arguments, 5, "", "access denied")

    monkeypatch.setattr(workspace_module.subprocess, "run", run_stub)
    with pytest.raises(WorkspacePolicyError, match="access denied"):
        _WindowsDirectoryInheritance_Enable(tmp_path / "staging")
