from __future__ import annotations

import json
import shutil
import zipfile
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel

from silverstar_fccg import __version__
from silverstar_fccg.app.service import FccgService
from silverstar_fccg.app.version import (
    SILVERSTAR_BUILD_ID,
    SILVERSTAR_CORE_COMPONENT_ID,
    SILVERSTAR_LOG_BUILD_TAG,
    SILVERSTAR_PLATFORM_VERSION,
    SILVERSTAR_SYSTEM_PROFILE_ID,
)
from silverstar_fccg.generator.log_decoder_profile import (
    LogDecoderPackage_Verify,
)
from silverstar_fccg.generator.render import (
    GeneratedFiles_Render,
    LogDecoderProfile_Render,
    MetadataFiles_Render,
)
from silverstar_fccg.generator.source_graph import SourceGraph_Resolve
from silverstar_fccg.hardware.platform import (
    DetectedMcuFacts,
    PlatformMatchError,
    PlatformMatch_Resolve,
)
from silverstar_fccg.i18n.translator import Translator
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.plugins.manifest import (
    PluginManifestError,
    PluginManifest_Parse,
)
from silverstar_fccg.project.configuration import (
    ProjectConfiguration_Reconcile,
)
from silverstar_fccg.project.lifecycle import ProjectReadiness_Inspect
from silverstar_fccg.project.logging import (
    LogPolicyLevel,
    LoggingProfile_Reconcile,
    ProtocolLogDefinitions_Get,
)
from silverstar_fccg.project.model import (
    PROJECT_FORMAT_VERSION,
    ProjectModelError,
    ProjectModel_Parse,
)
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.validation import Project_Validate
from silverstar_fccg.ui.pages.components import FlightConfigurationPage


CALIBRATION_COMPONENT = "silverstar.algorithm.calibration"
CALIBRATION_RECORD = "FLIGHT_LOG_RECORD_CALIBRATION_RESULT"
F407_MCU = "silverstar.mcu.stm32f407vet6"
H743_FIXTURE_MCU = "fixture.mcu.stm32h743zit6"


def _LegacyProjectData_Get(
    builtin_catalog: PluginCatalog,
    calibration: list[str],
) -> dict:
    data = ReferenceProject_Create(
        "LegacyPreRelease", catalog=builtin_catalog
    ).Dictionary_Get()
    data["project"]["firmware_version"] = "0.0.9"
    data["project"]["build_target"] = "SilverStar_0_0_9"
    data["components"]["core"] = "silverstar.core.0_0_9"
    data["modes"]["calibration"] = list(calibration)
    for selection in data["protocols"].values():
        if selection is not None:
            selection["version"] = "0.0.9"
            selection["manifest_sha256"] = "0" * 64
    data["hardware"]["platform_version"] = "0.0.9"
    data["hardware"]["platform_manifest_sha256"] = "0" * 64
    return data


def _OldCoreProvenance_Get() -> dict[str, object]:
    return {
        "version": "0.0.9",
        "source": "builtin",
        "manifest_id": "silverstar.core.0_0_9",
        "payload_digest": "0" * 64,
        "files": {},
    }


def _H743Catalog_Create(
    tmp_path: Path,
    workspace_root: Path,
) -> tuple[PluginCatalog, Path]:
    installed_root = tmp_path / "plugins" / "installed"
    source = (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_mcu_stm32f407vet6"
    )
    package = installed_root / "fixture_mcu_stm32h743zit6"
    shutil.copytree(source, package)
    manifest_path = package / "plugin.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["id"] = H743_FIXTURE_MCU
    data["name"] = "Fixture STM32H743ZIT6 Platform"
    data["class"] = "stm32h7_test_fixture"
    data["description"] = (
        "Test-only alternate Platform fixture; it is not a production support claim."
    )
    data["provides"] = [
        "mcu.cortex_m7",
        "platform.fixture_stm32h7",
        "memory.ccmram",
        "hardware_provider.stm32_cubemx",
    ]
    data["metadata"]["mcu_model"] = "STM32H743ZIT6"
    data["metadata"]["display_names"] = {
        "zh_CN": "测试用 STM32H743ZIT6",
        "en_US": "Fixture STM32H743ZIT6",
    }
    data["platform"]["build_target"]["profile"] = (
        "SilverStar_H743_Test"
    )
    data["platform"]["match_rules"] = [
        {
            "vendor": "STM32",
            "exact_part": "STM32H743ZIT6",
            "family_pattern": "STM32H7*",
            "package_pattern": "LQFP144",
            "core_pattern": "*M7*",
            "priority": 100,
            "specificity": 1000,
            "verification": "experimental",
        }
    ]
    data["platform"]["support"] = {
        "level": "experimental",
        "limitations": [
            "Test fixture only; no firmware, hardware, flash or flight support claim"
        ],
    }
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    catalog = PluginCatalog(
        workspace_root / "plugins" / "builtin",
        installed_root,
    )
    catalog.Scan()
    return catalog, manifest_path


def _CustomH743Model_Get(catalog: PluginCatalog):
    model = ReferenceProject_Create("AlternateTarget", catalog=catalog)
    inventory = deepcopy(model.hardware.inventory)
    inventory.update(
        {
            "mcu_part": "STM32H743ZIT6",
            "mcu_name": "STM32H743ZITx",
            "mcu_family": "STM32H7",
            "package": "LQFP144",
            "core": "ARM Cortex-M7",
        }
    )
    model.board = ""
    model.hardware = replace(
        model.hardware,
        mode="custom",
        source_kind="manual_import",
        provider="silverstar.hardware_provider.stm32_cubemx",
        snapshot_id="fixture-h743",
        mcu="STM32H743ZIT6",
        inventory=inventory,
        platform_component="",
        platform_version="",
        platform_manifest_sha256="",
        source_digest="a" * 64,
        source_label="Test-only STM32H743ZIT6 fixture",
        risk_acknowledged=True,
        assignment_fingerprint="",
    )
    return ProjectConfiguration_Reconcile(model, catalog).model


def test_platform_release_has_one_runtime_version_truth(
    workspace_root: Path,
) -> None:
    assert __version__ == SILVERSTAR_PLATFORM_VERSION == "0.0.10"
    assert SILVERSTAR_BUILD_ID == "SilverStar_0_0_10"
    assert SILVERSTAR_CORE_COMPONENT_ID == "silverstar.core.0_0_10"
    assert SILVERSTAR_LOG_BUILD_TAG == "SILV0010"
    assert len(SILVERSTAR_LOG_BUILD_TAG.encode("ascii")) == 8
    assert SILVERSTAR_SYSTEM_PROFILE_ID == 0x0000000A

    manifests = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(
            (workspace_root / "plugins" / "builtin").glob(
                "*/plugin.json"
            )
        )
    ]
    assert len(manifests) == 36
    for manifest in manifests:
        expected = (
            "11.3.0"
            if manifest["id"] == "silverstar.os.freertos_11_3_0"
            else "0.0.10"
        )
        assert manifest["version"] == expected
        if manifest["type"] == "protocol":
            contribution = manifest["protocol"]
            assert contribution["firmware_version"] == "0.0.10"
            assert contribution["documentation_version"] == "0.0.10"
            profiles = next(iter(contribution["profiles"].values()))
            assert {profile["version"] for profile in profiles} == {"0.0"}

    assert not (
        workspace_root / "plugins" / "builtin" / "silverstar_core_0_0_9"
    ).exists()
    assert (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_core_0_0_10"
        / "docs"
        / "SilverStar_0_0_10.md"
    ).is_file()


def test_new_project_and_generated_identity_are_consistently_0_0_10(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("VersionTruth", catalog=builtin_catalog)
    assert model.format_version == PROJECT_FORMAT_VERSION == 11
    assert model.identity.firmware_version == "0.0.10"
    assert model.identity.build_target == "SilverStar_0_0_10"
    assert model.core == "silverstar.core.0_0_10"
    assert model.build.target_profile == "SilverStar_F407"

    graph = SourceGraph_Resolve(model, builtin_catalog)
    generated = GeneratedFiles_Render(model, builtin_catalog, graph)
    metadata = MetadataFiles_Render(model, builtin_catalog, graph)
    saved = ProjectModel_Parse(json.loads(metadata["SilverStar.ssproject"]))
    assert saved.identity == model.identity
    assert saved.core == model.core
    assert saved.build.target_profile == "SilverStar_F407"
    assert "TARGET_PROFILE ?= SilverStar_F407" in metadata[
        "Makefile"
    ].decode("utf-8")
    assert "Targets/SilverStar_F407/target.mk" in metadata

    semantics = json.loads(
        generated["Generated/project_semantics.json"].decode("utf-8")
    )
    assert semantics["firmware_version"] == "0.0.10"
    assert semantics["target"] == "SilverStar_F407"
    assert any(
        lock["component"] == "silverstar.core.0_0_10"
        and lock["version"] == "0.0.10"
        for lock in semantics["component_locks"]
    )

    package = LogDecoderProfile_Render(model, builtin_catalog)
    manifest = LogDecoderPackage_Verify(package.content)
    assert manifest["package_schema"] == {
        "id": "silverstar.ssdecoder/1.1",
        "major": 1,
        "minor": 1,
    }
    assert manifest["firmware_version"] == "0.0.10"
    assert manifest["fccg_version"] == "0.0.10"
    with zipfile.ZipFile(BytesIO(package.content)) as archive:
        decoder_readme = archive.read("README.md").decode("utf-8")
    assert "not a whitelist" in decoder_readme
    assert "NONE/identity" in decoder_readme


def test_generated_firmware_version_macros_are_revision_ten(
    workspace_root: Path,
) -> None:
    config = (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_core_0_0_10"
        / "payload"
        / "System"
        / "User"
        / "system_user_config.h"
    ).read_text(encoding="utf-8")
    assert "#define SYSTEM_VERSION_MAJOR 0U" in config
    assert "#define SYSTEM_VERSION_MINOR 0U" in config
    assert "#define SYSTEM_VERSION_PATCH 10U" in config
    assert "#define SYSTEM_VERSION_BUILD 0U" in config
    assert '#define SYSTEM_BUILD_TAG "SILV0010"' in config
    assert "#define SYSTEM_PROFILE_ID 0x0000000AUL" in config


@pytest.mark.parametrize(
    ("legacy", "expected"),
    (
        (["Existing"], []),
        (["Existing", "OneFace"], ["OneFace"]),
        (["Existing", "SixFace"], ["SixFace"]),
        (
            ["Existing", "OneFace", "SixFace"],
            ["OneFace", "SixFace"],
        ),
    ),
)
def test_current_pre_release_calibration_migration_is_deterministic(
    builtin_catalog: PluginCatalog,
    legacy: list[str],
    expected: list[str],
) -> None:
    migrated = ProjectModel_Parse(
        _LegacyProjectData_Get(builtin_catalog, legacy)
    )
    assert migrated.format_version == 11
    assert migrated.identity.firmware_version == "0.0.10"
    assert migrated.identity.build_target == "SilverStar_0_0_10"
    assert migrated.core == "silverstar.core.0_0_10"
    assert migrated.modes["calibration"] == expected

    reconciled = ProjectConfiguration_Reconcile(
        migrated, builtin_catalog
    ).model
    assert reconciled.build.target_profile == "SilverStar_F407"
    assert all(
        selection is None
        or (
            selection.version == "0.0.10"
            and selection.manifest_sha256
            == builtin_catalog.Component_Get(
                selection.component
            ).ManifestSha256_Get()
        )
        for selection in reconciled.protocols.values()
    )
    serialized = reconciled.Dictionary_Get()
    assert "Existing" not in json.dumps(serialized)


def test_pre_release_migration_rejects_duplicates_and_unknowns_strictly(
    builtin_catalog: PluginCatalog,
) -> None:
    duplicate = _LegacyProjectData_Get(
        builtin_catalog, ["Existing", "OneFace", "OneFace"]
    )
    with pytest.raises(ProjectModelError, match="duplicate"):
        ProjectModel_Parse(duplicate)

    unknown = ProjectModel_Parse(
        _LegacyProjectData_Get(
            builtin_catalog, ["Existing", "ThirdPartyCalibration"]
        )
    )
    assert unknown.modes["calibration"] == ["ThirdPartyCalibration"]
    validation = Project_Validate(unknown, builtin_catalog)
    assert not validation.valid
    assert any(issue.code == "mode_option" for issue in validation.issues)


def test_generated_pre_release_payload_is_blocked_and_marked_stale(
    tmp_path: Path,
    builtin_catalog: PluginCatalog,
) -> None:
    data = _LegacyProjectData_Get(builtin_catalog, ["Existing"])
    data["component_provenance"] = {
        "silverstar.core.0_0_9": _OldCoreProvenance_Get()
    }
    project_file = tmp_path / "SilverStar.ssproject"
    project_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    migrated = ProjectModel_Parse(data)
    marker = migrated.reference_provenance["pre_release_migration"]
    assert marker["requires_new_output_directory"] is True
    validation = Project_Validate(migrated, builtin_catalog)
    assert any(
        issue.code == "pre_release_rebuild_required"
        for issue in validation.issues
    )
    readiness = ProjectReadiness_Inspect(
        migrated, tmp_path, builtin_catalog
    )
    assert "SilverStar.ssproject:pre_release_rebuild_required" in (
        readiness.stale
    )


def test_calibration_manifest_gui_and_defaults_use_empty_selection(
    qapp,
    workspace_root: Path,
    builtin_catalog: PluginCatalog,
) -> None:
    del qapp
    manifest = builtin_catalog.Component_Get(CALIBRATION_COMPONENT)
    selection = manifest.selection
    assert selection is not None
    assert selection.required is False
    assert selection.allow_none is True
    assert selection.allow_multiple is True
    assert selection.options == ("OneFace", "SixFace")
    assert selection.default == ()
    assert selection.aggregate_symbol == (
        "SYSTEM_CALIBRATION_BUILD_PROCEDURE_MASK"
    )
    assert "Existing" not in selection.options

    model = ReferenceProject_Create("CalibrationGui", catalog=builtin_catalog)
    assert model.modes["calibration"] == []
    service = FccgService(workspace_root)
    views = service.ComponentViews_Get("zh_CN")
    page = FlightConfigurationPage(Translator("zh_CN"))
    page.Configuration_Set(
        views,
        model.strategies,
        model.modes,
        model.mode_parameters,
    )
    checks = page.mode_checks["calibration"]
    assert [check.property("selectionOption") for check in checks] == [
        "OneFace",
        "SixFace",
    ]
    assert not any(check.isChecked() for check in checks)
    assert all("现有校准" not in check.text() for check in checks)
    notes = [
        label.text()
        for label in page.findChildren(QLabel)
        if label.property("secondaryText") is True
    ]
    assert any("单位校正" in note and "仍记录" in note for note in notes)


@pytest.mark.parametrize(
    ("selected", "expected_expression"),
    (
        ([], "0U"),
        (
            ["OneFace"],
            "(SYSTEM_CALIBRATION_CAPABILITY_ONE_FACE)",
        ),
        (
            ["SixFace"],
            "(SYSTEM_CALIBRATION_CAPABILITY_SIX_FACE)",
        ),
        (
            ["OneFace", "SixFace"],
            "(SYSTEM_CALIBRATION_CAPABILITY_ONE_FACE | SYSTEM_CALIBRATION_CAPABILITY_SIX_FACE)",
        ),
    ),
)
def test_calibration_four_selection_combinations_round_trip_and_render(
    builtin_catalog: PluginCatalog,
    selected: list[str],
    expected_expression: str,
) -> None:
    model = ReferenceProject_Create(
        "CalibrationCombination", catalog=builtin_catalog
    )
    model.modes["calibration"] = list(selected)
    model = ProjectConfiguration_Reconcile(model, builtin_catalog).model
    assert model.modes["calibration"] == selected
    reparsed = ProjectModel_Parse(model.Dictionary_Get())
    assert reparsed.modes["calibration"] == selected
    graph = SourceGraph_Resolve(model, builtin_catalog)
    generated = GeneratedFiles_Render(model, builtin_catalog, graph)
    header = generated[
        "Generated/Inc/project_flight_config.h"
    ].decode("utf-8")
    line = next(
        value
        for value in header.splitlines()
        if value.startswith(
            "#define SYSTEM_CALIBRATION_BUILD_PROCEDURE_MASK"
        )
    )
    assert line.split(None, 2)[2] == expected_expression

    semantics = json.loads(
        generated["Generated/project_semantics.json"].decode("utf-8")
    )
    assert semantics["modes"]["calibration"] == selected
    assert "Existing" not in json.dumps(semantics)
    assert CALIBRATION_COMPONENT in semantics["algorithms"]
    assert "System/Calibration/Src/system_calibration.c" in graph.sources
    assert "APP/Src/imu_sample_bus.c" in graph.sources
    assert "APP/Src/flight_task.c" in graph.sources


def test_none_calibration_initialization_and_required_record_contract(
    workspace_root: Path,
    builtin_catalog: PluginCatalog,
) -> None:
    core = (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_core_0_0_10"
        / "payload"
    )
    app_tasks = (core / "APP" / "Src" / "app_tasks.c").read_text(
        encoding="utf-8"
    )
    assert "SYSTEM_CALIBRATION_BUILD_PROCEDURE_MASK == 0U" in app_tasks
    assert "SystemCalibration_Start(" in app_tasks
    assert "SYSTEM_CALIBRATION_MODE_NONE" in app_tasks
    assert app_tasks.index("SystemCalibration_Start(") < app_tasks.index(
        "SystemAlignment_Init();"
    )
    assert "AppTasksInitResult_CalibrationInitFailed" in (
        core / "APP" / "Inc" / "app_tasks.h"
    ).read_text(encoding="utf-8")

    model = ReferenceProject_Create(
        "RequiredCalibrationResult", catalog=builtin_catalog
    )
    definition = next(
        item
        for item in ProtocolLogDefinitions_Get(model, builtin_catalog)
        if item.record == CALIBRATION_RECORD
    )
    assert definition.record_id == "0x17"
    assert definition.version == 0
    assert definition.payload_size == 72
    assert definition.default_stream.policy == "EVENT"
    assert definition.level == LogPolicyLevel.REQUIRED
    assert definition.producer_components == (
        "silverstar.core.flight_task",
    )

    stream = next(
        item for item in model.logging_streams if item.record == CALIBRATION_RECORD
    )
    stream.enabled = False
    LoggingProfile_Reconcile(model, builtin_catalog)
    assert next(
        item for item in model.logging_streams if item.record == CALIBRATION_RECORD
    ).enabled

    schema = json.loads(
        (
            workspace_root
            / "plugins"
            / "builtin"
            / "silverstar_protocol_logging_sslog_0_0"
            / "payload"
            / "Protocol"
            / "SSLOG"
            / "schema"
            / "sslog_schema.json"
        ).read_text(encoding="utf-8")
    )
    record = next(
        item
        for item in schema["records"]
        if item["name"] == "CALIBRATION_RESULT"
    )
    assert record["id"] == "0x17"
    assert record["version"] == 0
    assert record["payload_size"] == 72
    assert [field["name"] for field in record["fields"]] == [
        "source_id",
        "virtual_imu_id",
        "mode",
        "state",
        "ready",
        "completed_face_mask",
        "samples",
        "reject_count",
        "retry_count",
        "start_sequence",
        "accel_bias_mps2",
        "accel_scale",
        "gyro_bias_radps",
        "gyro_scale",
    ]


def test_logging_disabled_removes_logger_but_keeps_identity_correction(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create(
        "NoLoggingIdentityCorrection", catalog=builtin_catalog
    )
    model.protocols["logging"] = None
    model = ProjectConfiguration_Reconcile(model, builtin_catalog).model
    graph = SourceGraph_Resolve(model, builtin_catalog)
    assert "System/Calibration/Src/system_calibration.c" in graph.sources
    assert "APP/Src/imu_sample_bus.c" in graph.sources
    assert "APP/Src/logger_task.c" not in graph.sources
    assert "Protocol/SSLOG/Src/sslog_protocol.c" not in graph.sources
    header = GeneratedFiles_Render(model, builtin_catalog, graph)[
        "Generated/Inc/project_flight_config.h"
    ].decode("utf-8")
    assert "#define SILVERSTAR_PROTOCOL_LOGGING_ENABLED 0U" in header
    assert "#define SYSTEM_CALIBRATION_BUILD_PROCEDURE_MASK 0U" in header


def test_f407_target_profile_is_manifest_owned_and_tamper_detected(
    builtin_catalog: PluginCatalog,
) -> None:
    platform = builtin_catalog.Component_Get(F407_MCU)
    assert platform.platform is not None
    assert platform.platform.build_target_profile == "SilverStar_F407"

    model = ReferenceProject_Create("TargetLock", catalog=builtin_catalog)
    model.build = replace(model.build, target_profile="Tampered_Target")
    validation = Project_Validate(model, builtin_catalog)
    assert not validation.valid
    issue = next(
        item for item in validation.issues if item.code == "target_profile_lock"
    )
    assert "SilverStar_F407" in issue.message
    reconciled = ProjectConfiguration_Reconcile(model, builtin_catalog).model
    assert reconciled.build.target_profile == "SilverStar_F407"


@pytest.mark.parametrize(
    "invalid",
    (
        "",
        "1LeadingDigit",
        "SilverStar H743",
        "../SilverStar_H743",
        "SilverStar/H743",
        "SilverStar\\H743",
        "SilverStar_$(H743)",
        "SilverStar_H743\nall:",
    ),
)
def test_mcu_manifest_rejects_missing_or_unsafe_target_profiles(
    invalid: str,
    workspace_root: Path,
) -> None:
    manifest_path = (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_mcu_stm32f407vet6"
        / "plugin.json"
    )
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["platform"]["build_target"]["profile"] = invalid
    with pytest.raises(
        PluginManifestError,
        match=r"platform\.build_target\.profile",
    ):
        PluginManifest_Parse(data, manifest_path, source="installed")


def test_mcu_manifest_requires_target_and_non_mcu_cannot_declare_platform(
    workspace_root: Path,
) -> None:
    manifest_path = (
        workspace_root
        / "plugins"
        / "builtin"
        / "silverstar_mcu_stm32f407vet6"
        / "plugin.json"
    )
    missing = json.loads(manifest_path.read_text(encoding="utf-8"))
    del missing["platform"]["build_target"]
    with pytest.raises(PluginManifestError, match="build_target"):
        PluginManifest_Parse(missing, manifest_path, source="installed")

    wrong_type = json.loads(manifest_path.read_text(encoding="utf-8"))
    wrong_type["id"] = "fixture.algorithm.invalid_platform"
    wrong_type["type"] = "algorithm"
    with pytest.raises(
        PluginManifestError,
        match="MCU plugins must declare exactly one platform contract",
    ):
        PluginManifest_Parse(wrong_type, manifest_path, source="installed")


def test_synthetic_h743_target_flows_through_match_project_and_renderers(
    tmp_path: Path,
    workspace_root: Path,
) -> None:
    catalog, manifest_path = _H743Catalog_Create(tmp_path, workspace_root)
    manifest = catalog.Component_Get(H743_FIXTURE_MCU)
    assert manifest.manifest_path == manifest_path.resolve()
    assert manifest.platform is not None
    assert manifest.platform.build_target_profile == "SilverStar_H743_Test"
    match = PlatformMatch_Resolve(
        DetectedMcuFacts(
            vendor="STM32",
            part="STM32H743ZIT6",
            family="STM32H7",
            package="LQFP144",
            core="ARM Cortex-M7",
            provider="stm32_cubemx",
        ),
        catalog,
    )
    assert match.selected.component_id == H743_FIXTURE_MCU

    model = _CustomH743Model_Get(catalog)
    assert model.mcu == H743_FIXTURE_MCU
    assert model.build.target_profile == "SilverStar_H743_Test"
    graph = SourceGraph_Resolve(model, catalog)
    generated = GeneratedFiles_Render(model, catalog, graph)
    metadata = MetadataFiles_Render(model, catalog, graph)
    assert "Targets/SilverStar_H743_Test/target.mk" in metadata
    assert "TARGET_PROFILE ?= SilverStar_H743_Test" in metadata[
        "Makefile"
    ].decode("utf-8")
    assert "SilverStar_H743_Test" in metadata[".vscode/tasks.json"].decode(
        "utf-8"
    )
    assert "SilverStar_H743_Test" in metadata[".eide/eide.yml"].decode(
        "utf-8"
    )
    assert "SilverStar_H743_Test" in metadata[
        "AlternateTarget.code-workspace"
    ].decode("utf-8")
    semantics = json.loads(
        generated["Generated/project_semantics.json"].decode("utf-8")
    )
    assert semantics["target"] == "SilverStar_H743_Test"
    assert semantics["hardware"]["matched_mcu_platform"] == H743_FIXTURE_MCU

    inventory = deepcopy(model.hardware.inventory)
    inventory.update(
        {
            "mcu_part": "STM32F407VET6",
            "mcu_name": "STM32F407VETx",
            "mcu_family": "STM32F4",
            "package": "LQFP100",
            "core": "ARM Cortex-M4",
        }
    )
    model.hardware = replace(
        model.hardware,
        mcu="STM32F407VET6",
        inventory=inventory,
    )
    f407 = ProjectConfiguration_Reconcile(model, catalog).model
    assert f407.mcu == F407_MCU
    assert f407.build.target_profile == "SilverStar_F407"


def test_synthetic_target_conflict_is_rejected(
    tmp_path: Path,
    workspace_root: Path,
) -> None:
    catalog, _manifest_path = _H743Catalog_Create(tmp_path, workspace_root)
    original = catalog.Component_Get(H743_FIXTURE_MCU)
    duplicate = replace(
        original,
        component_id="fixture.mcu.stm32h743zit6_duplicate",
        name="Duplicate H743 test target",
    )

    class MatchCatalog:
        def Type_Get(self, component_type: str):
            return (
                (original, duplicate)
                if component_type == "mcu"
                else ()
            )

    with pytest.raises(PlatformMatchError, match="ambiguous"):
        PlatformMatch_Resolve(
            DetectedMcuFacts(
                vendor="STM32",
                part="STM32H743ZIT6",
                family="STM32H7",
                package="LQFP144",
                core="ARM Cortex-M7",
                provider="stm32_cubemx",
            ),
            MatchCatalog(),  # type: ignore[arg-type]
        )
