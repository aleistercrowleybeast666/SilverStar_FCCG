"""Instrument the real Host fixture, retaining a compact hash of every operation.

The fixture zero-initializes its contexts/events, including padding. Pointer-valued
storage identity is deliberately excluded; all stored KF/history bytes are included.
Only test code writes trace files. No instrumentation enters generated runtime code.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


TRACE_WRAPPERS = r'''
static FILE *s_trace;
static uint64_t TestTrace_Hash(uint64_t hash, const void *data, size_t size)
{
    const unsigned char *bytes = data;
    size_t i;
    for (i = 0; i < size; i++) { hash = (hash ^ bytes[i]) * UINT64_C(1099511628211); }
    return hash;
}
static void TestTrace_Record(NavigationReplayContext *h, NavigationKfContext *s,
                             NavigationReplayOutcome *o, int result)
{
    uint64_t hash = UINT64_C(14695981039346656037);
    if (h != NULL)
    {
        size_t offset = offsetof(NavigationReplayContext, events);
        hash = TestTrace_Hash(hash, (const unsigned char *)h + offset, sizeof(*h) - offset);
        if (h->storage != NULL) { hash = TestTrace_Hash(hash, h->storage, sizeof(*h->storage)); }
    }
    if (s != NULL) { hash = TestTrace_Hash(hash, s, sizeof(*s)); }
    if (o != NULL) { hash = TestTrace_Hash(hash, o, sizeof(*o)); }
    (void)fwrite(&result, sizeof(result), 1, s_trace);
    (void)fwrite(&hash, sizeof(hash), 1, s_trace);
}
static NavigationReplayResult TestTrace_Predict(NavigationReplayContext *h,
    NavigationKfContext *s, uint64_t t, const float *d, float dt)
{
    NavigationReplayResult r = NavigationReplay_Predict(h, s, t, d, dt);
    TestTrace_Record(h, s, NULL, (int)r);
    return r;
}
static NavigationReplayResult TestTrace_Insert(NavigationReplayContext *h,
    NavigationKfContext *s, const NavigationReplayEvent *e, NavigationReplayOutcome *o)
{
    NavigationReplayResult r = NavigationReplay_Insert(h, s, e, o);
    TestTrace_Record(h, s, o, (int)r);
    return r;
}
static NavigationReplayResult TestTrace_Receive(NavigationReplayContext *h,
    const NavigationKfGnssEpoch *e, NavigationReplayEvent *out)
{
    NavigationReplayResult r = NavigationReplay_ReceiveTrack(h, e, out);
    TestTrace_Record(h, NULL, NULL, (int)r);
    return r;
}
#define NavigationReplay_Predict TestTrace_Predict
#define NavigationReplay_Insert TestTrace_Insert
#define NavigationReplay_ReceiveTrack TestTrace_Receive
'''


def replay_trace_run(project: Path, output: Path, fixture: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    source = fixture.read_text(encoding="utf-8")
    marker = "static NavigationReplayContext s_reference_history;"
    source = source.replace(marker, "#include <stddef.h>\n" + TRACE_WRAPPERS + "\n" + marker)
    head, main = source.split("int main(void)", 1)
    names = []
    def instrument(match):
        call = match.group(0)
        name = re.sub(r"[^A-Za-z0-9_]", "", call)
        names.append(name)
        return f's_trace = fopen("{name}.trace", "wb");\n    if (s_trace == NULL) {{ return 2; }}\n    {call}\n    (void)fclose(s_trace);'
    main = re.sub(r"Test_(?!Finish)[A-Za-z0-9_]+\([^;\n]*\);", instrument, main)
    instrumented = output / "replay_trace.c"
    instrumented.write_text(head + "int main(void)" + main, encoding="utf-8")
    script = (project / "Tests/Host/run_tests.ps1").read_text(encoding="utf-8")
    includes = re.findall(r'"-I\$repoRoot\\([^"\n]+)"', script)
    command = ["D:/msys64/ucrt64/bin/gcc.exe", "-std=c11", "-Wall", "-Wextra",
               "-Werror", "-pedantic", "-O2", "-include",
               str(project / "Generated/Inc/project_flight_config.h")]
    command += ["-I" + str(project / p.replace("\\", "/")) for p in includes]
    command += [str(project / p) for p in (
        "Algorithm/Estimator/KF6/Src/navigation_kf.c",
        "Algorithm/Estimator/KF6/Src/navigation_kf_replay.c",
        "System/Src/system_time.c", "Common/Src/silverstar_assert.c")]
    command += [str(instrumented), "-lm", "-o", str(output / "trace.exe")]
    env = dict(os.environ, TEMP=str(output), TMP=str(output))
    env["PATH"] = "D:/msys64/ucrt64/bin;" + env.get("PATH", "")
    built = subprocess.run(command, env=env, capture_output=True, text=True)
    (output / "compile.log").write_text(built.stdout + built.stderr, encoding="utf-8")
    assert built.returncode == 0, built.stderr
    run = subprocess.run([str(output / "trace.exe")], cwd=output, env=env, capture_output=True, text=True)
    (output / "result.log").write_text(run.stdout + run.stderr, encoding="utf-8")
    assert run.returncode == 0, run.stdout + run.stderr
    traces = {}
    for name in names:
        data = (output / (name + ".trace")).read_bytes()
        assert data and len(data) % 12 == 0
        traces[name] = {"operations": len(data) // 12, "sha256": hashlib.sha256(data).hexdigest()}
    (output / "traces.json").write_text(json.dumps(traces, indent=2) + "\n", encoding="utf-8")
    return traces


def replay_work_limit_run(project: Path, output: Path, fixture: Path) -> str:
    """Inject budget exhaustion in a test-only source copy; production stays 560.

    Valid histories cannot naturally exceed that conservative bound. A one-step
    budget exercises the existing public transactional failure path on both the
    original and refactored engines without modifying their storage or math.
    """
    output.mkdir(parents=True, exist_ok=True)
    engine = project / "Algorithm/Estimator/KF6/Src/navigation_kf_replay.c"
    injected = output / "replay_budget_fault.c"
    source = engine.read_text(encoding="utf-8")
    assert source.count("> NAV_REPLAY_MAX_STEPS") == 2
    injected.write_text(source.replace("> NAV_REPLAY_MAX_STEPS", "> 1U"), encoding="utf-8")
    script = (project / "Tests/Host/run_tests.ps1").read_text(encoding="utf-8")
    includes = re.findall(r'"-I\$repoRoot\\([^"\n]+)"', script)
    command = ["D:/msys64/ucrt64/bin/gcc.exe", "-std=c11", "-Wall", "-Wextra", "-Werror",
               "-pedantic", "-O2", "-include", str(project / "Generated/Inc/project_flight_config.h")]
    command += ["-I" + str(project / p.replace("\\", "/")) for p in includes]
    command += [str(project / p) for p in (
        "Algorithm/Estimator/KF6/Src/navigation_kf.c", "Common/Src/silverstar_assert.c")]
    command += [str(injected), str(fixture), "-lm", "-o", str(output / "work-limit.exe")]
    env = dict(os.environ, TEMP=str(output), TMP=str(output))
    env["PATH"] = "D:/msys64/ucrt64/bin;" + env.get("PATH", "")
    built = subprocess.run(command, env=env, capture_output=True, text=True)
    assert built.returncode == 0, built.stderr
    result = subprocess.run([str(output / "work-limit.exe")], env=env, capture_output=True, text=True)
    (output / "result.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def estimator_trace_run(project: Path, output: Path, fixture: Path) -> dict:
    """Compile the actual App GNSS dispatch functions, not a rewritten model."""
    output.mkdir(parents=True, exist_ok=True)
    app = (project / "APP/Src/estimator_task.c").read_text(encoding="utf-8")
    type_end = app.index("} EstimatorGnssUpdateWork;") + len("} EstimatorGnssUpdateWork;")
    type_start = app.rfind("typedef struct", 0, type_end)
    start = app.index("static SystemMeasurementTimeResult Estimator_MeasurementTimeResolve(")
    end = app.index("static void Estimator_GnssUpdate(", start)
    source = '''#include <math.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include "navigation_kf_replay.h"
#include "system_user_config.h"
#include "system_gnss_if.h"
#include "sslog_protocol.h"
#include "silverstar_assert.h"
#include "system_time.h"
#include "platform_time.h"
#include "platform_critical.h"
PlatformResult PlatformTime_Init(void) { return PLATFORM_OK; }
uint64_t PlatformTime_Us(void) { return 0ULL; }
PlatformCriticalState PlatformCritical_Enter(void) { return 0U; }
void PlatformCritical_Exit(PlatformCriticalState state) { (void)state; }
static struct { NavigationKfContext kf; } s_estimator;
static struct { float position_innovation[3]; } s_snapshot;
static NavigationReplayContext s_replay;
'''
    source += app[type_start:type_end] + "\n" + app[start:end] + fixture.read_text(encoding="utf-8")
    instrumented = output / "app_trace.c"
    instrumented.write_text(source, encoding="utf-8")
    script = (project / "Tests/Host/run_tests.ps1").read_text(encoding="utf-8")
    includes = re.findall(r'"-I\$repoRoot\\([^"\n]+)"', script)
    command = ["D:/msys64/ucrt64/bin/gcc.exe", "-std=c11", "-Wall", "-Wextra", "-Werror",
               "-pedantic", "-O2", "-include", str(project / "Generated/Inc/project_flight_config.h")]
    command += ["-I" + str(project / p.replace("\\", "/")) for p in includes]
    command += [str(project / p) for p in (
        "Algorithm/Estimator/KF6/Src/navigation_kf.c", "Algorithm/Estimator/KF6/Src/navigation_kf_replay.c",
        "System/Src/system_time.c", "Common/Src/silverstar_assert.c")]
    command += [str(instrumented), "-lm", "-o", str(output / "app.exe")]
    env = dict(os.environ, TEMP=str(output), TMP=str(output))
    env["PATH"] = "D:/msys64/ucrt64/bin;" + env.get("PATH", "")
    traces = {}
    for pos, vel in ((0, 270), (270, 0), (0, 0), (100, 100)):
        build = command + [f"-DSYSTEM_ESTIMATOR_GNSS_POSITION_MEASUREMENT_DELAY_MS={pos}",
                           f"-DSYSTEM_ESTIMATOR_GNSS_VELOCITY_MEASUREMENT_DELAY_MS={vel}"]
        result = subprocess.run(build, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        result = subprocess.run([str(output / "app.exe")], env=env, capture_output=True)
        assert result.returncode == 0, result.stderr
        (output / f"app-{pos}-{vel}.trace").write_bytes(result.stdout)
        traces[f"{pos}/{vel}"] = hashlib.sha256(result.stdout).hexdigest()
    return traces
