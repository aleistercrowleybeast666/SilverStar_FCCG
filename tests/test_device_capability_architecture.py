from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from silverstar_fccg.app.service import FccgService
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.generator.source_graph import SourceGraph_Resolve
from silverstar_fccg.plugins.catalog import PluginCatalog
from silverstar_fccg.project.capabilities import CapabilityResolution_Resolve
from silverstar_fccg.project.logging import LoggingProfile_Reconcile
from silverstar_fccg.project.model import (
    DeviceInstance,
    ProjectModel_Load,
    ProjectModel_Parse,
)
from silverstar_fccg.project.reference import ReferenceProject_Create
from silverstar_fccg.project.resources import ResourceRequirementOptions_Get
from silverstar_fccg.project.validation import Project_Validate
from silverstar_fccg.ui.main_window import MainWindow
from silverstar_fccg.ui.widgets import LockedCheckBox, StandardCheckBox


def _MultiBarometerCatalog_Create(
    workspace_root: Path, installed_root: Path
) -> PluginCatalog:
    package = installed_root / "fixture.device.sensor.bmp280" / "1.0.0"
    package.mkdir(parents=True)
    (package / "payload" / "Fixture").mkdir(parents=True)
    manifest = {
        "schema_version": 0,
        "id": "fixture.device.sensor.bmp280",
        "name": "BMP280",
        "type": "device",
        "class": "other_sensors",
        "instance_policy": {
            "project_max": 4,
            "same_plugin_multiple": True,
            "multi_instance_ready": True,
        },
        "physical_device": {
            "vendor": "Bosch",
            "model": "BMP280",
            "chipset": "BMP280",
            "driver": "Fixture BMP280 Driver",
        },
        "version": "1.0.0",
        "description": "Test-only declarative physical barometer.",
        "requires": {
            "components": [
                {"id": "silverstar.core.0_0_9", "optional": False}
            ],
            "resources": [],
            "capabilities": [],
        },
        "resources": {"provides": [], "roles": [], "conflicts": []},
        "provides": ["barometer.altitude"],
        "build": {
            "sources": [],
            "asm_sources": [],
            "include_dirs": [],
            "defines": [],
        },
        "payload": {"roots": ["Fixture"]},
        "metadata": {
            "display_names": {"zh_CN": "BMP280", "en_US": "BMP280"}
        },
    }
    (package / "plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    catalog = PluginCatalog(workspace_root / "plugins" / "builtin", installed_root)
    catalog.Scan()
    return catalog


def _MultiInstanceDeviceCatalog_Create(
    workspace_root: Path, installed_root: Path
) -> PluginCatalog:
    specifications = (
        (
            "fixture.device.imu.contextual",
            "imu",
            ("device.imu", "imu.acceleration", "imu.angular_rate"),
        ),
        (
            "fixture.device.gnss.contextual",
            "gnss",
            ("device.gnss", "gnss.position", "gnss.velocity"),
        ),
    )
    for component_id, component_class, capabilities in specifications:
        package = installed_root / component_id / "1.0.0"
        payload = package / "payload"
        source_relative = f"Fixture/{component_class}/contextual_device.c"
        source = payload / source_relative
        source.parent.mkdir(parents=True)
        source.write_text(
            f"void Fixture_{component_class.capitalize()}Process(void) {{}}\n",
            encoding="utf-8",
        )
        manifest = {
            "schema_version": 0,
            "id": component_id,
            "name": f"Contextual {component_class.upper()}",
            "type": "device",
            "class": component_class,
            "instance_policy": {
                "project_max": 2,
                "same_plugin_multiple": True,
                "multi_instance_ready": True,
            },
            "physical_device": {
                "vendor": "Fixture",
                "model": f"CTX-{component_class.upper()}",
                "chipset": "TEST",
                "driver": "Context-safe fixture driver",
            },
            "version": "1.0.0",
            "description": "Test-only context-safe multi-instance device.",
            "requires": {
                "components": [
                    {"id": "silverstar.core.0_0_9", "optional": False}
                ],
                "resources": [{"name": "data", "kind": "uart"}],
                "capabilities": [],
            },
            "resources": {"provides": [], "roles": [], "conflicts": []},
            "provides": list(capabilities),
            "build": {
                "sources": [source_relative],
                "asm_sources": [],
                "include_dirs": [],
                "defines": [],
            },
            "payload": {"roots": [f"Fixture/{component_class}"]},
            "metadata": {
                "display_names": {
                    "zh_CN": f"上下文化 {component_class.upper()}",
                    "en_US": f"Contextual {component_class.upper()}",
                }
            },
        }
        (package / "plugin.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
    catalog = PluginCatalog(workspace_root / "plugins" / "builtin", installed_root)
    catalog.Scan()
    return catalog


def test_project_v2_migrates_devices_and_resource_owners() -> None:
    data = ReferenceProject_Create("MigrateV2").Dictionary_Get()
    instances = list(data["components"]["devices"])
    instance_to_plugin = {
        entry["instance_id"]: entry["plugin"] for entry in instances
    }
    data["format_version"] = 2
    data["components"]["devices"] = [entry["plugin"] for entry in instances]
    data["resources"] = {
        (
            f"{instance_to_plugin.get(owner, owner)}:{requirement}"
            if separator
            else key
        ): resource
        for key, resource in data["resources"].items()
        for owner, separator, requirement in (key.partition(":"),)
    }
    data.pop("capability_sources")
    data["generated_glue"].remove("project_capability_routes")

    migrated = ProjectModel_Parse(data)
    assert migrated.format_version == 5
    assert [instance.instance_id for instance in migrated.device_instances] == [
        "imu0",
        "gnss0",
        "telemetry0",
        "maintenance0",
    ]
    assert migrated.resource_assignments["imu0:data"] == "PLATFORM_UART_1"
    assert migrated.capability_source_overrides == {}
    assert "capability_selections" not in migrated.Dictionary_Get()
    assert "project_capability_routes" in migrated.generated_glue


def test_project_v3_migrates_without_capability_selections() -> None:
    data = ReferenceProject_Create("MigrateV3").Dictionary_Get()
    data["format_version"] = 3

    migrated = ProjectModel_Parse(data)

    assert migrated.format_version == 5
    assert "capability_selections" not in migrated.Dictionary_Get()


def test_project_v4_removes_legacy_capability_and_build_choices() -> None:
    data = ReferenceProject_Create("MigrateV4").Dictionary_Get()
    data["format_version"] = 4
    data["capability_selections"] = {"imu0": ["magnetometer.field"]}
    data["build"]["configuration"] = "Release"

    migrated = ProjectModel_Parse(data)

    serialized = migrated.Dictionary_Get()
    assert migrated.format_version == 5
    assert "capability_selections" not in serialized
    assert "configuration" not in serialized["build"]


def test_reference_capability_resolution_matches_physical_truth(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("CapabilityTruth")
    resolution = CapabilityResolution_Resolve(model, builtin_catalog)
    assert resolution.valid
    assert not resolution.choices
    assert all(route.automatic for route in resolution.routes)
    assert len(
        [instance for instance in model.device_instances if instance.instance_id == "imu0"]
    ) == 1

    jy901b = builtin_catalog.Component_Get("silverstar.device.imu.jy901b")
    assert set(jy901b.provides) == {
        "device.imu",
        "imu.acceleration",
        "imu.angular_rate",
        "attitude.external",
        "magnetometer.field",
        "barometer.altitude",
    }
    assert set(resolution.ConsumedCapabilitiesForInstance_Get("imu0")) == {
        "imu.acceleration",
        "imu.angular_rate",
        "barometer.altitude",
    }
    assert {"attitude.external", "magnetometer.field"}.issubset(
        resolution.unused_by_instance["imu0"]
    )
    assert not {"attitude.external", "magnetometer.field"}.intersection(
        resolution.EnabledCapabilitiesForInstance_Get("imu0")
    )
    assert {route.requirement.purpose for route in resolution.routes} == {
        "initialization",
        "runtime",
        "measurement_update",
        "calibration",
        "landing_detection",
    }
    assert not any(
        token in route.requirement.purpose
        for route in resolution.routes
        for token in ("pre_start", "ascent", "recovery")
    )


def test_external_attitude_is_strategy_requirement_without_phase_policy(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("HardwareAttitude")
    model.strategies["alignment"] = (
        "silverstar.algorithm.alignment.hardware_quat_6axis_known_yaw"
    )
    resolution = CapabilityResolution_Resolve(model, builtin_catalog)
    routes = [
        route
        for route in resolution.routes
        if route.requirement.capability == "attitude.external"
    ]
    assert resolution.valid
    assert len(routes) == 1
    assert routes[0].provider.instance_id == "imu0"
    assert routes[0].requirement.purpose == "initialization"
    assert "phase" not in model.Dictionary_Get()


def test_ambiguous_provider_requires_only_one_saved_override(
    tmp_path: Path, workspace_root: Path
) -> None:
    catalog = _MultiBarometerCatalog_Create(workspace_root, tmp_path / "installed")
    model = ReferenceProject_Create("AmbiguousProvider")
    model.device_instances.extend(
        (
            DeviceInstance("barometer0", "fixture.device.sensor.bmp280"),
            DeviceInstance("barometer1", "fixture.device.sensor.bmp280"),
        )
    )
    unresolved = CapabilityResolution_Resolve(model, catalog)
    barometer_choice = next(
        choice
        for choice in unresolved.choices
        if choice.capability == "barometer.altitude"
    )
    assert barometer_choice.requires_selection
    assert {provider.instance_id for provider in barometer_choice.providers} == {
        "imu0",
        "barometer0",
        "barometer1",
    }
    assert any(
        issue.code == "capability_ambiguous"
        for issue in Project_Validate(model, catalog).issues
    )

    model.capability_source_overrides = {"barometer.altitude": "barometer1"}
    resolved = CapabilityResolution_Resolve(model, catalog)
    assert resolved.valid
    assert all(
        route.provider.instance_id == "barometer1"
        for route in resolved.routes
        if route.requirement.capability == "barometer.altitude"
    )
    assert Project_Validate(model, catalog).valid
    assert model.Dictionary_Get()["capability_sources"] == {
        "barometer.altitude": "barometer1"
    }


def test_current_devices_are_singleton_and_mcu_neutral(
    builtin_catalog: PluginCatalog,
) -> None:
    for component_id in (
        "silverstar.device.imu.jy901b",
        "silverstar.device.gnss.neo_m9n",
        "silverstar.device.telemetry.sx1281",
        "silverstar.device.console.uart",
    ):
        manifest = builtin_catalog.Component_Get(component_id)
        assert manifest.instance_policy.project_max == 1
        assert not manifest.instance_policy.same_plugin_multiple
        assert not manifest.instance_policy.multi_instance_ready
        assert manifest.physical_device is not None
        assert "silverstar.mcu.stm32f407vet6" not in {
            dependency.component_id for dependency in manifest.dependencies
        }


def test_singleton_device_plugin_cannot_be_instantiated_twice(
    builtin_catalog: PluginCatalog,
) -> None:
    model = ReferenceProject_Create("DuplicateSingleton")
    model.device_instances.append(
        DeviceInstance("imu1", "silverstar.device.imu.jy901b")
    )
    issue_codes = {issue.code for issue in Project_Validate(model, builtin_catalog).issues}
    assert "device_instance_limit" in issue_codes
    assert "device_same_plugin_multiple" in issue_codes
    assert "device_multi_instance_not_ready" in issue_codes


def test_context_ready_mock_devices_support_independent_instances_and_dedup_sources(
    tmp_path: Path, workspace_root: Path
) -> None:
    catalog = _MultiInstanceDeviceCatalog_Create(
        workspace_root, tmp_path / "multi-instance-installed"
    )
    model = ReferenceProject_Create("MultiInstanceModel")
    model.device_instances = [
        DeviceInstance("imu0", "fixture.device.imu.contextual"),
        DeviceInstance("imu1", "fixture.device.imu.contextual"),
        DeviceInstance("gnss0", "fixture.device.gnss.contextual"),
        DeviceInstance("gnss1", "fixture.device.gnss.contextual"),
    ]

    reparsed = ProjectModel_Parse(model.Dictionary_Get())
    assert [instance.instance_id for instance in reparsed.device_instances] == [
        "imu0",
        "imu1",
        "gnss0",
        "gnss1",
    ]
    issue_codes = {issue.code for issue in Project_Validate(model, catalog).issues}
    assert not issue_codes.intersection(
        {
            "device_instance_limit",
            "device_same_plugin_multiple",
            "device_multi_instance_not_ready",
            "device_class_instance_limit",
            "device_class_multi_instance_not_ready",
        }
    )

    requirement_keys = {
        option.key for option in ResourceRequirementOptions_Get(model, catalog)
    }
    assert {"imu0:data", "imu1:data", "gnss0:data", "gnss1:data"}.issubset(
        requirement_keys
    )

    unresolved = CapabilityResolution_Resolve(model, catalog)
    acceleration = next(
        choice
        for choice in unresolved.choices
        if choice.capability == "imu.acceleration"
    )
    position = next(
        choice
        for choice in unresolved.choices
        if choice.capability == "gnss.position"
    )
    assert {provider.instance_id for provider in acceleration.providers} == {
        "imu0",
        "imu1",
    }
    assert {provider.instance_id for provider in position.providers} == {
        "gnss0",
        "gnss1",
    }

    model.capability_source_overrides.update(
        {
            "imu.acceleration": "imu1",
            "imu.angular_rate": "imu1",
            "gnss.position": "gnss0",
            "gnss.velocity": "gnss0",
        }
    )
    resolved = CapabilityResolution_Resolve(model, catalog)
    assert all(
        route.provider.instance_id == "imu1"
        for route in resolved.routes
        if route.requirement.capability
        in {"imu.acceleration", "imu.angular_rate"}
    )
    assert all(
        route.provider.instance_id == "gnss0"
        for route in resolved.routes
        if route.requirement.capability in {"gnss.position", "gnss.velocity"}
    )

    graph = SourceGraph_Resolve(model, catalog)
    assert graph.sources.count("Fixture/imu/contextual_device.c") == 1
    assert graph.sources.count("Fixture/gnss/contextual_device.c") == 1
    assert isinstance(model.strategies["estimator"], str)


def test_physical_names_and_protocol_versions_are_structured(
    builtin_catalog: PluginCatalog,
) -> None:
    telemetry = builtin_catalog.Component_Get(
        "silverstar.device.telemetry.sx1281"
    )
    assert telemetry.DisplayName_Get("zh_CN") == "E28-2G4M12SX（SX1281）"
    assert telemetry.physical_device is not None
    assert telemetry.physical_device.model == "E28-2G4M12SX"
    assert telemetry.physical_device.chipset == "SX1281"
    assert telemetry.physical_device.driver == "SX1281 Driver"

    console = builtin_catalog.Component_Get("silverstar.device.console.uart")
    assert console.DisplayName_Get("zh_CN") == "串口维护协议 0.0"
    protocol = builtin_catalog.Component_Get("silverstar.protocol.reference_v0")
    assert protocol.protocol is not None
    assert protocol.protocol.maintenance_protocol_version == "0.0"
    assert protocol.protocol.firmware_version == "0.0.9"
    assert protocol.protocol.documentation_version == "0.0.9"


def test_save_as_copies_full_source_and_excludes_intermediates(
    tmp_path: Path, workspace_root: Path
) -> None:
    service = FccgService(workspace_root)
    source = tmp_path / "SourceProject"
    destination = tmp_path / "CopiedProject"
    model = service.ReferenceProject_Create("SourceProject")
    plan = service.GenerationPlan_Create(model, source)
    service.GenerationPlan_Apply(model, plan)

    component_source = (
        source / "Devices" / "IMU" / "JY901B" / "Src" / "jy901b_device.c"
    )
    marker = "\n/* MANUAL SOURCE MUST SURVIVE SAVE AS */\n"
    component_source.write_text(
        component_source.read_text(encoding="utf-8") + marker,
        encoding="utf-8",
        newline="\n",
    )
    build_artifact = source / "build" / "Debug" / "firmware.o"
    build_artifact.parent.mkdir(parents=True)
    build_artifact.write_bytes(b"intermediate")
    cache_file = source / ".fccg" / "cache" / "scan.bin"
    cache_file.parent.mkdir(parents=True)
    cache_file.write_bytes(b"cache")
    destination.mkdir()

    copied = service.Project_SaveAs(model, source, destination)
    copied_source = (
        copied / "Devices" / "IMU" / "JY901B" / "Src" / "jy901b_device.c"
    )
    assert copied_source.read_text(encoding="utf-8").endswith(marker)
    assert not (copied / "build").exists()
    assert not (copied / ".fccg" / "cache").exists()
    assert (copied / ".fccg" / "ownership.json").is_file()
    assert ProjectModel_Load(copied / "SilverStar.ssproject").identity.name == (
        "SourceProject"
    )


def test_gui_save_as_action_switches_to_complete_project_copy(
    tmp_path: Path, workspace_root: Path, qapp, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    source = tmp_path / "GuiSource"
    destination = tmp_path / "GuiCopy"
    destination.mkdir()
    model = service.ReferenceProject_Create("GuiSource")
    service.GenerationPlan_Apply(
        model, service.GenerationPlan_Create(model, source)
    )
    window = MainWindow(
        SettingsStore(tmp_path / "gui-save-as.ini"),
        service=service,
        language="en_US",
    )
    try:
        window._Project_Open(source)
        monkeypatch.setattr(
            QFileDialog,
            "getExistingDirectory",
            lambda *_args, **_kwargs: str(destination),
        )
        window._Project_SaveAs()
        deadline = time.monotonic() + 30.0
        while window._active_worker is not None and time.monotonic() < deadline:
            qapp.processEvents()
            # QTest.qWait() keeps the Python GIL for most of its wait on
            # Windows/Python 3.14, starving the Python-heavy save worker.
            time.sleep(0.01)
        assert window._active_worker is None
        assert window._project_root == destination.resolve()
        assert (destination / "SilverStar.ssproject").is_file()
        assert (destination / "Devices" / "IMU" / "JY901B").is_dir()
    finally:
        window.close()
        qapp.processEvents()


def test_required_logging_checkbox_is_active_locked_and_model_forced(
    tmp_path: Path, qapp
) -> None:
    window = MainWindow(SettingsStore(tmp_path / "settings.ini"), language="zh_CN")
    try:
        table = window.flight_configuration_page.logging_table
        required_row = next(
            row
            for row in range(table.rowCount())
            if table.cellWidget(row, 0)
            .findChild(StandardCheckBox)
            .property("streamId")
            == "FLIGHT_LOG_RECORD_EVENT"
        )
        check = table.cellWidget(required_row, 0).findChild(StandardCheckBox)
        assert isinstance(check, LockedCheckBox)
        assert check.isEnabled() and check.isChecked()
        assert check.toolTip() == "系统必需日志"
        check.click()
        assert check.isChecked()
        stream = window.flight_configuration_page.Streams_Get()[required_row]
        assert stream.required and stream.enabled
        window._model.logging_streams = [
            replace(item, enabled=False)
            if item.record == "FLIGHT_LOG_RECORD_EVENT"
            else item
            for item in window._model.logging_streams
        ]
        LoggingProfile_Reconcile(window._model, window._service.catalog)
        assert next(
            item
            for item in window._model.logging_streams
            if item.record == "FLIGHT_LOG_RECORD_EVENT"
        ).enabled
    finally:
        window.close()
        qapp.processEvents()


def test_eide_manual_change_is_detected_and_regenerated(
    tmp_path: Path, workspace_root: Path
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "EideProject"
    model = service.ReferenceProject_Create("EideProject")
    service.GenerationPlan_Apply(
        model, service.GenerationPlan_Create(model, project_root)
    )
    eide = project_root / ".eide" / "eide.yml"
    marker = "\n# MANUAL EIDE CHANGE\n"
    eide.write_text(
        eide.read_text(encoding="utf-8") + marker,
        encoding="utf-8",
        newline="\n",
    )
    plan = service.GenerationPlan_Create(model, project_root)
    operation = next(
        operation for operation in plan.operations if operation.target == ".eide/eide.yml"
    )
    assert operation.operation == "MODIFY"
    assert operation.dangerous
    assert "manually modified" in operation.detail
    service.GenerationPlan_Apply(model, plan, confirm_dangerous=True)
    assert marker.strip() not in eide.read_text(encoding="utf-8")
