from __future__ import annotations

import json
from pathlib import Path

from silverstar_fccg.app.service import FccgService
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.project.configuration import (
    ProjectConfiguration_Reconcile,
    StrategyAvailabilities_Get,
)
from silverstar_fccg.project.model import DeviceInstance
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.validation import Project_EditValidate, Project_Validate
from silverstar_fccg.ui.main_window import MainWindow


ACCEL_DEVICE_ID = "fixture.device.imu.accel_only"


def _AccelOnlyCatalog_Create(
    workspace_root: Path, installed_root: Path
) -> PluginCatalog:
    package = installed_root / ACCEL_DEVICE_ID / "1.0.0"
    (package / "payload" / "Fixture").mkdir(parents=True)
    manifest = {
        "schema_version": 0,
        "id": ACCEL_DEVICE_ID,
        "name": "Accel-only IMU",
        "type": "device",
        "class": "imu",
        "instance_policy": {
            "project_max": 2,
            "same_plugin_multiple": True,
            "multi_instance_ready": True,
        },
        "physical_device": {
            "vendor": "Fixture",
            "model": "ACCEL-ONLY",
            "chipset": "TEST",
            "driver": "Context-safe fixture driver",
        },
        "version": "1.0.0",
        "description": "Test-only acceleration and angular-rate provider.",
        "requires": {
            "components": [
                {"id": "silverstar.core.0_0_9", "optional": False}
            ],
            "resources": [],
            "capabilities": [],
        },
        "resources": {"provides": [], "roles": [], "conflicts": []},
        "provides": [
            "device.imu",
            "imu.acceleration",
            "imu.angular_rate",
            "barometer.altitude",
        ],
        "build": {
            "sources": [],
            "asm_sources": [],
            "include_dirs": [],
            "defines": [],
        },
        "payload": {"roots": ["Fixture"]},
        "metadata": {
            "display_names": {
                "zh_CN": "仅加速度与角速度的IMU",
                "en_US": "Acceleration-only IMU",
            },
            "descriptions": {
                "zh_CN": "仅用于测试能力兼容性的加速度、角速度和气压高度设备。",
                "en_US": "Test-only acceleration, angular-rate, and barometer provider.",
            },
        },
    }
    (package / "plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    catalog = PluginCatalog(workspace_root / "plugins" / "builtin", installed_root)
    catalog.Scan()
    return catalog


def test_unselected_hardware_is_editable_but_strictly_not_buildable(
    workspace_root: Path,
) -> None:
    service = FccgService(workspace_root)
    model = service.ProjectDraft_Create("UnselectedHardware")

    edit = Project_EditValidate(model, service.catalog)
    strict = Project_Validate(model, service.catalog)

    assert model.hardware.mode == "unselected"
    assert edit.valid
    assert any(issue.code == "hardware_unselected" for issue in edit.issues)
    assert not strict.valid
    assert any(issue.code == "hardware_unselected" for issue in strict.issues)
    assert model.modes["calibration"] == ["Existing", "OneFace", "SixFace"]
    assert model.modes["deployment"] == [
        "ApogeeVerticalVelocity",
        "Tilt",
        "Delay",
    ]


def test_strategy_availability_uses_physical_capabilities_without_ioc(
    tmp_path: Path, workspace_root: Path
) -> None:
    catalog = _AccelOnlyCatalog_Create(workspace_root, tmp_path / "installed")
    model = ReferenceProject_Create("LogicalAvailability", catalog=catalog)
    model.device_instances = [
        DeviceInstance("imu0", ACCEL_DEVICE_ID)
        if instance.instance_id == "imu0"
        else instance
        for instance in model.device_instances
    ]
    model.board = ""
    model.hardware = model.hardware.__class__()
    model.resource_assignments = {}

    availability = StrategyAvailabilities_Get(model, catalog)

    assert availability[
        "silverstar.algorithm.alignment.gravity_known_yaw"
    ].available
    unavailable = availability[
        "silverstar.algorithm.alignment.gravity_mag_triad"
    ]
    assert not unavailable.available
    assert unavailable.missing_capabilities == ("magnetometer.field",)


def test_device_change_safely_replaces_invalid_strategy_and_modes(
    tmp_path: Path, workspace_root: Path
) -> None:
    catalog = _AccelOnlyCatalog_Create(workspace_root, tmp_path / "installed")
    model = ReferenceProject_Create("StrategyReconcile", catalog=catalog)
    model.strategies["alignment"] = (
        "silverstar.algorithm.alignment.gravity_mag_triad"
    )
    model.device_instances = [
        DeviceInstance("imu0", ACCEL_DEVICE_ID)
        if instance.instance_id == "imu0"
        else instance
        for instance in model.device_instances
    ]

    result = ProjectConfiguration_Reconcile(model, catalog)

    assert result.model.strategies["alignment"] == (
        "silverstar.algorithm.alignment.gravity_known_yaw"
    )
    assert any(
        notice.code == "configuration.strategy_auto_selected"
        for notice in result.notices
    )
    assert result.edit_validation.valid


def test_resource_reconcile_retains_valid_clears_removed_and_auto_assigns_new(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("ResourceReconcile", catalog=builtin_catalog)
    imu_assignment = model.resource_assignments["imu0:data"]
    model.device_instances = [
        instance
        for instance in model.device_instances
        if instance.instance_id != "telemetry0"
    ]

    removed = ProjectConfiguration_Reconcile(model, builtin_catalog)

    assert removed.model.resource_assignments["imu0:data"] == imu_assignment
    assert not any(
        key.startswith("telemetry0:")
        for key in removed.model.resource_assignments
    )
    assert removed.cleared_assignments >= 1

    removed.model.device_instances.append(
        DeviceInstance("telemetry0", "silverstar.device.telemetry.sx1281")
    )
    restored = ProjectConfiguration_Reconcile(removed.model, builtin_catalog)
    assert restored.model.resource_assignments["imu0:data"] == imu_assignment
    assert restored.model.resource_assignments["telemetry0:radio_bus"] == (
        "PLATFORM_SPI_1"
    )
    assert restored.pending_assignments == 0


def test_candidate_failure_keeps_main_window_model_unchanged(
    tmp_path: Path, qapp, monkeypatch
) -> None:
    window = MainWindow(SettingsStore(tmp_path / "candidate.ini"))
    before = window._model.Dictionary_Get()
    errors: list[object] = []
    monkeypatch.setattr(window, "_Error_Show", errors.append)
    original_reconcile = window._service.ProjectConfiguration_Reconcile
    calls = 0

    def reconcile(model):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("fixture failure")
        return original_reconcile(model)

    monkeypatch.setattr(
        window._service,
        "ProjectConfiguration_Reconcile",
        reconcile,
    )
    try:
        result = window._ProjectConfiguration_Change(
            lambda candidate: setattr(candidate, "mcu", "fixture.invalid")
        )
        assert result is None
        assert window._model.Dictionary_Get() == before
        assert len(errors) == 1
    finally:
        window.close()


def test_flight_page_disables_incompatible_strategy_and_only_shows_ambiguous_sources(
    tmp_path: Path, workspace_root: Path, qapp
) -> None:
    catalog = _AccelOnlyCatalog_Create(workspace_root, tmp_path / "installed")
    service = FccgService(workspace_root)
    service.catalog = catalog
    model = ReferenceProject_Create("FlightAvailability", catalog=catalog)
    model.device_instances = [
        DeviceInstance("imu0", ACCEL_DEVICE_ID)
        if instance.instance_id == "imu0"
        else instance
        for instance in model.device_instances
    ]
    model = ProjectConfiguration_Reconcile(model, catalog).model
    window = MainWindow(
        SettingsStore(tmp_path / "flight-availability.ini"),
        service=service,
        language="zh_CN",
    )
    try:
        window._model = model
        window._Project_Display()
        combo = window.flight_configuration_page.strategy_combos["alignment"]
        unavailable_index = combo.findData(
            "silverstar.algorithm.alignment.gravity_mag_triad"
        )
        unavailable_item = combo.model().item(unavailable_index)
        assert unavailable_item is not None
        assert not unavailable_item.isEnabled()
        assert "缺少能力" in unavailable_item.toolTip()
        assert "磁场" in unavailable_item.toolTip()
        assert all(
            window.flight_configuration_page.capability_table.cellWidget(row, 2)
            is None
            for row in range(
                window.flight_configuration_page.capability_table.rowCount()
            )
        )

        model.device_instances.append(DeviceInstance("imu1", ACCEL_DEVICE_ID))
        window._model = ProjectConfiguration_Reconcile(model, catalog).model
        window._Project_Display()
        source_editors = [
            window.flight_configuration_page.capability_table.cellWidget(row, 2)
            for row in range(
                window.flight_configuration_page.capability_table.rowCount()
            )
        ]
        assert any(editor is not None for editor in source_editors)
    finally:
        window.close()


def test_strict_validation_navigates_to_and_highlights_hardware_issue(
    tmp_path: Path, qapp, monkeypatch
) -> None:
    window = MainWindow(SettingsStore(tmp_path / "strict-navigation.ini"))
    errors: list[tuple[object, ...]] = []
    monkeypatch.setattr(window, "_Error_Show", lambda *args: errors.append(args))
    try:
        plan = window._service.GenerationPlan_Create(
            window._model,
            tmp_path / "strict-unselected-project",
        )
        assert not window._GenerationPlan_ApplyAllowed(plan)
        assert window.navigation_list.currentRow() == 2
        assert window.pages.currentWidget() is window.board_hardware_page
        assert window.board_hardware_page.board_combo.property("validationIssue") is True
        assert len(errors) == 1
    finally:
        window.close()
