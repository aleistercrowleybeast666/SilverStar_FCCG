"""Actual backend + NONE calibration + FlightTask snapshots + LoggerTask byte writer.

Existing generated metadata is refreshed through the product service; copied
project-owned C is preserved. Only clock/device inputs and the Host file sink
are fixtures; no success/status/descriptor/record payload is fabricated.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from silverstar_fccg.app.service import FccgService
from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.project.logging import LoggingProfile_SelectAllAvailable

root = Path(__file__).resolve().parents[2]
project = root / "tests/joint_rework_20260927/backend_bridge_test"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--refresh-sources", action="store_true",
                    help="Synchronize the explicitly reviewed final test-project source deltas")
options = parser.parse_args()
policy = WorkspacePolicy(root)
output = project / "build/FCCG/Host/BackendBridge"
if options.refresh_sources:
    if not (project / "SilverStar.ssproject").is_file():
        raise ValueError("Source refresh requires the existing generated bridge test project")
    archive = output / ("previous_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f"))
    for saved in (output / "actual_backend_logger.BIN", project / "ActualBackendLoggerBridgeTest.ssdecoder"):
        if saved.is_file():
            policy.File_Copy(saved, archive / saved.name)
    for owner, paths in (
        ("silverstar_core_0_0_12", ("System/User/system_user_config.h", "System/Inc/system_navigation_health.h",
                                  "System/Src/system_navigation_health.c", "APP/Src/logger_bus.c",
                                  "Tools/check_architecture.ps1")),
        ("silverstar_algorithm_estimator_eskf15", ("Algorithm/Estimator/ESKF15/Src/navigation_eskf_replay.c",)),
    ):
        for relative in paths:
            policy.File_Copy(root / "plugins/builtin" / owner / "payload" / relative, project / relative)
service = FccgService(root)
if not project.exists():
    model = service.ReferenceProject_Create("ActualBackendLoggerBridgeTest")
    model.strategies["estimator"] = "silverstar.algorithm.estimator.eskf15"
    model = service.ProjectConfiguration_Reconcile(model).model
    LoggingProfile_SelectAllAvailable(model, service.catalog)
    model = service.ProjectConfiguration_Reconcile(model).model
else:
    model = service.Project_Open(project)
    model = service.ProjectConfiguration_Reconcile(model).model
service.Project_Save(model, project, confirm_dangerous=True)
policy.Directory_Ensure(output)
fixture = root / "plugins/builtin/silverstar_core_0_0_12/payload/Tests/Host/test_eskf_backend.c"
includes = re.findall(r'"-I\$repoRoot\\([^"\n]+)"', (project / "Tests/Host/run_tests.ps1").read_text())
sources = ["Tests/Host/host_platform_mock.c", "Algorithm/Estimator/ESKF15/Src/navigation_eskf.c",
    "Algorithm/Estimator/ESKF15/Src/navigation_eskf_replay.c", "Algorithm/Estimator/ESKF15/Src/navigation_eskf_backend.c",
    "Algorithm/Common/Src/navigation_quality.c", "Algorithm/Common/Src/geodesy_local.c", "APP/Src/estimator_bus.c",
    "APP/Src/logger_bus.c", "System/Src/system_navigation_health.c", "System/Src/system_time.c", "System/Src/system_log_policy.c",
    "System/Src/system_gnss_quality.c", "System/Src/system_navigation_profile.c", "System/Src/system_estimator_profile.c",
    "System/Src/system_profile.c", "System/Calibration/Src/system_calibration.c", "Common/Src/common_spsc_queue.c",
    "Common/Src/silverstar_assert.c", "Generated/Src/project_metadata.c", "Generated/Src/project_log_decoder_profile.c",
    "Generated/Src/project_log_config.c", "Protocol/SSLOG/Src/sslog_protocol.c", "Protocol/SSLOG/Src/sslog_records.c"]
binary = output / "backend_bridge.exe"
command = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic", "-flto",
    "-DTEST_ESKF_BACKEND_EXPORT=1",
    "-ffunction-sections", "-fdata-sections", "-DSYSTEM_BUILD_ESTIMATOR_ENABLED=0U",
    "-DSYSTEM_BUILD_ESKF15_ENABLED=1U", "-DSYSTEM_BUILD_FUSION_ALGORITHM=SYSTEM_FUSION_ESKF15",
    "-include", str(project / "Generated/Inc/project_flight_config.h")]
command += ["-I" + str(project / path.replace("\\", "/")) for path in includes]
command += ["-I" + str(project / "Algorithm/Estimator/ESKF15/Inc"), str(fixture)]
command += [str(project / path) for path in sources] + ["-Wl,--gc-sections", "-lm", "-o", str(binary)]
compiled_files = [fixture, root / "plugins/builtin/silverstar_core_0_0_12/payload/APP/Src/flight_task.c",
                  root / "plugins/builtin/silverstar_core_0_0_12/payload/APP/Src/logger_task.c"]
compiled_files += [project / path for path in sources]
policy.Text_AtomicWrite(output / "source_hashes.json", json.dumps([
    {"path": str(path.relative_to(root)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for path in compiled_files], indent=2) + "\n")
environment = dict(os.environ, TEMP=str(output), TMP=str(output), PYTHONDONTWRITEBYTECODE="1")
result = subprocess.run(command, cwd=project, env=environment, text=True, capture_output=True)
(output / "compile.log").write_text(result.stdout + result.stderr, encoding="utf-8")
print("compile", result.returncode, flush=True)
if result.returncode:
    print(result.stdout + result.stderr, flush=True)
    raise SystemExit(result.returncode)
result = subprocess.run([str(binary), str(output / "actual_backend_logger.BIN")], cwd=project, env=environment,
                        text=True, capture_output=True)
(output / "run.log").write_text(result.stdout + result.stderr, encoding="utf-8")
print(result.stdout + result.stderr, flush=True)
raise SystemExit(result.returncode)
