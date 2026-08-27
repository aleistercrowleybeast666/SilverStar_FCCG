from __future__ import annotations

import json
import zlib
from typing import Any

from silverstar_fccg.project.model import ProjectModel


def ProjectGenerationState_Normalize(model: ProjectModel) -> dict[str, Any]:
    """Return the portable state that can change generated project output."""
    data = model.Dictionary_Get()
    data.pop("component_provenance", None)
    data.pop("reference_provenance", None)
    data.pop("log_decoder_profile", None)
    hardware = data["hardware"]
    hardware.pop("source_label", None)
    hardware.pop("risk_acknowledged", None)
    hardware.pop("assignment_fingerprint", None)
    build = data["build"]
    data["build"] = {
        "target_profile": build["target_profile"],
        "toolchain_prefix": build["toolchain_prefix"],
        "eide_mode": build["eide_mode"],
    }
    return data


def ProjectGenerationFingerprint_Get(model: ProjectModel) -> int:
    data = ProjectGenerationState_Normalize(model)
    canonical = json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return zlib.crc32(canonical.encode("utf-8")) & 0xFFFFFFFF


def ProjectDigest_Get(model: ProjectModel) -> int:
    """Compatibility name for the authoritative generation fingerprint."""
    return ProjectGenerationFingerprint_Get(model)
