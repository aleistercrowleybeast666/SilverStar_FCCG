from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.view_models import ToolchainToolView
from silverstar_fccg.ui.pages.base import ScrollableLocalizedPage
from silverstar_fccg.ui.widgets import (
    CollapsibleSection,
    EngineeringTable,
    StandardComboBox,
    StatusPill,
)


class BuildPage(ScrollableLocalizedPage):
    detectionRequested = Signal()
    browseRequested = Signal(str)
    actionRequested = Signal(str)

    _PRIMARY_ACTIONS = (
        ("generate_apply", "action.generate_apply_project"),
        ("open_vscode", "action.open_vscode_workspace"),
        ("open_folder", "action.open_project_folder"),
    )
    _QUALITY_ACTIONS = (
        ("host_tests", "action.host_tests"),
        ("architecture_check", "action.architecture_check"),
        ("power10_check", "action.power10_check"),
        ("static_analysis", "action.static_analysis"),
        ("artifact_check", "action.artifact_check"),
    )
    _TOOL_OPTIONS = (
        ("compiler", "tool.compiler"),
        ("make", "tool.make"),
        ("host_gcc", "tool.host_gcc"),
    )

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.build", "page.build.description")
        summary_form = QFormLayout()
        self.target_label = QLabel()
        self.Text_Register(self.target_label, "field.build_target")
        self.target_value = QLabel("—")
        summary_form.addRow(self.target_label, self.target_value)
        self.environment_label = QLabel()
        self.Text_Register(self.environment_label, "field.development_environment")
        self.environment_value = QLabel("VS Code + EIDE")
        summary_form.addRow(self.environment_label, self.environment_value)
        self.toolchain_label = QLabel()
        self.Text_Register(self.toolchain_label, "field.toolchain_status")
        self.toolchain_status = StatusPill()
        summary_form.addRow(self.toolchain_label, self.toolchain_status)
        summary_layout = QVBoxLayout()
        summary_layout.addLayout(summary_form)
        self.tool_table = self.Table_Register(
            EngineeringTable(
                ("column.tool", "column.path", "column.version", "column.status")
            )
        )
        self.tool_table.setMinimumHeight(105)
        summary_layout.addWidget(self.tool_table)
        self.root_layout.addWidget(
            self.Group_Create("group.build_configuration", summary_layout)
        )

        primary_actions = QHBoxLayout()
        self.action_buttons: dict[str, QPushButton] = {}
        for action_id, key in self._PRIMARY_ACTIONS:
            button = self._ActionButton_Create(action_id, key)
            if action_id == "generate_apply":
                button.setObjectName("primaryButton")
            primary_actions.addWidget(button)
        primary_actions.addStretch(1)
        self.root_layout.addLayout(primary_actions)

        advanced_layout = QVBoxLayout()
        verification_label = QLabel()
        verification_label.setObjectName("sectionLabel")
        self.Text_Register(verification_label, "build.section.verification")
        advanced_layout.addWidget(verification_label)
        verification_row = QHBoxLayout()
        verification_button = self._ActionButton_Create(
            "build", "action.validation_build"
        )
        verification_button.setMinimumWidth(180)
        verification_row.addWidget(verification_button)
        clean_button = self._ActionButton_Create("clean", "action.clean")
        clean_button.setMinimumWidth(120)
        verification_row.addWidget(clean_button)
        verification_row.addStretch(1)
        advanced_layout.addLayout(verification_row)

        quality_label = QLabel()
        quality_label.setObjectName("sectionLabel")
        self.Text_Register(quality_label, "build.section.quality")
        advanced_layout.addWidget(quality_label)
        quality_grid = QGridLayout()
        quality_grid.setColumnStretch(0, 1)
        quality_grid.setColumnStretch(1, 1)
        for index, (action_id, key) in enumerate(self._QUALITY_ACTIONS):
            button = self._ActionButton_Create(action_id, key)
            button.setMinimumWidth(180)
            quality_grid.addWidget(button, index // 2, index % 2)
        advanced_layout.addLayout(quality_grid)

        output_form = QFormLayout()
        self.latest_artifact_label = QLabel()
        self.Text_Register(self.latest_artifact_label, "field.latest_firmware")
        self.latest_artifact_value = QLabel("—")
        output_form.addRow(
            self.latest_artifact_label, self.latest_artifact_value
        )
        self.firmware_output_label = QLabel()
        self.Text_Register(self.firmware_output_label, "field.firmware_output_directory")
        self.firmware_output_value = QLabel("—")
        self.firmware_output_value.setWordWrap(True)
        output_form.addRow(
            self.firmware_output_label, self.firmware_output_value
        )
        advanced_layout.addLayout(output_form)
        firmware_output_button = self._ActionButton_Create(
            "open_firmware_output", "action.open_firmware_output"
        )
        firmware_output_button.setMinimumWidth(180)
        advanced_layout.addWidget(firmware_output_button)

        tools_label = QLabel()
        tools_label.setObjectName("sectionLabel")
        self.Text_Register(tools_label, "build.section.toolchain")
        advanced_layout.addWidget(tools_label)
        detect_row = QGridLayout()
        self.tool_path_combo = StandardComboBox()
        self.tool_path_combo.setMinimumWidth(220)
        self.browse_button = QPushButton()
        self.browse_button.setMinimumWidth(100)
        self.Text_Register(self.browse_button, "action.browse")
        self.browse_button.clicked.connect(
            lambda: self.browseRequested.emit(
                str(self.tool_path_combo.currentData() or "")
            )
        )
        self.detect_button = QPushButton()
        self.detect_button.setMinimumWidth(120)
        self.Text_Register(self.detect_button, "action.detect_toolchain")
        self.detect_button.clicked.connect(
            lambda _checked=False: self.detectionRequested.emit()
        )
        detect_row.addWidget(self.tool_path_combo, 0, 0)
        detect_row.addWidget(self.browse_button, 0, 1)
        detect_row.addWidget(self.detect_button, 0, 2)
        detect_row.setColumnStretch(0, 1)
        advanced_layout.addLayout(detect_row)
        self.quality_tool_table = self.Table_Register(
            EngineeringTable(
                ("column.tool", "column.path", "column.version", "column.status")
            )
        )
        self.quality_tool_table.setMinimumHeight(88)
        advanced_layout.addWidget(self.quality_tool_table)
        self.advanced_section = CollapsibleSection(expanded=False)
        self.advanced_section.BodyLayout_Set(advanced_layout)
        self.advanced_group = self.advanced_section
        self.root_layout.addWidget(self.advanced_section)

        log_layout = QVBoxLayout()
        self.build_log = QPlainTextEdit()
        self.build_log.setObjectName("buildLog")
        self.build_log.setReadOnly(True)
        self.build_log.setMaximumBlockCount(20_000)
        self.build_log.setMinimumHeight(220)
        log_layout.addWidget(self.build_log)
        advanced_layout.addWidget(self.Group_Create("group.build_log", log_layout))
        self.root_layout.addStretch(1)
        self._tools: tuple[ToolchainToolView, ...] = ()
        self.Language_Apply(translator)
        self.Tools_Set(())
        self.GeneratedProject_Set(False)
        self.FirmwareArtifact_Set("", "")

    def _ActionButton_Create(self, action_id: str, key: str) -> QPushButton:
        button = QPushButton()
        button.setMinimumWidth(120)
        self.Text_Register(button, key)
        button.clicked.connect(
            lambda _checked=False, selected=action_id: self.actionRequested.emit(
                selected
            )
        )
        self.action_buttons[action_id] = button
        return button

    def Tools_Set(self, tools: Iterable[ToolchainToolView]) -> None:
        self._tools = tuple(tools)
        self.tool_table.Rows_Set(
            (
                self._translator.Text_Get(f"tool.{tool.tool_id}"),
                tool.path or tool.command,
                tool.version or "—",
                self._translator.Text_Get(f"tool.status.{tool.status}"),
            )
            for tool in self._tools
            if tool.tool_id in {"compiler", "make"}
        )
        self.quality_tool_table.Rows_Set(
            (
                self._translator.Text_Get(f"tool.{tool.tool_id}"),
                tool.path or tool.command,
                tool.version or "—",
                self._translator.Text_Get(f"tool.status.{tool.status}"),
            )
            for tool in self._tools
            if tool.tool_id == "host_gcc"
        )
        compiler = next(
            (tool for tool in self._tools if tool.tool_id == "compiler"), None
        )
        make = next(
            (tool for tool in self._tools if tool.tool_id == "make"), None
        )
        if compiler is None or compiler.status == "not_checked":
            key, level = "toolchain.not_checked", "info"
        elif (
            compiler.status == "found"
            and make is not None
            and make.status == "found"
        ):
            version = compiler.version or compiler.path
            self.toolchain_status.Status_Set(
                self._translator.Text_Get(
                    "toolchain.compiler_found", version=version
                ),
                "success",
            )
            return
        else:
            key, level = "toolchain.incomplete", "warning"
        self.toolchain_status.Status_Set(self._translator.Text_Get(key), level)

    def Project_Set(
        self, target: str, environment: str = "VS Code + EIDE"
    ) -> None:
        self.target_value.setText(target or "—")
        self.environment_value.setText(environment or "—")

    def GeneratedProject_Set(self, available: bool) -> None:
        for action_id in ("open_vscode", "open_folder"):
            button = self.action_buttons.get(action_id)
            if button is not None:
                button.setEnabled(available)

    def FirmwareArtifact_Set(self, directory: str, artifact_name: str) -> None:
        self.firmware_output_value.setText(directory or "—")
        self.firmware_output_value.setToolTip(directory)
        self.latest_artifact_value.setText(artifact_name or "—")
        button = self.action_buttons.get("open_firmware_output")
        if button is not None:
            button.setEnabled(bool(directory and artifact_name))

    def BuildLog_Set(self, text: str) -> None:
        self.build_log.setPlainText(text)

    def BuildLog_Append(self, text: str) -> None:
        if text:
            self.build_log.appendPlainText(text.rstrip())

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self.advanced_section.Title_Set(translator.Text_Get("group.advanced_build"))
        selected_tool = self.tool_path_combo.currentData()
        self.tool_path_combo.blockSignals(True)
        self.tool_path_combo.clear()
        for tool_id, translation_key in self._TOOL_OPTIONS:
            self.tool_path_combo.addItem(translator.Text_Get(translation_key), tool_id)
        selected_index = self.tool_path_combo.findData(selected_tool)
        self.tool_path_combo.setCurrentIndex(max(0, selected_index))
        self.tool_path_combo.blockSignals(False)
        if hasattr(self, "_tools"):
            self.Tools_Set(self._tools)


def DefaultTools_Get() -> tuple[ToolchainToolView, ...]:
    return (
        ToolchainToolView("compiler", "Arm GNU Compiler", "arm-none-eabi-gcc"),
        ToolchainToolView("make", "Make", "mingw32-make"),
        ToolchainToolView("host_gcc", "Host GCC", "gcc"),
    )
