from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThreadPool, QUrl, Qt
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from silverstar_fccg.app.service import FccgService
from silverstar_fccg.app.version import PRODUCT_NAME, __version__
from silverstar_fccg.build.runner import BuildAction, BuildResult
from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.core.view_models import ComponentType, ComponentView, LoggingStreamView, ToolchainToolView
from silverstar_fccg.generator.assembler import ApplyResult, GenerationPlan
from silverstar_fccg.project.model import (
    HardwareConfiguration,
    LogStreamConfig,
    ProjectIdentity,
    ProjectModel,
    ProjectModel_Save,
)
from silverstar_fccg.project.resources import ResourceAssignments_Resolve
from silverstar_fccg.ui.dialogs import NewProjectWizard
from silverstar_fccg.ui.pages import (
    BoardHardwarePage,
    BuildPage,
    DevicesPage,
    FlightConfigurationPage,
    PluginsPage,
    ProjectPage,
)
from silverstar_fccg.ui.pages.build import DefaultTools_Get
from silverstar_fccg.ui.theme import Theme_Apply, WindowCaption_Apply
from silverstar_fccg.ui.widgets import EngineeringTable, StandardComboBox
from silverstar_fccg.ui.workers import FunctionWorker


class MainWindow(QMainWindow):
    PAGE_CODES = (
        "page.project",
        "page.devices",
        "page.board_hardware",
        "page.flight_configuration",
        "page.build",
        "page.plugins",
    )

    def __init__(
        self,
        settings: SettingsStore,
        *,
        service: FccgService | None = None,
        language: str = "zh_CN",
        theme: str = "light",
    ) -> None:
        super().__init__()
        self._settings = settings
        workspace_root = Path(__file__).resolve().parents[3]
        self._service = service or FccgService(workspace_root)
        self._translator = Translator(language)
        self._theme = theme if theme in {"light", "dark"} else "light"
        self._thread_pool = QThreadPool.globalInstance()
        self._active_worker: FunctionWorker | None = None
        self._worker_result_callback: Callable[[Any], None] | None = None
        self._worker_error_callback: Callable[[str], None] | None = None
        self._component_views: tuple[ComponentView, ...] = ()
        self._model: ProjectModel = self._service.ReferenceProject_Create("SilverStar")
        self._project_root: Path | None = None
        self._generation_plan: GenerationPlan | None = None
        self._displaying_model = False
        self.setWindowTitle(PRODUCT_NAME)
        self.setAcceptDrops(True)
        self.resize(1460, 900)
        self.setMinimumSize(1080, 700)
        self._Ui_Build()
        self._Menu_Build()
        self._Signals_Connect()
        self.Language_Apply(language)
        self.Theme_Apply(self._theme)
        self.build_page.Tools_Set(DefaultTools_Get())
        self._Catalog_Load()
        self._Project_Display()

    def _Ui_Build(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("headerBar")
        header.setMinimumHeight(58)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 6, 14, 6)
        self.title_label = QLabel()
        self.title_label.setObjectName("headerTitle")
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("headerVersion")
        self.credit_label = QLabel()
        self.credit_label.setObjectName("headerCredit")
        self.apply_button = QPushButton()
        self.apply_button.setObjectName("primaryButton")
        self.language_label = QLabel()
        self.language_label.setObjectName("headerControlLabel")
        self.language_combo = StandardComboBox()
        self.language_combo.setObjectName("headerLanguageCombo")
        self.language_combo.addItem("简体中文", "zh_CN")
        self.language_combo.addItem("English", "en_US")
        self.theme_label = QLabel()
        self.theme_label.setObjectName("headerControlLabel")
        self.theme_combo = StandardComboBox()
        self.theme_combo.setObjectName("headerThemeCombo")
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.version_label)
        header_layout.addWidget(self.credit_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.apply_button)
        header_layout.addSpacing(12)
        header_layout.addWidget(self.language_label)
        header_layout.addWidget(self.language_combo)
        header_layout.addWidget(self.theme_label)
        header_layout.addWidget(self.theme_combo)
        root_layout.addWidget(header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 8, 0, 8)
        self.navigation_list = QListWidget()
        self.navigation_list.setObjectName("navigation")
        self.navigation_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for code in self.PAGE_CODES:
            item = QListWidgetItem(code)
            item.setData(Qt.ItemDataRole.UserRole, code)
            self.navigation_list.addItem(item)
        sidebar_layout.addWidget(self.navigation_list)
        body_layout.addWidget(sidebar)

        self.pages = QStackedWidget()
        self.project_page = ProjectPage(self._translator)
        self.devices_page = DevicesPage(self._translator)
        self.board_hardware_page = BoardHardwarePage(self._translator)
        self.flight_configuration_page = FlightConfigurationPage(self._translator)
        self.build_page = BuildPage(self._translator)
        self.plugins_page = PluginsPage(self._translator)
        self._page_widgets = (
            self.project_page,
            self.devices_page,
            self.board_hardware_page,
            self.flight_configuration_page,
            self.build_page,
            self.plugins_page,
        )
        for page in self._page_widgets:
            self.pages.addWidget(page)
        body_layout.addWidget(self.pages, 1)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(central)

        status = QStatusBar()
        self.status_label = QLabel()
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self._Task_Cancel)
        self.cancel_button.setVisible(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setFixedWidth(250)
        self.progress_bar.setVisible(False)
        status.addWidget(self.status_label, 1)
        status.addPermanentWidget(self.cancel_button)
        status.addPermanentWidget(self.progress_bar)
        self.setStatusBar(status)
        self.navigation_list.setCurrentRow(0)

    def _Menu_Build(self) -> None:
        self.file_menu = self.menuBar().addMenu("")
        self.new_action = QAction(self)
        self.new_action.setShortcut("Ctrl+N")
        self.open_action = QAction(self)
        self.open_action.setShortcut("Ctrl+O")
        self.save_action = QAction(self)
        self.save_action.setShortcut("Ctrl+S")
        self.exit_action = QAction(self)
        self.file_menu.addActions(
            (self.new_action, self.open_action, self.save_action)
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)
        self.plugin_menu = self.menuBar().addMenu("")
        self.install_plugin_action = QAction(self)
        self.plugin_menu.addAction(self.install_plugin_action)
        self.help_menu = self.menuBar().addMenu("")
        self.about_action = QAction(self)
        self.help_menu.addAction(self.about_action)

    def _Signals_Connect(self) -> None:
        self.navigation_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.language_combo.currentIndexChanged.connect(self._Language_Selected)
        self.theme_combo.currentIndexChanged.connect(self._Theme_Selected)
        self.apply_button.clicked.connect(self._GenerateOrApply_Request)
        self.new_action.triggered.connect(self._NewProject_Show)
        self.open_action.triggered.connect(self._Project_OpenDialog)
        self.save_action.triggered.connect(self._Project_Save)
        self.exit_action.triggered.connect(self.close)
        self.install_plugin_action.triggered.connect(self._PluginInstall_Dialog)
        self.about_action.triggered.connect(self._About_Show)
        self.project_page.changed.connect(self._ConfigurationDirty_Set)
        self.project_page.outputBrowseRequested.connect(self._OutputDirectory_Browse)
        self.devices_page.selectionChanged.connect(self._DeviceSelection_Change)
        self.board_hardware_page.boardChanged.connect(self._BoardSelection_Change)
        self.board_hardware_page.customSelected.connect(self._CustomHardware_Select)
        self.board_hardware_page.importIocRequested.connect(
            lambda: self._CubeMxImport_Request(False)
        )
        self.board_hardware_page.importDirectoryRequested.connect(
            lambda: self._CubeMxImport_Request(True)
        )
        self.board_hardware_page.exportRequested.connect(
            self._CustomBoardExport_Request
        )
        self.board_hardware_page.autoAssignRequested.connect(
            self._Resources_AutoAssign
        )
        self.board_hardware_page.assignmentChanged.connect(
            self._ResourceAssignment_Change
        )
        self.flight_configuration_page.strategyChanged.connect(
            self._Strategy_Change
        )
        self.flight_configuration_page.modeChanged.connect(self._Mode_Change)
        self.flight_configuration_page.loggingChanged.connect(
            self._ConfigurationDirty_Set
        )
        self.build_page.configurationChanged.connect(self._BuildConfiguration_Change)
        self.build_page.detectionRequested.connect(self._Toolchains_Detect)
        self.build_page.browseRequested.connect(self._ToolchainBrowse)
        self.build_page.actionRequested.connect(self._Build_Request)
        self.plugins_page.installRequested.connect(self._PluginInstall_Dialog)
        self.plugins_page.removeRequested.connect(self._PluginRemove_Request)
        self.plugins_page.detailsRequested.connect(self._PluginDetails_Show)

    def _Catalog_Load(self) -> None:
        self._component_views = self._service.ComponentViews_Get(
            self._translator.language
        )
        self.plugins_page.Components_Set(self._component_views)

    def _Project_Display(self) -> None:
        self._displaying_model = True
        try:
            mcus = tuple(
                component
                for component in self._component_views
                if component.component_type == ComponentType.MCU
            )
            self.project_page.Mcus_Set(mcus, self._model.mcu)
            self.project_page.name_edit.setText(self._model.identity.name)
            self.project_page.version_edit.setText(
                self._model.identity.firmware_version
            )
            self.project_page.output_edit.setText(
                str(self._project_root) if self._project_root else ""
            )
            automatic_ids = {
                self._model.core,
                self._model.os,
                *self._model.protocol_bundles,
                self._model.development_environment,
            }
            self.project_page.AutoComponents_Set(
                component.name
                for component in self._component_views
                if component.component_id in automatic_ids
            )
            devices = tuple(
                component
                for component in self._component_views
                if component.component_type == ComponentType.DEVICE
            )
            self.devices_page.Components_Set(devices, self._model.devices)
            selectable = tuple(
                component
                for component in self._component_views
                if component.selection_kind
            )
            self.flight_configuration_page.Configuration_Set(
                selectable, self._model.strategies, self._model.modes
            )
            self.flight_configuration_page.Streams_Set(
                self._LoggingViews_Get(self._model.logging_streams)
            )
            self.build_page.Project_Set(
                self._model.build.target_profile, self._model.build.configuration
            )
            self._BoardPage_Refresh()
            self._ApplyText_Refresh()
            self.project_page.Status_Set(
                "generated"
                if self._project_root
                and (self._project_root / "SilverStar.ssproject").is_file()
                else "draft"
            )
        finally:
            self._displaying_model = False

    def _BoardPage_Refresh(self) -> None:
        provider = self._service.HardwareProviderForMcu_Get(self._model.mcu)
        custom_selected = self._model.hardware.mode == "custom"
        boards = self._service.BoardCompatibilities_Get(
            self._model, language=self._translator.language
        )
        self.board_hardware_page.Boards_Set(
            boards,
            self._model.board,
            custom_available=bool(provider),
            custom_selected=custom_selected,
            custom_ready=custom_selected and bool(self._model.hardware.snapshot_id),
        )
        requirements = self._service.ResourceRequirementViews_Get(self._model)
        resolution = ResourceAssignments_Resolve(
            self._model, self._service.catalog
        )
        self.board_hardware_page.Resources_Set(requirements, resolution.valid)

    @staticmethod
    def _LoggingViews_Get(
        streams: list[LogStreamConfig],
    ) -> tuple[LoggingStreamView, ...]:
        return tuple(
            LoggingStreamView(
                stream_id=stream.record,
                name=stream.record.removeprefix("FLIGHT_LOG_RECORD_").replace("_", " "),
                enabled=stream.enabled,
                decimation=stream.decimation,
                policy=stream.policy,
                period_us=stream.period_us,
            )
            for stream in streams
        )

    def _ProjectModel_Sync(self) -> None:
        name, output, version, mcu_id = self.project_page.Values_Get()
        if name:
            self._model.identity = ProjectIdentity(
                name=name,
                firmware_version=version or self._model.identity.firmware_version,
                build_target=self._model.identity.build_target,
            )
        if output is not None:
            self._project_root = output.resolve(strict=False)
        if mcu_id and mcu_id != self._model.mcu:
            self._model.mcu = mcu_id
            self._model.resource_assignments = {}
        stream_views = self.flight_configuration_page.Streams_Get()
        if stream_views:
            self._model.logging_streams = [
                LogStreamConfig(
                    record=stream.stream_id,
                    enabled=stream.enabled,
                    policy=stream.policy,
                    decimation=stream.decimation,
                    period_us=stream.period_us,
                )
                for stream in stream_views
            ]

    def _ConfigurationDirty_Set(self, *_unused: object) -> None:
        if self._displaying_model:
            return
        previous_mcu = self._model.mcu
        self._ProjectModel_Sync()
        self._generation_plan = None
        if self._model.mcu != previous_mcu:
            self._BoardPage_Refresh()
        self.project_page.Status_Set("draft")
        self.status_label.setText(
            self._translator.Text_Get("status.configuration_changed_simple")
        )
        self._ApplyText_Refresh()

    def _DeviceSelection_Change(self, component_class: str, component_id: str) -> None:
        self._model.devices = [
            selected
            for selected in self._model.devices
            if self._service.Plugin_Get(selected).component_class != component_class
        ]
        if component_id:
            self._model.devices.append(component_id)
        valid_keys = {
            option.key
            for option in self._service.ResourceRequirementViews_Get(self._model)
        }
        self._model.resource_assignments = {
            key: value
            for key, value in self._model.resource_assignments.items()
            if key in valid_keys
        }
        self._Resources_AutoAssign(silent=True)
        self._ConfigurationDirty_Set()
        self._Project_Display()

    def _BoardSelection_Change(self, board_id: str) -> None:
        board = self._service.Plugin_Get(board_id)
        self._model.board = board_id
        self._model.hardware = HardwareConfiguration(
            mode="board_plugin",
            source_kind=board.board.source_kind if board.board else "third_party",
        )
        self._model.resource_assignments = {}
        self._Resources_AutoAssign(silent=True)
        self._ConfigurationDirty_Set()
        self._Project_Display()

    def _CustomHardware_Select(self) -> None:
        provider = self._service.HardwareProviderForMcu_Get(self._model.mcu)
        if not provider:
            self._Error_Show(self._translator.Text_Get("board.no_provider"))
            return
        self._model.board = ""
        self._model.hardware = HardwareConfiguration(
            mode="custom",
            source_kind="manual_import",
            provider=provider,
        )
        self._model.resource_assignments = {}
        self._ConfigurationDirty_Set()
        self._Project_Display()

    def _CubeMxImport_Request(self, directory: bool) -> None:
        warning = QMessageBox.warning(
            self,
            self._translator.Text_Get("dialog.custom_hardware_risk_title"),
            self._translator.Text_Get("dialog.custom_hardware_risk_message"),
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if warning != QMessageBox.StandardButton.Ok:
            return
        if directory:
            selected = QFileDialog.getExistingDirectory(
                self, self._translator.Text_Get("dialog.import_cubemx_directory")
            )
        else:
            selected, _filter = QFileDialog.getOpenFileName(
                self,
                self._translator.Text_Get("dialog.import_cubemx_ioc"),
                "",
                "STM32CubeMX (*.ioc)",
            )
        if not selected:
            return
        try:
            result = self._service.CubeMxProject_Import(
                Path(selected), self._model, risk_acknowledged=True
            )
            self._model.board = ""
            self._model.hardware = result.hardware
            self._model.resource_assignments = {}
            self._Resources_AutoAssign(silent=True)
        except Exception as error:
            self._Error_Show(str(error))
            return
        self._ConfigurationDirty_Set()
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get(
                "status.cubemx_imported", count=len(result.peripherals)
            )
        )

    def _CustomBoardExport_Request(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            self._translator.Text_Get("dialog.export_board_title"),
            self._translator.Text_Get("field.board_name"),
        )
        if not accepted or not name.strip():
            return
        default_id = "local.board." + "_".join(name.lower().split())
        component_id, accepted = QInputDialog.getText(
            self,
            self._translator.Text_Get("dialog.export_board_title"),
            self._translator.Text_Get("field.plugin_id"),
            text=default_id,
        )
        if not accepted:
            return
        default_path = self._service.workspace_root / "tests" / "artifacts" / f"{name}.ssplugin"
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            self._translator.Text_Get("dialog.export_board_title"),
            str(default_path),
            "SilverStar Plugin (*.ssplugin)",
        )
        if not selected:
            return
        try:
            path = self._service.CustomBoardPlugin_Export(
                self._model,
                Path(selected),
                component_id=component_id.strip(),
                name=name.strip(),
            )
        except Exception as error:
            self._Error_Show(str(error))
            return
        self.status_label.setText(
            self._translator.Text_Get("status.board_exported", path=str(path))
        )

    def _Resources_AutoAssign(self, *, silent: bool = False) -> None:
        result = self._service.Resources_AutoAssign(self._model)
        if not silent:
            self.status_label.setText(
                self._translator.Text_Get(
                    "status.resources_assigned"
                    if result.valid
                    else "status.resources_incomplete",
                    count=len(result.errors),
                )
            )
        self._BoardPage_Refresh()

    def _ResourceAssignment_Change(self, key: str, resource_id: str) -> None:
        if resource_id:
            self._model.resource_assignments[key] = resource_id
        else:
            self._model.resource_assignments.pop(key, None)
        self._ConfigurationDirty_Set()
        self._BoardPage_Refresh()

    def _Strategy_Change(self, slot: str, component_id: object) -> None:
        self._model.strategies[slot] = (
            str(component_id) if component_id is not None else None
        )
        self._ConfigurationDirty_Set()

    def _Mode_Change(self, slot: str, values: object) -> None:
        self._model.modes[slot] = list(values) if isinstance(values, list) else []
        self._ConfigurationDirty_Set()

    def _BuildConfiguration_Change(self, value: str) -> None:
        if self._displaying_model:
            return
        self._model.build = replace(self._model.build, configuration=value)
        self._ConfigurationDirty_Set()

    def _GenerateOrApply_Request(self) -> None:
        self._ProjectModel_Sync()
        if self._project_root is None:
            self._Error_Show(self._translator.Text_Get("error.output_required"))
            return
        try:
            plan = self._service.GenerationPlan_Create(
                self._model, self._project_root
            )
        except Exception as error:
            self._Error_Show(str(error))
            return
        self._generation_plan = plan
        if not plan.valid:
            details = "\n".join(
                f"[{issue.code}] {issue.message}" for issue in plan.validation.issues
            )
            conflicts = "\n".join(
                f"{operation.target}: {operation.detail}"
                for operation in plan.operations
                if operation.operation == "CONFLICT"
            )
            self.project_page.Status_Set(
                "invalid", len(plan.validation.issues)
            )
            self._Error_Show(details or conflicts or self._translator.Text_Get("error.plan_invalid"))
            return
        confirmed = not plan.dangerous or self._DangerousPlan_Confirm(plan)
        if not confirmed:
            return

        def generate(context) -> ApplyResult:
            context.Progress_Report(0.2, "status.generation_running")
            result = self._service.GenerationPlan_Apply(
                self._model,
                plan,
                confirm_dangerous=plan.dangerous,
            )
            context.Progress_Report(1.0, "status.generation_running")
            return result

        self.status_label.setText(
            self._translator.Text_Get("status.generation_running")
        )
        self.Task_Run(generate, self._Generation_Complete)

    def _DangerousPlan_Confirm(self, plan: GenerationPlan) -> bool:
        dialog = QDialog(self)
        dialog.setWindowTitle(
            self._translator.Text_Get("dialog.dangerous_changes_title")
        )
        dialog.resize(900, 520)
        layout = QVBoxLayout(dialog)
        notice = QLabel(
            self._translator.Text_Get("dialog.dangerous_changes_message")
        )
        notice.setWordWrap(True)
        layout.addWidget(notice)
        table = EngineeringTable(
            ("column.operation", "column.target", "column.detail")
        )
        table.Language_Apply(self._translator)
        table.Rows_Set(
            (operation.operation, operation.target, operation.detail)
            for operation in plan.operations
            if operation.dangerous or operation.operation == "CONFLICT"
        )
        layout.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            self._translator.Text_Get("action.continue")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            self._translator.Text_Get("action.cancel")
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _Generation_Complete(self, result: ApplyResult) -> None:
        self._project_root = result.project_root
        self._generation_plan = None
        self.project_page.Status_Set("generated")
        self.status_label.setText(
            self._translator.Text_Get(
                "status.generation_complete",
                added=result.files_added,
                modified=result.files_modified,
            )
        )
        self._Project_Display()

    def _NewProject_Show(self) -> None:
        wizard = NewProjectWizard(self._translator, self)
        wizard.Catalog_Set(self._component_views)
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        values = wizard.WizardData_Get()
        self._model = self._service.ReferenceProject_Create(values["name"])
        if values["mcu"]:
            self._model.mcu = values["mcu"]
        self._model.identity = ProjectIdentity(
            values["name"], values["firmware_version"], self._model.identity.build_target
        )
        self._project_root = Path(values["output_directory"]).resolve(strict=False)
        self._generation_plan = None
        self._Project_Display()

    def _Project_OpenDialog(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._translator.Text_Get("dialog.open_project"),
            str(self._service.workspace_root),
            "SilverStar Project (SilverStar.ssproject *.ssproject)",
        )
        if selected:
            self._Project_Open(Path(selected))

    def _Project_Open(self, path: Path) -> None:
        try:
            self._model = self._service.Project_Open(path)
            self._project_root = (
                path.resolve() if path.is_dir() else path.resolve().parent
            )
        except Exception as error:
            self._Error_Show(str(error))
            return
        self._generation_plan = None
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get(
                "status.project_opened", name=self._model.identity.name
            )
        )

    def _Project_Save(self) -> None:
        self._ProjectModel_Sync()
        if self._project_root is None:
            self._Error_Show(self._translator.Text_Get("error.output_required"))
            return
        try:
            ProjectModel_Save(
                self._model,
                self._project_root / "SilverStar.ssproject",
                self._service.policy,
            )
        except Exception as error:
            self._Error_Show(str(error))
            return
        self.status_label.setText(self._translator.Text_Get("status.project_saved"))

    def _OutputDirectory_Browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._translator.Text_Get("dialog.select_output_directory"),
            str(self._service.workspace_root / "tests" / "generated_projects"),
        )
        if selected:
            self.project_page.OutputDirectory_Set(Path(selected))

    def _PluginInstall_Dialog(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._translator.Text_Get("dialog.install_plugin"),
            str(self._service.workspace_root),
            "SilverStar Plugin (*.ssplugin)",
        )
        if not selected:
            return
        self.Task_Run(
            lambda _context: self._service.Plugin_Install(Path(selected)),
            self._PluginChange_Complete,
        )

    def _PluginRemove_Request(self, component_id: str) -> None:
        manifest = self._service.Plugin_Get(component_id)
        if manifest.source != "installed":
            self._Error_Show(
                self._translator.Text_Get(
                    "error.plugin_builtin_readonly", name=manifest.name
                )
            )
            return
        answer = QMessageBox.question(
            self,
            self._translator.Text_Get("dialog.plugin_remove_title"),
            self._translator.Text_Get(
                "dialog.plugin_remove_message",
                name=manifest.name,
                id=manifest.component_id,
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.Task_Run(
                lambda _context: self._service.Plugin_Remove(component_id),
                self._PluginChange_Complete,
            )

    def _PluginChange_Complete(self, manifest) -> None:
        self._Catalog_Load()
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get("status.plugin_changed", name=manifest.name)
        )

    def _PluginDetails_Show(self, component_id: str) -> None:
        manifest = self._service.Plugin_Get(component_id)
        QMessageBox.information(
            self,
            self._translator.Text_Get("dialog.plugin_details_title"),
            self._translator.Text_Get(
                "plugin.details_template",
                id=manifest.component_id,
                name=manifest.DisplayName_Get(self._translator.language),
                type=manifest.component_type,
                class_name=manifest.component_class or "—",
                version=manifest.version,
                source=manifest.source,
                dependencies=", ".join(item.component_id for item in manifest.dependencies) or "—",
                provides=", ".join(manifest.provides) or "—",
                resources=", ".join(item.kind for item in manifest.resource_requirements) or "—",
            ),
        )

    def _Toolchains_Detect(self) -> None:
        self.Task_Run(
            lambda _context: self._service.Toolchains_Detect(
                self._model.build.tool_paths
            ),
            self._Toolchains_Show,
        )

    def _Toolchains_Show(self, results) -> None:
        display_names = {
            tool.tool_id: tool.display_name for tool in DefaultTools_Get()
        }
        views = tuple(
            ToolchainToolView(
                tool_id=result.tool_id,
                display_name=display_names.get(result.tool_id, result.tool_id),
                command=result.command,
                path=result.path,
                version=result.version,
                status=(
                    "found"
                    if result.available and result.compatible
                    else "invalid" if result.available else "not_found"
                ),
            )
            for result in results
        )
        self.build_page.Tools_Set(views)

    def _ToolchainBrowse(self, tool_id: str) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._translator.Text_Get("dialog.select_tool", tool=tool_id),
        )
        if selected:
            paths = dict(self._model.build.tool_paths)
            paths[tool_id] = selected
            self._model.build = replace(self._model.build, tool_paths=paths)
            self._ConfigurationDirty_Set()

    def _Build_Request(self, action_text: str) -> None:
        if self._project_root is None or not (
            self._project_root / "SilverStar.ssproject"
        ).is_file():
            self._Error_Show(self._translator.Text_Get("error.generate_before_build"))
            return
        actions = {
            "build": BuildAction.BUILD,
            "clean": BuildAction.CLEAN,
            "flash": BuildAction.FLASH,
            "host_tests": BuildAction.HOST_TESTS,
            "architecture_check": BuildAction.ARCHITECTURE_CHECK,
            "power10_check": BuildAction.POWER10_CHECK,
            "static_analysis": BuildAction.STATIC_ANALYSIS,
            "artifact_check": BuildAction.ARTIFACT_CHECK,
        }
        action = actions.get(action_text)
        if action is None:
            return
        self.Task_Run(
            lambda context: self._service.Build_Run(
                self._model, self._project_root, action, context.token
                if hasattr(context, "token")
                else context
            ),
            self._Build_Complete,
        )

    def _Build_Complete(self, result: BuildResult) -> None:
        key = "status.build_succeeded" if result.succeeded else "status.build_failed"
        self.status_label.setText(
            self._translator.Text_Get(key, action=result.action.value)
        )
        if not result.succeeded:
            self._Error_Show(result.output[-6000:])

    def Task_Run(
        self,
        function: Callable[[Any], Any],
        result_callback: Callable[[Any], None],
        error_callback: Callable[[str], None] | None = None,
    ) -> bool:
        if self._active_worker is not None:
            self._Error_Show(
                self._translator.Text_Get("error.background_task_active")
            )
            return False
        worker = FunctionWorker(function)
        self._active_worker = worker
        self._worker_result_callback = result_callback
        self._worker_error_callback = error_callback
        worker.signals.progress.connect(self._Task_Progress)
        worker.signals.result.connect(self._Task_Result)
        worker.signals.error.connect(self._Task_Error)
        worker.signals.cancelled.connect(
            lambda: self.status_label.setText(
                self._translator.Text_Get("status.task_cancelled")
            )
        )
        worker.signals.finished.connect(self._Task_Finish)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.cancel_button.setVisible(True)
        self._Actions_SetEnabled(False)
        self._thread_pool.start(worker)
        return True

    def _Task_Progress(self, progress: float, code: str) -> None:
        self.progress_bar.setValue(int(max(0.0, min(1.0, progress)) * 1000))
        self.status_label.setText(self._translator.Text_Get(code))

    def _Task_Result(self, result: Any) -> None:
        if self._worker_result_callback is not None:
            self._worker_result_callback(result)

    def _Task_Error(self, message: str, traceback_text: str) -> None:
        logging.error("Background task failed:\n%s", traceback_text)
        if self._worker_error_callback is not None:
            self._worker_error_callback(message)
        else:
            self._Error_Show(message)

    def _Task_Finish(self) -> None:
        self._active_worker = None
        self._worker_result_callback = None
        self._worker_error_callback = None
        self.progress_bar.setVisible(False)
        self.cancel_button.setVisible(False)
        self._Actions_SetEnabled(True)

    def _Task_Cancel(self) -> None:
        if self._active_worker is not None:
            self._active_worker.Worker_Cancel()

    def _Actions_SetEnabled(self, enabled: bool) -> None:
        self.apply_button.setEnabled(enabled)
        self.new_action.setEnabled(enabled)
        self.open_action.setEnabled(enabled)
        self.install_plugin_action.setEnabled(enabled)

    def _ApplyText_Refresh(self) -> None:
        existing = bool(
            self._project_root
            and (self._project_root / "SilverStar.ssproject").is_file()
        )
        self.apply_button.setText(
            self._translator.Text_Get(
                "action.apply_configuration" if existing else "action.generate_project"
            )
        )

    def _Language_Selected(self) -> None:
        language = str(self.language_combo.currentData() or "zh_CN")
        if language != self._translator.language:
            self.Language_Apply(language)

    def _Theme_Selected(self) -> None:
        theme = str(self.theme_combo.currentData() or "light")
        if theme != self._theme:
            self.Theme_Apply(theme)

    def Language_Apply(self, language: str) -> None:
        self._translator.Language_Set(language)
        self.title_label.setText(self._translator.Text_Get("app.title"))
        self.credit_label.setText(self._translator.Text_Get("app.credit"))
        self.language_label.setText(
            self._translator.Text_Get("label.interface_language")
        )
        self.theme_label.setText(self._translator.Text_Get("label.theme"))
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItem(self._translator.Text_Get("theme.light"), "light")
        self.theme_combo.addItem(self._translator.Text_Get("theme.dark"), "dark")
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self._theme)))
        self.theme_combo.blockSignals(False)
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(language))
        )
        self.language_combo.blockSignals(False)
        for index, code in enumerate(self.PAGE_CODES):
            self.navigation_list.item(index).setText(
                self._translator.Text_Get(code)
            )
        for page in self._page_widgets:
            page.Language_Apply(self._translator)
        self.file_menu.setTitle(self._translator.Text_Get("menu.file"))
        self.plugin_menu.setTitle(self._translator.Text_Get("menu.plugins"))
        self.help_menu.setTitle(self._translator.Text_Get("menu.help"))
        for action, key in (
            (self.new_action, "action.new_project"),
            (self.open_action, "action.open_project"),
            (self.save_action, "action.save_project"),
            (self.exit_action, "action.exit"),
            (self.install_plugin_action, "action.install_plugin"),
            (self.about_action, "action.about"),
        ):
            action.setText(self._translator.Text_Get(key))
        self.cancel_button.setText(
            self._translator.Text_Get("action.cancel_task")
        )
        self._settings.Value_Set("language", language)
        if self._component_views:
            self._Catalog_Load()
            self._Project_Display()
        self._ApplyText_Refresh()

    def Theme_Apply(self, theme: str) -> None:
        self._theme = theme if theme in {"light", "dark"} else "light"
        application = QApplication.instance()
        if application is not None:
            Theme_Apply(application, self._theme)
        WindowCaption_Apply(self, self._theme)
        self._settings.Value_Set("theme", self._theme)

    def _About_Show(self) -> None:
        QMessageBox.about(
            self,
            PRODUCT_NAME,
            self._translator.Text_Get("about.text", version=__version__),
        )

    def _Error_Show(self, message: str) -> None:
        QMessageBox.critical(
            self, PRODUCT_NAME, message or self._translator.Text_Get("status.failed")
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if any(
            Path(url.toLocalFile()).suffix.casefold() in {".ssproject", ".ssplugin"}
            or Path(url.toLocalFile()).name == "SilverStar.ssproject"
            for url in urls
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.casefold() == ".ssplugin":
                self.Task_Run(
                    lambda _context, archive=path: self._service.Plugin_Install(archive),
                    self._PluginChange_Complete,
                )
                break
            if path.name == "SilverStar.ssproject" or path.suffix.casefold() == ".ssproject":
                self._Project_Open(path)
                break
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._active_worker is not None:
            answer = QMessageBox.question(
                self,
                PRODUCT_NAME,
                self._translator.Text_Get("dialog.close_active_task"),
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._active_worker.Worker_Cancel()
        event.accept()
