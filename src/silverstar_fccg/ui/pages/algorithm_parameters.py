from __future__ import annotations

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QGroupBox, QLabel, QPushButton, QVBoxLayout, QWidget

from silverstar_fccg.core.i18n import Translator
from silverstar_fccg.plugins.manifest import PluginManifest
from silverstar_fccg.ui.pages.base import ScrollableLocalizedPage
from silverstar_fccg.ui.widgets import CollapsibleSection


class AlgorithmParametersPage(ScrollableLocalizedPage):
    parameterChanged = Signal(str, str, object)
    defaultsRequested = Signal(str)

    def __init__(self, translator: Translator) -> None:
        super().__init__(translator, "page.algorithm_parameters", "algorithm_parameters.description")
        self._content = QWidget()
        self.root_layout.addWidget(self._content)
        self.root_layout.addStretch(1)
        self._owners: tuple[PluginManifest, ...] = ()
        self._values: dict = {}
        self._expanded: dict[tuple[str, str], bool] = {}
        self.editors: dict[tuple[str, str], QDoubleSpinBox] = {}

    def Configuration_Set(self, owners: tuple[PluginManifest, ...], values: dict) -> None:
        self._owners = owners
        self._values = values
        content = QWidget()
        layout = QVBoxLayout(content)
        self.editors = {}
        language = self._translator.language
        if not owners:
            layout.addWidget(QLabel(self._translator.Text_Get("algorithm_parameters.empty")))
        for owner in owners:
            group = QGroupBox(owner.DisplayName_Get(language))
            group_layout = QVBoxLayout(group)
            for level in ("basic", "advanced"):
                parameters = [p for p in owner.algorithm_parameters if p.group == level]
                if not parameters:
                    continue
                key = (owner.component_id, level)
                section = CollapsibleSection(expanded=self._expanded.get(key, level == "basic"))
                section.ExpandedChanged.connect(lambda expanded, k=key: self._expanded.__setitem__(k, expanded))
                section.Title_Set(self._translator.Text_Get("algorithm_parameters." + level))
                form = QFormLayout(section.body)
                form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
                for parameter in parameters:
                    editor = QDoubleSpinBox()
                    editor.setDecimals(parameter.precision)
                    editor.setRange(parameter.minimum, parameter.maximum)
                    editor.setSingleStep(parameter.step)
                    editor.setKeyboardTracking(False)
                    editor.setSuffix(" " + parameter.unit)
                    editor.setToolTip(parameter.Description_Get(language))
                    editor.setValue(values.get(owner.component_id, {}).get(parameter.parameter_id, parameter.default))
                    editor.valueChanged.connect(
                        lambda value, c=owner.component_id, p=parameter:
                        QTimer.singleShot(0, self, lambda:
                            self.parameterChanged.emit(c, p.parameter_id, int(value) if p.value_type == "integer" else value)))
                    form.addRow(parameter.DisplayName_Get(language), editor)
                    self.editors[(owner.component_id, parameter.parameter_id)] = editor
                group_layout.addWidget(section)
            reset = QPushButton(self._translator.Text_Get("algorithm_parameters.reset"))
            reset.clicked.connect(lambda _checked=False, c=owner.component_id:
                                  QTimer.singleShot(0, self, lambda: self.defaultsRequested.emit(c)))
            group_layout.addWidget(reset)
            layout.addWidget(group)
        self.root_layout.replaceWidget(self._content, content)
        self._content.hide()
        self._content.deleteLater()
        self._content = content

    def Language_Apply(self, translator: Translator) -> None:
        super().Language_Apply(translator)
        self.Configuration_Set(self._owners, self._values)
