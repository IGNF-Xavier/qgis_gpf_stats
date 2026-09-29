"""« Datastores » tab (storage usage, quotas, endpoints available per
datastore - ``GET /datastores/{id}``). This route is slow (10-30s each on
production), so it never loads anything on its own: the user picks which
rows to fetch, exactly like the datastore-selection step before a catalog
refresh.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..exporters.xlsx_exporter import human_bytes

COLUMNS = ("", "Nom", "Nom technique", "Statut", "Stockage", "Endpoints")


class DatastoreInfoTab(QWidget):
    refreshListRequested = pyqtSignal()
    detailRequested = pyqtSignal(list)  # list[DatastoreRef]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._refs_by_id: dict = {}
        self._infos_by_id: dict = {}

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Le détail (stockage, endpoints) est chargé à la demande, datastore par datastore : "
            "chaque appel peut prendre jusqu'à 30 secondes. Cochez uniquement ce qui vous intéresse."
        ))

        top_row = QHBoxLayout()
        self.btn_refresh_list = QPushButton("Actualiser la liste des datastores")
        self.btn_refresh_list.clicked.connect(self.refreshListRequested.emit)
        top_row.addWidget(self.btn_refresh_list)
        top_row.addStretch()
        root.addLayout(top_row)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher un datastore…")
        self.search.textChanged.connect(self._apply_filter)
        root.addWidget(self.search)

        bulk_row = QHBoxLayout()
        self.btn_check_all = QPushButton("Tout cocher")
        self.btn_uncheck_all = QPushButton("Tout décocher")
        self.btn_load_detail = QPushButton("Charger le détail des datastores cochés")
        self.btn_check_all.clicked.connect(lambda: self._set_all_checked(True))
        self.btn_uncheck_all.clicked.connect(lambda: self._set_all_checked(False))
        self.btn_load_detail.clicked.connect(self._emit_detail_request)
        for button in (self.btn_check_all, self.btn_uncheck_all, self.btn_load_detail):
            bulk_row.addWidget(button)
        bulk_row.addStretch()
        self.count_label = QLabel()
        bulk_row.addWidget(self.count_label)
        root.addLayout(bulk_row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._show_detail_for_current_row)
        root.addWidget(self.table, 2)

        root.addWidget(QLabel("<b>Détail du datastore sélectionné</b>"))
        self.detail_tree = QTreeWidget()
        self.detail_tree.setHeaderHidden(True)
        root.addWidget(self.detail_tree, 3)

    # -- populating ---------------------------------------------------------
    def set_datastore_refs(self, refs: list) -> None:
        self._refs_by_id = {ref.datastore_id: ref for ref in refs}
        self._infos_by_id = {}
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for ref in sorted(refs, key=lambda r: r.name.casefold()):
            row = self.table.rowCount()
            self.table.insertRow(row)
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            check_item.setCheckState(Qt.Unchecked)
            check_item.setData(Qt.UserRole, ref.datastore_id)
            self.table.setItem(row, 0, check_item)
            self.table.setItem(row, 1, QTableWidgetItem(ref.name))
            self.table.setItem(row, 2, QTableWidgetItem(ref.technical_name))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            self.table.setItem(row, 4, QTableWidgetItem("(non chargé)"))
            self.table.setItem(row, 5, QTableWidgetItem("(non chargé)"))
        self.table.blockSignals(False)
        self.detail_tree.clear()
        self._refresh_count()

    def apply_datastore_infos(self, infos: list, errors: list) -> None:
        for info in infos:
            self._infos_by_id[info.datastore_id] = info
        errors_by_id = {e.datastore_id: e for e in errors}
        for row in range(self.table.rowCount()):
            datastore_id = self.table.item(row, 0).data(Qt.UserRole)
            info = self._infos_by_id.get(datastore_id)
            if info is not None:
                self.table.item(row, 3).setText("Actif" if info.active else "Inactif")
                self.table.item(row, 4).setText(
                    f"{human_bytes(info.total_use_bytes())} / {human_bytes(info.total_quota_bytes())}"
                )
                connected = sum(1 for e in info.endpoints if e.use > 0)
                self.table.item(row, 5).setText(f"{len(info.endpoints)} endpoint(s), {connected} avec offre raccordée")
            elif datastore_id in errors_by_id:
                self.table.item(row, 4).setText("Erreur")
                self.table.item(row, 5).setText(errors_by_id[datastore_id].message)
        self._show_detail_for_current_row()

    # -- selection / filtering -----------------------------------------------
    def _apply_filter(self, text: str) -> None:
        needle = text.casefold().strip()
        for row in range(self.table.rowCount()):
            name = self.table.item(row, 1).text().casefold()
            technical = self.table.item(row, 2).text().casefold()
            self.table.setRowHidden(row, bool(needle and needle not in name and needle not in technical))

    def _set_all_checked(self, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                self.table.item(row, 0).setCheckState(state)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._refresh_count()

    def _refresh_count(self) -> None:
        total = self.table.rowCount()
        checked = sum(1 for row in range(total) if self.table.item(row, 0).checkState() == Qt.Checked)
        self.count_label.setText(f"{checked} datastore(s) coché(s) sur {total}")

    def checked_refs(self) -> list:
        refs = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.Checked:
                datastore_id = self.table.item(row, 0).data(Qt.UserRole)
                ref = self._refs_by_id.get(datastore_id)
                if ref is not None:
                    refs.append(ref)
        return refs

    def _emit_detail_request(self) -> None:
        refs = self.checked_refs()
        if refs:
            self.detailRequested.emit(refs)

    # -- detail panel ---------------------------------------------------------
    def _show_detail_for_current_row(self) -> None:
        self.detail_tree.clear()
        row = self.table.currentRow()
        if row < 0:
            return
        datastore_id = self.table.item(row, 0).data(Qt.UserRole)
        info = self._infos_by_id.get(datastore_id)
        if info is None:
            return

        storage_root = QTreeWidgetItem([f"Stockage — {human_bytes(info.total_use_bytes())} / {human_bytes(info.total_quota_bytes())}"])
        self.detail_tree.addTopLevelItem(storage_root)
        for storage in info.data_storages:
            pct = f"{100 * storage.use_bytes / storage.quota_bytes:.1f} %" if storage.quota_bytes else "—"
            storage_root.addChild(QTreeWidgetItem([f"{storage.name} ({storage.type}) — {human_bytes(storage.use_bytes)} / {human_bytes(storage.quota_bytes)} ({pct})"]))
        for label, storage in (("Dépôts (uploads)", info.uploads_storage), ("Annexes", info.annexes_storage)):
            if storage is not None:
                pct = f"{100 * storage.use_bytes / storage.quota_bytes:.1f} %" if storage.quota_bytes else "—"
                storage_root.addChild(QTreeWidgetItem([f"{label} : {storage.name} — {human_bytes(storage.use_bytes)} / {human_bytes(storage.quota_bytes)} ({pct})"]))

        endpoints_root = QTreeWidgetItem([f"Endpoints — {len(info.endpoints)}"])
        self.detail_tree.addTopLevelItem(endpoints_root)
        for endpoint in sorted(info.endpoints, key=lambda e: e.name.casefold()):
            visibility = "ouvert" if endpoint.open else "restreint"
            item = QTreeWidgetItem([f"{endpoint.name} · {endpoint.type} · {visibility} · {endpoint.use}/{endpoint.quota} offre(s) raccordée(s)"])
            if endpoint.urls:
                item.setToolTip(0, "\n".join(endpoint.urls))
            endpoints_root.addChild(item)

        self.detail_tree.expandAll()
