from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWizard,
    QWizardPage,
)

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.view_models import ComponentView
from silverstar_fccg.ui.widgets import StandardComboBox


class ProjectIdentityWizardPage(QWizardPage):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self._translator = translator
        layout = QFormLayout(self)
        self.name_label = QLabel()
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(lambda _text: self.completeChanged.emit())
        layout.addRow(self.name_label, self.name_edit)
        self.output_label = QLabel()
        output_layout = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.textChanged.connect(lambda _text: self.completeChanged.emit())
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._Output_Browse)
        output_layout.addWidget(self.output_edit, 1)
        output_layout.addWidget(self.browse_button)
        layout.addRow(self.output_label, output_layout)
        self.firmware_label = QLabel()
        self.firmware_edit = QLineEdit("0.0.9")
        layout.addRow(self.firmware_label, self.firmware_edit)
        self.mcu_label = QLabel()
        self.mcu_combo = StandardComboBox()
        layout.addRow(self.mcu_label, self.mcu_combo)
        self.Language_Apply(translator)

    def isComplete(self) -> bool:
        return bool(
            self.name_edit.text().strip()
            and self.output_edit.text().strip()
            and self.mcu_combo.currentData()
        )

    def Language_Apply(self, translator: Translator) -> None:
        self._translator = translator
        self.setTitle(translator.Text_Get("wizard.step.project"))
        self.setSubTitle(translator.Text_Get("wizard.identity_summary"))
        self.name_label.setText(translator.Text_Get("field.project_name"))
        self.name_edit.setPlaceholderText(translator.Text_Get("placeholder.project_name"))
        self.output_label.setText(translator.Text_Get("field.output_directory"))
        self.output_edit.setPlaceholderText(
            translator.Text_Get("placeholder.output_directory")
        )
        self.browse_button.setText(translator.Text_Get("action.browse"))
        self.firmware_label.setText(translator.Text_Get("field.firmware_version"))
        self.mcu_label.setText(translator.Text_Get("field.mcu"))

    def _Output_Browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            self._translator.Text_Get("dialog.select_output_directory"),
            self.output_edit.text() or str(Path.cwd()),
        )
        if selected:
            self.output_edit.setText(selected)


class NewProjectWizard(QWizard):
    """One-step identity dialog; configuration continues through the six main pages."""

    def __init__(self, translator: Translator, parent=None) -> None:
        super().__init__(parent)
        self._translator = translator
        self.identity_page = ProjectIdentityWizardPage(translator)
        self.addPage(self.identity_page)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.Language_Apply(translator)

    def Catalog_Set(self, components: list[ComponentView] | tuple[ComponentView, ...]) -> None:
        self.identity_page.mcu_combo.clear()
        for component in components:
            if component.component_type.value == "mcu":
                self.identity_page.mcu_combo.addItem(
                    component.name, component.component_id
                )
        self.identity_page.completeChanged.emit()

    def WizardData_Get(self) -> dict[str, Any]:
        return {
            "name": self.identity_page.name_edit.text().strip(),
            "output_directory": self.identity_page.output_edit.text().strip(),
            "firmware_version": self.identity_page.firmware_edit.text().strip(),
            "mcu": str(self.identity_page.mcu_combo.currentData() or ""),
        }

    def Language_Apply(self, translator: Translator) -> None:
        self._translator = translator
        self.setWindowTitle(translator.Text_Get("dialog.new_project"))
        self.identity_page.Language_Apply(translator)
        self.setButtonText(QWizard.WizardButton.FinishButton, translator.Text_Get("wizard.finish"))
        self.setButtonText(QWizard.WizardButton.CancelButton, translator.Text_Get("action.cancel"))
