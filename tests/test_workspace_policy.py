from __future__ import annotations

from pathlib import Path

import pytest

from silverstar_fccg.core.workspace import WorkspacePolicy, WorkspacePolicyError


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
