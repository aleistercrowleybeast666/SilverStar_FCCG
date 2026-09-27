"""Execute final production health/window sources and permanent Host fixture."""
import os
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
project = root / "tests/joint_rework_20260927/verified_matrix/kf6_flight"
core = root / "plugins/builtin/silverstar_core_0_0_12/payload"
common = root / "plugins/builtin/silverstar_algorithm_common/payload"
output = project / "build/FCCG/Host/QualityAggregationFinal"
output.mkdir(parents=True, exist_ok=True)
runner = (project / "Tests/Host/run_tests.ps1").read_text(encoding="utf-8")
includes = re.findall(r'"-I\$repoRoot\\([^"\n]+)"', runner)
command = ["D:/msys64/ucrt64/bin/gcc.exe", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
           "-include", str(project / "Generated/Inc/project_flight_config.h")]
command += ["-I" + str(project / path.replace("\\", "/")) for path in includes]
command += [str(core / path) for path in ("Tests/Host/test_navigation_quality_supervisor.c",
            "Tests/Host/host_platform_mock.c", "System/Src/system_navigation_health.c", "Common/Src/silverstar_assert.c")]
command += [str(common / "Algorithm/Common/Src/navigation_quality.c"), "-lm", "-o", str(output / "health.exe")]
environment = dict(os.environ, TEMP=str(output), TMP=str(output))
for step in (command, [str(output / "health.exe")]):
    result = subprocess.run(step, capture_output=True, text=True, env=environment)
    print(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)
