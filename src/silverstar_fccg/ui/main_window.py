from __future__ import annotations

import logging
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThreadPool, QTimer, QUrl, Qt
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
from silverstar_fccg.build.runner import BuildAction, BuildProgress, BuildResult
from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.errors import FccgError
from silverstar_fccg.core.settings import SettingsStore
from silverstar_fccg.core.view_models import ComponentType, ComponentView, LoggingStreamView, ToolchainToolView
from silverstar_fccg.generator.assembler import ApplyResult, GenerationPlan
from silverstar_fccg.project.model import (
    DeviceInstance,
    HardwareConfiguration,
    LogStreamConfig,
    ProjectModel,
)
from silverstar_fccg.project.logging import (
    LogAvailability_Get,
    LogPolicyLevel,
    ProtocolLogDefinitions_Get,
)
from silverstar_fccg.project.lifecycle import ProjectLifecycleState
from silverstar_fccg.project.configuration import ProjectConfigurationResult
from silverstar_fccg.project.validation import ValidationIssue
from silverstar_fccg.ui.dialogs import NewProjectWizard
from silverstar_fccg.ui.message_box import MessageBoxButtons_Localize
from silverstar_fccg.ui.pages import (
    BoardHardwarePage,
    BuildPage,
    DevicesPage,
    FlightConfigurationPage,
    PluginManagerDialog,
)
from silverstar_fccg.ui.pages.build import DefaultTools_Get
from silverstar_fccg.ui.theme import Theme_Apply, WindowCaption_Apply
from silverstar_fccg.ui.widgets import EngineeringTable, HeaderComboBox
from silverstar_fccg.ui.workers import FunctionWorker


class MainWindow(QMainWindow):
    PAGE_CODES = (
        "page.devices",
        "page.flight_configuration",
        "page.board_hardware",
        "page.build",
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
        self._worker_error_callback: Callable[[object], None] | None = None
        self._worker_line_callback: Callable[[str], None] | None = None
        self._progress_hide_timer = QTimer(self)
        self._progress_hide_timer.setSingleShot(True)
        self._progress_hide_timer.timeout.connect(self._Progress_CompletionHide)
        self._component_views: tuple[ComponentView, ...] = ()
        self._model: ProjectModel = self._service.ProjectDraft_Create("SilverStar")
        self._project_root: Path | None = None
        self._generation_plan: GenerationPlan | None = None
        self._displaying_model = False
        self._project_state = ProjectLifecycleState.DRAFT
        self._pending_build_action: str | None = None
        self._validation_focus_widget: QWidget | None = None
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
        self.current_project_label = QLabel()
        self.current_project_label.setObjectName("headerControlLabel")
        self.current_project_value = QLabel()
        self.current_project_value.setObjectName("headerProjectValue")
        self.language_label = QLabel()
        self.language_label.setObjectName("headerControlLabel")
        self.language_combo = HeaderComboBox("headerLanguageCombo")
        self.language_combo.addItem("简体中文", "zh_CN")
        self.language_combo.addItem("English", "en_US")
        self.theme_label = QLabel()
        self.theme_label.setObjectName("headerControlLabel")
        self.theme_combo = HeaderComboBox("headerThemeCombo")
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.version_label)
        header_layout.addWidget(self.credit_label)
        header_layout.addSpacing(16)
        header_layout.addWidget(self.current_project_label)
        header_layout.addWidget(self.current_project_value)
        header_layout.addStretch(1)
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
        self.devices_page = DevicesPage(self._translator)
        self.flight_configuration_page = FlightConfigurationPage(self._translator)
        self.board_hardware_page = BoardHardwarePage(self._translator)
        self.build_page = BuildPage(self._translator)
        self._page_widgets = (
            self.devices_page,
            self.flight_configuration_page,
            self.board_hardware_page,
            self.build_page,
        )
        for page in self._page_widgets:
            self.pages.addWidget(page)
        self.plugin_manager_dialog = PluginManagerDialog(self._translator, self)
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
        self.save_as_action = QAction(self)
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.exit_action = QAction(self)
        self.file_menu.addActions(
            (self.new_action, self.open_action, self.save_action, self.save_as_action)
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)
        self.plugin_menu = self.menuBar().addMenu("")
        self.manage_plugins_action = QAction(self)
        self.install_plugin_action = QAction(self)
        self.refresh_plugins_action = QAction(self)
        self.plugin_menu.addActions(
            (
                self.manage_plugins_action,
                self.install_plugin_action,
                self.refresh_plugins_action,
            )
        )
        self.help_menu = self.menuBar().addMenu("")
        self.about_action = QAction(self)
        self.help_menu.addAction(self.about_action)

    def _Signals_Connect(self) -> None:
        self.navigation_list.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.language_combo.currentIndexChanged.connect(self._Language_Selected)
        self.theme_combo.currentIndexChanged.connect(self._Theme_Selected)
        self.new_action.triggered.connect(self._NewProject_Show)
        self.open_action.triggered.connect(self._Project_OpenDialog)
        self.save_action.triggered.connect(self._Project_Save)
        self.save_as_action.triggered.connect(self._Project_SaveAs)
        self.exit_action.triggered.connect(self.close)
        self.manage_plugins_action.triggered.connect(self._PluginManager_Show)
        self.install_plugin_action.triggered.connect(self._PluginInstall_Dialog)
        self.refresh_plugins_action.triggered.connect(self._Plugins_Refresh)
        self.about_action.triggered.connect(self._About_Show)
        self.devices_page.mcuChanged.connect(self._McuSelection_Change)
        self.devices_page.instanceChanged.connect(self._DeviceInstance_Change)
        self.devices_page.instanceAddRequested.connect(self._DeviceInstance_Add)
        self.devices_page.otherDeviceToggled.connect(self._OtherDevice_Toggle)
        self.devices_page.installRequested.connect(self._PluginInstall_Dialog)
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
        self.board_hardware_page.prepareRequested.connect(
            self._HardwarePrepare_Request
        )
        self.flight_configuration_page.strategyChanged.connect(
            self._Strategy_Change
        )
        self.flight_configuration_page.modeChanged.connect(self._Mode_Change)
        self.flight_configuration_page.capabilitySourceChanged.connect(
            self._CapabilitySource_Change
        )
        self.flight_configuration_page.loggingChanged.connect(
            self._Logging_Change
        )
        self.build_page.detectionRequested.connect(self._Toolchains_Detect)
        self.build_page.browseRequested.connect(self._ToolchainBrowse)
        self.build_page.actionRequested.connect(self._Build_Request)
        self.plugin_manager_dialog.panel.installRequested.connect(
            self._PluginInstall_Dialog
        )
        self.plugin_manager_dialog.panel.removeRequested.connect(
            self._PluginRemove_Request
        )

    def _Catalog_Load(self) -> None:
        self._component_views = self._service.ComponentViews_Get(
            self._translator.language
        )
        self.plugin_manager_dialog.Components_Set(self._component_views)

    def _Project_Display(self) -> None:
        self._ValidationIssue_Clear()
        self._displaying_model = True
        try:
            mcus = tuple(
                component
                for component in self._component_views
                if component.component_type == ComponentType.MCU
                and component.vendor.casefold() == "stm32"
            )
            devices = tuple(
                component
                for component in self._component_views
                if component.component_type == ComponentType.DEVICE
            )
            configuration = self._service.ProjectConfiguration_Reconcile(
                self._model
            )
            protocol_versions = ("", "", "")
            for protocol_id in self._model.protocol_bundles:
                contribution = self._service.Plugin_Get(protocol_id).protocol
                if contribution is not None:
                    protocol_versions = (
                        contribution.firmware_version,
                        contribution.maintenance_protocol_version,
                        contribution.documentation_version,
                    )
                    break
            self.devices_page.Configuration_Set(
                mcus,
                self._model.mcu,
                devices,
                self._service.DeviceInstanceViews_Get(
                    self._model, self._translator.language
                ),
                protocol_versions,
            )
            selectable = tuple(
                component
                for component in self._component_views
                if component.selection_kind
            )
            self.flight_configuration_page.Configuration_Set(
                selectable,
                self._model.strategies,
                self._model.modes,
                configuration.strategy_availability,
                configuration.mode_availability,
            )
            self.flight_configuration_page.Capabilities_Set(
                self._service.CapabilityUsageViews_Get(
                    self._model, self._translator.language
                )
            )
            definitions = ProtocolLogDefinitions_Get(
                self._model, self._service.catalog
            )
            self.flight_configuration_page.Streams_Set(
                self._LoggingViews_Get(definitions)
            )
            self.build_page.Project_Set(
                self._model.build.target_profile
            )
            self._BoardPage_Refresh()
            self._HeaderProject_Refresh()
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
            prepared=(
                self._project_root is not None
                and self._service.Project_HardwarePrepared_Is(
                    self._model, self._project_root
                )
            ),
            hardware_mode=self._model.hardware.mode,
        )
        requirements = self._service.ResourceRequirementViews_Get(
            self._model, self._translator.language
        )
        configuration = self._service.ProjectConfiguration_Reconcile(self._model)
        self.board_hardware_page.Resources_Set(
            requirements,
            configuration.resource_resolution.valid,
            hardware_selected=self._model.hardware.mode != "unselected",
        )

    def _LoggingViews_Get(
        self,
        definitions,
    ) -> tuple[LoggingStreamView, ...]:
        streams = {stream.record: stream for stream in self._model.logging_streams}
        views: list[LoggingStreamView] = []
        for definition in definitions:
            stream = streams[definition.record]
            availability = LogAvailability_Get(
                definition, self._model, self._service.catalog
            )
            reason = ""
            if not availability.available:
                reason = self._translator.Text_Get(
                    availability.reason_code,
                    missing=", ".join(availability.missing),
                )
            description = self._translator.Text_Get(
                "logging.record_metadata",
                id=definition.record_id,
                version=definition.version,
                size=definition.payload_size,
            )
            views.append(
                LoggingStreamView(
                    stream_id=stream.record,
                    name=definition.DisplayName_Get(self._translator.language),
                    enabled=stream.enabled,
                    decimation=stream.decimation,
                    description=description,
                    policy=stream.policy,
                    period_us=stream.period_us,
                    level=definition.level.value,
                    required=definition.level == LogPolicyLevel.REQUIRED,
                    available=availability.available,
                    availability_reason=reason,
                    record_id=definition.record_id,
                    version=definition.version,
                    payload_size=definition.payload_size,
                )
            )
        return tuple(views)

    def _LoggingState_Apply(self, model: ProjectModel) -> None:
        stream_views = self.flight_configuration_page.Streams_Get()
        if stream_views:
            model.logging_streams = [
                LogStreamConfig(
                    record=stream.stream_id,
                    enabled=stream.enabled,
                    policy=stream.policy,
                    decimation=stream.decimation,
                    period_us=stream.period_us,
                )
                for stream in stream_views
            ]

    def _ProjectModel_Sync(self) -> None:
        self._LoggingState_Apply(self._model)

    def _ProjectConfiguration_Change(
        self,
        mutator: Callable[[ProjectModel], None],
        *,
        status_key: str = "status.configuration_changed_simple",
    ) -> ProjectConfigurationResult | None:
        if self._displaying_model:
            return None
        candidate = deepcopy(self._model)
        self._LoggingState_Apply(candidate)
        try:
            mutator(candidate)
            result = self._service.ProjectConfiguration_Reconcile(candidate)
        except Exception as error:
            self._Error_Show(error)
            self._Project_Display()
            return None
        self._model = result.model
        self._generation_plan = None
        self._project_state = ProjectLifecycleState.DIRTY
        self._Project_Display()
        if result.notices:
            self.status_label.setText(
                self._translator.Text_Get(result.notices[-1].code)
            )
        else:
            self.status_label.setText(
                self._translator.Text_Get(
                    "status.configuration_reconciled"
                    if result.cleared_assignments or result.pending_assignments
                    else status_key,
                    retained=result.retained_assignments,
                    cleared=result.cleared_assignments,
                    pending=result.pending_assignments,
                )
            )
        self._HeaderProject_Refresh()
        return result

    def _ConfigurationDirty_Set(self, *_unused: object) -> None:
        if self._displaying_model:
            return
        self._generation_plan = None
        self._project_state = ProjectLifecycleState.DIRTY
        self.status_label.setText(
            self._translator.Text_Get("status.configuration_changed_simple")
        )
        self._HeaderProject_Refresh()

    def _McuSelection_Change(self, component_id: str) -> None:
        if self._displaying_model or not component_id or component_id == self._model.mcu:
            return
        self._ProjectConfiguration_Change(
            lambda candidate: setattr(candidate, "mcu", component_id)
        )

    def _DeviceInstance_Change(self, instance_id: str, component_id: str) -> None:
        if self._displaying_model:
            return
        def change(candidate: ProjectModel) -> None:
            existing = candidate.DeviceInstance_Get(instance_id)
            if component_id:
                replacement = DeviceInstance(instance_id, component_id)
                if existing is None:
                    candidate.device_instances.append(replacement)
                else:
                    candidate.device_instances = [
                        replacement if item.instance_id == instance_id else item
                        for item in candidate.device_instances
                    ]
            else:
                candidate.device_instances = [
                    item
                    for item in candidate.device_instances
                    if item.instance_id != instance_id
                ]

        self._ProjectConfiguration_Change(change)

    def _DeviceInstance_Add(self, component_class: str) -> None:
        candidates = sorted(
            (
                component
                for component in self._component_views
                if component.component_type == ComponentType.DEVICE
                and component.component_class == component_class
                and component.multi_instance_ready
            ),
            key=lambda item: item.name,
        )
        if not candidates:
            return
        selected = [
            instance
            for instance in self._model.device_instances
            if self._service.Plugin_Get(instance.plugin).component_class
            == component_class
        ]
        project_max = max(component.project_max for component in candidates)
        if len(selected) >= project_max:
            return
        instance_id = self._DeviceInstanceId_Next(component_class)
        self._ProjectConfiguration_Change(
            lambda candidate: candidate.device_instances.append(
                DeviceInstance(instance_id, candidates[0].component_id)
            )
        )

    def _OtherDevice_Toggle(self, component_id: str, selected: bool) -> None:
        manifest = self._service.Plugin_Get(component_id)
        def change(candidate: ProjectModel) -> None:
            if selected:
                if any(
                    instance.plugin == component_id
                    for instance in candidate.device_instances
                ):
                    return
                candidate.device_instances.append(
                    DeviceInstance(
                        self._DeviceInstanceId_Next(
                            manifest.component_class or "sensor",
                            model=candidate,
                        ),
                        component_id,
                    )
                )
            else:
                candidate.device_instances = [
                    instance
                    for instance in candidate.device_instances
                    if instance.plugin != component_id
                ]

        self._ProjectConfiguration_Change(change)

    def _CapabilitySource_Change(self, capability: str, instance_id: str) -> None:
        def change(candidate: ProjectModel) -> None:
            if instance_id:
                candidate.capability_source_overrides[capability] = instance_id
            else:
                candidate.capability_source_overrides.pop(capability, None)

        self._ProjectConfiguration_Change(change)

    def _DeviceInstanceId_Next(
        self, component_class: str, *, model: ProjectModel | None = None
    ) -> str:
        prefix = "maintenance" if component_class == "console" else component_class
        prefix = prefix.replace(".", "_").replace("-", "_") or "device"
        selected_model = model or self._model
        used = {instance.instance_id for instance in selected_model.device_instances}
        for index in range(64):
            candidate = f"{prefix}{index}"
            if candidate not in used:
                return candidate
        raise FccgError(
            "error.device_instance_limit",
            {"device": component_class},
            f"No free instance id for device class {component_class}",
        )

    def _BoardSelection_Change(self, board_id: str) -> None:
        board = self._service.Plugin_Get(board_id)
        def change(candidate: ProjectModel) -> None:
            candidate.board = board_id
            candidate.hardware = HardwareConfiguration(
                mode="board_plugin",
                source_kind=(
                    board.board.source_kind if board.board else "third_party"
                ),
            )
            candidate.resource_assignments = {}

        self._ProjectConfiguration_Change(change)

    def _CustomHardware_Select(self) -> None:
        provider = self._service.HardwareProviderForMcu_Get(self._model.mcu)
        if not provider:
            self._Error_Show(self._translator.Text_Get("board.no_provider"))
            return
        def change(candidate: ProjectModel) -> None:
            candidate.board = ""
            candidate.hardware = HardwareConfiguration(
                mode="custom",
                source_kind="manual_import",
                provider=provider,
            )
            candidate.resource_assignments = {}

        self._ProjectConfiguration_Change(change)

    def _HardwarePrepare_Request(self) -> None:
        if self._model.hardware.mode == "custom":
            return
        self._ProjectModel_Sync()
        if self._project_root is None:
            self._Error_Show(
                self._translator.Text_Get("error.save_before_hardware_prepare")
            )
            return
        try:
            plan = self._service.GenerationPlan_Create(
                self._model, self._project_root
            )
        except Exception as error:
            self._Error_Show(error)
            return
        if not self._GenerationPlan_ApplyAllowed(plan):
            return
        project_root = self._project_root
        self._project_state = ProjectLifecycleState.MATERIALIZING

        def prepare(context) -> ApplyResult:
            context.Progress_Report(0.1, "status.hardware_preparing")
            context.Progress_Report(0.35, "status.hardware_validating")
            result = self._service.Project_HardwarePrepare(
                self._model,
                project_root,
                confirm_dangerous=plan.dangerous,
            )
            context.Progress_Report(1.0, "status.hardware_prepared")
            return result

        self.Task_Run(
            prepare,
            self._HardwarePrepare_Complete,
            self._Project_Materialization_Error,
        )

    def _HardwarePrepare_Complete(self, result: ApplyResult) -> None:
        self._project_root = result.project_root
        self._project_state = ProjectLifecycleState.READY
        self._generation_plan = None
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get(
                "status.hardware_already_prepared"
                if result.files_added == 0 and result.files_modified == 0
                else "status.hardware_prepared"
            )
        )

    def _CubeMxImport_Request(self, directory: bool) -> None:
        warning = self._MessageBox_Exec(
            QMessageBox.Icon.Warning,
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
                self._translator.Text_Get("filter.cubemx_ioc"),
            )
        if not selected:
            return
        def import_project(context):
            context.Progress_Report(0.1, "status.cubemx_importing")
            result = self._service.CubeMxProject_Import(
                Path(selected), self._model, risk_acknowledged=True
            )
            context.Progress_Report(1.0, "status.cubemx_importing")
            return result

        self.Task_Run(import_project, self._CubeMxImport_Complete)

    def _CubeMxImport_Complete(self, result) -> None:
        def change(candidate: ProjectModel) -> None:
            candidate.board = ""
            candidate.hardware = result.hardware
            candidate.resource_assignments = {}

        self._ProjectConfiguration_Change(change)
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
        default_path = Path.home() / "Documents" / f"{name}.ssplugin"
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            self._translator.Text_Get("dialog.export_board_title"),
            str(default_path),
            self._translator.Text_Get("filter.silverstar_plugin"),
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
            self._Error_Show(error)
            return
        self.status_label.setText(
            self._translator.Text_Get("status.board_exported", path=str(path))
        )

    def _Resources_AutoAssign(self, *, silent: bool = False) -> None:
        result = self._ProjectConfiguration_Change(lambda _candidate: None)
        if not silent and result is not None:
            self.status_label.setText(
                self._translator.Text_Get(
                    "status.resources_assigned"
                    if result.resource_resolution.valid
                    else "status.resources_incomplete",
                    count=len(result.resource_resolution.errors),
                )
            )

    def _ResourceAssignment_Change(self, key: str, resource_id: str) -> None:
        def change(candidate: ProjectModel) -> None:
            if resource_id:
                candidate.resource_assignments[key] = resource_id
            else:
                candidate.resource_assignments.pop(key, None)

        self._ProjectConfiguration_Change(change)

    def _Strategy_Change(self, slot: str, component_id: object) -> None:
        self._ProjectConfiguration_Change(
            lambda candidate: candidate.strategies.__setitem__(
                slot, str(component_id) if component_id is not None else None
            )
        )

    def _Mode_Change(self, slot: str, values: object) -> None:
        self._ProjectConfiguration_Change(
            lambda candidate: candidate.modes.__setitem__(
                slot, list(values) if isinstance(values, list) else []
            )
        )

    def _Logging_Change(self) -> None:
        self._ProjectConfiguration_Change(lambda _candidate: None)

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
            self._Error_Show(error)
            return
        self._generation_plan = plan
        if not plan.valid:
            validation_details = "\n".join(
                f"[{issue.code}] {issue.message}" for issue in plan.validation.issues
            )
            conflicts = "\n".join(
                f"{operation.target}: {operation.detail}"
                for operation in plan.operations
                if operation.operation == "CONFLICT"
            )
            localized = "\n".join(
                self._translator.Text_Get(
                    "validation.issue_summary", code=issue.code
                )
                for issue in plan.validation.issues
            )
            if conflicts:
                localized = "\n".join(
                    filter(
                        None,
                        (
                            localized,
                            self._translator.Text_Get("validation.file_conflict"),
                        ),
                    )
                )
            self._Error_Show(
                localized or self._translator.Text_Get("error.plan_invalid"),
                "\n".join(filter(None, (validation_details, conflicts))),
            )
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
        eide_modified = any(
            operation.target == ".eide/eide.yml" and operation.dangerous
            for operation in plan.operations
        )
        notice = QLabel(
            self._translator.Text_Get(
                "dialog.eide_manual_modified"
                if eide_modified
                else "dialog.dangerous_changes_message"
            )
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

    def _GenerationPlan_ApplyAllowed(self, plan: GenerationPlan) -> bool:
        if not plan.valid:
            self._ValidationIssue_Navigate(plan.validation.issues)
            validation_details = "\n".join(
                f"[{issue.code}] {issue.message}"
                for issue in plan.validation.issues
            )
            conflicts = "\n".join(
                f"{operation.target}: {operation.detail}"
                for operation in plan.operations
                if operation.operation == "CONFLICT"
            )
            localized = "\n".join(
                self._translator.Text_Get(
                    "validation.issue_summary", code=issue.code
                )
                for issue in plan.validation.issues
            )
            if conflicts:
                localized = "\n".join(
                    filter(
                        None,
                        (
                            localized,
                            self._translator.Text_Get(
                                "validation.file_conflict"
                            ),
                        ),
                    )
                )
            self._Error_Show(
                localized or self._translator.Text_Get("error.plan_invalid"),
                "\n".join(filter(None, (validation_details, conflicts))),
            )
            return False
        return not plan.dangerous or self._DangerousPlan_Confirm(plan)

    def _ValidationIssue_Clear(self) -> None:
        widget = self._validation_focus_widget
        if widget is None:
            return
        widget.setProperty("validationIssue", False)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
        self._validation_focus_widget = None

    def _ValidationIssue_Navigate(
        self, issues: tuple[ValidationIssue, ...]
    ) -> None:
        issue = next((item for item in issues if item.level == "error"), None)
        if issue is None:
            return
        self._ValidationIssue_Clear()
        code = issue.code
        page_index = 3
        target: QWidget = self.build_page.tool_table
        if code.startswith(("hardware", "board", "resource")):
            page_index = 2
            target = (
                self.board_hardware_page.resource_table
                if code.startswith("resource")
                else self.board_hardware_page.board_combo
            )
        elif code.startswith(("strategy", "mode", "capability", "logging")):
            page_index = 1
            if code.startswith("strategy"):
                target = next(
                    iter(self.flight_configuration_page.strategy_combos.values()),
                    self.flight_configuration_page,
                )
            elif code.startswith("mode"):
                target = next(
                    (
                        check
                        for checks in self.flight_configuration_page.mode_checks.values()
                        for check in checks
                    ),
                    self.flight_configuration_page,
                )
            elif code.startswith("logging"):
                target = self.flight_configuration_page.logging_table
            else:
                target = self.flight_configuration_page.capability_table
        elif code.startswith(("mcu", "device")):
            page_index = 0
            target = self.devices_page.mcu_combo
        self.navigation_list.setCurrentRow(page_index)
        target.setProperty("validationIssue", True)
        target.style().unpolish(target)
        target.style().polish(target)
        target.update()
        target.setFocus(Qt.FocusReason.OtherFocusReason)
        self._validation_focus_widget = target

    def _Generation_Complete(self, result: ApplyResult) -> None:
        self._project_root = result.project_root
        self._generation_plan = None
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
        if wizard.exec() != QDialog.DialogCode.Accepted:
            return
        values = wizard.WizardData_Get()
        self._model = self._service.ProjectDraft_Create(values["name"])
        self._project_root = Path(values["output_directory"]).resolve(strict=False)
        self._generation_plan = None
        self._project_state = ProjectLifecycleState.DRAFT
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get("status.project_draft")
        )

    def _Project_OpenDialog(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._translator.Text_Get("dialog.open_project"),
            str(self._service.workspace_root),
            self._translator.Text_Get("filter.silverstar_project"),
        )
        if selected:
            self._Project_Open(Path(selected))

    def _Project_Open(self, path: Path) -> None:
        try:
            loaded = self._service.Project_Open(path)
            configuration = self._service.ProjectConfiguration_Reconcile(loaded)
            reconciled = configuration.model
            changed_during_open = (
                loaded.Dictionary_Get() != reconciled.Dictionary_Get()
            )
            self._model = reconciled
            self._project_root = (
                path.resolve() if path.is_dir() else path.resolve().parent
            )
        except Exception as error:
            self._Error_Show(error)
            return
        self._generation_plan = None
        readiness = self._service.ProjectReadiness_Get(
            self._model, self._project_root
        )
        self._project_state = (
            ProjectLifecycleState.DIRTY
            if changed_during_open
            else readiness.state
        )
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get(
                "status.project_opened", name=self._model.identity.name
            )
        )

    def _Project_Save(self) -> None:
        self._ProjectModel_Sync()
        if self._project_root is None:
            self._Project_SaveAs()
            return
        try:
            plan = self._service.GenerationPlan_Create(
                self._model, self._project_root
            )
        except Exception as error:
            self._Error_Show(error)
            return
        if not self._GenerationPlan_ApplyAllowed(plan):
            return
        self._project_state = ProjectLifecycleState.MATERIALIZING

        def save(context) -> ApplyResult:
            context.Progress_Report(0.08, "status.project_validating")
            context.Progress_Report(0.25, "status.project_materializing")
            result = self._service.Project_Save(
                self._model,
                self._project_root,
                confirm_dangerous=plan.dangerous,
            )
            context.Progress_Report(1.0, "status.project_saved")
            return result

        self.Task_Run(
            save,
            self._Project_Save_Complete,
            self._Project_Materialization_Error,
        )

    def _Project_Save_Complete(self, result: ApplyResult) -> None:
        self._project_root = result.project_root
        self._project_state = ProjectLifecycleState.READY
        self._generation_plan = None
        self.status_label.setText(
            self._translator.Text_Get("status.project_saved_ready")
        )
        self._Project_Display()

    def _Project_Materialization_Error(self, error: object) -> None:
        self._project_state = ProjectLifecycleState.ERROR
        self._Error_Show(error)

    def _Project_SaveAs(self) -> None:
        self._ProjectModel_Sync()
        selected = QFileDialog.getExistingDirectory(
            self,
            self._translator.Text_Get("dialog.save_project_as"),
            str(Path.home() / "Documents"),
        )
        if not selected:
            return
        dangerous = False
        if self._project_root is not None and (
            self._project_root / "SilverStar.ssproject"
        ).is_file():
            try:
                source_plan = self._service.GenerationPlan_Create(
                    self._model, self._project_root
                )
            except Exception as error:
                self._Error_Show(error)
                return
            if not self._GenerationPlan_ApplyAllowed(source_plan):
                return
            dangerous = source_plan.dangerous
        self._project_state = ProjectLifecycleState.MATERIALIZING

        def save_as(context) -> Path:
            context.Progress_Report(0.1, "status.project_copying")
            destination = self._service.Project_SaveAs(
                self._model,
                self._project_root,
                Path(selected),
                confirm_dangerous=dangerous,
            )
            context.Progress_Report(1.0, "status.project_saved")
            return destination

        self.Task_Run(
            save_as,
            self._Project_SaveAs_Complete,
            self._Project_Materialization_Error,
        )

    def _Project_SaveAs_Complete(self, destination: Path) -> None:
        self._project_root = destination
        self._project_state = ProjectLifecycleState.READY
        self._generation_plan = None
        self._Project_Display()
        self.status_label.setText(
            self._translator.Text_Get(
                "status.project_saved_as", path=str(destination)
            )
        )
        if self._pending_build_action is not None:
            pending = self._pending_build_action
            self._pending_build_action = None
            QTimer.singleShot(0, lambda: self._Build_Request(pending))

    def _PluginManager_Show(self) -> None:
        self.plugin_manager_dialog.Components_Set(self._component_views)
        self.plugin_manager_dialog.show()
        self.plugin_manager_dialog.raise_()
        self.plugin_manager_dialog.activateWindow()

    def _Plugins_Refresh(self) -> None:
        try:
            self._service.Plugins_Refresh()
            self._Catalog_Load()
            self._Project_Display()
        except Exception as error:
            self._Error_Show(error)
            return
        self.status_label.setText(
            self._translator.Text_Get("status.plugins_refreshed")
        )

    def _PluginInstall_Dialog(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            self._translator.Text_Get("dialog.install_plugin"),
            str(self._service.workspace_root),
            self._translator.Text_Get("filter.silverstar_plugin"),
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
        answer = self._MessageBox_Exec(
            QMessageBox.Icon.Question,
            self._translator.Text_Get("dialog.plugin_remove_title"),
            self._translator.Text_Get(
                "dialog.plugin_remove_message",
                name=manifest.name,
                id=manifest.component_id,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
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

    def _Toolchains_Detect(self) -> None:
        self.Task_Run(
            lambda _context: self._service.Toolchains_Detect(
                self._model.build.tool_paths
            ),
            self._Toolchains_Show,
        )

    def _Toolchains_Show(self, results) -> None:
        display_names = {
            tool.tool_id: self._translator.Text_Get(f"tool.{tool.tool_id}")
            for tool in DefaultTools_Get()
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
            def change(candidate: ProjectModel) -> None:
                paths = dict(candidate.build.tool_paths)
                paths[tool_id] = selected
                candidate.build = replace(candidate.build, tool_paths=paths)

            self._ProjectConfiguration_Change(change)

    def _Build_Request(self, action_text: str) -> None:
        self._ProjectModel_Sync()
        if self._project_root is None:
            self._pending_build_action = action_text
            self.status_label.setText(
                self._translator.Text_Get("error.save_before_build")
            )
            self._Project_SaveAs()
            return
        actions = {
            "build": BuildAction.BUILD,
            "build_release": BuildAction.BUILD_RELEASE,
            "clean": BuildAction.CLEAN,
            "host_tests": BuildAction.HOST_TESTS,
            "architecture_check": BuildAction.ARCHITECTURE_CHECK,
            "power10_check": BuildAction.POWER10_CHECK,
            "static_analysis": BuildAction.STATIC_ANALYSIS,
            "artifact_check": BuildAction.ARTIFACT_CHECK,
        }
        action = actions.get(action_text)
        if action is None:
            return
        project_root = self._project_root
        readiness = self._service.ProjectReadiness_Get(self._model, project_root)
        materialization_required = not readiness.ready
        plan: GenerationPlan | None = None
        if materialization_required:
            try:
                plan = self._service.GenerationPlan_Create(
                    self._model, project_root
                )
            except Exception as error:
                self._Error_Show(error)
                return
            if not self._GenerationPlan_ApplyAllowed(plan):
                return
        self._project_state = ProjectLifecycleState.BUILDING
        self.build_page.BuildLog_Set("")

        def build(context) -> BuildResult:
            if materialization_required:
                assert plan is not None
                context.Progress_Report(0.08, "status.project_materializing")
                self._service.Project_EnsureBuildable(
                    self._model,
                    project_root,
                    confirm_dangerous=plan.dangerous,
                )
            context.Progress_Report(0.28, "status.build_planning")

            def progress_report(progress: BuildProgress) -> None:
                if progress.stage == "PLAN":
                    context.Line_Report(
                        "FCCG_UI_PLAN|"
                        f"{progress.total_steps}|{progress.stage_total}"
                    )
                    return
                if progress.stage == "COMPLETE":
                    fraction = 1.0
                elif progress.total_steps:
                    fraction = progress.completed_steps / progress.total_steps
                else:
                    fraction = 0.0
                context.Progress_Report(
                    0.30 + (0.68 * max(0.0, min(1.0, fraction))),
                    "status.build_running",
                )
                context.Line_Report(
                    "FCCG_UI_PROGRESS|"
                    f"{progress.stage}|{progress.stage_completed}|"
                    f"{progress.stage_total}|{progress.subject}"
                )

            result = self._service.Build_Run(
                self._model,
                project_root,
                action,
                context.token if hasattr(context, "token") else context,
                confirm_dangerous=bool(plan and plan.dangerous),
                line_callback=context.Line_Report,
                progress_callback=progress_report,
                ensure_buildable=False,
            )
            context.Progress_Report(1.0, "status.build_running")
            return result

        self.Task_Run(
            build,
            self._Build_Complete,
            self._Build_Error,
            line_callback=self._BuildLine_Append,
        )

    def _Build_Complete(self, result: BuildResult) -> None:
        command_text = " ".join(result.command)
        raw_output = result.output.rstrip()
        if raw_output and not result.live_streamed:
            self.build_page.BuildLog_Append(raw_output)
        self.build_page.BuildLog_Append(f"> {command_text}")
        key = "status.build_succeeded" if result.succeeded else "status.build_failed"
        self.status_label.setText(
            self._translator.Text_Get(
                key,
                action=self._translator.Text_Get(
                    f"build.action.{result.action.value}"
                ),
            )
        )
        self._project_state = (
            ProjectLifecycleState.READY
            if result.succeeded
            else ProjectLifecycleState.ERROR
        )
        if not result.succeeded:
            self._Error_Show(
                self._translator.Text_Get("error.build_failed_summary")
            )

    def _BuildLine_Append(self, line: str) -> None:
        if line.startswith("FCCG_UI_PLAN|"):
            _prefix, total, compile_count = line.split("|", 2)
            text = self._translator.Text_Get(
                "build.progress.plan",
                total=total,
                compile=compile_count,
            )
            self.status_label.setText(text)
            self.build_page.BuildLog_Append(text)
            return
        if line.startswith("FCCG_UI_PROGRESS|"):
            _prefix, stage, current, total, subject = line.split("|", 4)
            if stage == "COMPLETE":
                return
            key = (
                "build.progress.compile"
                if stage == "COMPILE"
                else "build.progress.stage"
            )
            text = self._translator.Text_Get(
                key,
                stage=self._translator.Text_Get(
                    f"build.progress.stage.{stage.casefold()}"
                ),
                current=current,
                total=total,
                source=Path(subject).name or subject,
            )
            self.status_label.setText(text)
            self.build_page.BuildLog_Append(text)
            return
        self.build_page.BuildLog_Append(line)

    def _Build_Error(self, error: object) -> None:
        self._project_state = ProjectLifecycleState.ERROR
        technical_detail = (
            error.technical_detail
            if isinstance(error, FccgError)
            else str(error)
        )
        self.build_page.BuildLog_Append(technical_detail)
        self._Error_Show(error)

    def Task_Run(
        self,
        function: Callable[[Any], Any],
        result_callback: Callable[[Any], None],
        error_callback: Callable[[object], None] | None = None,
        *,
        indeterminate: bool = False,
        line_callback: Callable[[str], None] | None = None,
    ) -> bool:
        if self._active_worker is not None:
            self._Error_Show(
                self._translator.Text_Get("error.background_task_active")
            )
            return False
        worker = FunctionWorker(function)
        self._progress_hide_timer.stop()
        self._active_worker = worker
        self._worker_result_callback = result_callback
        self._worker_error_callback = error_callback
        self._worker_line_callback = line_callback
        worker.signals.progress.connect(self._Task_Progress)
        worker.signals.line.connect(self._Task_Line)
        worker.signals.result.connect(self._Task_Result)
        worker.signals.error.connect(self._Task_Error)
        worker.signals.cancelled.connect(
            lambda: self.status_label.setText(
                self._translator.Text_Get("status.task_cancelled")
            )
        )
        worker.signals.finished.connect(self._Task_Finish)
        self.progress_bar.setRange(0, 0 if indeterminate else 1000)
        if not indeterminate:
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

    def _Task_Line(self, line: str) -> None:
        if self._worker_line_callback is not None:
            self._worker_line_callback(line)

    def _Task_Error(self, error: object, traceback_text: str) -> None:
        logging.error("Background task failed:\n%s", traceback_text)
        if self._worker_error_callback is not None:
            self._worker_error_callback(error)
        else:
            self._Error_Show(error, traceback_text)

    def _Task_Finish(self) -> None:
        self._active_worker = None
        self._worker_result_callback = None
        self._worker_error_callback = None
        self._worker_line_callback = None
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.cancel_button.setVisible(False)
        self._Actions_SetEnabled(True)
        self._progress_hide_timer.start(350)

    def _Progress_CompletionHide(self) -> None:
        if self._active_worker is None:
            self.progress_bar.setVisible(False)

    def _Task_Cancel(self) -> None:
        if self._active_worker is not None:
            self._active_worker.Worker_Cancel()

    def _Actions_SetEnabled(self, enabled: bool) -> None:
        self.new_action.setEnabled(enabled)
        self.open_action.setEnabled(enabled)
        self.save_action.setEnabled(enabled)
        self.save_as_action.setEnabled(enabled)
        self.manage_plugins_action.setEnabled(enabled)
        self.install_plugin_action.setEnabled(enabled)
        self.refresh_plugins_action.setEnabled(enabled)
        self.board_hardware_page.prepare_button.setEnabled(
            enabled
            and (
                self._model.hardware.mode == "board_plugin"
                or bool(self._model.hardware.snapshot_id)
            )
        )
        for button in self.build_page.action_buttons.values():
            button.setEnabled(enabled)

    def _HeaderProject_Refresh(self) -> None:
        path = str(self._project_root) if self._project_root is not None else "—"
        self.current_project_value.setText(self._model.identity.name)
        self.current_project_value.setToolTip(
            self._translator.Text_Get(
                "project.state_tooltip",
                path=path,
                state=self._translator.Text_Get(
                    f"project.state.{self._project_state.value}"
                ),
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
        self.current_project_label.setText(
            self._translator.Text_Get("label.current_project")
        )
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
        self.plugin_manager_dialog.Language_Apply(self._translator)
        self.file_menu.setTitle(self._translator.Text_Get("menu.file"))
        self.plugin_menu.setTitle(self._translator.Text_Get("menu.plugins"))
        self.help_menu.setTitle(self._translator.Text_Get("menu.help"))
        for action, key in (
            (self.new_action, "action.new_project"),
            (self.open_action, "action.open_project"),
            (self.save_action, "action.save_project"),
            (self.save_as_action, "action.save_project_as"),
            (self.exit_action, "action.exit"),
            (self.manage_plugins_action, "action.manage_plugins"),
            (self.install_plugin_action, "action.install_plugin"),
            (self.refresh_plugins_action, "action.refresh_plugins"),
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
        self._HeaderProject_Refresh()

    def Theme_Apply(self, theme: str) -> None:
        self._theme = theme if theme in {"light", "dark"} else "light"
        application = QApplication.instance()
        if application is not None:
            Theme_Apply(application, self._theme)
        WindowCaption_Apply(self, self._theme)
        self._settings.Value_Set("theme", self._theme)

    def _About_Show(self) -> None:
        self._MessageBox_Exec(
            QMessageBox.Icon.Information,
            PRODUCT_NAME,
            self._translator.Text_Get("about.text", version=__version__),
        )

    def _Error_Show(self, error: object, technical_detail: str = "") -> None:
        if isinstance(error, FccgError):
            message = self._translator.Text_Get(error.code, **error.params)
            if message == error.code:
                message = self._translator.Text_Get("error.operation_failed")
            technical_detail = technical_detail or error.technical_detail
        elif isinstance(error, Exception):
            message = self._translator.Text_Get("error.operation_failed")
            technical_detail = technical_detail or str(error)
        else:
            message = str(error)
        self._MessageBox_Exec(
            QMessageBox.Icon.Critical,
            self._translator.Text_Get("dialog.error_title"),
            message or self._translator.Text_Get("status.failed"),
            details=technical_detail,
        )

    def _MessageBox_Exec(
        self,
        icon: QMessageBox.Icon,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
        *,
        details: str = "",
    ) -> QMessageBox.StandardButton:
        box = self._MessageBox_Create(
            icon, title, text, buttons, default, details=details
        )
        return QMessageBox.StandardButton(box.exec())

    def _MessageBox_Create(
        self,
        icon: QMessageBox.Icon,
        title: str,
        text: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
        *,
        details: str = "",
    ) -> QMessageBox:
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default != QMessageBox.StandardButton.NoButton:
            box.setDefaultButton(default)
        if details:
            box.setDetailedText(details)
        MessageBoxButtons_Localize(box, self._translator)
        return box

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
            answer = self._MessageBox_Exec(
                QMessageBox.Icon.Question,
                PRODUCT_NAME,
                self._translator.Text_Get("dialog.close_active_task"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._active_worker.Worker_Cancel()
        event.accept()
