from __future__ import annotations

import json
import os
import re
import zipfile
from pathlib import Path

from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.project.model import ProjectModel


class BoardPluginExportError(ValueError):
    pass


class BoardPluginExporter:
    """Export one trusted custom-hardware snapshot as declarative Board data."""

    _COMPONENT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")

    def __init__(self, policy: WorkspacePolicy) -> None:
        self.policy = policy

    def Plugin_Export(
        self,
        model: ProjectModel,
        snapshot_root: Path,
        output_path: Path,
        *,
        component_id: str,
        name: str,
        version: str | None = None,
    ) -> Path:
        if model.hardware.mode != "custom":
            raise BoardPluginExportError("Only imported custom hardware can be exported")
        if not self._COMPONENT_ID_PATTERN.fullmatch(component_id):
            raise BoardPluginExportError("Invalid Board component id")
        if not name.strip():
            raise BoardPluginExportError("Board name must not be empty")
        snapshot = self.policy.Path_Resolve(snapshot_root, allow_root=False)
        if not snapshot.is_dir():
            raise BoardPluginExportError("Custom hardware snapshot is unavailable")
        output = self.policy.Path_Resolve(output_path, allow_root=False)
        if output.suffix.casefold() != ".ssplugin":
            output = output.with_suffix(".ssplugin")
            output = self.policy.Path_Resolve(output, allow_root=False)
        manifest = self._Manifest_Get(
            model,
            component_id=component_id,
            name=name.strip(),
            version=version or model.identity.firmware_version,
        )
        stage = self.policy.StagingDirectory_Create("board-export-")
        staged_archive = stage / output.name
        try:
            with zipfile.ZipFile(
                staged_archive, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr(
                    "plugin.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                )
                archive.writestr(
                    "docs/HARDWARE_PROVENANCE.md",
                    self._Provenance_Render(model, name),
                )
                for source in sorted(snapshot.rglob("*")):
                    if source.is_symlink():
                        raise BoardPluginExportError(
                            "Hardware snapshot contains an unexpected symlink"
                        )
                    if not source.is_file():
                        continue
                    relative = source.relative_to(snapshot).as_posix()
                    archive.write(
                        source,
                        f"payload/HardwareGenerated/STM32CubeMX/{relative}",
                    )
            output.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_archive, output)
            return output
        finally:
            if stage.exists():
                self.policy.Tree_Remove(stage)

    @staticmethod
    def _Manifest_Get(
        model: ProjectModel, *, component_id: str, name: str, version: str
    ) -> dict:
        provisions = [
            {
                "id": resource.resource_id,
                "kind": resource.kind,
                "metadata": resource.metadata,
            }
            for resource in model.hardware.resources
        ]
        by_id = {
            resource.resource_id: resource for resource in model.hardware.resources
        }
        roles = []
        for key, selected in sorted(model.resource_assignments.items()):
            resource = by_id.get(selected)
            if resource is None:
                continue
            candidates = [
                candidate.resource_id
                for candidate in model.hardware.resources
                if candidate.kind == resource.kind
            ]
            roles.append(
                {
                    "key": key,
                    "kind": resource.kind,
                    "default": selected,
                    "candidates": candidates,
                    "fixed": False,
                }
            )
        platform_resources = BoardPluginExporter._PlatformResources_Get(model)
        capability_slug = component_id.replace("-", "_").replace(".", "_")
        return {
            "schema_version": 0,
            "id": component_id,
            "name": name,
            "type": "board",
            "class": "flight_controller_board",
            "version": version,
            "description": "Custom Board imported through the trusted STM32CubeMX provider.",
            "requires": {
                "components": [
                    {"id": model.core, "optional": False},
                    {"id": model.mcu, "optional": False},
                ],
                "resources": [],
                "capabilities": [],
            },
            "resources": {
                "provides": provisions,
                "roles": roles,
                "conflicts": [],
            },
            "provides": [
                f"board.{capability_slug}",
                "hardware.stm32.generated",
            ],
            "build": {
                "sources": list(model.hardware.build_sources),
                "asm_sources": list(model.hardware.asm_sources),
                "include_dirs": list(model.hardware.include_dirs),
                "defines": list(model.hardware.defines),
                "linker_script": model.hardware.linker_script,
            },
            "payload": {"roots": ["HardwareGenerated/STM32CubeMX"]},
            "metadata": {
                "display_names": {"zh_CN": f"{name}（自定义硬件）", "en_US": f"{name} (Custom)"},
                "platform_resources": platform_resources,
                "hardware_provenance": {
                    "provider": model.hardware.provider,
                    "source_kind": "manual_import",
                    "source_label": model.hardware.source_label,
                    "source_digest": model.hardware.source_digest,
                    "ioc_file": model.hardware.ioc_file,
                    "mcu": model.hardware.mcu,
                },
            },
            "board": {
                "source_kind": "manual_import",
                "compatible_mcus": [model.mcu],
                "vendor": "STM32",
                "provider": model.hardware.provider,
                "verified": False,
                "hardware_root": "HardwareGenerated/STM32CubeMX",
            },
        }

    @staticmethod
    def _PlatformResources_Get(model: ProjectModel) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {
            "uarts": [],
            "spis": [],
            "adcs": [],
            "gpios": [],
        }
        destinations = {
            "uart": "uarts",
            "spi": "spis",
            "adc": "adcs",
        }
        for resource in model.hardware.resources:
            metadata = resource.metadata
            destination = destinations.get(resource.kind)
            if destination and isinstance(metadata.get("handle"), str):
                result[destination].append(
                    {"id": resource.resource_id, "handle": metadata["handle"], **metadata}
                )
            elif resource.kind.startswith("gpio_") and isinstance(metadata.get("port"), str):
                result["gpios"].append(
                    {"id": resource.resource_id, **metadata}
                )
        return result

    @staticmethod
    def _Provenance_Render(model: ProjectModel, name: str) -> str:
        return f"""# {name} hardware provenance

- Source kind: `manual_import`
- Provider: `{model.hardware.provider}`
- MCU: `{model.hardware.mcu}`
- CubeMX input: `{model.hardware.source_label}/{model.hardware.ioc_file}`
- Source digest: `{model.hardware.source_digest}`

This package contains vendor-generated hardware data. It is not an official
SilverStar hardware verification claim. Validate clocks, DMA, interrupts,
GPIO electrical levels and power behavior on the target board.
"""
