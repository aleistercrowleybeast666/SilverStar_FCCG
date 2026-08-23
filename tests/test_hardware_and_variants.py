from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath

import pytest

from silverstar_fccg.core.workspace import WorkspacePolicy
from silverstar_fccg.generator.assembler import ProjectAssembler
from silverstar_fccg.generator.render import (
    ComponentProvenance_Get,
    GeneratedFiles_Render,
    MetadataFiles_Render,
)
from silverstar_fccg.generator.source_graph import SourceGraph_Resolve
from silverstar_fccg.hardware import (
    BoardPluginExporter,
    CubeMxImportError,
    CubeMxImporter,
)
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.installer import PluginInstaller
from silverstar_fccg.project.model import HardwareConfiguration
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.resources import ResourceAssignments_Resolve
from silverstar_fccg.project.validation import Project_Validate


def _Catalog_Create(workspace_root: Path, installed_root: Path) -> PluginCatalog:
    catalog = PluginCatalog(workspace_root / "plugins" / "builtin", installed_root)
    catalog.Scan()
    return catalog


def _TopLevelYamlList_Get(text: str, key: str) -> tuple[str, ...]:
    lines = text.splitlines()
    start = lines.index(f"{key}:") + 1
    values: list[str] = []
    for line in lines[start:]:
        if not line.startswith("  - "):
            break
        values.append(line[4:])
    return tuple(values)


def test_estimator_none_is_absent_from_make_and_eide(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("NoEstimator")
    model.strategies["estimator"] = None
    validation = Project_Validate(model, builtin_catalog)
    assert validation.valid

    graph = SourceGraph_Resolve(model, builtin_catalog)
    assert not any("Algorithm/Estimator/KF6" in source for source in graph.sources)
    assert "SYSTEM_BUILD_FUSION_ALGORITHM=SYSTEM_FUSION_NONE" in graph.defines
    assert "SYSTEM_BUILD_ESTIMATOR_ENABLED=0U" in graph.defines

    make_graph = graph.MakeFragment_Render()
    eide = MetadataFiles_Render(model, builtin_catalog, graph)[
        ".eide/eide.yml"
    ].decode("utf-8")
    assert "Algorithm/Estimator/KF6" not in make_graph
    assert "Algorithm/Estimator/KF6" not in eide
    assert "SYSTEM_FUSION_NONE" in make_graph
    assert "SYSTEM_FUSION_NONE" in eide


def test_environment_plugin_renders_one_resolved_source_graph(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("EnvironmentTruth")
    graph = SourceGraph_Resolve(model, builtin_catalog)
    metadata = MetadataFiles_Render(model, builtin_catalog, graph)
    expected_outputs = {
        "EnvironmentTruth.code-workspace",
        ".vscode/tasks.json",
        ".vscode/settings.json",
        ".vscode/extensions.json",
        ".eide/eide.yml",
        "Makefile",
        "Targets/SilverStar_F407/target.mk",
    }
    assert expected_outputs.issubset(metadata)

    eide = metadata[".eide/eide.yml"].decode("utf-8")
    actual_source_dirs = _TopLevelYamlList_Get(eide, "srcDirs")
    expected_source_dirs = tuple(
        dict.fromkeys(
            PurePosixPath(source).parent.as_posix()
            for source in graph.sources
            if source not in graph.virtual_sources
        )
    )
    assert actual_source_dirs == expected_source_dirs
    assert "srcDirs: []" not in eide
    assert "outDir: build\\EIDE\\SilverStar_F407" in eide
    assert "mingw32-make" in metadata[".vscode/tasks.json"].decode("utf-8")
    for source in graph.sources:
        assert source in graph.MakeFragment_Render()


def test_same_mcu_supports_two_board_resource_maps(workspace_root: Path) -> None:
    catalog = PluginCatalog(
        workspace_root / "plugins" / "builtin",
        workspace_root / "tests" / "fixtures" / "board_variants",
    )
    catalog.Scan()
    graphs = []
    mappings: list[dict[str, str]] = []
    platform_sources: list[str] = []
    mcu_provenance = ComponentProvenance_Get(
        catalog, "silverstar.mcu.stm32f407vet6"
    )

    for board_id in ("fixture.board.f407_a", "fixture.board.f407_b"):
        model = ReferenceProject_Create(board_id.rsplit("_", 1)[-1].upper())
        model.devices = [
            "silverstar.device.imu.jy901b",
            "silverstar.device.gnss.neo_m9n",
        ]
        model.board = board_id
        model.hardware = HardwareConfiguration(
            mode="board_plugin", source_kind="third_party"
        )
        model.resource_assignments = {}
        resolution = ResourceAssignments_Resolve(model, catalog, auto_assign=True)
        assert resolution.valid
        assert Project_Validate(model, catalog).valid
        graph = SourceGraph_Resolve(model, catalog)
        graphs.append(graph)
        mappings.append(dict(model.resource_assignments))
        platform_sources.append(
            GeneratedFiles_Render(model, catalog, graph)[
                "Generated/Src/platform_resources.c"
            ].decode("utf-8")
        )

    imu_key = "silverstar.device.imu.jy901b:data"
    gnss_key = "silverstar.device.gnss.neo_m9n:data"
    assert (mappings[0][imu_key], mappings[0][gnss_key]) == ("USART1", "USART2")
    assert (mappings[1][imu_key], mappings[1][gnss_key]) == ("USART3", "USART6")
    assert graphs[0] == graphs[1]
    assert platform_sources[0] != platform_sources[1]
    assert "&huart1" in platform_sources[0] and "&huart2" in platform_sources[0]
    assert "&huart3" in platform_sources[1] and "&huart6" in platform_sources[1]
    assert ComponentProvenance_Get(
        catalog, "silverstar.mcu.stm32f407vet6"
    ) == mcu_provenance


def test_cubemx_import_generate_export_install_and_reuse(
    tmp_path: Path, workspace_root: Path
) -> None:
    policy = WorkspacePolicy(tmp_path)
    installed_root = tmp_path / "plugins" / "installed"
    catalog = _Catalog_Create(workspace_root, installed_root)
    importer = CubeMxImporter(policy)
    fixture = workspace_root / "tests" / "fixtures" / "cubemx_minimal"

    model = ReferenceProject_Create("CustomHardware")
    imported = importer.Project_Import(
        fixture,
        expected_mcu="STM32F407VET6",
        risk_acknowledged=True,
    )
    model.board = ""
    model.hardware = imported.hardware
    model.resource_assignments = {}
    resources = ResourceAssignments_Resolve(model, catalog, auto_assign=True)
    assert resources.valid
    assert len(resources.assignments) == 13
    assert imported.snapshot_root.is_relative_to(tmp_path)
    assert imported.hardware.provider == "silverstar.hardware_provider.stm32_cubemx"
    assert imported.hardware.build_sources == (
        "HardwareGenerated/STM32CubeMX/Core/Src/main.c",
    )
    validation = Project_Validate(model, catalog)
    assert validation.valid
    assert any(issue.code == "hardware_manual" for issue in validation.issues)

    assembler = ProjectAssembler(policy, catalog)
    first_root = tmp_path / "generated" / "CustomHardware"
    first_plan = assembler.Plan(model, first_root)
    assert first_plan.validation.valid
    assert not first_plan.dangerous
    assembler.Apply(model, first_plan)
    hardware_root = first_root / "HardwareGenerated" / "STM32CubeMX"
    assert (hardware_root / "MockFlightController.ioc").is_file()
    assert (hardware_root / "README.md").is_file()
    assert not (first_root / "Platform" / "MockFlightController.ioc").exists()
    project_sources = (first_root / "Generated" / "project_sources.mk").read_text(
        encoding="utf-8"
    )
    assert "HardwareGenerated/STM32CubeMX/Core/Src/main.c" in project_sources

    archive = BoardPluginExporter(policy).Plugin_Export(
        model,
        imported.snapshot_root,
        tmp_path / "artifacts" / "mock_f407.ssplugin",
        component_id="local.board.mock_f407",
        name="Mock F407",
    )
    with zipfile.ZipFile(archive) as package:
        names = set(package.namelist())
    assert "plugin.json" in names
    assert "docs/HARDWARE_PROVENANCE.md" in names
    assert "payload/HardwareGenerated/STM32CubeMX/MockFlightController.ioc" in names

    installed = PluginInstaller(policy, installed_root, catalog).Install(archive)
    assert installed.component_id == "local.board.mock_f407"
    second = ReferenceProject_Create("ReusedBoard")
    second.board = installed.component_id
    second.hardware = HardwareConfiguration(
        mode="board_plugin", source_kind="manual_import"
    )
    second.resource_assignments = {}
    second_resources = ResourceAssignments_Resolve(
        second, catalog, auto_assign=True
    )
    assert second_resources.valid
    assert Project_Validate(second, catalog).valid
    second_root = tmp_path / "generated" / "ReusedBoard"
    second_plan = assembler.Plan(second, second_root)
    assembler.Apply(second, second_plan)
    assert (
        second_root
        / "HardwareGenerated"
        / "STM32CubeMX"
        / "MockFlightController.ioc"
    ).is_file()
    assert second.hardware.mode == "board_plugin"
    assert second.hardware.snapshot_id == ""


def test_cubemx_freertos_conflict_is_rejected(
    tmp_path: Path, workspace_root: Path
) -> None:
    fixture = workspace_root / "tests" / "fixtures" / "cubemx_minimal"
    conflict = tmp_path / "cubemx_rtos_conflict"
    shutil.copytree(fixture, conflict)
    ioc = conflict / "MockFlightController.ioc"
    ioc.write_text(
        ioc.read_text(encoding="utf-8") + "\nMcu.IP8=FREERTOS\n",
        encoding="utf-8",
    )
    with pytest.raises(CubeMxImportError, match="FreeRTOS/CMSIS-RTOS2"):
        CubeMxImporter(WorkspacePolicy(tmp_path)).Project_Import(
            conflict,
            expected_mcu="STM32F407VET6",
            risk_acknowledged=True,
        )
