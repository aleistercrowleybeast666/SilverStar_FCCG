"""Final maintained-source checks, with all generated outputs under tests."""
from __future__ import annotations

import compileall
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "tests/joint_rework_20260927/evidence_final"
OUTPUT.mkdir(exist_ok=True)
os.chdir(ROOT)
sys.pycache_prefix = str(ROOT / "tests/joint_rework_20260927/pycache_delivery")


def git(*arguments: str) -> list[str]:
    return subprocess.check_output(["git", *arguments], text=True, encoding="utf-8").splitlines()


changed = set(git("diff", "--name-only", "HEAD"))
changed.update(git("ls-files", "--others", "--exclude-standard", "--", "src", "tools", "plugins"))
tracked_tests = set(git("ls-files", "--", "tests/*.py"))
changed.update(path.relative_to(ROOT).as_posix() for path in (ROOT / "tests").glob("*.py")
               if path.relative_to(ROOT).as_posix() not in tracked_tests)
lint_paths = sorted(path for path in changed if path.endswith(".py") and (ROOT / path).is_file())
command = ["D:/python_software/SilverStar_FLP/.venv/Scripts/python.exe", "-m", "ruff", "check",
           "--select", "E4,E7,E9,F,I", *lint_paths]
lint = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
(OUTPUT / "ruff_delivery.log").write_text(lint.stdout + lint.stderr, encoding="utf-8")
python_paths = sorted(set((ROOT / "src").rglob("*.py")) | set((ROOT / "tools").rglob("*.py")) |
                      set((ROOT / "tests").glob("*.py")))
compiled = all(compileall.compile_file(str(path), force=True, quiet=1) for path in python_paths)
json_paths = sorted(set((ROOT / "schemas").rglob("*.json")) | set((ROOT / "plugins/builtin").rglob("*.json")) |
                    set((ROOT / "src").rglob("*.json")) | set((ROOT / "docs/contracts").rglob("*.json")))
for path in json_paths:
    json.loads(path.read_text(encoding="utf-8"))
diff = subprocess.run(["git", "diff", "--check"], capture_output=True, text=True, encoding="utf-8")
(OUTPUT / "diff_delivery.log").write_text(diff.stdout + diff.stderr, encoding="utf-8")
summary = {"ruff_exit": lint.returncode, "ruff_command": command, "lint_paths": lint_paths,
           "compileall": compiled, "compiled_file_count": len(python_paths),
           "json_count": len(json_paths), "json_pass": True, "diff_exit": diff.returncode}
(OUTPUT / "python_checks.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key not in ("ruff_command", "lint_paths")}, indent=2))
raise SystemExit(int(lint.returncode != 0 or not compiled or diff.returncode != 0))
