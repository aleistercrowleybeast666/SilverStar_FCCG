from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
    ComponentView,
    LoggingStreamView,
    ResourceRequirementView,
)
from silverstar_fccg.ui.pages.base import LocalizedPage, ScrollableLocalizedPage
from silverstar_fccg.ui.widgets import EngineeringTable, StandardComboBox, StatusPill


class DevicesPage(ScrollableLocalizedPage):
    selectionChanged = Signal(str, str)

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.devices", "page.devices.description")
        self.selection_form = QFormLayout()
        self.selection_group = self.Group_Create(
            "group.device_selection", self.selection_form
        )
        self.root_layout.addWidget(self.selection_group)
        notice = QLabel()
        notice.setWordWrap(True)
        notice.setObjectName("noticeLabel")
        self.Text_Register(notice, "device.resources_next_step")
        self.root_layout.addWidget(notice)
        self.requirement_table = self.Table_Register(
            EngineeringTable(
                (
                    "column.component",
                    "column.requirement",
                    "column.resource_type",
                    "column.mode",
                )
            )
        )
        self.root_layout.addWidget(self.requirement_table)
        self.root_layout.addStretch(1)
        self.device_combos: dict[str, StandardComboBox] = {}
        self._components: tuple[ComponentView, ...] = ()
        self._selected: tuple[str, ...] = ()
        self.Language_Apply(translator)

    def Components_Set(
        self, components: Iterable[ComponentView], selected: Iterable[str]
    ) -> None:
        self._components = tuple(components)
        self._selected = tuple(selected)
        while self.selection_form.rowCount():
            self.selection_form.removeRow(0)
        self.device_combos.clear()
        grouped: defaultdict[str, list[ComponentView]] = defaultdict(list)
        for component in self._components:
            grouped[component.component_class or "other"].append(component)
        selected_set = set(self._selected)
        for component_class in sorted(grouped):
            label = QLabel(
                self._translator.Text_Get(f"device.class.{component_class}")
            )
            combo = StandardComboBox()
            combo.addItem(self._translator.Text_Get("selection.none"), "")
            for component in sorted(grouped[component_class], key=lambda item: item.name):
                combo.addItem(component.name, component.component_id)
                if component.component_id in selected_set:
                    combo.setCurrentIndex(combo.count() - 1)
            combo.currentIndexChanged.connect(
                lambda _index, selected_class=component_class, editor=combo: self.selectionChanged.emit(
                    selected_class, str(editor.currentData() or "")
                )
            )
            self.selection_form.addRow(label, combo)
            self.device_combos[component_class] = combo
        selected_components = [
            component
            for component in self._components
            if component.component_id in selected_set
        ]
        self.requirement_table.Rows_Set(
            (
                component.name,
                requirement.name,
                requirement.kind,
                self._translator.Text_Get(f"resource.mode.{requirement.mode}"),
            )
            for component in selected_components
            for requirement in component.requirements
        )

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        if self._components:
            self.Components_Set(self._components, self._selected)


class BoardHardwarePage(ScrollableLocalizedPage):
    boardChanged = Signal(str)
    customSelected = Signal()
    importIocRequested = Signal()
    importDirectoryRequested = Signal()
    exportRequested = Signal()
    autoAssignRequested = Signal()
    assignmentChanged = Signal(str, str)

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
        self.resource_table = QTableWidget(0, 4)
        self.resource_table.setObjectName("engineeringTable")
        self.resource_table.setAlternatingRowColors(True)
        self.resource_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.resource_table.verticalHeader().setVisible(False)
        self.resource_table.horizontalHeader().setStretchLastSection(True)
        advanced_layout.addWidget(self.resource_table)
        self.advanced_group = QGroupBox()
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        self.Title_Register(self.advanced_group, "group.advanced_resources")
        self.advanced_group.setLayout(advanced_layout)
        self.root_layout.addWidget(self.advanced_group)
        self.root_layout.addStretch(1)
        self._boards: tuple[BoardCompatibilityView, ...] = ()
        self._resources: tuple[ResourceRequirementView, ...] = ()
        self._selected_board = ""
        self._custom_available = False
        self._custom_selected = False
        self._custom_ready = False
        self.Language_Apply(translator)

    def Boards_Set(
        self,
        boards: Iterable[BoardCompatibilityView],
        selected: str,
        *,
        custom_available: bool,
        custom_selected: bool,
        custom_ready: bool,
    ) -> None:
        self._boards = tuple(boards)
        self._selected_board = selected
        self._custom_available = custom_available
        self._custom_selected = custom_selected
        self._custom_ready = custom_ready
        self.board_combo.blockSignals(True)
        self.board_combo.clear()
        for board in self._boards:
            suffix = "" if board.compatible else self._translator.Text_Get(
                "board.incompatible_suffix", missing=board.missing_text or board.detail
            )
            self.board_combo.addItem(board.name + suffix, board.component_id)
            item = self.board_combo.model().item(self.board_combo.count() - 1)
            if item is not None:
                item.setEnabled(board.compatible)
        if custom_available:
            self.board_combo.addItem(
                self._translator.Text_Get("board.custom_hardware"), "__custom__"
            )
        current_data = "__custom__" if custom_selected else selected
        index = self.board_combo.findData(current_data)
        if index >= 0:
            self.board_combo.setCurrentIndex(index)
        self.board_combo.blockSignals(False)
        self.custom_widget.setVisible(custom_selected)
        self.export_button.setEnabled(custom_ready)
        if not custom_available:
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
        self, resources: Iterable[ResourceRequirementView], valid: bool
    ) -> None:
        self._resources = tuple(resources)
        self.resource_table.blockSignals(True)
        self.resource_table.setRowCount(len(self._resources))
        for row, requirement in enumerate(self._resources):
            self.resource_table.setItem(row, 0, QTableWidgetItem(requirement.key))
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
        self.resource_table.blockSignals(False)
        self.resource_table.setHorizontalHeaderLabels(
            [
                self._translator.Text_Get("column.requirement"),
                self._translator.Text_Get("column.resource_type"),
                self._translator.Text_Get("column.status"),
                self._translator.Text_Get("column.assignment"),
            ]
        )
        self.hardware_status.Status_Set(
            self._translator.Text_Get(
                "board.resources_valid" if valid else "board.resources_invalid"
            ),
            "success" if valid else "warning",
        )

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self.Boards_Set(
            self._boards,
            self._selected_board,
            custom_available=self._custom_available,
            custom_selected=self._custom_selected,
            custom_ready=self._custom_ready,
        )
        self.Resources_Set(self._resources, not any(not item.assignment and item.required for item in self._resources))

    def _Board_Emit(self) -> None:
        value = str(self.board_combo.currentData() or "")
        if value == "__custom__":
            self.customSelected.emit()
        elif value:
            self.boardChanged.emit(value)


class FlightConfigurationPage(ScrollableLocalizedPage):
    strategyChanged = Signal(str, object)
    modeChanged = Signal(str, object)
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
        self.logging_group = QGroupBox()
        self.logging_group.setCheckable(True)
        self.logging_group.setChecked(False)
        self.Title_Register(self.logging_group, "group.logging")
        logging_layout = QVBoxLayout(self.logging_group)
        logging_notice = QLabel()
        logging_notice.setWordWrap(True)
        self.Text_Register(logging_notice, "logging.thin_glue_notice")
        logging_layout.addWidget(logging_notice)
        self.logging_table = QTableWidget(0, 5)
        self.logging_table.setObjectName("engineeringTable")
        self.logging_table.setAlternatingRowColors(True)
        self.logging_table.verticalHeader().setVisible(False)
        self.logging_table.horizontalHeader().setStretchLastSection(True)
        self.logging_table.itemChanged.connect(lambda _item: self.loggingChanged.emit())
        logging_layout.addWidget(self.logging_table)
        self.root_layout.addWidget(self.logging_group)
        self.root_layout.addStretch(1)
        self.strategy_combos: dict[str, StandardComboBox] = {}
        self.mode_checks: dict[str, list[QCheckBox]] = {}
        self._components: tuple[ComponentView, ...] = ()
        self._strategies: dict[str, str | None] = {}
        self._modes: dict[str, list[str]] = {}
        self._streams: list[LoggingStreamView] = []
        self.Language_Apply(translator)

    def Configuration_Set(
        self,
        components: Iterable[ComponentView],
        strategies: dict[str, str | None],
        modes: dict[str, list[str]],
    ) -> None:
        self._components = tuple(components)
        self._strategies = dict(strategies)
        self._modes = {key: list(value) for key, value in modes.items()}
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
            if any(candidate.allow_none for candidate in candidates):
                combo.addItem(self._translator.Text_Get("strategy.none"), None)
            for candidate in sorted(candidates, key=lambda item: item.name):
                combo.addItem(candidate.name, candidate.component_id)
            index = combo.findData(self._strategies.get(slot))
            if index >= 0:
                combo.setCurrentIndex(index)
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
            checks: list[QCheckBox] = []
            labels = owner.options.get("selection_labels", {})
            for option in owner.selection_options:
                check = QCheckBox(str(labels.get(option, option)))
                check.setProperty("selectionOption", option)
                check.setChecked(option in self._modes.get(slot, []))
                check.toggled.connect(
                    lambda _checked, selected_slot=slot: self._Mode_Emit(selected_slot)
                )
                section_layout.addWidget(check)
                checks.append(check)
            section_layout.addStretch(1)
            self.mode_layout.addWidget(section)
            self.mode_checks[slot] = checks

    def Streams_Set(self, streams: Iterable[LoggingStreamView]) -> None:
        self._streams = list(streams)
        self.logging_table.blockSignals(True)
        self.logging_table.setRowCount(len(self._streams))
        for row, stream in enumerate(self._streams):
            enabled_item = QTableWidgetItem()
            enabled_item.setCheckState(
                Qt.CheckState.Checked if stream.enabled else Qt.CheckState.Unchecked
            )
            enabled_item.setData(Qt.ItemDataRole.UserRole, stream.stream_id)
            self.logging_table.setItem(row, 0, enabled_item)
            self.logging_table.setItem(row, 1, QTableWidgetItem(stream.name))
            decimation = QSpinBox()
            decimation.setRange(1, 65535)
            decimation.setValue(max(1, stream.decimation))
            decimation.valueChanged.connect(lambda _value: self.loggingChanged.emit())
            self.logging_table.setCellWidget(row, 2, decimation)
            period = QSpinBox()
            period.setRange(0, 2_147_483_647)
            period.setSuffix(" us")
            period.setValue(stream.period_us)
            period.setEnabled(stream.policy == "PERIODIC")
            period.valueChanged.connect(lambda _value: self.loggingChanged.emit())
            self.logging_table.setCellWidget(row, 3, period)
            self.logging_table.setItem(row, 4, QTableWidgetItem(stream.description or "—"))
        self.logging_table.blockSignals(False)
        self._LoggingHeaders_Apply()

    def Streams_Get(self) -> tuple[LoggingStreamView, ...]:
        values: list[LoggingStreamView] = []
        for row, original in enumerate(self._streams):
            enabled_item = self.logging_table.item(row, 0)
            decimation = self.logging_table.cellWidget(row, 2)
            period = self.logging_table.cellWidget(row, 3)
            values.append(
                LoggingStreamView(
                    stream_id=original.stream_id,
                    name=original.name,
                    enabled=bool(
                        enabled_item
                        and enabled_item.checkState() == Qt.CheckState.Checked
                    ),
                    decimation=(decimation.value() if isinstance(decimation, QSpinBox) else original.decimation),
                    rate_text=original.rate_text,
                    description=original.description,
                    policy=original.policy,
                    period_us=(period.value() if isinstance(period, QSpinBox) else original.period_us),
                )
            )
        return tuple(values)

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self._LoggingHeaders_Apply()
        if self._components:
            self.Configuration_Set(self._components, self._strategies, self._modes)

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
                self._translator.Text_Get("column.decimation"),
                self._translator.Text_Get("column.rate_period"),
                self._translator.Text_Get("column.description"),
            ]
        )
