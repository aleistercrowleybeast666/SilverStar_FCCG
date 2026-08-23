from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.view_models import ComponentView, ProjectDraftView
from silverstar_fccg.ui.pages.base import ScrollableLocalizedPage
from silverstar_fccg.ui.widgets import StandardComboBox, StatusPill


class ProjectPage(ScrollableLocalizedPage):
    changed = Signal()
    outputBrowseRequested = Signal()

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.project", "page.project.description")
        form = QFormLayout()
        self.name_label = QLabel()
        self.Text_Register(self.name_label, "field.project_name")
        self.name_edit = QLineEdit()
        self.Placeholder_Register(self.name_edit, "placeholder.project_name")
        self.name_edit.textChanged.connect(lambda _text: self.changed.emit())
        form.addRow(self.name_label, self.name_edit)

        self.output_label = QLabel()
        self.Text_Register(self.output_label, "field.output_directory")
        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.Placeholder_Register(self.output_edit, "placeholder.output_directory")
        self.output_edit.textChanged.connect(lambda _text: self.changed.emit())
        self.output_button = QPushButton()
        self.Text_Register(self.output_button, "action.browse")
        self.output_button.clicked.connect(
            lambda _checked=False: self.outputBrowseRequested.emit()
        )
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(self.output_button)
        form.addRow(self.output_label, output_layout)

        self.version_label = QLabel()
        self.Text_Register(self.version_label, "field.firmware_version")
        self.version_edit = QLineEdit("0.0.9")
        self.version_edit.textChanged.connect(lambda _text: self.changed.emit())
        form.addRow(self.version_label, self.version_edit)

        self.mcu_label = QLabel()
        self.Text_Register(self.mcu_label, "field.mcu")
        self.mcu_combo = StandardComboBox()
        self.mcu_combo.currentIndexChanged.connect(lambda _index: self.changed.emit())
        form.addRow(self.mcu_label, self.mcu_combo)
        self.root_layout.addWidget(self.Group_Create("group.project_identity", form))

        state_form = QFormLayout()
        self.status_label = QLabel()
        self.Text_Register(self.status_label, "field.project_status")
        self.status_pill = StatusPill()
        state_form.addRow(self.status_label, self.status_pill)
        self.auto_components_label = QLabel()
        self.Text_Register(self.auto_components_label, "field.auto_components")
        self.auto_components_value = QLabel("—")
        self.auto_components_value.setWordWrap(True)
        state_form.addRow(self.auto_components_label, self.auto_components_value)
        self.root_layout.addWidget(self.Group_Create("group.project_state", state_form))
        self.root_layout.addStretch(1)
        self.Status_Set("draft")
        self.Language_Apply(translator)

    def Mcus_Set(self, components: Iterable[ComponentView], selected: str = "") -> None:
        self.mcu_combo.blockSignals(True)
        self.mcu_combo.clear()
        for component in components:
            self.mcu_combo.addItem(component.name, component.component_id)
        index = self.mcu_combo.findData(selected)
        if index >= 0:
            self.mcu_combo.setCurrentIndex(index)
        self.mcu_combo.blockSignals(False)

    def Project_Set(self, project: ProjectDraftView) -> None:
        self.name_edit.setText(project.name)
        self.output_edit.setText(
            str(project.output_directory) if project.output_directory else ""
        )
        self.version_edit.setText(project.firmware_version)
        index = self.mcu_combo.findData(project.core_component_id)
        if index >= 0:
            self.mcu_combo.setCurrentIndex(index)
        self.Status_Set(project.status)

    def Values_Get(self) -> tuple[str, Path | None, str, str]:
        output_text = self.output_edit.text().strip()
        return (
            self.name_edit.text().strip(),
            Path(output_text) if output_text else None,
            self.version_edit.text().strip(),
            str(self.mcu_combo.currentData() or ""),
        )

    def OutputDirectory_Set(self, path: Path) -> None:
        self.output_edit.setText(str(path))

    def AutoComponents_Set(self, names: Iterable[str]) -> None:
        self.auto_components_value.setText(" · ".join(names) or "—")

    def Status_Set(self, status_code: str, issue_count: int = 0) -> None:
        key = {
            "not_created": "project.status.not_created",
            "draft": "project.status.draft",
            "valid": "project.status.valid",
            "invalid": "validation.failed",
            "generated": "project.status.generated",
        }.get(status_code, "project.status.draft")
        level = "success" if status_code in {"valid", "generated"} else (
            "warning" if status_code == "invalid" else "info"
        )
        self.status_pill.Status_Set(
            self._translator.Text_Get(key, count=issue_count), level
        )

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
