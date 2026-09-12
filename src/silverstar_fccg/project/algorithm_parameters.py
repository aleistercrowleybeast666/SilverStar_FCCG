from __future__ import annotations

from typing import Any

from silverstar_fccg.plugins.algorithm_parameters import PARAMETER_SCHEMA_ID
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import PluginManifest
from silverstar_fccg.project.model import ProjectModel


def AlgorithmParameterOwners_Get(model: ProjectModel, catalog: PluginCatalog) -> tuple[PluginManifest, ...]:
    return tuple(manifest for component in model.ComponentIds_Get()
                 if (manifest := catalog.Component_Get(component)).algorithm_parameters)


def AlgorithmParameters_Reconcile(model: ProjectModel, catalog: PluginCatalog) -> None:
    owners = AlgorithmParameterOwners_Get(model, catalog)
    # Removed algorithms are pruned. Unknown fields within a retained algorithm
    # remain visible to validation; never silently discard stale configuration.
    model.algorithm_parameters = {
        owner.component_id: {
            **{p.parameter_id: p.default for p in owner.algorithm_parameters},
            **model.algorithm_parameters.get(owner.component_id, {}),
        } for owner in owners
    }


def AlgorithmParameters_Resolve(model: ProjectModel, catalog: PluginCatalog) -> list[dict[str, Any]]:
    owners = AlgorithmParameterOwners_Get(model, catalog)
    if set(model.algorithm_parameters) != {m.component_id for m in owners}:
        raise ValueError("Algorithm parameter owners are missing or stale")
    symbols: set[str] = set()
    result = []
    for owner in owners:
        definitions = owner.algorithm_parameters
        values = model.algorithm_parameters[owner.component_id]
        if set(values) != {p.parameter_id for p in definitions}:
            raise ValueError(f"{owner.component_id}: missing or unknown algorithm parameter")
        resolved = {p.parameter_id: p.Value_Resolve(values[p.parameter_id]) for p in definitions}
        parameters = []
        for parameter in definitions:
            if parameter.generated_symbol in symbols:
                raise ValueError("Conflicting algorithm parameter generated symbols")
            symbols.add(parameter.generated_symbol)
            if parameter.greater_than and resolved[parameter.parameter_id] <= resolved[parameter.greater_than]:
                raise ValueError(f"{parameter.parameter_id} must exceed {parameter.greater_than} in target precision")
            parameters.append({"id": parameter.parameter_id, "value": resolved[parameter.parameter_id],
                               "unit": parameter.unit, "representation": parameter.representation,
                               "storage_type": "float32" if parameter.value_type == "float" else "int32",
                               "description": parameter.description["en_US"]})
        result.append({"component": owner.component_id, "schema_id": PARAMETER_SCHEMA_ID,
                       "manifest_sha256": owner.ManifestSha256_Get(), "parameters": parameters})
    return result


def AlgorithmParametersHeader_Render(model: ProjectModel, catalog: PluginCatalog) -> str:
    resolved = {r["component"]: {p["id"]: p["value"] for p in r["parameters"]}
                for r in AlgorithmParameters_Resolve(model, catalog)}
    rows = ["#ifndef __PROJECT_ALGORITHM_PARAMETERS_H", "#define __PROJECT_ALGORITHM_PARAMETERS_H",
            "", "/* Generated actual values. Binary32 constants; no runtime parsing. */"]
    for owner in AlgorithmParameterOwners_Get(model, catalog):
        for parameter in owner.algorithm_parameters:
            value = resolved[owner.component_id][parameter.parameter_id]
            literal = f"{value:.9e}f" if parameter.value_type == "float" else str(value)
            # Existing override convention is retained for explicit Host fixtures.
            rows.extend((f"#ifndef {parameter.generated_symbol}",
                         f"#define {parameter.generated_symbol} {literal}", "#endif"))
    return "\n".join((*rows, "", "#endif /* __PROJECT_ALGORITHM_PARAMETERS_H */", ""))
