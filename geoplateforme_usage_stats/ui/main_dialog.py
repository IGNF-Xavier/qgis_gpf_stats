"""Main plugin window: wires the core/net services, the background workers
and every panel together. This module intentionally contains no business
logic of its own (catalog building, coverage, aggregation, exports) - it
only orchestrates calls into ``core``/``net``/``exporters`` and reflects
their results in the widgets.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
)

from ..core import cache_service
from ..core.export_context import build_export_context
from ..core.group_service import GroupService
from ..core.models import ENDPOINT, PRODUCER_PERMISSION
from ..core.period_service import PeriodValidationError
from ..exporters import csv_exporter, xlsx_exporter
from ..net.api_client import ApiClient
from ..net.qgis_transport import QgsTransport
from ..workers.tasks import CatalogLoadTask, StatsQueryTask
from . import settings_store
from .dashboard_widget import DashboardWidget
from .dual_selector import DualSelector
from .glossary_dialog import GlossaryDialog
from .group_editor import GroupEditor
from .period_panel import PeriodPanel
from .producer_tree_selector import ProducerTreeSelector
from .progress_dialog import ProgressDialog
from .settings_dialog import SettingsDialog

CACHE_MAX_AGE_SECONDS = 6 * 3600


@dataclass
class _GroupEntry:
    """Duck-typed like a CatalogItem so it can share the DualSelector with
    real API objects, while staying visually distinct (section 2.4)."""

    kind: str
    label: str
    item_id: str
    group_id: str
    datastore_name: str = ""
    service_type: str = "Groupe utilisateur (local)"
    stats_path: str = ""


class MainDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.group_service = GroupService(settings_store.QgsGroupStore())
        self.groups = self.group_service.load()
        self.cache_store = cache_service.FileCacheStore(settings_store.cache_directory())
        self.catalog = None
        self.results = []
        self.period_config = None
        self._active_task = None
        self._active_dialog = None

        self.setWindowTitle("Statistiques analytiques Géoplateforme 7.2.0")
        self.resize(1500, 980)
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualiser depuis l'API")
        self.btn_use_cache = QPushButton("Utiliser le cache")
        self.btn_clear_cache = QPushButton("Vider le cache")
        self.btn_groups = QPushButton("Composer les groupes…")
        self.btn_run = QPushButton("Interroger la sélection")
        self.btn_groups.setEnabled(False)
        for button, slot in (
            (self.btn_refresh, self._load_from_api),
            (self.btn_use_cache, self._load_from_cache),
            (self.btn_clear_cache, self._clear_cache),
            (self.btn_groups, self._open_group_editor),
            (self.btn_run, self._run_query),
        ):
            button.clicked.connect(slot)
            top.addWidget(button)
        top.addStretch()
        root.addLayout(top)

        producer_filters = QHBoxLayout()
        self.hide_unused_endpoints = QCheckBox("Masquer les endpoints sans offre raccordée (usage = 0)")
        self.hide_unused_endpoints.setToolTip(
            "Un datastore peut avoir une dizaine d'endpoints (un par service technique : WMTS, "
            "WFS, CSW, téléchargement…) même quand peu d'offres y sont réellement raccordées. "
            "Cochez pour ne garder que les endpoints avec au moins une offre active."
        )
        self.hide_unused_endpoints.toggled.connect(self._refresh_producer_selector)
        producer_filters.addWidget(self.hide_unused_endpoints)
        producer_filters.addStretch()
        root.addLayout(producer_filters)

        self.tabs = QTabWidget()
        self.consumer_selector = DualSelector("Permissions consommateur disponibles", "Permissions consommateur sélectionnées")
        self.producer_selector = ProducerTreeSelector("Objets producteur et groupes disponibles", "Objets producteur et groupes sélectionnés")
        self.dashboard = DashboardWidget()
        self.tabs.addTab(self.consumer_selector, "Consommateur")
        self.tabs.addTab(self.producer_selector, "Producteur")
        self.tabs.addTab(self.dashboard, "Dashboard")
        root.addWidget(self.tabs, 1)

        self.period_panel = PeriodPanel()
        root.addWidget(self.period_panel)

        exports = QHBoxLayout()
        self.btn_export_csv = QPushButton("Exporter CSV…")
        self.btn_export_xlsx = QPushButton("Exporter XLSX analytique…")
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_xlsx.clicked.connect(self._export_xlsx)
        exports.addWidget(self.btn_export_csv)
        exports.addWidget(self.btn_export_xlsx)
        exports.addStretch()
        root.addLayout(exports)

        self.status_label = QLabel(
            "Chargez les droits (API ou cache), composez éventuellement des groupes, "
            "sélectionnez des objets puis interrogez la période souhaitée."
        )
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        settings_button = QPushButton("Configurer OAuth2…")
        settings_button.clicked.connect(self._open_settings)
        glossary_button = QPushButton("Glossaire / Aide…")
        glossary_button.clicked.connect(self._open_glossary)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(settings_button)
        bottom.addWidget(glossary_button)
        bottom.addStretch()
        bottom.addWidget(buttons)
        root.addLayout(bottom)
        self._glossary_dialog = None

        cached = cache_service.load_catalog(self.cache_store)
        if cached is not None:
            stale_note = " (peut être obsolète)" if cache_service.is_stale(cached.loaded_at, CACHE_MAX_AGE_SECONDS) else ""
            self.status_label.setText(
                f"Un cache local du {cached.loaded_at} est disponible{stale_note}. Cliquez « Utiliser le cache » "
                "pour le charger sans réseau, ou « Actualiser depuis l'API » pour vérifier l'authentification et "
                "repartir à jour. Le cache n'est jamais chargé automatiquement, pour ne pas masquer un jeton expiré."
            )

    # -- catalog loading --------------------------------------------------
    def _client(self) -> ApiClient | None:
        authcfg = settings_store.get_authcfg()
        if not authcfg:
            QMessageBox.warning(self, "Authentification", "Configurez d'abord une configuration OAuth2 (bouton « Configurer OAuth2… »).")
            return None
        return ApiClient(QgsTransport(authcfg))

    def _busy_buttons(self) -> tuple:
        return (self.btn_refresh, self.btn_use_cache, self.btn_clear_cache, self.btn_run, self.btn_groups)

    def _set_busy(self, busy: bool) -> None:
        for button in self._busy_buttons():
            button.setEnabled(not busy)
        if not busy:
            self.btn_groups.setEnabled(bool(self.catalog and self.catalog.offerings()))

    def _start_task(self, task, dialog) -> None:
        self._active_task = task
        self._active_dialog = dialog
        self._set_busy(True)
        QgsApplication.taskManager().addTask(task)
        dialog.show()

    def _finish_task(self) -> None:
        self._active_task = None
        self._active_dialog = None
        self._set_busy(False)

    def _show_operation_error(self, title: str, message: str, status: int = 0) -> None:
        """A plain error box for most failures; for 401/403 (dead or invalid
        OAuth2 token) a one-click path back to « Configurer OAuth2… », since
        a generic error message left the user with no obvious way back in."""
        if status not in (401, 403):
            QMessageBox.critical(self, title, message)
            return
        box = QMessageBox(QMessageBox.Critical, title, message, parent=self)
        box.setInformativeText(
            "Votre authentification OAuth2 semble expirée ou invalide. Reconfigurez-la, ou "
            "réautorisez-la depuis les paramètres d'authentification de QGIS (icône crayon)."
        )
        open_settings_button = box.addButton("Configurer OAuth2…", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is open_settings_button:
            self._open_settings()

    def _load_from_api(self) -> None:
        if self._active_task is not None:
            QMessageBox.information(
                self, "Opération en cours",
                "Une opération est déjà en cours ; patientez ou annulez-la avant d'en lancer une autre.",
            )
            return
        client = self._client()
        if client is None:
            return

        task = CatalogLoadTask(client)
        dialog = ProgressDialog("Chargement du catalogue Géoplateforme", task, self)

        def on_loaded(catalog):
            self._finish_task()
            dialog.accept()
            cache_service.save_catalog(self.cache_store, catalog)
            self._apply_catalog(catalog)

        def on_failed(message, status):
            self._finish_task()
            dialog.reject()
            self._show_operation_error("Chargement du catalogue", message, status)

        task.loaded.connect(on_loaded)
        task.failed.connect(on_failed)
        self._start_task(task, dialog)

    def _load_from_cache(self) -> None:
        catalog = cache_service.load_catalog(self.cache_store)
        if catalog is None:
            QMessageBox.information(self, "Cache", "Aucun cache local disponible : utilisez « Actualiser depuis l'API ».")
            return
        if cache_service.is_stale(catalog.loaded_at, CACHE_MAX_AGE_SECONDS):
            if QMessageBox.question(
                self, "Cache",
                f"Le cache local date du {catalog.loaded_at} et peut être obsolète. L'utiliser quand même ?",
            ) != QMessageBox.Yes:
                return
        self._apply_catalog(catalog)

    def _clear_cache(self) -> None:
        cache_service.clear(self.cache_store)
        QMessageBox.information(self, "Cache", "Le cache local a été vidé.")

    def _apply_catalog(self, catalog) -> None:
        self.catalog = catalog
        self.consumer_selector.set_available(catalog.by_scope("consumer"))
        self._refresh_producer_selector()
        self.btn_groups.setEnabled(bool(catalog.offerings()))

        message = (
            f"{len(catalog.items)} objet(s) chargé(s) "
            f"({len(catalog.offerings())} offering(s), "
            f"{sum(1 for i in catalog.items if i.kind == ENDPOINT)} endpoint(s), "
            f"{sum(1 for i in catalog.items if i.kind == PRODUCER_PERMISSION)} permission(s) producteur)"
            f"{' — chargé depuis le cache' if catalog.from_cache else ''}."
        )
        if catalog.errors:
            message += f" {len(catalog.errors)} erreur(s) de chargement partiel."
        self.status_label.setText(message)
        if catalog.errors:
            details = "\n".join(f"- {e.datastore_name} ({e.stage}) : {e.message}" for e in catalog.errors)
            QMessageBox.warning(self, "Chargement partiel", f"Le chargement a rencontré des erreurs :\n{details}")

    def _producer_entries(self) -> list:
        entries = list(self.catalog.by_scope("producer")) if self.catalog else []
        if self.hide_unused_endpoints.isChecked():
            entries = [e for e in entries if e.kind != ENDPOINT or e.endpoint_use > 0]
        entries += [
            _GroupEntry(
                kind="user_group",
                label=f"{group.name} ({len(group.offering_ids)} offre(s))",
                item_id=f"group:{group.group_id}",
                group_id=group.group_id,
            )
            for group in self.groups
        ]
        return entries

    def _refresh_producer_selector(self) -> None:
        groups_by_id = {group.group_id: group for group in self.groups}
        self.producer_selector.set_available(self._producer_entries(), groups_by_id)

    # -- groups -------------------------------------------------------------
    def _open_group_editor(self) -> None:
        if not self.catalog or not self.catalog.offerings():
            QMessageBox.information(
                self, "Composer les groupes",
                "Chargez d'abord le catalogue producteur : aucun offering n'est disponible pour composer un groupe.",
            )
            return
        dialog = GroupEditor(self.groups, self.catalog.offerings(), self.group_service, self)
        if dialog.exec():
            self.groups = dialog.groups
            self.group_service.save(self.groups)
            self._refresh_producer_selector()

    # -- query ----------------------------------------------------------
    def _selected_items(self) -> list:
        offerings_by_id = {item.offering_id: item for item in self.catalog.offerings()} if self.catalog else {}
        groups_by_id = {group.group_id: group for group in self.groups}
        selected = self.consumer_selector.selected_items() + self.producer_selector.selected_items()

        expanded = []
        seen_paths = set()
        for entry in selected:
            if getattr(entry, "kind", "") == "user_group":
                group = groups_by_id.get(entry.group_id)
                members = [offerings_by_id[oid] for oid in (group.offering_ids if group else []) if oid in offerings_by_id]
            else:
                members = [entry]
            for member in members:
                if member.stats_path and member.stats_path not in seen_paths:
                    seen_paths.add(member.stats_path)
                    expanded.append(member)
        return expanded

    def _run_query(self) -> None:
        if self._active_task is not None:
            QMessageBox.information(
                self, "Opération en cours",
                "Une opération est déjà en cours ; patientez ou annulez-la avant d'en lancer une autre.",
            )
            return
        try:
            config = self.period_panel.build_config()
        except PeriodValidationError as exc:
            QMessageBox.warning(self, "Période", str(exc))
            return

        items = self._selected_items()
        if not items:
            QMessageBox.warning(self, "Sélection", "Ajoutez au moins un objet dans la liste des éléments sélectionnés.")
            return

        client = self._client()
        if client is None:
            return

        task = StatsQueryTask(client, items, config.requested_start, config.requested_end, config.details_requested)
        dialog = ProgressDialog("Interrogation des statistiques d'usage", task, self)

        def on_finished(results):
            self._finish_task()
            dialog.accept()
            auth_failures = [r for r in results if r.http_status in (401, 403)]
            if results and len(auth_failures) == len(results):
                self._show_operation_error(
                    "Interrogation", f"Les {len(results)} objet(s) interrogé(s) ont échoué : {auth_failures[0].message}",
                    auth_failures[0].http_status,
                )
                return
            self.results = results
            self.period_config = config
            self.dashboard.set_data(self.results, self.groups, self.period_config)
            missing = sum(1 for r in self.results if r.status == "with_usage" and not r.points and config.details_requested)
            self.status_label.setText(
                f"Période {config.duration_days} jour(s) · {len(self.results)} réponse(s) obtenue(s) "
                f"sur {len(items)} objet(s) interrogé(s) · {missing} sans détail temporel exploitable."
            )

        def on_failed(message, status):
            self._finish_task()
            dialog.reject()
            self._show_operation_error("Interrogation", message, status)

        task.finishedWithResults.connect(on_finished)
        task.failed.connect(on_failed)
        self._start_task(task, dialog)

    # -- exports --------------------------------------------------------
    def _build_export_context(self):
        errors = self.catalog.errors if self.catalog else []
        return build_export_context(self.results, self.groups, self.period_config, errors)

    def _export_csv(self) -> None:
        if not self.results:
            QMessageBox.information(self, "Export", "Interrogez d'abord une sélection.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Choisir le dossier d'export CSV")
        if not directory:
            return
        base_name, ok = QInputDialog.getText(self, "Export CSV", "Préfixe des fichiers :", text="stats_geoplateforme_7_0")
        if not ok or not base_name.strip():
            return
        context = self._build_export_context()
        written = csv_exporter.export_all_csv(directory, base_name.strip(), context)
        QMessageBox.information(self, "Export CSV", "Fichiers écrits :\n" + "\n".join(Path(p).name for p in written))

    def _export_xlsx(self) -> None:
        if not self.results:
            QMessageBox.information(self, "Export", "Interrogez d'abord une sélection.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter l'analyse XLSX", "stats_geoplateforme_7_0.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            context = self._build_export_context()
            xlsx_exporter.export_workbook(path, context)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
            QMessageBox.critical(self, "Export XLSX", str(exc))
            return
        QMessageBox.information(self, "Export XLSX", f"Classeur créé :\n{path}")

    def _open_settings(self) -> None:
        SettingsDialog(self).exec()

    def _open_glossary(self) -> None:
        if self._glossary_dialog is None:
            self._glossary_dialog = GlossaryDialog(self)
        self._glossary_dialog.show()
        self._glossary_dialog.raise_()
        self._glossary_dialog.activateWindow()
