"""Run final production deltas through all ARM gates and affected real Host fixtures.

This complements, and never replaces, the preserved six full Host/storage runs.
It does not modify a gate, capacity, fixture assertion, or generated selection.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone

from run_final_matrix import CORE, ESKF, ESKF_FILES, ROOT
from validate_joint_navigation import VARIANTS, Gates_Run

from silverstar_fccg.core.workspace import WorkspacePolicy

KF6 = ROOT / "plugins/builtin/silverstar_algorithm_estimator_kf6/payload"
COMMON = ("System/Src/system_navigation_health.c", "APP/Src/estimator_task.c",
          "Tests/Host/test_navigation_quality_supervisor.c", "Tests/Host/test_estimator_preparation.c")
MOCK = "Tests/Host/host_platform_mock.c"
ASSERT = "Common/Src/silverstar_assert.c"
HEALTH = ["Tests/Host/test_navigation_quality_supervisor.c", MOCK,
          "Algorithm/Common/Src/navigation_quality.c", "System/Src/system_navigation_health.c"]
PREPARATION = ["Tests/Host/test_estimator_preparation.c", MOCK, "APP/Src/ins_task.c",
    "APP/Src/estimator_bus.c", "APP/Src/estimator_barometer_pending.c", "Algorithm/Common/Src/attitude_frame.c",
    "Algorithm/Common/Src/geodesy_local.c", "Algorithm/Common/Src/navigation_quality.c",
    "Algorithm/INS/Coning2Sculling2/Src/ins_mechanization.c", "System/Src/system_estimator_diagnostics.c",
    "System/Src/system_estimator_profile.c", "System/Src/system_navigation_profile.c",
    "System/Src/system_navigation_health.c", "System/Src/system_gnss_quality.c", "System/Src/system_barometer.c"]
LTO = ["-flto", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections"]
KF_SOURCES = ["Algorithm/Estimator/KF6/Src/" + name + ".c"
              for name in ("navigation_kf", "navigation_kf_replay", "navigation_integrity")]
ESKF_SOURCES = ["Algorithm/Estimator/ESKF15/Src/" + name + ".c"
                for name in ("navigation_eskf", "navigation_eskf_replay", "navigation_eskf_backend")]


def HostDelta_Run(project, report):
    runner = (project / "Tests/Host/run_tests.ps1").read_text(encoding="utf-8")
    includes = re.findall(r'"-I\$repoRoot\\([^"\n]+)"', runner)
    include_args = ["-include", str(project / "Generated/Inc/project_flight_config.h")]
    include_args += ["-I" + str(project / path.replace("\\", "/")) for path in includes]
    graph = (project / "Generated/project_sources.mk").read_text(encoding="utf-8")
    definitions = {}
    for name in ("SYSTEM_BUILD_ESTIMATOR_ENABLED", "SYSTEM_BUILD_FUSION_ALGORITHM"):
        matches = re.findall(r"(?m)^\s*" + name + r"=([A-Z0-9_]+)\s*(?:\\)?\s*$", graph)
        if len(matches) != 1:
            raise ValueError(f"{project.name}: expected one selected {name}")
        definitions[name] = matches[0]
    fusion = definitions["SYSTEM_BUILD_FUSION_ALGORITHM"]
    prep_args = LTO + ["-DSILVERSTAR_PROTOCOL_LOGGING_ENABLED=0U"]
    prep_args += ["-D" + name + "=" + value for name, value in definitions.items()]
    prep_sources = list(PREPARATION)
    jobs = [("navigation_quality_supervisor", HEALTH, [])]
    if fusion == "SYSTEM_FUSION_KF6":
        prep_sources += KF_SOURCES
        jobs += [("air_kf", ["Tests/Host/test_air_kf.c", "Protocol/Src/air_protocol.c", KF_SOURCES[0],
                              "Algorithm/Common/Src/attitude_frame.c", "System/Src/system_estimator_profile.c"], []),
                 ("navigation_kf_replay", ["Tests/Host/test_navigation_kf_replay.c", *KF_SOURCES[:2],
                                           "System/Src/system_time.c"], [])]
    elif fusion == "SYSTEM_FUSION_ESKF15":
        prep_sources += ESKF_SOURCES + ["System/Calibration/Src/system_calibration.c"]
        prep_args += ["-DSYSTEM_BUILD_ESKF15_ENABLED=1U", "-I" + str(project / "Algorithm/Estimator/ESKF15/Inc")]
        if project.name != "eskf15_no_logging":
            backend = [MOCK, "APP/Src/logger_bus.c", "Common/Src/common_spsc_queue.c",
                "System/Src/system_log_policy.c", "System/Src/system_profile.c",
                "System/Src/system_navigation_profile.c", "System/Src/system_estimator_profile.c",
                "Generated/Src/project_metadata.c", "Generated/Src/project_log_decoder_profile.c",
                "Generated/Src/project_log_config.c", "Protocol/SSLOG/Src/sslog_protocol.c",
                "Protocol/SSLOG/Src/sslog_records.c", "Tests/Host/test_eskf_backend.c", *ESKF_SOURCES,
                "Algorithm/Common/Src/geodesy_local.c", "Algorithm/Common/Src/navigation_quality.c",
                "APP/Src/estimator_bus.c", "System/Src/system_navigation_health.c",
                "System/Src/system_gnss_quality.c", "System/Src/system_time.c",
                "System/Calibration/Src/system_calibration.c"]
            jobs.append(("eskf_backend_actual", backend, LTO + ["-DSYSTEM_BUILD_ESTIMATOR_ENABLED=0U",
                "-DSYSTEM_BUILD_ESKF15_ENABLED=1U", "-DSYSTEM_BUILD_FUSION_ALGORITHM=SYSTEM_FUSION_ESKF15",
                "-I" + str(project / "Algorithm/Estimator/ESKF15/Inc")]))
    jobs.append(("estimator_preparation_actual", prep_sources, prep_args))
    results = []
    environment = dict(os.environ, TEMP=str(report), TMP=str(report), PYTHONDONTWRITEBYTECODE="1")
    environment["PATH"] = "D:/msys64/ucrt64/bin" + os.pathsep + environment.get("PATH", "")
    for name in ("GCC_EXEC_PREFIX", "COMPILER_PATH", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH",
                 "OBJC_INCLUDE_PATH", "LIBRARY_PATH", "DEPENDENCIES_OUTPUT", "SUNPRO_DEPENDENCIES"):
        environment.pop(name, None)
    for name, sources, extra in jobs:
        executable = report / (name + ".exe")
        command = ["D:/msys64/ucrt64/bin/gcc.exe", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-O2"]
        command += extra + include_args + [str(project / path) for path in sources + [ASSERT]]
        command += ["-lm", "-o", str(executable)]
        compiled = subprocess.run(command, cwd=project, env=environment, capture_output=True, text=True)
        log = "COMMAND " + json.dumps(command) + "\n" + compiled.stdout + compiled.stderr
        code = compiled.returncode
        if code == 0:
            run = subprocess.run([str(executable)], cwd=project, env=environment, capture_output=True, text=True)
            log += run.stdout + run.stderr
            code = run.returncode
        (report / (name + ".log")).write_text(log, encoding="utf-8")
        counts = re.findall(r": (\d+) checks, (\d+) failures", log)
        if code == 0 and (len(counts) != 1 or int(counts[0][1]) != 0):
            code = 1
        results.append({"name": name, "exit": code, "counts": counts,
                        "log": str((report / (name + ".log")).relative_to(ROOT))})
        print(json.dumps(results[-1]), flush=True)
    return results


def Delta_Run():
    policy = WorkspacePolicy(ROOT)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    report_name = "FinalDelta_" + stamp
    output = policy.Directory_Ensure("tests/joint_rework_20260927/" + report_name)
    rows = []
    for variant in VARIANTS:
        project = policy.Path_Resolve(ROOT / "tests/joint_rework_20260927/verified_matrix" / variant, allow_root=False)
        if not (project / "SilverStar.ssproject").is_file():
            raise ValueError("Only an existing test project may be updated")
        selected = [(CORE, path) for path in COMMON]
        if variant.startswith("kf6"):
            selected += [(KF6, KF_SOURCES[0]), (CORE, "Tests/Host/test_air_kf.c")]
        elif variant.startswith("eskf15"):
            selected += [(ESKF, path) for path in ESKF_FILES]
        changes = []
        for owner, relative in selected:
            destination = project / relative
            before, final = destination.read_bytes(), (owner / relative).read_bytes()
            if before != final:
                policy.File_Copy(destination, output / variant / "previous_sources" / relative)
                policy.Bytes_AtomicWrite(destination, final)
            changes.append({"path": relative, "changed": before != final,
                            "sha256": hashlib.sha256(final).hexdigest()})
        row = {"variant": variant, "source_sync": changes, "report_name": report_name}
        rows.append(row)
        print(json.dumps({"variant": variant, "phase": "sync", "report": str(output)}), flush=True)
        row["gates_exit"] = Gates_Run(project, False, report_name=report_name, keep_going=True)
        report = policy.Directory_Ensure(project / "build/FCCG" / report_name)
        row["gates"] = json.loads((report / "results.json").read_text(encoding="utf-8"))
        row["host_delta"] = HostDelta_Run(project, report)
        policy.Text_AtomicWrite(output / "final_results.json", json.dumps(rows, indent=2) + "\n")
    return int(any(row["gates_exit"] or any(test["exit"] for test in row["host_delta"]) for row in rows))


if __name__ == "__main__":
    raise SystemExit(Delta_Run())
