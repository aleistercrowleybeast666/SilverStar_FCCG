from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QLabel,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from silverstar_fccg.core.i18n import Translator


class StandardComboBox(QComboBox):
    """Conventional dropdown with at most ten visible rows."""

    MAX_VISIBLE_ITEMS = 10

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.setMaxVisibleItems(self.MAX_VISIBLE_ITEMS)
        self.setMinimumContentsLength(12)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view().setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)

    def showPopup(self) -> None:
        view = self.view()
        view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
            if self.count() > self.MAX_VISIBLE_ITEMS
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        super().showPopup()
        if self.count() == 0:
            return
        popup = view.window()
        if not popup.isVisible():
            return
        available = self.screen().availableGeometry()
        combo_top = self.mapToGlobal(QPoint(0, 0))
        combo_bottom = self.mapToGlobal(QPoint(0, self.height()))
        popup_height = popup.height()
        if self.count() > self.MAX_VISIBLE_ITEMS:
            row_height = sum(
                max(view.sizeHintForRow(index), 1) for index in range(self.MAX_VISIBLE_ITEMS)
            )
            scroller_height = self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            popup_height = min(popup_height, row_height + scroller_height)
        popup.resize(max(popup.width(), self.width()), popup_height)
        maximum_x = max(available.left(), available.right() - popup.width() + 1)
        popup_x = min(max(combo_bottom.x(), available.left()), maximum_x)
        popup_y = (
            combo_bottom.y()
            if combo_bottom.y() + popup.height() - 1 <= available.bottom()
            else max(available.top(), combo_top.y() - popup.height())
        )
        popup.move(popup_x, popup_y)


class PageHeader(QWidget):
    def __init__(self, title_key: str, description_key: str) -> None:
        super().__init__()
        self.title_key = title_key
        self.description_key = description_key
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(3)
        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        self.description_label = QLabel()
        self.description_label.setObjectName("pageDescription")
        self.description_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)

    def Language_Apply(self, translator: Translator) -> None:
        self.title_label.setText(translator.Text_Get(self.title_key))
        self.description_label.setText(translator.Text_Get(self.description_key))


class EngineeringTable(QTableWidget):
    def __init__(self, column_keys: Sequence[str]) -> None:
        super().__init__(0, len(column_keys))
        self.column_keys = tuple(column_keys)
        self.setObjectName("engineeringTable")
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if self.columnCount() > 0:
            self.horizontalHeader().setSectionResizeMode(
                self.columnCount() - 1, QHeaderView.ResizeMode.Stretch
            )

    def Language_Apply(self, translator: Translator) -> None:
        self.setHorizontalHeaderLabels(
            [translator.Text_Get(column_key) for column_key in self.column_keys]
        )

    def Rows_Set(self, rows: Iterable[Sequence[str]]) -> None:
        row_values = [tuple(str(value) for value in row) for row in rows]
        self.setRowCount(len(row_values))
        for row_index, row in enumerate(row_values):
            for column_index in range(self.columnCount()):
                value = row[column_index] if column_index < len(row) else ""
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.setItem(row_index, column_index, item)
        self.resizeRowsToContents()


class StatusPill(QLabel):
    def Status_Set(self, text: str, level: str) -> None:
        self.setText(text)
        self.setProperty("statusLevel", level)
        self.style().unpolish(self)
        self.style().polish(self)

