from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.view_models import (
    BoardCompatibilityView,
    CapabilityUsageView,
    ComponentView,
    DeviceInstanceView,
    LoggingStreamView,
    ResourceRequirementView,
)
from silverstar_fccg.project.capabilities import (
    Capability_UserSelectable_Is,
)
from silverstar_fccg.project.configuration import SelectionAvailability
from silverstar_fccg.ui.pages.base import LocalizedPage, ScrollableLocalizedPage
from silverstar_fccg.ui.widgets import (
    CollapsibleSection,
    EngineeringTable,
    LockedCheckBox,
    StandardCheckBox,
    StandardComboBox,
    StatusPill,
)


class DevicesPage(ScrollableLocalizedPage):
    mcuChanged = Signal(str)
    instanceChanged = Signal(str, str)
    instanceAddRequested = Signal(str)
    otherDeviceToggled = Signal(str, bool)
    installRequested = Signal()

    _PRIMARY_CLASSES = ("imu", "gnss", "telemetry", "console")
    _DEFAULT_INSTANCE_IDS = {
        "imu": "imu0",
        "gnss": "gnss0",
        "telemetry": "telemetry0",
        "console": "maintenance0",
    }

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.devices", "page.devices.description")
        self.mcu_form = QFormLayout()
        self.mcu_label = QLabel()
        self.Text_Register(self.mcu_label, "field.mcu")
        self.mcu_combo = StandardComboBox()
        self.mcu_combo.setObjectName("mcuCombo")
        self.mcu_combo.currentIndexChanged.connect(
            lambda _index: self.mcuChanged.emit(
                str(self.mcu_combo.currentData() or "")
            )
        )
        self.mcu_form.addRow(self.mcu_label, self.mcu_combo)
        self.root_layout.addWidget(self.Group_Create("group.main_controller", self.mcu_form))

        self.primary_form = QFormLayout()
        self.primary_group = self.Group_Create("group.primary_devices", self.primary_form)
        self.root_layout.addWidget(self.primary_group)

        self.other_layout = QVBoxLayout()
        self.other_empty_label = QLabel()
        self.other_empty_label.setObjectName("otherSensorsEmptyLabel")
        self.other_empty_label.setWordWrap(True)
        self.Text_Register(self.other_empty_label, "device.other_empty")
        self.other_layout.addWidget(self.other_empty_label)
        self.other_checks_container = QWidget()
        self.other_checks_layout = QVBoxLayout(self.other_checks_container)
        self.other_checks_layout.setContentsMargins(0, 0, 0, 0)
        self.other_layout.addWidget(self.other_checks_container)
        self.install_button = QPushButton()
        self.install_button.setObjectName("primaryButton")
        self.Text_Register(self.install_button, "action.install_plugin")
        self.install_button.clicked.connect(
            lambda _checked=False: self.installRequested.emit()
        )
        self.other_layout.addWidget(self.install_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.other_group = self.Group_Create("group.other_sensors", self.other_layout)
        self.other_group.setObjectName("otherSensorsGroup")
        self.root_layout.addWidget(self.other_group)

        self.root_layout.addStretch(1)
        self.device_combos: dict[str, StandardComboBox] = {}
        self.device_checks: dict[str, StandardCheckBox] = {}
        self.add_buttons: dict[str, QPushButton] = {}
        self._mcus: tuple[ComponentView, ...] = ()
        self._components: tuple[ComponentView, ...] = ()
        self._instances: tuple[DeviceInstanceView, ...] = ()
        self._selected_mcu = ""
        self._maintenance_versions: tuple[str, str, str] = ("", "", "")
        self.Language_Apply(translator)

    @staticmethod
    def _Layout_Clear(layout: QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                DevicesPage._Layout_Clear(item.layout())

    def Configuration_Set(
        self,
        mcus: Iterable[ComponentView],
        selected_mcu: str,
        components: Iterable[ComponentView],
        instances: Iterable[DeviceInstanceView],
        maintenance_versions: tuple[str, str, str] = ("", "", ""),
    ) -> None:
        self._mcus = tuple(mcus)
        self._components = tuple(components)
        self._instances = tuple(instances)
        self._selected_mcu = selected_mcu
        self._maintenance_versions = maintenance_versions

        self.mcu_combo.blockSignals(True)
        self.mcu_combo.clear()
        for mcu in self._mcus:
            self.mcu_combo.addItem(mcu.name, mcu.component_id)
        mcu_index = self.mcu_combo.findData(selected_mcu)
        if mcu_index >= 0:
            self.mcu_combo.setCurrentIndex(mcu_index)
        self.mcu_combo.blockSignals(False)

        self._Layout_Clear(self.primary_form)
        self.device_combos.clear()
        self.add_buttons.clear()
        components_by_class: defaultdict[str, list[ComponentView]] = defaultdict(list)
        instances_by_class: defaultdict[str, list[DeviceInstanceView]] = defaultdict(list)
        for component in self._components:
            components_by_class[component.component_class].append(component)
        for instance in self._instances:
            instances_by_class[instance.component_class].append(instance)

        for component_class in self._PRIMARY_CLASSES:
            candidates = sorted(
                components_by_class.get(component_class, ()), key=lambda item: item.name
            )
            selected_instances = sorted(
                instances_by_class.get(component_class, ()), key=lambda item: item.instance_id
            )
            rows: list[DeviceInstanceView | None] = list(selected_instances) or [None]
            for row_index, instance in enumerate(rows):
                instance_id = (
                    instance.instance_id
                    if instance is not None
                    else self._DEFAULT_INSTANCE_IDS[component_class]
                )
                combo = StandardComboBox()
                combo.setObjectName(f"deviceCombo_{instance_id}")
                combo.addItem(self._translator.Text_Get("selection.none"), "")
                for component in candidates:
                    combo.addItem(component.name, component.component_id)
                    combo.setItemData(
                        combo.count() - 1,
                        self._PhysicalDetails_Get(component),
                        Qt.ItemDataRole.ToolTipRole,
                    )
                selected_plugin = instance.plugin_id if instance is not None else ""
                selected_index = combo.findData(selected_plugin)
                combo.setCurrentIndex(max(0, selected_index))
                combo.currentIndexChanged.connect(
                    lambda _index, selected_instance=instance_id, editor=combo: self.instanceChanged.emit(
                        selected_instance, str(editor.currentData() or "")
                    )
                )
                self.primary_form.addRow(
                    QLabel(
                        self._translator.Text_Get(
                            f"device.instance.{component_class}", index=row_index
                        )
                    ),
                    combo,
                )
                self.device_combos[instance_id] = combo
                if instance is not None:
                    summary = QLabel(self._CapabilitySummary_Get(instance))
                    summary.setObjectName(f"deviceCapabilitySummary_{instance_id}")
                    summary.setWordWrap(True)
                    summary.setProperty("muted", True)
                    self.primary_form.addRow(QLabel(), summary)
            if component_class == "console" and any(maintenance_versions):
                details = QLabel(
                    self._translator.Text_Get(
                        "device.maintenance_versions",
                        firmware=maintenance_versions[0] or "—",
                        protocol=maintenance_versions[1] or "—",
                        documentation=maintenance_versions[2] or "—",
                    )
                )
                details.setObjectName("muted")
                details.setWordWrap(True)
                self.primary_form.addRow(QLabel(), details)
            ready_candidates = tuple(
                item for item in candidates if item.multi_instance_ready
            )
            project_max = max(
                (item.project_max for item in ready_candidates), default=1
            )
            if (
                selected_instances
                and ready_candidates
                and all(item.multi_instance_ready for item in selected_instances)
                and project_max > len(selected_instances)
            ):
                add_button = QPushButton(
                    self._translator.Text_Get(
                        "action.add_device",
                        device=self._translator.Text_Get(
                            f"device.class.{component_class}"
                        ),
                    )
                )
                add_button.setObjectName(f"addDeviceButton_{component_class}")
                add_button.clicked.connect(
                    lambda _checked=False, selected_class=component_class: self.instanceAddRequested.emit(
                        selected_class
                    )
                )
                self.primary_form.addRow(QLabel(), add_button)
                self.add_buttons[component_class] = add_button

        self._Layout_Clear(self.other_checks_layout)
        self.device_checks.clear()
        other_components = sorted(
            (
                component
                for component in self._components
                if component.component_class not in self._PRIMARY_CLASSES
            ),
            key=lambda item: item.name,
        )
        selected_plugins = {instance.plugin_id for instance in self._instances}
        for component in other_components:
            check = StandardCheckBox(component.name)
            check.setProperty("componentId", component.component_id)
            check.setChecked(component.component_id in selected_plugins)
            check.setToolTip(self._PhysicalDetails_Get(component))
            check.toggled.connect(
                lambda checked, plugin_id=component.component_id: self.otherDeviceToggled.emit(
                    plugin_id, checked
                )
            )
            self.other_checks_layout.addWidget(check)
            self.device_checks[component.component_id] = check
        self.other_empty_label.setVisible(not other_components)
        self.other_checks_container.setVisible(bool(other_components))

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        if self._components:
            self.Configuration_Set(
                self._mcus,
                self._selected_mcu,
                self._components,
                self._instances,
                self._maintenance_versions,
            )

    def _CapabilitySummary_Get(self, instance: DeviceInstanceView) -> str:
        capabilities = ", ".join(
            self._translator.Text_Get(f"capability.{capability}")
            for capability in instance.provides
            if Capability_UserSelectable_Is(capability)
        )
        return self._translator.Text_Get(
            "device.provides_summary", capabilities=capabilities or "—"
        )

    @staticmethod
    def _PhysicalDetails_Get(component: ComponentView) -> str:
        values = (
            component.physical_vendor,
            component.physical_model,
            component.chipset,
            component.driver,
        )
        return " · ".join(value for value in values if value)


class BoardHardwarePage(ScrollableLocalizedPage):
    boardChanged = Signal(str)
    customSelected = Signal()
    importIocRequested = Signal()
    importDirectoryRequested = Signal()
    exportRequested = Signal()
    autoAssignRequested = Signal()
    assignmentChanged = Signal(str, str)
    prepareRequested = Signal()

    def __init__(self, translator: Translator) -> None:
        super().__init__(
            translator, "page.board_hardware", "page.board_hardware.description"
        )
        selection_form = QFormLayout()
        self.board_label = QLabel()
        self.Text_Register(self.board_label, "field.board")
        self.board_combo = StandardComboBox()
        self.board_combo.currentIndexChanged.connect(self._Board_Emit)
        selection_form.addRow(self.board_label, self.board_combo)
        self.hardware_status_label = QLabel()
        self.Text_Register(self.hardware_status_label, "field.hardware_resources")
        self.hardware_status = StatusPill()
        selection_form.addRow(self.hardware_status_label, self.hardware_status)
        self.preparation_label = QLabel()
        self.Text_Register(self.preparation_label, "field.hardware_preparation")
        self.preparation_widget = QWidget()
        preparation_row = QHBoxLayout(self.preparation_widget)
        preparation_row.setContentsMargins(0, 0, 0, 0)
        self.prepare_button = QPushButton()
        self.prepare_button.setObjectName("primaryButton")
        self.prepare_button.clicked.connect(
            lambda _checked=False: self.prepareRequested.emit()
        )
        self.preparation_status = StatusPill()
        preparation_row.addWidget(self.prepare_button)
        preparation_row.addWidget(self.preparation_status, 1)
        selection_form.addRow(self.preparation_label, self.preparation_widget)
        self.root_layout.addWidget(
            self.Group_Create("group.board_selection", selection_form)
        )

        self.provider_notice = QLabel()
        self.provider_notice.setWordWrap(True)
        self.provider_notice.setObjectName("noticeLabel")
        self.root_layout.addWidget(self.provider_notice)

        custom_actions = QHBoxLayout()
        self.import_ioc_button = QPushButton()
        self.Text_Register(self.import_ioc_button, "action.import_cubemx_ioc")
        self.import_ioc_button.clicked.connect(
            lambda _checked=False: self.importIocRequested.emit()
        )
        self.import_directory_button = QPushButton()
        self.Text_Register(
            self.import_directory_button, "action.import_cubemx_directory"
        )
        self.import_directory_button.clicked.connect(
            lambda _checked=False: self.importDirectoryRequested.emit()
        )
        self.export_button = QPushButton()
        self.Text_Register(self.export_button, "action.export_board_plugin")
        self.export_button.clicked.connect(
            lambda _checked=False: self.exportRequested.emit()
        )
        custom_actions.addWidget(self.import_ioc_button)
        custom_actions.addWidget(self.import_directory_button)
        custom_actions.addWidget(self.export_button)
        custom_actions.addStretch(1)
        self.custom_widget = QWidget()
        self.custom_widget.setLayout(custom_actions)
        self.root_layout.addWidget(self.custom_widget)

        advanced_layout = QVBoxLayout()
        advanced_toolbar = QHBoxLayout()
        advanced_explanation = QLabel()
        advanced_explanation.setWordWrap(True)
        self.Text_Register(advanced_explanation, "board.advanced_explanation")
        self.auto_button = QPushButton()
        self.Text_Register(self.auto_button, "action.auto_assign")
        self.auto_button.clicked.connect(
            lambda _checked=False: self.autoAssignRequested.emit()
        )
        advanced_toolbar.addWidget(advanced_explanation, 1)
        advanced_toolbar.addWidget(self.auto_button)
        advanced_layout.addLayout(advanced_toolbar)
        self.resource_table = QTableWidget(0, 6)
        self.resource_table.setObjectName("engineeringTable")
        self.resource_table.setAlternatingRowColors(True)
        self.resource_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.resource_table.verticalHeader().setVisible(False)
        self.resource_table.horizontalHeader().setStretchLastSection(True)
        advanced_layout.addWidget(self.resource_table)
        self.advanced_section = CollapsibleSection(expanded=False)
        self.advanced_section.BodyLayout_Set(advanced_layout)
        self.advanced_group = self.advanced_section
        self.root_layout.addWidget(self.advanced_section)
        self.root_layout.addStretch(1)
        self._boards: tuple[BoardCompatibilityView, ...] = ()
        self._resources: tuple[ResourceRequirementView, ...] = ()
        self._selected_board = ""
        self._custom_available = False
        self._custom_selected = False
        self._custom_ready = False
        self._prepared = False
        self._hardware_mode = "unselected"
        self._resources_valid = False
        self.Language_Apply(translator)

    def Boards_Set(
        self,
        boards: Iterable[BoardCompatibilityView],
        selected: str,
        *,
        custom_available: bool,
        custom_selected: bool,
        custom_ready: bool,
        prepared: bool = False,
        hardware_mode: str = "unselected",
    ) -> None:
        self._boards = tuple(boards)
        self._selected_board = selected
        self._custom_available = custom_available
        self._custom_selected = custom_selected
        self._custom_ready = custom_ready
        self._prepared = prepared
        self._hardware_mode = hardware_mode
        self.board_combo.blockSignals(True)
        self.board_combo.clear()
        self.board_combo.addItem(
            self._translator.Text_Get("board.unselected"), "__unselected__"
        )
        if custom_available:
            self.board_combo.addItem(
                self._translator.Text_Get("board.custom_hardware"), "__custom__"
            )
        for board in self._boards:
            suffix = "" if board.compatible else self._translator.Text_Get(
                "board.incompatible_suffix", missing=board.missing_text or board.detail
            )
            self.board_combo.addItem(board.name + suffix, board.component_id)
            item = self.board_combo.model().item(self.board_combo.count() - 1)
            if item is not None:
                item.setEnabled(board.compatible)
        current_data = (
            "__custom__"
            if custom_selected
            else selected if hardware_mode == "board_plugin" else "__unselected__"
        )
        index = self.board_combo.findData(current_data)
        if index >= 0:
            self.board_combo.setCurrentIndex(index)
        self.board_combo.blockSignals(False)
        self.custom_widget.setVisible(custom_selected)
        self.export_button.setEnabled(custom_ready)
        board_selected = hardware_mode == "board_plugin"
        self.preparation_label.setVisible(board_selected)
        self.preparation_widget.setVisible(board_selected)
        self.prepare_button.setEnabled(board_selected)
        self.auto_button.setEnabled(hardware_mode != "unselected")
        self.prepare_button.setText(
            self._translator.Text_Get("action.prepare_hardware")
        )
        self.preparation_status.Status_Set(
            self._translator.Text_Get(
                "status.hardware_prepared"
                if prepared
                else "status.hardware_not_prepared"
            ),
            "success" if prepared else "info",
        )
        if hardware_mode == "unselected":
            self.provider_notice.setText(
                self._translator.Text_Get("board.selection_pending")
            )
        elif not custom_available:
            self.provider_notice.setText(
                self._translator.Text_Get("board.no_provider")
            )
        elif custom_selected:
            self.provider_notice.setText(
                self._translator.Text_Get("board.cubemx_steps")
            )
        else:
            self.provider_notice.setText(
                self._translator.Text_Get("board.automatic_summary")
            )

    def Resources_Set(
        self,
        resources: Iterable[ResourceRequirementView],
        valid: bool,
        *,
        hardware_selected: bool,
    ) -> None:
        self._resources = tuple(resources)
        self._resources_valid = valid
        self.resource_table.blockSignals(True)
        self.resource_table.setRowCount(len(self._resources))
        for row, requirement in enumerate(self._resources):
            requirement_item = QTableWidgetItem(
                requirement.display_name or requirement.name
            )
            requirement_item.setToolTip(requirement.key)
            self.resource_table.setItem(row, 0, requirement_item)
            self.resource_table.setItem(row, 1, QTableWidgetItem(requirement.kind))
            self.resource_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    self._translator.Text_Get(
                        "status.required" if requirement.required else "selection.optional"
                    )
                ),
            )
            if requirement.fixed and requirement.assignment:
                fixed_value = QLabel(requirement.assignment or "—")
                fixed_value.setProperty("fixedResource", True)
                self.resource_table.setCellWidget(row, 3, fixed_value)
            else:
                combo = StandardComboBox()
                combo.addItem(self._translator.Text_Get("status.unassigned"), "")
                for candidate in requirement.candidates:
                    combo.addItem(candidate, candidate)
                index = combo.findData(requirement.assignment)
                if index >= 0:
                    combo.setCurrentIndex(index)
                combo.currentIndexChanged.connect(
                    lambda _index, key=requirement.key, editor=combo: self.assignmentChanged.emit(
                        key, str(editor.currentData() or "")
                    )
                )
                self.resource_table.setCellWidget(row, 3, combo)
            self.resource_table.setItem(
                row,
                4,
                QTableWidgetItem(requirement.recommended_assignment or "—"),
            )
            self.resource_table.setItem(
                row,
                5,
                QTableWidgetItem(requirement.physical_details or requirement.physical_resource or "—"),
            )
        self.resource_table.blockSignals(False)
        self.resource_table.setHorizontalHeaderLabels(
            [
                self._translator.Text_Get("column.requirement"),
                self._translator.Text_Get("column.resource_type"),
                self._translator.Text_Get("column.status"),
                self._translator.Text_Get("column.assignment"),
                self._translator.Text_Get("column.recommended_assignment"),
                self._translator.Text_Get("column.physical_resource"),
            ]
        )
        pending_count = sum(
            1
            for requirement in self._resources
            if requirement.required and not requirement.assignment
        )
        if not hardware_selected:
            self.hardware_status.Status_Set(
                self._translator.Text_Get(
                    "board.hardware_pending", count=pending_count
                ),
                "info",
            )
        else:
            self.hardware_status.Status_Set(
                self._translator.Text_Get(
                    "board.resources_valid" if valid else "board.resources_invalid"
                ),
                "success" if valid else "warning",
            )

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self.advanced_section.Title_Set(
            translator.Text_Get("group.advanced_resources")
        )
        self.Boards_Set(
            self._boards,
            self._selected_board,
            custom_available=self._custom_available,
            custom_selected=self._custom_selected,
            custom_ready=self._custom_ready,
            prepared=self._prepared,
            hardware_mode=self._hardware_mode,
        )
        self.Resources_Set(
            self._resources,
            self._resources_valid,
            hardware_selected=self._hardware_mode != "unselected",
        )

    def _Board_Emit(self) -> None:
        value = str(self.board_combo.currentData() or "")
        if value == "__unselected__":
            return
        if value == "__custom__":
            self.customSelected.emit()
        elif value:
            self.boardChanged.emit(value)


class FlightConfigurationPage(ScrollableLocalizedPage):
    strategyChanged = Signal(str, object)
    modeChanged = Signal(str, object)
    capabilitySourceChanged = Signal(str, str)
    loggingChanged = Signal()

    def __init__(self, translator: Translator) -> None:
        super().__init__(
            translator, "page.flight_configuration", "page.flight_configuration.description"
        )
        self.strategy_form = QFormLayout()
        self.strategy_group = self.Group_Create(
            "group.strategy_selection", self.strategy_form
        )
        self.root_layout.addWidget(self.strategy_group)
        self.mode_layout = QVBoxLayout()
        self.mode_group = self.Group_Create("group.mode_selection", self.mode_layout)
        self.root_layout.addWidget(self.mode_group)
        capability_layout = QVBoxLayout()
        capability_notice = QLabel()
        capability_notice.setWordWrap(True)
        self.Text_Register(capability_notice, "capability.flight_summary")
        capability_layout.addWidget(capability_notice)
        self.capability_table = QTableWidget(0, 4)
        self.capability_table.setObjectName("engineeringTable")
        self.capability_table.setAlternatingRowColors(True)
        self.capability_table.verticalHeader().setVisible(False)
        capability_header = self.capability_table.horizontalHeader()
        capability_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        capability_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        capability_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        capability_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        capability_layout.addWidget(self.capability_table)
        self.capability_group = self.Group_Create(
            "group.capability_data_sources", capability_layout
        )
        self.root_layout.addWidget(self.capability_group)
        logging_layout = QVBoxLayout()
        self.logging_group = self.Group_Create("group.logging", logging_layout)
        logging_notice = QLabel()
        logging_notice.setWordWrap(True)
        self.Text_Register(logging_notice, "logging.thin_glue_notice")
        logging_layout.addWidget(logging_notice)
        self.logging_table = QTableWidget(0, 6)
        self.logging_table.setObjectName("engineeringTable")
        self.logging_table.setAlternatingRowColors(True)
        self.logging_table.verticalHeader().setVisible(False)
        logging_header = self.logging_table.horizontalHeader()
        logging_header.setStretchLastSection(False)
        for column in (0, 2, 3, 4):
            logging_header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        logging_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        logging_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        logging_layout.addWidget(self.logging_table)
        self.root_layout.addWidget(self.logging_group)
        self.root_layout.addStretch(1)
        self.strategy_combos: dict[str, StandardComboBox] = {}
        self.mode_checks: dict[str, list[StandardCheckBox]] = {}
        self._components: tuple[ComponentView, ...] = ()
        self._strategies: dict[str, str | None] = {}
        self._modes: dict[str, list[str]] = {}
        self._streams: list[LoggingStreamView] = []
        self._capabilities: tuple[CapabilityUsageView, ...] = ()
        self._strategy_availability: dict[str, SelectionAvailability] = {}
        self._mode_availability: dict[tuple[str, str], SelectionAvailability] = {}
        self.Language_Apply(translator)

    def Configuration_Set(
        self,
        components: Iterable[ComponentView],
        strategies: dict[str, str | None],
        modes: dict[str, list[str]],
        strategy_availability: dict[str, SelectionAvailability] | None = None,
        mode_availability: dict[tuple[str, str], SelectionAvailability] | None = None,
    ) -> None:
        self._components = tuple(components)
        self._strategies = dict(strategies)
        self._modes = {key: list(value) for key, value in modes.items()}
        self._strategy_availability = dict(strategy_availability or {})
        self._mode_availability = dict(mode_availability or {})
        while self.strategy_form.rowCount():
            self.strategy_form.removeRow(0)
        while self.mode_layout.count():
            item = self.mode_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.strategy_combos.clear()
        self.mode_checks.clear()
        strategy_slots: defaultdict[str, list[ComponentView]] = defaultdict(list)
        mode_owners: list[ComponentView] = []
        for component in self._components:
            if component.selection_kind == "strategy":
                strategy_slots[component.selection_slot].append(component)
            elif component.selection_kind == "mode":
                mode_owners.append(component)
        for slot, candidates in sorted(
            strategy_slots.items(), key=lambda item: min(value.ui_order for value in item[1])
        ):
            combo = StandardComboBox()
            allow_none = any(candidate.allow_none for candidate in candidates)
            combo.addItem(
                self._translator.Text_Get(
                    "strategy.none" if allow_none else "selection.choose_strategy"
                ),
                None,
            )
            placeholder = combo.model().item(0)
            if placeholder is not None and not allow_none:
                placeholder.setEnabled(False)
            for candidate in sorted(candidates, key=lambda item: item.name):
                combo.addItem(candidate.name, candidate.component_id)
                availability = self._strategy_availability.get(
                    candidate.component_id, SelectionAvailability(True)
                )
                item = combo.model().item(combo.count() - 1)
                if item is not None:
                    item.setEnabled(availability.available)
                    item.setToolTip(
                        self._AvailabilityText_Get(availability, candidate.description)
                    )
            index = combo.findData(self._strategies.get(slot))
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.currentIndexChanged.connect(
                lambda _index, selected_slot=slot, editor=combo: self.strategyChanged.emit(
                    selected_slot, editor.currentData()
                )
            )
            self.strategy_form.addRow(
                QLabel(self._translator.Text_Get(f"strategy.slot.{slot}")), combo
            )
            self.strategy_combos[slot] = combo
        for owner in sorted(mode_owners, key=lambda item: item.ui_order):
            slot = owner.selection_slot
            section = QWidget()
            section_layout = QHBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.addWidget(
                QLabel(self._translator.Text_Get(f"mode.slot.{slot}"))
            )
            checks: list[StandardCheckBox] = []
            labels = owner.options.get("selection_labels", {})
            for option in owner.selection_options:
                check = StandardCheckBox(str(labels.get(option, option)))
                check.setProperty("selectionOption", option)
                check.setChecked(option in self._modes.get(slot, []))
                availability = self._mode_availability.get(
                    (slot, option), SelectionAvailability(True)
                )
                check.setEnabled(availability.available)
                check.setToolTip(self._AvailabilityText_Get(availability))
                check.toggled.connect(
                    lambda _checked, selected_slot=slot: self._Mode_Emit(selected_slot)
                )
                section_layout.addWidget(check)
                checks.append(check)
            section_layout.addStretch(1)
            self.mode_layout.addWidget(section)
            self.mode_checks[slot] = checks

    def Capabilities_Set(
        self, capabilities: Iterable[CapabilityUsageView]
    ) -> None:
        self._capabilities = tuple(capabilities)
        self.capability_table.blockSignals(True)
        self.capability_table.setRowCount(len(self._capabilities))
        for row, capability in enumerate(self._capabilities):
            capability_name = self._translator.Text_Get(
                f"capability.{capability.capability}"
            )
            capability_item = QTableWidgetItem(capability_name)
            capability_item.setToolTip(capability.capability)
            self.capability_table.setItem(row, 0, capability_item)
            if capability.missing:
                status_key = "capability.status.missing"
            elif capability.ambiguous:
                status_key = "capability.status.source_required"
            elif capability.used:
                status_key = "capability.status.used"
            else:
                status_key = "capability.status.unused"
            self.capability_table.setItem(
                row, 1, QTableWidgetItem(self._translator.Text_Get(status_key))
            )
            if capability.consumers and len(capability.providers) > 1:
                source_combo = StandardComboBox()
                source_combo.addItem(
                    self._translator.Text_Get("selection.choose_provider"), ""
                )
                for instance_id, name in capability.providers:
                    source_combo.addItem(name, instance_id)
                selected_index = source_combo.findData(capability.source_instance_id)
                source_combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
                source_combo.currentIndexChanged.connect(
                    lambda _index, capability_id=capability.capability, editor=source_combo: self.capabilitySourceChanged.emit(
                        capability_id, str(editor.currentData() or "")
                    )
                )
                self.capability_table.setCellWidget(row, 2, source_combo)
            else:
                self.capability_table.setItem(
                    row, 2, QTableWidgetItem(capability.source_name or "—")
                )
            purpose_text = ", ".join(
                self._translator.Text_Get(f"capability.purpose.{purpose}")
                for purpose in capability.purposes
            )
            consumer_text = ", ".join(capability.consumers)
            details = " · ".join(value for value in (consumer_text, purpose_text) if value)
            self.capability_table.setItem(row, 3, QTableWidgetItem(details or "—"))
        self.capability_table.blockSignals(False)
        self._CapabilityHeaders_Apply()

    def Streams_Set(self, streams: Iterable[LoggingStreamView]) -> None:
        self._streams = list(streams)
        self.logging_table.blockSignals(True)
        self.logging_table.setRowCount(len(self._streams))
        for row, stream in enumerate(self._streams):
            enabled_check = LockedCheckBox() if stream.required else StandardCheckBox()
            enabled_check.setProperty("streamId", stream.stream_id)
            enabled_check.setChecked(True if stream.required else stream.enabled)
            if not stream.required:
                enabled_check.setEnabled(stream.available)
            tooltip = stream.availability_reason
            if stream.required:
                tooltip = self._translator.Text_Get("logging.required_tooltip")
            enabled_check.setToolTip(tooltip)
            enabled_check.toggled.connect(
                lambda _checked: self.loggingChanged.emit()
            )
            enabled_container = QWidget()
            enabled_layout = QHBoxLayout(enabled_container)
            enabled_layout.setContentsMargins(8, 0, 0, 0)
            enabled_layout.addWidget(enabled_check)
            enabled_layout.addStretch(1)
            self.logging_table.setCellWidget(row, 0, enabled_container)
            name_item = QTableWidgetItem(stream.name)
            name_item.setToolTip(stream.name)
            self.logging_table.setItem(row, 1, name_item)
            self.logging_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    self._translator.Text_Get(f"logging.level.{stream.level}")
                ),
            )
            decimation = QSpinBox()
            decimation.setRange(1, 65535)
            decimation.setValue(max(1, stream.decimation))
            decimation.setEnabled(stream.available)
            decimation.valueChanged.connect(lambda _value: self.loggingChanged.emit())
            self.logging_table.setCellWidget(row, 3, decimation)
            period = QSpinBox()
            period.setRange(0, 2_147_483_647)
            period.setSuffix(" us")
            period.setValue(stream.period_us)
            period.setEnabled(stream.available and stream.policy == "PERIODIC")
            period.valueChanged.connect(lambda _value: self.loggingChanged.emit())
            self.logging_table.setCellWidget(row, 4, period)
            description = stream.description or "—"
            if not stream.available and stream.availability_reason:
                description = stream.availability_reason
            description_item = QTableWidgetItem(description)
            description_item.setToolTip(description)
            self.logging_table.setItem(row, 5, description_item)
        self.logging_table.blockSignals(False)
        self._LoggingHeaders_Apply()

    def Streams_Get(self) -> tuple[LoggingStreamView, ...]:
        values: list[LoggingStreamView] = []
        for row, original in enumerate(self._streams):
            enabled_container = self.logging_table.cellWidget(row, 0)
            enabled_check = (
                enabled_container.findChild(StandardCheckBox)
                if isinstance(enabled_container, QWidget)
                else None
            )
            decimation = self.logging_table.cellWidget(row, 3)
            period = self.logging_table.cellWidget(row, 4)
            values.append(
                LoggingStreamView(
                    stream_id=original.stream_id,
                    name=original.name,
                    enabled=(
                        True
                        if original.required
                        else bool(enabled_check and enabled_check.isChecked())
                    ),
                    decimation=(decimation.value() if isinstance(decimation, QSpinBox) else original.decimation),
                    rate_text=original.rate_text,
                    description=original.description,
                    policy=original.policy,
                    period_us=(period.value() if isinstance(period, QSpinBox) else original.period_us),
                    level=original.level,
                    required=original.required,
                    available=original.available,
                    availability_reason=original.availability_reason,
                    record_id=original.record_id,
                    version=original.version,
                    payload_size=original.payload_size,
                )
            )
        return tuple(values)

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self._LoggingHeaders_Apply()
        self._CapabilityHeaders_Apply()
        if self._components:
            self.Configuration_Set(
                self._components,
                self._strategies,
                self._modes,
                self._strategy_availability,
                self._mode_availability,
            )
        self.Capabilities_Set(self._capabilities)

    def _Mode_Emit(self, slot: str) -> None:
        selected = [
            str(check.property("selectionOption"))
            for check in self.mode_checks.get(slot, [])
            if check.isChecked()
        ]
        self.modeChanged.emit(slot, selected)

    def _LoggingHeaders_Apply(self) -> None:
        self.logging_table.setHorizontalHeaderLabels(
            [
                self._translator.Text_Get("column.enabled"),
                self._translator.Text_Get("column.record_stream"),
                self._translator.Text_Get("column.policy_level"),
                self._translator.Text_Get("column.decimation"),
                self._translator.Text_Get("column.rate_period"),
                self._translator.Text_Get("column.description"),
            ]
        )

    def _CapabilityHeaders_Apply(self) -> None:
        self.capability_table.setHorizontalHeaderLabels(
            [
                self._translator.Text_Get("column.capability"),
                self._translator.Text_Get("column.status"),
                self._translator.Text_Get("column.data_source"),
                self._translator.Text_Get("column.consumers_purpose"),
            ]
        )

    def _AvailabilityText_Get(
        self,
        availability: SelectionAvailability,
        description: str = "",
    ) -> str:
        parts = [description] if description else []
        if availability.missing_capabilities:
            missing = ", ".join(
                self._translator.Text_Get(f"capability.{capability}")
                for capability in availability.missing_capabilities
            )
            parts.append(
                self._translator.Text_Get(
                    "selection.unavailable.capability", missing=missing
                )
            )
        if availability.missing_components:
            parts.append(
                self._translator.Text_Get(
                    "selection.unavailable.component",
                    missing=", ".join(availability.missing_components),
                )
            )
        return "\n".join(parts)
