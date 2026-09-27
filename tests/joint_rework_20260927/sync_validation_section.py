"""Refresh only this round's validation section; preserve historical text verbatim."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from silverstar_fccg.core.workspace import WorkspacePolicy

target = ROOT / "VALIDATION.md"
historical_marker = "# Validation — 2026-09-22 joint field-log contract"
current = target.read_text(encoding="utf-8")
assert current.count(historical_marker) == 1
history = current[current.index(historical_marker):]
draft = (ROOT / "tests/joint_rework_20260927/validation_section_draft.md").read_text(encoding="utf-8")
assert draft.startswith("# Validation — 2026-09-27")
WorkspacePolicy(ROOT).Text_AtomicWrite(target, draft.rstrip() + "\n\n" + history)
print("Updated this round; retained historical validation text.")
