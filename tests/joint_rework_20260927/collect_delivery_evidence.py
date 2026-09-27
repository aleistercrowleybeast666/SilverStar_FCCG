"""Copy exact small gate results; generated trees, executables and raw logs stay local."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from silverstar_fccg.core.workspace import WorkspacePolicy

policy = WorkspacePolicy(ROOT)
round_root = ROOT / "tests/joint_rework_20260927"
evidence = round_root / "evidence_final"
policy.Directory_Ensure(evidence)
copied = []
local_only = set()


def copy(source: Path, relative: str) -> None:
    if not source.is_file():
        return
    destination = evidence / relative
    original = source.read_bytes()
    lines = original.splitlines()
    wrapped = source.suffix == ".log" and (
        any(line.endswith((b" ", b"\t")) for line in lines)
        or (bool(lines) and lines[-1] == b"")
    )
    if wrapped:
        # Retain raw logs unchanged locally and commit a byte-reversible JSON
        # container, so whitespace checks need no exceptions or relaxed rules.
        local_only.add(destination)
        destination = destination.with_suffix(destination.suffix + ".json")
        container = {"encoding": "utf-8", "sha256": hashlib.sha256(original).hexdigest(),
                     "raw_utf8": original.decode("utf-8")}
        policy.Text_AtomicWrite(destination, json.dumps(container, ensure_ascii=False, indent=2) + "\n")
        restored = json.loads(destination.read_text(encoding="utf-8"))["raw_utf8"].encode("utf-8")
        assert restored == original
    else:
        policy.File_Copy(source, destination)
    copied.append({"source": source.relative_to(ROOT).as_posix(),
                   "committed": destination.relative_to(ROOT).as_posix(),
                   "storage": "lossless_utf8_json" if wrapped else "bytes",
                   "bytes": len(original),
                   "sha256": hashlib.sha256(original).hexdigest(),
                   "committed_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})


for project in sorted((round_root / "verified_matrix").iterdir()):
    if not project.is_dir():
        continue
    for report in sorted((project / "build/FCCG").glob("Final*")):
        if not report.is_dir():
            continue
        for source in report.glob("*"):
            if source.is_file() and source.suffix in (".log", ".json"):
                copy(source, f"matrix/{project.name}/{report.name}/{source.name}")
for report in sorted(round_root.glob("Final*")):
    if report.is_dir():
        for source in report.glob("*.json"):
            copy(source, f"matrix/{report.name}/{source.name}")
for name in (
    "fccg_delivery_product.log", "fccg_delivery_product.exit", "fccg_delivery_full.log",
    "fccg_delivery_final.log", "fccg_delivery_final.exit", "final_delta_fixture.log",
    "docs_delivery_final.log", "docs_delivery_final.exit",
    "body_cadence400.log", "body_cadence400_retry.log", "health_latch_final.log",
    "health_quality_aggregation_final.log", "size_probe.c", "size_probe.log",
    "backend-bridge-audit.json", "backend-bridge-hashes.json", "backend-bridge-source-match.json",
    "backend-bridge.log", "backend-bridge.exit", "final-matrix-run.log",
    "backend-bridge-final-refresh.log", "backend-bridge-final-refresh.exit",
    "backend-bridge-final-audit.json", "backend-bridge-final-audit.exit",
    "backend-bridge-final-hashes.json", "backend-bridge-final-difference.json",
    "final-delta-run.log", "final-delta-run.exit",
    "eskf-flight-storage-final.log", "eskf-flight-storage-final.exit",
    "eskf-test-storage-final.log", "eskf-test-storage-final.exit",
    "catalog-negative-result.json", "indicator-binding-final.log",
    "architecture-logging-final.log", "architecture-enabled-final.log",
):
    copy(round_root / name, name)
copy(round_root / "body_cadence400_retry/test_actual_app_400hz_samples_0/generated/build/FCCG/Host/BodyCadence/run.log",
     "body_cadence400_c_run.log")
for source in (round_root / "package_delivery").glob("*"):
    if source.is_file() and source.suffix in (".json", ".log", ".png"):
        copy(source, "package/" + source.name)
copy(round_root / "backend_bridge_test/ActualBackendLoggerBridgeTest.ssdecoder", "bridge/ActualBackendLoggerBridgeTest.ssdecoder")
copy(round_root / "backend_bridge_test/build/FCCG/Host/BackendBridge/source_hashes.json", "bridge/source_hashes.json")
for source in (round_root / "sensors/navigation_review").glob("*"):
    if source.is_file() and source.suffix in (".log", ".json", ".txt", ".c"):
        copy(source, "navigation_review/" + source.name)
timing_manifest = round_root / "timing_bench_evidence.json"
if timing_manifest.is_file():
    timing = json.loads(timing_manifest.read_text(encoding="utf-8"))
    for item in timing["files"]:
        source = ROOT / item["path"]
        assert source.resolve().is_relative_to(round_root.resolve())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == item["sha256"]
        copy(source, "timing/" + source.relative_to(round_root).as_posix())
    copy(timing_manifest, "timing/evidence.json")
    for name in ("timing_bench_validation.log", "timing_bench_validation.exit",
                 "timing_bench_validation2.log", "timing_bench_validation2.exit"):
        copy(round_root / name, "timing/" + name)
policy.Text_AtomicWrite(evidence / "copied_evidence.json", json.dumps(copied, indent=2))
files = [path.relative_to(ROOT).as_posix() for path in evidence.rglob("*")
         if path.is_file() and path not in local_only]
policy.Text_AtomicWrite(round_root / "local_only_evidence_paths.json",
                        json.dumps(sorted(path.relative_to(ROOT).as_posix() for path in local_only), indent=2))
for name in ("collect_delivery_evidence.py", "prepare_commit_plan.py", "verify_delivery_python.py",
             "run_health_quality_final.py", "run_final_matrix.py", "run_final_delta.py",
             "run_backend_bridge.py", "package_smoke.py", "package_delivery.py",
             "sync_validation_section.py", "validation_section_draft.md",
             "audit_delivery_evidence.py"):
    if (round_root / name).is_file():
        files.append((round_root / name).relative_to(ROOT).as_posix())
policy.Text_AtomicWrite(round_root / "COMMIT_EVIDENCE_LIST.txt", "\n".join(sorted(set(files))) + "\n")
print(json.dumps({"files": len(set(files)), "bytes": sum((ROOT / path).stat().st_size for path in set(files))}))
