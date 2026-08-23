from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from silverstar_fccg.app.version import PRODUCT_NAME, __version__
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.core.view_models import (
    ComponentType,
    ComponentView,
    ResourceRequirementView,
)
from silverstar_fccg.ui.dialogs import NewProjectWizard
from silverstar_fccg.ui.main_window import MainWindow


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
        assert window.pages.count() == 6
        assert window.navigation_list.count() == 6
        assert [
            window.navigation_list.item(index).text()
            for index in range(window.navigation_list.count())
        ] == ["工程", "设备", "板卡与硬件", "飞控配置", "构建", "插件"]
        for index in range(window.pages.count()):
            window.navigation_list.setCurrentRow(index)
            assert window.pages.currentIndex() == index

        window.Language_Apply("en_US")
        assert window.title_label.text() == "SilverStar Flight Controller Code Generator"
        assert [
            window.navigation_list.item(index).text()
            for index in range(window.navigation_list.count())
        ] == [
            "Project",
            "Devices",
            "Board & Hardware",
            "Flight Configuration",
            "Build",
            "Plugins",
        ]
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
        wizard.Catalog_Set(window._component_views)
        assert wizard.pageIds() == [0]
        assert not wizard.identity_page.isComplete()
        wizard.identity_page.name_edit.setText("Reference")
        wizard.identity_page.output_edit.setText(str(tmp_path / "generated"))
        assert wizard.identity_page.isComplete()
        values = wizard.WizardData_Get()
        assert values["name"] == "Reference"
        assert values["firmware_version"] == "0.0.9"
    finally:
        wizard.close()
        window.close()


def test_device_resources_are_manifest_driven(tmp_path: Path, qapp) -> None:
    window = _Window_Create(tmp_path, qapp)
    component = ComponentView(
        component_id="example.device.dynamic",
        name="Dynamic Device",
        component_type=ComponentType.DEVICE,
        component_class="example",
        version="1.2.3",
        requirements=(
            ResourceRequirementView(
                kind="spi",
                name="control_bus",
                assignment="SPI2",
                candidates=("SPI1", "SPI2"),
            ),
            ResourceRequirementView(kind="gpio", name="enable"),
        ),
    )
    try:
        window.devices_page.Components_Set((component,), (component.component_id,))
        qapp.processEvents()
        assert tuple(window.devices_page.device_combos) == ("example",)
        assert (
            window.devices_page.device_combos["example"].currentData()
            == component.component_id
        )
        assert window.devices_page.requirement_table.rowCount() == 2
        assert window.devices_page.requirement_table.item(0, 1).text() == "control_bus"
        source = Path("src/silverstar_fccg/ui/pages/components.py").read_text(encoding="utf-8")
        assert "JY901B" not in source
        assert "BMI088" not in source
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
        assert not window.progress_bar.isVisible()
    finally:
        window.close()
