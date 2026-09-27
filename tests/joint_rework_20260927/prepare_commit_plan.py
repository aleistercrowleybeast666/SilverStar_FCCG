"""Inventory only the three products and explicit compact evidence for review."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

BASE = Path("D:/python_software")
OUTPUT = BASE / "SilverStar_FCCG/tests/joint_rework_20260927"
BASELINES = {
    "SilverStar_FCCG": "d013ae10924a308e95478445f91c370601871f19",
    "SilverStar_FLP": "c4605f458c50b8a718b0cf6c3cc9d0da8aba8cc0",
    "SilverStar_GSHC": "cbee51e1f259d56a8e9dcdb7c3b236f9b054e4fb",
}


def read_git(root: Path, *arguments: str) -> list[str]:
    result = subprocess.run(["git", *arguments], cwd=root, capture_output=True,
                            encoding="utf-8", check=True)
    return result.stdout.splitlines()


plans = []
for name in ("SilverStar_FCCG", "SilverStar_FLP", "SilverStar_GSHC"):
    root = BASE / name
    # Inventory the entire round, including a sibling already committed locally.
    # Initial tracked trees were clean; unrelated temporary trees stay excluded.
    tracked = set(read_git(root, "diff", "--name-only", BASELINES[name]))
    extra = set(read_git(root, "ls-files", "--others", "--exclude-standard", "--",
                         "src", "tools", "docs", "schemas", "plugins", "tests/fixtures",
                         "ui", "services", "protocol", "processing", "transport"))
    known_top_tests = set(read_git(root, "ls-files", "--", "tests/*.py"))
    extra.update(path.relative_to(root).as_posix() for path in (root / "tests").glob("*.py")
                 if path.relative_to(root).as_posix() not in known_top_tests)
    for report in ("JOINT_REWORK_REPORT.md",):
        if (root / report).is_file():
            extra.add(report)
    evidence_lists = [root / "tests/joint_rework_20260927/COMMIT_EVIDENCE_LIST.txt"]
    if name == "SilverStar_FCCG":
        evidence_lists.append(root / "tests/joint_rework_20260927/sensors/COMMIT_EVIDENCE_LIST.txt")
    missing_lists = []
    for manifest in evidence_lists:
        if not manifest.is_file():
            missing_lists.append(str(manifest.relative_to(root)))
            continue
        extra.add(manifest.relative_to(root).as_posix())
        extra.update(line.strip() for line in manifest.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.startswith("#"))
    files = sorted(tracked | extra)
    for name_part in files:
        resolved = (root / name_part).resolve()
        assert resolved.is_relative_to(root) and resolved.is_file(), name_part
        assert resolved.suffix.lower() not in {".bin", ".exe", ".o", ".elf", ".npz", ".zip", ".whl", ".pyc"}, name_part
        assert resolved.stat().st_size < 10_000_000, name_part
    size = sum((root / relative).stat().st_size for relative in files)
    plan = {"repo": root.name, "files": files, "file_count": len(files), "bytes": size,
            "missing_lists": missing_lists}
    plans.append(plan)
    print(json.dumps({key: value for key, value in plan.items() if key != "files"}))
(OUTPUT / "commit_plan.json").write_text(json.dumps(plans, indent=2), encoding="utf-8")
