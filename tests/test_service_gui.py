from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from silverstar_fccg.app.service import FccgService
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.ui.dialogs import NewProjectWizard
from silverstar_fccg.ui.main_window import MainWindow


def test_gui_service_loads_catalog_opens_project_and_previews(
    tmp_path: Path, workspace_root: Path, qapp
) -> None:
    service = FccgService(workspace_root)
    window = MainWindow(
        SettingsStore(tmp_path / "service-settings.ini"),
        service=service,
        language="en_US",
    )
    wizard = NewProjectWizard(window._translator, window)
    project_root = tmp_path / "GeneratedReference"
    model = service.ReferenceProject_Create("GeneratedReference")
    initial_plan = service.GenerationPlan_Create(model, project_root)
    assert initial_plan.validation.valid
    service.GenerationPlan_Apply(model, initial_plan)
    project_file = project_root / "SilverStar.ssproject"
    try:
        assert window.plugins_page.plugin_table.rowCount() == 23
        assert window.plugins_page.plugin_table.columnCount() == 9
        assert len(window.devices_page.device_combos) == 4
        wizard.Catalog_Set(window._component_views)
        wizard_values = wizard.WizardData_Get()
        assert wizard_values["mcu"] == "silverstar.mcu.stm32f407vet6"
        window._Project_Open(project_file)
        assert window.project_page.name_edit.text() == "GeneratedReference"
        logging_table = window.flight_configuration_page.logging_table
        assert logging_table.rowCount() == 28
        periodic_row = next(
            row
            for row in range(logging_table.rowCount())
            if logging_table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )
            == "FLIGHT_LOG_RECORD_TELEMETRY_DIAG"
        )
        period_editor = logging_table.cellWidget(periodic_row, 3)
        period_editor.setValue(250_000)
        window._ProjectModel_Sync()
        assert next(
            stream
            for stream in window._model.logging_streams
            if stream.record == "FLIGHT_LOG_RECORD_TELEMETRY_DIAG"
        ).period_us == 250_000
        normal_plan = service.GenerationPlan_Create(window._model, project_root)
        assert normal_plan.validation.valid
        assert not normal_plan.dangerous
        assert any(
            operation.target == "SilverStar.ssproject"
            for operation in normal_plan.operations
        )
        device_id = "silverstar.device.imu.jy901b"
        window._DeviceSelection_Change("imu", "")
        assert device_id not in window._model.devices
        window._DeviceSelection_Change("imu", device_id)
        assert device_id in window._model.devices
        assert service.Resources_AutoAssign(window._model).valid
        resource_key = "silverstar.board.silverstar_0_5:power_output_1"
        resource_row = next(
            row
            for row in range(window.board_hardware_page.resource_table.rowCount())
            if "power_output_1"
            in window.board_hardware_page.resource_table.item(row, 0).text()
        )
        resource_editor = window.board_hardware_page.resource_table.cellWidget(
            resource_row, 3
        )
        resource_editor.setCurrentIndex(0)
        qapp.processEvents()
        assert resource_key not in window._model.resource_assignments
        window._Resources_AutoAssign()
        assert resource_key in window._model.resource_assignments
        documentation = service.PluginDocumentationRoot_Get(
            "silverstar.protocol.reference_v0"
        )
        assert (documentation / "AIR_PROTOCOL.md").is_file()
        assert (project_root / "GeneratedReference.code-workspace").is_file()
        assert (project_root / ".vscode" / "tasks.json").is_file()
        assert (project_root / ".eide" / "eide.yml").is_file()
    finally:
        wizard.close()
        window.close()
        qapp.processEvents()
