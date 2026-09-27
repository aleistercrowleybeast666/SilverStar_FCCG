"""Export and stage the final local source package without accessing hardware."""
import hashlib
import json
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from silverstar_fccg.app.source_export import SourcePackage_Export
from silverstar_fccg.core.workspace import WorkspacePolicy

output = ROOT / "tests/joint_rework_20260927/package_delivery"
policy = WorkspacePolicy(ROOT)
policy.Directory_Ensure(output)
result = SourcePackage_Export(ROOT, output / "SilverStar_FCCG-source.zip")
staged = ROOT / "tests/.pkg28"
policy.Directory_Ensure(staged)
staging_policy = WorkspacePolicy(staged)
with zipfile.ZipFile(result.destination) as archive:
    for entry in archive.infolist():
        relative = Path(entry.filename).relative_to("SilverStar_FCCG").as_posix()
        if not entry.is_dir():
            staging_policy.RelativePath_Validate(relative)
            staging_policy.Bytes_AtomicWrite(relative, archive.read(entry))
    assert "SilverStar_FCCG/tests/fixtures/sensors/test_bmi088_sync.c" in archive.namelist()
    assert not any("joint_rework_20260927/" in name for name in archive.namelist())
metadata = asdict(result)
metadata["destination"] = str(result.destination)
metadata["sha256"] = hashlib.sha256(result.destination.read_bytes()).hexdigest()
metadata["staged"] = str(staged)
policy.Text_AtomicWrite(output / "export.json", json.dumps(metadata, indent=2))
print(json.dumps(metadata, indent=2))
