from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.view_models import ToolchainToolView
from silverstar_fccg.ui.pages.base import LocalizedPage
from silverstar_fccg.ui.widgets import EngineeringTable, StandardComboBox, StatusPill


class BuildPage(LocalizedPage):
    detectionRequested = Signal()
    browseRequested = Signal(str)
    actionRequested = Signal(str)
    configurationChanged = Signal(str)

    _PRIMARY_ACTIONS = (
        ("build", "action.build"),
        ("clean", "action.clean"),
        ("flash", "action.flash"),
    )
    _ADVANCED_ACTIONS = (
        ("host_tests", "action.host_tests"),
        ("architecture_check", "action.architecture_check"),
        ("power10_check", "action.power10_check"),
        ("static_analysis", "action.static_analysis"),
        ("artifact_check", "action.artifact_check"),
    )

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.build", "page.build.description")
        summary_form = QFormLayout()
        self.configuration_label = QLabel()
        self.Text_Register(self.configuration_label, "field.build_configuration")
        self.configuration_combo = StandardComboBox()
        self.configuration_combo.addItem("Debug", "Debug")
        self.configuration_combo.addItem("Release", "Release")
        self.configuration_combo.currentIndexChanged.connect(
            lambda _index: self.configurationChanged.emit(
                str(self.configuration_combo.currentData() or "Debug")
            )
        )
        summary_form.addRow(self.configuration_label, self.configuration_combo)
        self.target_label = QLabel()
        self.Text_Register(self.target_label, "field.build_target")
        self.target_value = QLabel("—")
        summary_form.addRow(self.target_label, self.target_value)
        self.toolchain_label = QLabel()
        self.Text_Register(self.toolchain_label, "field.toolchain_status")
        self.toolchain_status = StatusPill()
        summary_form.addRow(self.toolchain_label, self.toolchain_status)
        self.root_layout.addWidget(
            self.Group_Create("group.build_configuration", summary_form)
        )

        actions = QHBoxLayout()
        self.action_buttons: dict[str, QPushButton] = {}
        for action_id, key in self._PRIMARY_ACTIONS:
            button = QPushButton()
            if action_id == "build":
                button.setObjectName("primaryButton")
            self.Text_Register(button, key)
            button.clicked.connect(
                lambda _checked=False, selected=action_id: self.actionRequested.emit(selected)
            )
            actions.addWidget(button)
            self.action_buttons[action_id] = button
        actions.addStretch(1)
        self.root_layout.addLayout(actions)

        advanced_layout = QVBoxLayout()
        detect_row = QHBoxLayout()
        self.tool_path_combo = StandardComboBox()
        for tool_id, display_name in (
            ("compiler", "Arm GNU Compiler"),
            ("make", "Make"),
            ("objcopy", "Objcopy"),
            ("debugger", "OpenOCD"),
            ("host_gcc", "Host GCC"),
            ("static_analyzer", "GCC Static Analyzer"),
        ):
            self.tool_path_combo.addItem(display_name, tool_id)
        self.browse_button = QPushButton()
        self.Text_Register(self.browse_button, "action.browse")
        self.browse_button.clicked.connect(
            lambda: self.browseRequested.emit(str(self.tool_path_combo.currentData() or ""))
        )
        self.detect_button = QPushButton()
        self.Text_Register(self.detect_button, "action.detect_toolchain")
        self.detect_button.clicked.connect(
            lambda _checked=False: self.detectionRequested.emit()
        )
        detect_row.addWidget(self.tool_path_combo, 1)
        detect_row.addWidget(self.browse_button)
        detect_row.addWidget(self.detect_button)
        advanced_layout.addLayout(detect_row)
        self.tool_table = self.Table_Register(
            EngineeringTable(
                ("column.tool", "column.path", "column.version", "column.status")
            )
        )
        advanced_layout.addWidget(self.tool_table)
        advanced_actions = QHBoxLayout()
        for action_id, key in self._ADVANCED_ACTIONS:
            button = QPushButton()
            self.Text_Register(button, key)
            button.clicked.connect(
                lambda _checked=False, selected=action_id: self.actionRequested.emit(selected)
            )
            advanced_actions.addWidget(button)
            self.action_buttons[action_id] = button
        advanced_actions.addStretch(1)
        advanced_layout.addLayout(advanced_actions)
        self.advanced_group = QGroupBox()
        self.advanced_group.setCheckable(True)
        self.advanced_group.setChecked(False)
        self.Title_Register(self.advanced_group, "group.advanced_build")
        self.advanced_group.setLayout(advanced_layout)
        self.root_layout.addWidget(self.advanced_group, 1)
        self._tools: tuple[ToolchainToolView, ...] = ()
        self.Language_Apply(translator)
        self.Tools_Set(())

    def Tools_Set(self, tools: Iterable[ToolchainToolView]) -> None:
        self._tools = tuple(tools)
        self.tool_table.Rows_Set(
            (
                tool.display_name,
                tool.path or tool.command,
                tool.version or "—",
                self._translator.Text_Get(f"tool.status.{tool.status}"),
            )
            for tool in self._tools
        )
        compiler = next(
            (tool for tool in self._tools if tool.tool_id == "compiler"), None
        )
        if compiler is None or compiler.status == "not_checked":
            key, level = "toolchain.not_checked", "info"
        elif compiler.status == "found":
            version = compiler.version or compiler.path
            self.toolchain_status.Status_Set(
                self._translator.Text_Get("toolchain.compiler_found", version=version),
                "success",
            )
            return
        else:
            key, level = "toolchain.incomplete", "warning"
        self.toolchain_status.Status_Set(self._translator.Text_Get(key), level)

    def Project_Set(self, target: str, configuration: str) -> None:
        self.target_value.setText(target or "—")
        index = self.configuration_combo.findData(configuration)
        if index >= 0:
            self.configuration_combo.setCurrentIndex(index)

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        if hasattr(self, "_tools"):
            self.Tools_Set(self._tools)


def DefaultTools_Get() -> tuple[ToolchainToolView, ...]:
    return (
        ToolchainToolView("compiler", "Arm GNU Compiler", "arm-none-eabi-gcc"),
        ToolchainToolView("make", "Make", "mingw32-make"),
        ToolchainToolView("objcopy", "Objcopy", "arm-none-eabi-objcopy"),
        ToolchainToolView("size", "Size", "arm-none-eabi-size"),
        ToolchainToolView("host_gcc", "Host GCC", "gcc"),
        ToolchainToolView("debugger", "Debugger / Flasher", "openocd"),
        ToolchainToolView("static_analyzer", "GCC Static Analyzer", "arm-none-eabi-gcc"),
    )
