"""Sync explicitly authorized test project copies, then run one gate lane."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from validate_joint_navigation import VARIANTS, Gates_Run  # noqa: E402

from silverstar_fccg.core.workspace import WorkspacePolicy  # noqa: E402

CORE = ROOT / "plugins/builtin/silverstar_core_0_0_12/payload"
ESKF = ROOT / "plugins/builtin/silverstar_algorithm_estimator_eskf15/payload"
COMMON = (
    "System/User/system_user_config.h", "System/Inc/system_navigation_health.h",
    "System/Src/system_navigation_health.c", "Tests/Host/test_navigation_quality_supervisor.c",
    "Tests/Host/run_tests.ps1", "Tools/check_architecture.ps1",
    "Tests/Host/test_telemetry.c",
    "Tests/Host/test_runtime_startup.c", "Tests/Host/test_source_selector.c",
    "Tests/Host/test_lifecycle.c",
    "Tests/Host/test_system_startup.c",
)
ESKF_FILES = ("Algorithm/Estimator/ESKF15/Src/navigation_eskf_replay.c",)


def Matrix_Run() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", nargs="*", choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument("--sync-only", action="store_true")
    args = parser.parse_args()
    policy = WorkspacePolicy(ROOT)
    matrix = policy.Path_Resolve("tests/joint_rework_20260927/verified_matrix")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    report_name = "FinalMatrix_" + stamp
    output = policy.Directory_Ensure("tests/joint_rework_20260927/" + report_name)
    rows = []
    for variant in args.variants:
        project = policy.Path_Resolve(matrix / variant, allow_root=False)
        if not project.is_relative_to(matrix) or not (project / "SilverStar.ssproject").is_file():
            raise ValueError("Only existing generated test projects may be synchronized")
        copied = []
        selected = [(CORE, relative) for relative in COMMON]
        if variant.startswith("eskf15"):
            selected += [(ESKF, relative) for relative in ESKF_FILES]
            selected += [(CORE, "Tests/Host/test_eskf_backend.c")]
        for source_root, relative in selected:
            source = policy.Path_Resolve(source_root / relative)
            destination = policy.Path_Resolve(project / relative, allow_root=False)
            old = destination.read_bytes() if destination.exists() else b""
            data = source.read_bytes()
            if data != old:
                if destination.exists():
                    policy.File_Copy(destination, output / variant / "previous_sources" / relative)
                # A changed source must become newer than any cached object;
                # copy2's preserved source mtime could otherwise miss a rebuild.
                policy.Bytes_AtomicWrite(destination, data)
            copied.append({"path": relative, "changed": old != data,
                           "sha256": hashlib.sha256(data).hexdigest()})
        # Keep existing failure details even where the Host runner replaces its local detail log.
        old_detail = project / "build/FCCG/Host/Tests/host-tests-detail.log"
        if old_detail.is_file():
            policy.File_Copy(old_detail, output / variant / "previous_host_detail.log")
        row = {"variant": variant, "synchronized": copied, "report_name": report_name}
        rows.append(row)
        policy.Text_AtomicWrite(output / "final_results.json", json.dumps(rows, indent=2) + "\n")
        print(json.dumps({"variant": variant, "phase": "synced", "report": str(output)}), flush=True)
        if args.sync_only:
            continue
        row["exit"] = Gates_Run(project, True, report_name=report_name, keep_going=True)
        report = project / "build/FCCG" / report_name
        row["gates"] = json.loads((report / "results.json").read_text(encoding="utf-8"))
        row["summaries"] = {}
        for gate in row["gates"]:
            text = (ROOT / gate["log"]).read_text(encoding="utf-8", errors="replace")
            row["summaries"][gate["gate"]] = [line for line in text.splitlines() if re.search(
                r"(?:FLASH|main SRAM|CCMRAM)\s+used=|architecture check passed|Power.of.Ten.*(?:pass|check)|"
                r"SilverStar host summary:|All SilverStar host tests passed|static analysis.*(?:pass|complete)",
                line, re.IGNORECASE)]
        policy.Text_AtomicWrite(output / "final_results.json", json.dumps(rows, indent=2) + "\n")
        print(json.dumps({"variant": variant, "exit": row["exit"], "summary": row["summaries"]}), flush=True)
    return int(any(row.get("exit", 0) != 0 for row in rows))


if __name__ == "__main__":
    raise SystemExit(Matrix_Run())
