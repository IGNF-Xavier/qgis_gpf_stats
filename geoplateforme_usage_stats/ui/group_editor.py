"""Group composition window (section 2.4).

Left panel: group list + Créer/Renommer/Supprimer/Dupliquer.
Right panel: search + datastore/service-type filters + checkable offering
list + bulk check/uncheck controls + a live "N sur M" counter.

All edits happen on an in-memory ``list[Group]`` (immutable dataclasses,
replaced wholesale on each change) and are only handed back to the caller
when the dialog is accepted - the caller is responsible for persisting them
through ``core.group_service.GroupService.save``.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core import group_service as gs
from ..core.group_service import GroupService


class GroupEditor(QDialog):
    def __init__(self, groups: list, offerings: list, group_service: GroupService, parent=None):
        super().__init__(parent)
        # Window-modal: blocks only the plugin's own window while composing
        # groups, never the rest of QGIS (canvas, other panels, other plugins).
        self.setWindowModality(Qt.WindowModal)
        self.groups = list(groups)
        self.offerings = list(offerings)
        self._offerings_by_id = {o.offering_id: o for o in self.offerings}
        self._service = group_service
        self._current_group_id: str | None = None
        self._loading = False

        self.setWindowTitle("Composer les groupes d'offres")
        self.resize(1050, 650)
        root = QVBoxLayout(self)

        if not self.offerings:
            root.addWidget(QLabel(
                "⚠ Aucun offering n'est disponible : chargez d'abord le catalogue producteur "
                "(bouton « Charger les droits ») pour pouvoir affecter des offres à un groupe."
            ))

        self.overlap_warning = QLabel()
        self.overlap_warning.setWordWrap(True)
        self.overlap_warning.setStyleSheet("color: #990000;")
        root.addWidget(self.overlap_warning)

        split = QSplitter()
        root.addWidget(split, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("<b>Groupes</b>"))
        self.group_list = QListWidget()
        self.group_list.currentItemChanged.connect(self._on_group_changed)
        left_layout.addWidget(self.group_list, 1)
        button_row = QHBoxLayout()
        for text, slot in (
            ("Créer…", self._create_group),
            ("Renommer…", self._rename_group),
            ("Supprimer", self._delete_group),
            ("Dupliquer", self._duplicate_group),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            button_row.addWidget(button)
        left_layout.addLayout(button_row)
        split.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        filters_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher une offre…")
        self.search.textChanged.connect(self._apply_filters)
        filters_row.addWidget(self.search, 2)
        self.datastore_filter = QComboBox()
        self.datastore_filter.addItem("Tous les datastores", "")
        for name in sorted({o.datastore_name for o in self.offerings if o.datastore_name}):
            self.datastore_filter.addItem(name, name)
        self.datastore_filter.currentIndexChanged.connect(self._apply_filters)
        filters_row.addWidget(self.datastore_filter, 1)
        self.service_type_filter = QComboBox()
        self.service_type_filter.addItem("Tous les types de service", "")
        for name in sorted({o.service_type for o in self.offerings if o.service_type}):
            self.service_type_filter.addItem(name, name)
        self.service_type_filter.currentIndexChanged.connect(self._apply_filters)
        filters_row.addWidget(self.service_type_filter, 1)
        right_layout.addLayout(filters_row)

        bulk_row = QHBoxLayout()
        for text, slot in (
            ("Tout cocher", self._check_all),
            ("Tout décocher", self._uncheck_all),
            ("Cocher les éléments visibles", self._check_visible),
            ("Décocher les éléments visibles", self._uncheck_visible),
        ):
            button = QPushButton(text)
            button.clicked.connect(slot)
            bulk_row.addWidget(button)
        bulk_row.addStretch()
        right_layout.addLayout(bulk_row)

        self.offering_list = QListWidget()
        self.offering_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.offering_list.itemChanged.connect(self._on_item_toggled)
        right_layout.addWidget(self.offering_list, 1)

        self.counter_label = QLabel()
        right_layout.addWidget(self.counter_label)
        split.addWidget(right)
        split.setStretchFactor(1, 3)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._refresh_group_list()
        self._refresh_overlap_warning()

    # -- group list -----------------------------------------------------
    def _refresh_group_list(self, select_id: str | None = None) -> None:
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for group in sorted(self.groups, key=lambda g: g.name.casefold()):
            item = QListWidgetItem(f"{group.name}  ({len(group.offering_ids)})")
            item.setData(Qt.UserRole, group.group_id)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        target_id = select_id or self._current_group_id
        for index in range(self.group_list.count()):
            if self.group_list.item(index).data(Qt.UserRole) == target_id:
                self.group_list.setCurrentRow(index)
                return
        if self.group_list.count():
            self.group_list.setCurrentRow(0)
        else:
            self._current_group_id = None
            self.offering_list.clear()

    def _refresh_overlap_warning(self) -> None:
        pairs = gs.overlapping_pairs(self.groups)
        if not pairs:
            self.overlap_warning.setText("")
            return
        details = "; ".join(f"« {a.name} » / « {b.name} » ({len(common)} offre(s))" for a, b, common in pairs)
        self.overlap_warning.setText(
            "⚠ Des groupes se chevauchent : " + details +
            ". N'additionnez pas leurs totaux sans vérifier ce recouvrement."
        )

    def _create_group(self) -> None:
        name, ok = QInputDialog.getText(self, "Créer un groupe", "Nom du groupe :")
        if not ok or not name.strip():
            return
        try:
            self.groups = self._service.create(self.groups, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Créer un groupe", str(exc))
            return
        self._refresh_group_list(select_id=self.groups[-1].group_id)
        self._refresh_overlap_warning()

    def _rename_group(self) -> None:
        if self._current_group_id is None:
            return
        current = self._service.find(self.groups, self._current_group_id)
        name, ok = QInputDialog.getText(self, "Renommer le groupe", "Nouveau nom :", text=current.name)
        if not ok or not name.strip():
            return
        try:
            self.groups = self._service.rename(self.groups, self._current_group_id, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Renommer le groupe", str(exc))
            return
        self._refresh_group_list()

    def _delete_group(self) -> None:
        if self._current_group_id is None:
            return
        current = self._service.find(self.groups, self._current_group_id)
        if QMessageBox.question(self, "Supprimer le groupe", f"Supprimer le groupe « {current.name} » ?") != QMessageBox.Yes:
            return
        self.groups = self._service.delete(self.groups, self._current_group_id)
        self._current_group_id = None
        self._refresh_group_list()
        self._refresh_overlap_warning()

    def _duplicate_group(self) -> None:
        if self._current_group_id is None:
            return
        self.groups = self._service.duplicate(self.groups, self._current_group_id)
        self._refresh_group_list(select_id=self.groups[-1].group_id)
        self._refresh_overlap_warning()

    # -- offering list ----------------------------------------------------
    def _on_group_changed(self, current: QListWidgetItem, _previous) -> None:
        self._current_group_id = current.data(Qt.UserRole) if current else None
        self._rebuild_offering_list()

    def _other_groups_by_offering(self) -> dict:
        result: dict[str, list[str]] = {}
        for group in self.groups:
            if group.group_id == self._current_group_id:
                continue
            for offering_id in group.offering_ids:
                result.setdefault(offering_id, []).append(group.name)
        return result

    def _rebuild_offering_list(self) -> None:
        self._loading = True
        self.offering_list.clear()
        group = self._service.find(self.groups, self._current_group_id) if self._current_group_id else None
        members = set(group.offering_ids) if group else set()
        other_groups = self._other_groups_by_offering()
        for offering in sorted(self.offerings, key=lambda o: (o.datastore_name, o.offering_name.casefold())):
            text = f"{offering.offering_name}  ·  {offering.service_type}  ·  {offering.datastore_name}  ·  {offering.endpoint_name}"
            memberships = other_groups.get(offering.offering_id, [])
            if memberships:
                text += f"   [aussi dans : {', '.join(sorted(memberships))}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, offering.offering_id)
            tooltip = f"UUID offering : {offering.offering_id}"
            if memberships:
                tooltip += "\nAppartient aussi à : " + ", ".join(sorted(memberships))
                item.setForeground(QColor("#8E5C00"))
            item.setToolTip(tooltip)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if offering.offering_id in members else Qt.Unchecked)
            self.offering_list.addItem(item)
        self._loading = False
        self._apply_filters()
        self._refresh_counter()

    def _apply_filters(self) -> None:
        needle = self.search.text().casefold().strip()
        datastore = self.datastore_filter.currentData()
        service_type = self.service_type_filter.currentData()
        for index in range(self.offering_list.count()):
            item = self.offering_list.item(index)
            offering = self._offerings_by_id.get(item.data(Qt.UserRole))
            visible = True
            if needle and needle not in item.text().casefold():
                visible = False
            if datastore and offering and offering.datastore_name != datastore:
                visible = False
            if service_type and offering and offering.service_type != service_type:
                visible = False
            item.setHidden(not visible)
        self._refresh_counter()

    def _on_item_toggled(self, item: QListWidgetItem) -> None:
        if self._loading or self._current_group_id is None:
            return
        group = self._service.find(self.groups, self._current_group_id)
        members = set(group.offering_ids)
        offering_id = item.data(Qt.UserRole)
        if item.checkState() == Qt.Checked:
            members.add(offering_id)
        else:
            members.discard(offering_id)
        self.groups = self._service.set_offering_ids(self.groups, self._current_group_id, members)
        self._refresh_group_list()
        self._refresh_overlap_warning()
        self._refresh_counter()

    def _visible_items(self) -> list[QListWidgetItem]:
        return [self.offering_list.item(i) for i in range(self.offering_list.count()) if not self.offering_list.item(i).isHidden()]

    def _set_checked(self, items: list[QListWidgetItem], checked: bool) -> None:
        if self._current_group_id is None:
            return
        group = self._service.find(self.groups, self._current_group_id)
        members = set(group.offering_ids)
        for item in items:
            offering_id = item.data(Qt.UserRole)
            if checked:
                members.add(offering_id)
            else:
                members.discard(offering_id)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.groups = self._service.set_offering_ids(self.groups, self._current_group_id, members)
        self._refresh_group_list()
        self._refresh_overlap_warning()
        self._refresh_counter()

    def _check_all(self) -> None:
        self._loading = True
        self._set_checked([self.offering_list.item(i) for i in range(self.offering_list.count())], True)
        self._loading = False

    def _uncheck_all(self) -> None:
        self._loading = True
        self._set_checked([self.offering_list.item(i) for i in range(self.offering_list.count())], False)
        self._loading = False

    def _check_visible(self) -> None:
        self._loading = True
        self._set_checked(self._visible_items(), True)
        self._loading = False

    def _uncheck_visible(self) -> None:
        self._loading = True
        self._set_checked(self._visible_items(), False)
        self._loading = False

    def _refresh_counter(self) -> None:
        total = self.offering_list.count()
        checked = sum(1 for i in range(total) if self.offering_list.item(i).checkState() == Qt.Checked)
        self.counter_label.setText(f"{checked} offre(s) sélectionnée(s) sur {total}")
