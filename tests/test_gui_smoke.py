from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel

from silverstar_fccg.app.service import FccgService
from silverstar_fccg.app.version import PRODUCT_NAME, __version__
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.ui.dialogs import NewProjectWizard
from silverstar_fccg.ui.main_window import MainWindow
from silverstar_fccg.ui.widgets import LockedCheckBox


def _Window_Create(tmp_path: Path, qapp) -> MainWindow:
    window = MainWindow(SettingsStore(tmp_path / "settings.ini"))
    window.show()
    qapp.processEvents()
    return window


def test_main_window_shell_navigation_theme_and_language(tmp_path: Path, qapp) -> None:
    window = _Window_Create(tmp_path, qapp)
    try:
        assert window.windowTitle() == PRODUCT_NAME
        assert window.version_label.text() == f"v{__version__}"
        assert window.pages.count() == 4
        assert window.navigation_list.count() == 4
        assert not hasattr(window, "project_page")
        assert not hasattr(window, "plugins_page")
        assert [
            window.navigation_list.item(index).text()
            for index in range(window.navigation_list.count())
        ] == ["设备", "飞控配置", "硬件连接", "构建"]
        assert not hasattr(window.build_page, "configuration_combo")
        assert set(window.build_page.action_buttons) == {
            "build",
            "clean",
            "build_release",
            "host_tests",
            "architecture_check",
            "power10_check",
            "static_analysis",
            "artifact_check",
        }
        assert "flash" not in window.build_page.action_buttons
        assert window.save_as_action.shortcut().toString() == "Ctrl+Shift+S"
        assert window.plugin_manager_dialog.panel.plugin_table.rowCount() == 23
        for index in range(window.pages.count()):
            window.navigation_list.setCurrentRow(index)
            assert window.pages.currentIndex() == index

        window.Language_Apply("en_US")
        assert window.title_label.text() == "SilverStar Flight Controller Code Generator"
        assert [
            window.navigation_list.item(index).text()
            for index in range(window.navigation_list.count())
        ] == [
            "Devices",
            "Flight Configuration",
            "Hardware Connection",
            "Build",
        ]
        assert window.build_page.action_buttons["build_release"].text() == (
            "Build Release"
        )
        window.Theme_Apply("dark")
        assert window._theme == "dark"
        assert "#0B2447" in qapp.styleSheet()
        window.Theme_Apply("light")
        assert "#123A78" in qapp.styleSheet()
    finally:
        window.close()


def test_new_project_wizard_is_one_step_and_requires_identity(tmp_path: Path, qapp) -> None:
    window = _Window_Create(tmp_path, qapp)
    wizard = NewProjectWizard(window._translator, window)
    try:
        wizard.show()
        qapp.processEvents()
        assert isinstance(wizard, QDialog)
        assert wizard.height() <= 220
        assert wizard.windowTitle() == "新建 SilverStar 飞控工程"
        assert not wizard.identity_page.isComplete()
        assert not wizard.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        ).isEnabled()
        page = wizard.identity_page
        assert page.name_label.alignment() == (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        assert page.output_label.alignment() == (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        def center_y(widget) -> float:
            top_left = widget.mapTo(wizard, QPoint(0, 0))
            return top_left.y() + widget.height() / 2

        assert abs(center_y(page.name_label) - center_y(page.name_edit)) <= 2
        assert abs(center_y(page.output_label) - center_y(page.output_edit)) <= 2
        assert page.name_edit.mapTo(wizard, QPoint(0, 0)).x() == (
            page.output_edit.mapTo(wizard, QPoint(0, 0)).x()
        )
        assert page.name_edit.height() == page.output_edit.height()
        wizard.identity_page.name_edit.setText("Reference")
        wizard.identity_page.output_edit.setText(str(tmp_path / "generated"))
        assert wizard.identity_page.isComplete()
        assert wizard.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        ).isEnabled()
        values = wizard.WizardData_Get()
        assert values["name"] == "Reference"
        assert set(values) == {"name", "output_directory"}
        window.Theme_Apply("dark")
        wizard.Language_Apply(window._translator)
        qapp.processEvents()
        window.Language_Apply("en_US")
        wizard.Language_Apply(window._translator)
        assert page.name_label.text() == "Project Name"
        assert page.output_label.text() == "Output Directory"
        window.Theme_Apply("light")
        for language in ("zh_CN", "en_US"):
            window.Language_Apply(language)
            wizard.Language_Apply(window._translator)
            for theme in ("light", "dark"):
                window.Theme_Apply(theme)
                qapp.processEvents()
                screenshot = tmp_path / f"new-project-{language}-{theme}.png"
                assert wizard.grab().save(str(screenshot))
                assert screenshot.stat().st_size > 0
                assert wizard.height() <= 220
    finally:
        wizard.close()
        window.close()


def test_devices_page_is_physical_and_capabilities_are_on_flight_page(
    tmp_path: Path, qapp
) -> None:
    window = _Window_Create(tmp_path, qapp)
    try:
        qapp.processEvents()
        assert tuple(window.devices_page.device_combos) == (
            "imu0",
            "gnss0",
            "telemetry0",
            "maintenance0",
        )
        assert window.devices_page.mcu_combo.currentData() == (
            "silverstar.mcu.stm32f407vet6"
        )
        assert not hasattr(window.devices_page, "capability_table")
        assert not hasattr(window.devices_page, "capability_source_combos")
        assert window._model.hardware.mode == "unselected"
        assert window.board_hardware_page.board_combo.currentIndex() == 0
        assert window.board_hardware_page.board_combo.currentData() == "__unselected__"
        assert not window.board_hardware_page.preparation_widget.isVisible()
        assert window.devices_page.other_group.isVisible()
        assert window.devices_page.other_empty_label.isVisible()
        assert not hasattr(window.devices_page, "requirement_table")
        assert not window.devices_page.add_buttons
        assert any(
            "维护协议版本：0.0" in label.text()
            and "适用固件版本：0.0.9" in label.text()
            for label in window.devices_page.findChildren(QLabel)
        )
        source = Path("src/silverstar_fccg/ui/pages/components.py").read_text(encoding="utf-8")
        assert "JY901B" not in source
        assert "BMI088" not in source
        jy901b_summary = window.devices_page.findChild(
            QLabel, "deviceCapabilitySummary_imu0"
        )
        assert jy901b_summary is not None
        assert "加速度" in jy901b_summary.text()

        capability_table = window.flight_configuration_page.capability_table
        assert capability_table.rowCount() == 7
        assert all(
            capability_table.cellWidget(row, 2) is None
            for row in range(capability_table.rowCount())
        )
        statuses = {
            capability_table.item(row, 0).toolTip(): capability_table.item(row, 1).text()
            for row in range(capability_table.rowCount())
        }
        assert statuses["imu.acceleration"] == "使用"
        assert statuses["magnetometer.field"] == "未使用"
        assert statuses["attitude.external"] == "未使用"

        logging_table = window.flight_configuration_page.logging_table
        assert logging_table.horizontalHeaderItem(1).text() == "日志记录 / 日志流"
        assert logging_table.item(0, 1).text() == "完整飞行样本"
        assert abs(logging_table.columnWidth(1) - logging_table.columnWidth(5)) <= 2
        assert any(
            isinstance(
                logging_table.cellWidget(row, 0).findChild(LockedCheckBox),
                LockedCheckBox,
            )
            for row in range(logging_table.rowCount())
        )
    finally:
        window.close()


def test_background_worker_updates_shared_progress(tmp_path: Path, qapp) -> None:
    window = _Window_Create(tmp_path, qapp)
    results: list[int] = []

    def task(context) -> int:
        context.Progress_Report(0.25, "status.ready")
        context.Progress_Report(1.0, "status.ready")
        return 42

    try:
        assert window.Task_Run(task, results.append)
        deadline = time.monotonic() + 3.0
        while window._active_worker is not None and time.monotonic() < deadline:
            qapp.processEvents()
            QTest.qWait(5)
        assert window._active_worker is None
        assert results == [42]
        QTest.qWait(400)
        qapp.processEvents()
        assert not window.progress_bar.isVisible()
    finally:
        window.close()


def test_save_prepare_build_and_advanced_actions_use_shared_worker(
    tmp_path: Path, workspace_root: Path, qapp, monkeypatch
) -> None:
    service = FccgService(workspace_root)
    project_root = tmp_path / "ProgressActions"
    model = service.ReferenceProject_Create("ProgressActions")
    service.Project_Save(model, project_root)
    window = MainWindow(
        SettingsStore(tmp_path / "progress-actions.ini"),
        service=service,
    )
    invocations: list[tuple[str, bool]] = []

    def task_run(
        function,
        _result_callback,
        _error_callback=None,
        *,
        indeterminate=False,
        line_callback=None,
    ):
        invocations.append((function.__name__, indeterminate))
        return True

    try:
        window._Project_Open(project_root)
        monkeypatch.setattr(window, "Task_Run", task_run)
        window._Project_Save()
        window._HardwarePrepare_Request()
        window._Build_Request("build")
        descriptor_before_release = window._model.Dictionary_Get()
        window._Build_Request("build_release")
        assert window._model.Dictionary_Get() == descriptor_before_release
        window._Build_Request("architecture_check")
    finally:
        window.close()

    assert invocations == [
        ("save", False),
        ("prepare", False),
        ("build", False),
        ("build", False),
        ("build", False),
    ]
