"""Verify byte-preserving evidence storage and immutable shared inputs."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from silverstar_fccg.core.workspace import WorkspacePolicy

EVIDENCE = ROOT / "tests/joint_rework_20260927/evidence_final"
entries = json.loads((EVIDENCE / "copied_evidence.json").read_text(encoding="utf-8"))
wrapped = 0
for entry in entries:
    source = (ROOT / entry["source"]).resolve()
    stored = (ROOT / entry["committed"]).resolve()
    assert source.is_relative_to(ROOT) and stored.is_relative_to(EVIDENCE)
    original = source.read_bytes()
    payload = stored.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == entry["committed_sha256"]
    if entry["storage"] == "lossless_utf8_json":
        container = json.loads(payload.decode("utf-8"))
        payload = container["raw_utf8"].encode(container["encoding"])
        assert container["sha256"] == entry["sha256"]
        wrapped += 1
    assert payload == original and len(payload) == entry["bytes"]
    assert hashlib.sha256(payload).hexdigest() == entry["sha256"]

inputs = json.loads((EVIDENCE / "original_inputs_final.json").read_text(encoding="utf-8"))
for entry in inputs:
    assert hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest() == entry["sha256"]

contracts = []
for repository in ("SilverStar_FCCG", "SilverStar_FLP", "SilverStar_GSHC"):
    path = ROOT.parent / repository / "docs/contracts/navigation_v1.json"
    contracts.append(hashlib.sha256(path.read_bytes()).hexdigest())
assert len(set(contracts)) == 1
result = {"evidence_entries": len(entries), "lossless_log_containers": wrapped,
          "all_evidence_byte_exact": True, "immutable_original_inputs": len(inputs),
          "shared_contract_sha256": contracts[0], "passed": True}
WorkspacePolicy(ROOT).Text_AtomicWrite(EVIDENCE / "delivery_audit.json", json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
