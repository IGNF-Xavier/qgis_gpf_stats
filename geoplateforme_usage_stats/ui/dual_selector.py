"""Dual list selector (section 2.5): search on both sides, live counts,
double-click to move, UUID kept in the tooltip rather than the main label.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


KIND_PREFIXES = {
    "offering": "🧩 Offre",
    "endpoint": "🔌 Endpoint",
    "producer_permission": "🔑 Permission",
    "consumer_permission": "🔑 Permission",
}


def _display_text(catalog_item) -> str:
    prefix = KIND_PREFIXES.get(getattr(catalog_item, "kind", ""))
    text = catalog_item.label if not prefix else f"{prefix} — {catalog_item.label}"
    if getattr(catalog_item, "kind", "") == "endpoint" and getattr(catalog_item, "endpoint_quota", 0):
        text += f"  ({catalog_item.endpoint_use}/{catalog_item.endpoint_quota} offre(s) raccordée(s))"
    return text


def _tooltip_for(catalog_item) -> str:
    parts = [f"UUID : {catalog_item.item_id}"]
    if catalog_item.datastore_name:
        parts.append(f"Datastore : {catalog_item.datastore_name}")
    if catalog_item.service_type:
        parts.append(f"Type : {catalog_item.service_type}")
    if getattr(catalog_item, "kind", "") == "endpoint" and getattr(catalog_item, "endpoint_quota", 0):
        parts.append(
            f"Usage : {catalog_item.endpoint_use}/{catalog_item.endpoint_quota} offre(s) raccordée(s) à ce canal de diffusion"
        )
    if catalog_item.stats_path:
        parts.append(f"Route : {catalog_item.stats_path}")
    return "\n".join(parts)


class _SideList(QVBoxLayout):
    def __init__(self, title: str):
        super().__init__()
        self.count_label = QLabel()
        header = QHBoxLayout()
        header.addWidget(QLabel(f"<b>{title}</b>"))
        header.addStretch()
        header.addWidget(self.count_label)
        self.addLayout(header)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher…")
        self.addWidget(self.search)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.addWidget(self.list, 1)
        self.search.textChanged.connect(self._filter)
        self.list.model().rowsInserted.connect(self._refresh_count)
        self.list.model().rowsRemoved.connect(self._refresh_count)

    def _filter(self, text: str) -> None:
        needle = text.casefold().strip()
        for index in range(self.list.count()):
            item = self.list.item(index)
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    def _refresh_count(self, *_args) -> None:
        self.count_label.setText(f"{self.list.count()} élément(s)")


class DualSelector(QWidget):
    selectionChanged = pyqtSignal()

    def __init__(self, available_title: str, selected_title: str, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        body = QHBoxLayout()
        root.addLayout(body)

        self.available = _SideList(available_title)
        body.addLayout(self.available, 1)

        buttons = QVBoxLayout()
        buttons.addStretch()
        self.btn_add_all = QPushButton(">>")
        self.btn_add_selected = QPushButton(">>>")
        self.btn_remove_selected = QPushButton("<<<")
        self.btn_remove_all = QPushButton("<<")
        for button, slot, tip in (
            (self.btn_add_selected, self._add_selected, "Ajouter les éléments sélectionnés"),
            (self.btn_remove_selected, self._remove_selected, "Retirer les éléments sélectionnés"),
            (self.btn_add_all, self._add_all, "Tout ajouter"),
            (self.btn_remove_all, self._remove_all, "Tout retirer"),
        ):
            button.setMinimumWidth(70)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        body.addLayout(buttons)

        self.selected = _SideList(selected_title)
        body.addLayout(self.selected, 1)

        self.available.list.itemDoubleClicked.connect(lambda item: self._move(self.available.list, self.selected.list, [item]))
        self.selected.list.itemDoubleClicked.connect(lambda item: self._move(self.selected.list, self.available.list, [item]))

    def _make_item(self, catalog_item) -> QListWidgetItem:
        item = QListWidgetItem(_display_text(catalog_item))
        item.setData(Qt.UserRole, catalog_item)
        item.setToolTip(_tooltip_for(catalog_item))
        return item

    def set_available(self, catalog_items) -> None:
        self.available.list.clear()
        self.selected.list.clear()
        for catalog_item in sorted(catalog_items, key=lambda i: _display_text(i).casefold()):
            self.available.list.addItem(self._make_item(catalog_item))
        self.available._refresh_count()
        self.selected._refresh_count()

    def _move(self, source: QListWidget, destination: QListWidget, items) -> None:
        for item in list(items):
            catalog_item = item.data(Qt.UserRole)
            source.takeItem(source.row(item))
            destination.addItem(self._make_item(catalog_item))
        destination.sortItems()
        self.selectionChanged.emit()

    def _add_selected(self) -> None:
        self._move(self.available.list, self.selected.list, self.available.list.selectedItems())

    def _remove_selected(self) -> None:
        self._move(self.selected.list, self.available.list, self.selected.list.selectedItems())

    def _add_all(self) -> None:
        self._move(self.available.list, self.selected.list, [self.available.list.item(i) for i in range(self.available.list.count())])

    def _remove_all(self) -> None:
        self._move(self.selected.list, self.available.list, [self.selected.list.item(i) for i in range(self.selected.list.count())])

    def selected_items(self) -> list:
        return [self.selected.list.item(i).data(Qt.UserRole) for i in range(self.selected.list.count())]
