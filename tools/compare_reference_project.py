from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


DEFAULT_REFERENCE = Path(r"C:\Users\chdxm\Desktop\stm32-1\Flight_Controller0.5")
DEFAULT_GENERATED = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "generated_projects"
    / "SilverStar_F407_Reference_Generated"
)
INTENTIONAL_ADAPTATIONS = {"Tools/check_architecture.ps1"}


def _MakeOutput_Get(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["mingw32-make", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def _SourceSet_Get(root: Path) -> tuple[set[str], set[str]]:
    output = _MakeOutput_Get(
        root, "-s", "TARGET_PROFILE=SilverStar_F407", "CONFIG=Debug", "list-sources"
    )
    c_sources: set[str] = set()
    asm_sources: set[str] = set()
    for line in output.splitlines():
        value = line.strip().replace("\\", "/")
        if value.endswith(".c"):
            c_sources.add(value)
        elif value.startswith("Assembly:"):
            asm_sources.update(
                item.replace("\\", "/")
                for item in value.removeprefix("Assembly:").split()
                if item.endswith(".s")
            )
    return c_sources, asm_sources


def _MakeVariables_Get(root: Path) -> dict[str, tuple[str, ...]]:
    output = _MakeOutput_Get(
        root, "-pn", "TARGET_PROFILE=SilverStar_F407", "CONFIG=Debug"
    )
    names = {
        "C_INCLUDES",
        "C_DEFS",
        "TARGET_MCU_FLAGS",
        "TARGET_LDSCRIPT",
        "TARGET_SPECS",
        "TARGET_LIBS",
        "TOOLCHAIN_PREFIX",
    }
    values: dict[str, tuple[str, ...]] = {}
    for line in output.splitlines():
        match = re.match(r"^([A-Z_]+)\s*:?=\s*(.*)$", line)
        if match and match.group(1) in names:
            values[match.group(1)] = tuple(match.group(2).split())
    return values


def _ResourceDefines_Get(root: Path) -> dict[str, str]:
    path = root / "Generated" / "Inc" / "project_resources.h"
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#define\s+(PROJECT_RESOURCE_[A-Z0-9_]+)\s+(.+?)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _LogRows_Get(root: Path) -> tuple[tuple[str, str, str, str, str], ...]:
    text = (root / "Generated" / "Src" / "project_log_config.c").read_text(
        encoding="utf-8"
    )
    pattern = re.compile(
        r"\{(FLIGHT_LOG_RECORD_[A-Z0-9_]+),\s*([01]U),\s*([0-9]+U),\s*"
        r"([0-9]+UL),\s*SSLOG_STREAM_POLICY_([A-Z_]+)\}",
        re.MULTILINE,
    )
    return tuple(pattern.findall(text))


def Project_Compare(reference: Path, generated: Path) -> dict:
    reference = reference.resolve()
    generated = generated.resolve()
    reference_sources, reference_asm = _SourceSet_Get(reference)
    generated_sources, generated_asm = _SourceSet_Get(generated)
    reference_vars = _MakeVariables_Get(reference)
    generated_vars = _MakeVariables_Get(generated)
    variable_comparison = {
        name: set(reference_vars.get(name, ())) == set(generated_vars.get(name, ()))
        for name in sorted(set(reference_vars) | set(generated_vars))
    }
    ownership = json.loads(
        (generated / ".fccg" / "ownership.json").read_text(encoding="utf-8")
    )
    copied_count = 0
    copied_mismatches: list[str] = []
    missing_reference: list[str] = []
    for component in ownership["components"].values():
        for relative in component["files"]:
            copied_count += 1
            if relative in INTENTIONAL_ADAPTATIONS:
                continue
            source = reference.joinpath(*relative.split("/"))
            target = generated.joinpath(*relative.split("/"))
            if not source.is_file():
                missing_reference.append(relative)
            elif source.read_bytes() != target.read_bytes():
                copied_mismatches.append(relative)
    report = {
        "reference": str(reference),
        "generated": str(generated),
        "c_sources": {
            "reference_count": len(reference_sources),
            "generated_count": len(generated_sources),
            "missing": sorted(reference_sources - generated_sources),
            "extra": sorted(generated_sources - reference_sources),
            "equal": reference_sources == generated_sources,
        },
        "asm_sources_equal": reference_asm == generated_asm,
        "build_variables_equal": variable_comparison,
        "resource_mapping_equal": _ResourceDefines_Get(reference)
        == _ResourceDefines_Get(generated),
        "log_policy_equal": _LogRows_Get(reference) == _LogRows_Get(generated),
        "component_files_checked": copied_count,
        "component_file_mismatches": copied_mismatches,
        "component_files_without_reference": missing_reference,
        "intentional_adaptations": sorted(INTENTIONAL_ADAPTATIONS),
    }
    report["equivalent"] = all(
        (
            report["c_sources"]["equal"],
            report["asm_sources_equal"],
            all(variable_comparison.values()),
            report["resource_mapping_equal"],
            report["log_policy_equal"],
            not copied_mismatches,
            not missing_reference,
        )
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only functional comparison of reference and FCCG-generated firmware"
    )
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--generated", type=Path, default=DEFAULT_GENERATED)
    options = parser.parse_args()
    report = Project_Compare(options.reference, options.generated)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["equivalent"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
