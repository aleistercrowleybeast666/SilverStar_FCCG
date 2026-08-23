from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from silverstar_fccg.plugins.manifest import PluginManifest, PluginManifestError, PluginManifest_Load


class PluginCatalogError(ValueError):
    pass


class PluginCatalog:
    def __init__(self, builtin_root: Path, installed_root: Path) -> None:
        self.builtin_root = builtin_root.resolve()
        self.installed_root = installed_root.resolve()
        self._components: dict[str, PluginManifest] = {}

    def Scan(self) -> tuple[PluginManifest, ...]:
        manifests: dict[str, PluginManifest] = {}
        errors: list[str] = []
        for source, root in (("builtin", self.builtin_root), ("installed", self.installed_root)):
            if not root.exists():
                continue
            for path in sorted(root.rglob("plugin.json")):
                try:
                    manifest = PluginManifest_Load(path, source=source)
                except PluginManifestError as error:
                    errors.append(str(error))
                    continue
                previous = manifests.get(manifest.component_id)
                if previous is not None:
                    errors.append(
                        f"Duplicate component id {manifest.component_id}: "
                        f"{previous.manifest_path} and {manifest.manifest_path}"
                    )
                else:
                    manifests[manifest.component_id] = manifest
        if errors:
            raise PluginCatalogError("\n".join(errors))
        self._components = manifests
        return self.All_Get()

    def All_Get(self) -> tuple[PluginManifest, ...]:
        return tuple(self._components[key] for key in sorted(self._components))

    def Component_Get(self, component_id: str) -> PluginManifest:
        try:
            return self._components[component_id]
        except KeyError as error:
            raise PluginCatalogError(f"Unknown component: {component_id}") from error

    def Type_Get(self, component_type: str) -> tuple[PluginManifest, ...]:
        return tuple(
            component for component in self.All_Get() if component.component_type == component_type
        )

    def SelectionSlot_Get(self, slot: str) -> tuple[PluginManifest, ...]:
        return tuple(
            component
            for component in self.All_Get()
            if component.selection is not None and component.selection.slot == slot
        )

    def SelectionSlots_Get(self, kind: str) -> tuple[str, ...]:
        slots = {
            component.selection.slot
            for component in self.All_Get()
            if component.selection is not None
            and component.selection.kind.value == kind
        }
        return tuple(
            sorted(
                slots,
                key=lambda slot: min(
                    component.selection.ui_order
                    for component in self.SelectionSlot_Get(slot)
                    if component.selection is not None
                ),
            )
        )

    def ReferenceProvenance_Get(self) -> dict:
        path = self.builtin_root / "reference_provenance.json"
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PluginCatalogError(
                f"Invalid builtin reference provenance: {error}"
            ) from error
        if not isinstance(value, dict):
            raise PluginCatalogError("Builtin reference provenance must be an object")
        return value

    def DependencyErrors_Get(self, component_ids: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        selected = set(component_ids)
        errors: list[str] = []
        for component_id in sorted(selected):
            manifest = self._components.get(component_id)
            if manifest is None:
                errors.append(f"Missing selected component: {component_id}")
                continue
            for requirement in manifest.dependencies:
                if not requirement.optional and requirement.component_id not in selected:
                    errors.append(
                        f"{component_id} requires component {requirement.component_id}"
                    )
            available_capabilities = {
                capability
                for selected_id in selected
                if selected_id in self._components
                for capability in self._components[selected_id].provides
            }
            for capability in manifest.capabilities_required:
                if capability not in available_capabilities:
                    errors.append(f"{component_id} requires capability {capability}")
        return tuple(errors)

    def PathConflicts_Get(self, component_ids: tuple[str, ...] | list[str]) -> dict[str, tuple[str, ...]]:
        owners: defaultdict[str, list[str]] = defaultdict(list)
        for component_id in component_ids:
            manifest = self.Component_Get(component_id)
            for path in manifest.PayloadFiles_Get():
                relative = path.relative_to(manifest.payload_root).as_posix()
                owners[relative].append(component_id)
        return {
            path: tuple(component_owners)
            for path, component_owners in sorted(owners.items())
            if len(component_owners) > 1
        }
