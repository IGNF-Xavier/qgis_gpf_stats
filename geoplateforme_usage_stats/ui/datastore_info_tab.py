"""« Datastores » tab (storage usage, quotas, endpoints available per
datastore - ``GET /datastores/{id}``). This route is slow (10-30s each on
production), so it never loads anything on its own: the user picks which
rows to fetch, exactly like the datastore-selection step before a catalog
refresh.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
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
DETAIL_COLUMNS = ("Nom", "Type", "Utilisé", "Quota", "Détail")
NEAR_QUOTA_COLOR = QColor("#b26a00")
OVER_QUOTA_COLOR = QColor("#990000")


class DatastoreInfoTab(QWidget):
    refreshListRequested = pyqtSignal()
    detailRequested = pyqtSignal(list)  # list[DatastoreRef]
    exportRequested = pyqtSignal()

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
        self.btn_export = QPushButton("Exporter le détail chargé (CSV)…")
        self.btn_check_all.clicked.connect(lambda: self._set_all_checked(True))
        self.btn_uncheck_all.clicked.connect(lambda: self._set_all_checked(False))
        self.btn_load_detail.clicked.connect(self._emit_detail_request)
        self.btn_export.clicked.connect(self.exportRequested.emit)
        for button in (self.btn_check_all, self.btn_uncheck_all, self.btn_load_detail, self.btn_export):
            bulk_row.addWidget(button)
        bulk_row.addStretch()
        self.count_label = QLabel()
        bulk_row.addWidget(self.count_label)
        root.addLayout(bulk_row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        header = self.table.horizontalHeader()
        # Only "Nom" stretches to fill leftover space; every other column stays
        # Interactive (draggable) - "Nom technique" and the others get their
        # real width from resizeColumnToContents() once populated, instead of
        # a cramped default that made their header labels wrap onto two lines
        # and overlap the row below.
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(60)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._show_detail_for_current_row)
        root.addWidget(self.table, 2)

        root.addWidget(QLabel("<b>Détail du datastore sélectionné</b>"))
        self.detail_tree = QTreeWidget()
        self.detail_tree.setColumnCount(len(DETAIL_COLUMNS))
        self.detail_tree.setHeaderLabels(DETAIL_COLUMNS)
        self.detail_tree.setAlternatingRowColors(True)
        self.detail_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
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
        self._resize_columns_to_contents()
        self.detail_tree.clear()
        self._refresh_count()

    def _resize_columns_to_contents(self) -> None:
        for col in range(len(COLUMNS)):
            if col != 1:  # "Nom" is Stretch - sizing it to contents would fight that
                self.table.resizeColumnToContents(col)

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
        self._resize_columns_to_contents()
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

    def loaded_infos(self) -> list:
        return list(self._infos_by_id.values())

    # -- detail panel ---------------------------------------------------------
    @staticmethod
    def _pct_value(use_bytes: int, quota_bytes: int):
        return (100 * use_bytes / quota_bytes) if quota_bytes else None

    @staticmethod
    def _pct_text(pct) -> str:
        return f"{pct:.1f} %" if pct is not None else "—"

    def _make_row(self, name: str, type_: str, used_text: str, quota_text: str, detail_text: str, pct=None, bold: bool = False) -> QTreeWidgetItem:
        item = QTreeWidgetItem([name, type_, used_text, quota_text, detail_text])
        for col in (2, 3, 4):
            item.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
        if bold:
            for col in range(len(DETAIL_COLUMNS)):
                font = item.font(col)
                font.setBold(True)
                item.setFont(col, font)
        elif pct is not None and pct >= 90:
            color = OVER_QUOTA_COLOR if pct >= 100 else NEAR_QUOTA_COLOR
            for col in range(len(DETAIL_COLUMNS)):
                item.setForeground(col, color)
        return item

    def _show_detail_for_current_row(self) -> None:
        self.detail_tree.clear()
        row = self.table.currentRow()
        if row < 0:
            return
        datastore_id = self.table.item(row, 0).data(Qt.UserRole)
        info = self._infos_by_id.get(datastore_id)
        if info is None:
            return

        total_use, total_quota = info.total_use_bytes(), info.total_quota_bytes()
        total_pct = self._pct_value(total_use, total_quota)
        storage_root = self._make_row(
            "Stockage (total)", "", human_bytes(total_use),
            human_bytes(total_quota) if total_quota else "—",
            self._pct_text(total_pct), bold=True,
        )
        self.detail_tree.addTopLevelItem(storage_root)
        for storage in sorted(info.data_storages, key=lambda s: s.use_bytes, reverse=True):
            pct = self._pct_value(storage.use_bytes, storage.quota_bytes)
            storage_root.addChild(self._make_row(
                storage.name, storage.type, human_bytes(storage.use_bytes),
                human_bytes(storage.quota_bytes) if storage.quota_bytes else "—",
                self._pct_text(pct), pct,
            ))
        for label, storage in (("Dépôts (uploads)", info.uploads_storage), ("Annexes", info.annexes_storage)):
            if storage is not None:
                pct = self._pct_value(storage.use_bytes, storage.quota_bytes)
                storage_root.addChild(self._make_row(
                    f"{label} : {storage.name}", storage.type, human_bytes(storage.use_bytes),
                    human_bytes(storage.quota_bytes) if storage.quota_bytes else "—",
                    self._pct_text(pct), pct,
                ))

        endpoints_root = self._make_row(f"Endpoints ({len(info.endpoints)})", "", "", "", "", bold=True)
        self.detail_tree.addTopLevelItem(endpoints_root)
        for endpoint in sorted(info.endpoints, key=lambda e: e.name.casefold()):
            visibility = "Ouvert" if endpoint.open else "Restreint"
            item = self._make_row(
                endpoint.name, endpoint.type, f"{endpoint.use} offre(s)",
                f"{endpoint.quota} max" if endpoint.quota else "—", visibility,
            )
            if endpoint.urls:
                for col in range(len(DETAIL_COLUMNS)):
                    item.setToolTip(col, "\n".join(endpoint.urls))
            endpoints_root.addChild(item)

        self.detail_tree.expandAll()
        for col in range(1, len(DETAIL_COLUMNS)):
            self.detail_tree.resizeColumnToContents(col)
