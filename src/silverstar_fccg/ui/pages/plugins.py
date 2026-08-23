from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.core.view_models import ComponentView
from silverstar_fccg.ui.pages.base import LocalizedPage
from silverstar_fccg.ui.widgets import EngineeringTable


class PluginsPage(LocalizedPage):
    installRequested = Signal()
    removeRequested = Signal(str)
    detailsRequested = Signal(str)

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.plugins", "page.plugins.description")
        notice = QLabel()
        notice.setObjectName("noticeLabel")
        notice.setWordWrap(True)
        self.Text_Register(notice, "plugin.execution_safety_notice")
        self.root_layout.addWidget(notice)

        toolbar = QHBoxLayout()
        self.install_button = QPushButton()
        self.install_button.setObjectName("primaryButton")
        self.Text_Register(self.install_button, "action.install_plugin")
        self.install_button.clicked.connect(
            lambda _checked=False: self.installRequested.emit()
        )
        self.remove_button = QPushButton()
        self.remove_button.setObjectName("dangerButton")
        self.Text_Register(self.remove_button, "action.remove_plugin")
        self.remove_button.clicked.connect(self._Remove_Emit)
        self.details_button = QPushButton()
        self.Text_Register(self.details_button, "action.plugin_details")
        self.details_button.clicked.connect(self._Details_Emit)
        toolbar.addWidget(self.install_button)
        toolbar.addWidget(self.remove_button)
        toolbar.addWidget(self.details_button)
        toolbar.addStretch(1)
        self.root_layout.addLayout(toolbar)

        self.plugin_table = self.Table_Register(
            EngineeringTable(
                (
                    "column.id",
                    "column.name",
                    "column.type",
                    "column.class",
                    "column.version",
                    "column.source",
                    "column.dependencies",
                    "column.provides",
                    "column.status",
                )
            )
        )
        self.root_layout.addWidget(self.plugin_table, 1)
        self._components: list[ComponentView] = []
        self.Language_Apply(translator)

    def Components_Set(self, components: Iterable[ComponentView]) -> None:
        self._components = list(components)
        self.plugin_table.Rows_Set(
            (
                component.component_id,
                component.name,
                component.component_type.value,
                component.component_class or "—",
                component.version,
                component.source or "—",
                ", ".join(component.dependencies) or "—",
                ", ".join(component.provides) or "—",
                self._translator.Text_Get(f"component.status.{component.status}"),
            )
            for component in self._components
        )

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self.Components_Set(self._components)

    def _SelectedId_Get(self) -> str:
        row = self.plugin_table.currentRow()
        return self._components[row].component_id if 0 <= row < len(self._components) else ""

    def _Remove_Emit(self) -> None:
        component_id = self._SelectedId_Get()
        if component_id:
            self.removeRequested.emit(component_id)

    def _Details_Emit(self) -> None:
        component_id = self._SelectedId_Get()
        if component_id:
            self.detailsRequested.emit(component_id)
