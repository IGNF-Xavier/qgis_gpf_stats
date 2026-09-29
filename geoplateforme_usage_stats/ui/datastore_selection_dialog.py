"""Datastore picker shown before « Actualiser depuis l'API » (section 3):
an account in many communities would otherwise force a full, slow reload of
every single one of them just to refresh a handful.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class DatastoreSelectionDialog(QDialog):
    def __init__(self, refs: list, previously_selected_ids: set, parent=None) -> None:
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle("Choisir les datastores à actualiser")
        self.resize(520, 520)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Sélectionnez les datastores à recharger depuis l'API. Les permissions consommateur "
            "sont toujours actualisées, quel que soit ce choix."
        ))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un datastore…")
        self.search.textChanged.connect(self._apply_filter)
        root.addWidget(self.search)

        bulk_row = QHBoxLayout()
        for text, slot in (("Tout cocher", self._check_all), ("Tout décocher", self._uncheck_all)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            bulk_row.addWidget(button)
        bulk_row.addStretch()
        self.count_label = QLabel()
        bulk_row.addWidget(self.count_label)
        root.addLayout(bulk_row)

        self.list = QListWidget()
        self.list.itemChanged.connect(self._refresh_count)
        for ref in sorted(refs, key=lambda r: r.name.casefold()):
            item = QListWidgetItem(f"{ref.name}  ({ref.technical_name})" if ref.technical_name else ref.name)
            item.setData(Qt.UserRole, ref.datastore_id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if ref.datastore_id in previously_selected_ids else Qt.Unchecked)
            self.list.addItem(item)
        root.addWidget(self.list, 1)
        self._refresh_count()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _apply_filter(self, text: str) -> None:
        needle = text.casefold().strip()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(needle and needle not in item.text().casefold()))

    def _set_all(self, state) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item.isHidden():
                item.setCheckState(state)

    def _check_all(self) -> None:
        self._set_all(Qt.Checked)

    def _uncheck_all(self) -> None:
        self._set_all(Qt.Unchecked)

    def _refresh_count(self, *_args) -> None:
        total = self.list.count()
        checked = sum(1 for i in range(total) if self.list.item(i).checkState() == Qt.Checked)
        self.count_label.setText(f"{checked} datastore(s) sélectionné(s) sur {total}")

    def selected_ids(self) -> set:
        return {
            self.list.item(i).data(Qt.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.Checked
        }
