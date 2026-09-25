"""Dashboard tab (section 6): KPIs and charts, always for a single analysis
level, recomputed in memory from the last query's raw points - no network
calls happen here.
"""
from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..charts.chart_widgets import make_bar_chart, make_line_chart, make_pie_chart
from ..core import aggregation_service, dashboard_service
from ..core.coverage_service import assess_coverage
from ..core.models import OFFERING
from ..exporters.xlsx_exporter import human_bytes

LEVEL_CHOICES = (
    ("offering", "Offerings"),
    ("endpoint", "Endpoints"),
    ("consumer_permission", "Permissions consommateur"),
    ("producer_permission", "Permissions producteur"),
    ("user_group", "Groupes utilisateur"),
)
GRAIN_CHOICES = (("day", "Jour"), ("week", "Semaine"), ("month", "Mois"))
METRIC_CHOICES = (("hits", "Hits"), ("data_transfer", "Volume transféré"))

# Which filters make sense for which level: a permission has no single datastore
# to speak of at the consumer side, permissions/groups have no single service_type,
# and the group filter only means anything once "Groupes utilisateur" is selected.
LEVELS_WITH_DATASTORE_FILTER = {"offering", "endpoint", "producer_permission"}
LEVELS_WITH_SERVICE_TYPE_FILTER = {"offering", "endpoint"}


class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._results = []
        self._groups = []
        self._period = None

        root = QVBoxLayout(self)
        controls = QHBoxLayout()
        # Populated in set_data() with only the levels actually queried -
        # picking "Endpoints" should never be possible if nothing but
        # offerings was interrogated.
        self.level_combo = QComboBox()
        self.metric_combo = QComboBox()
        for key, label in METRIC_CHOICES:
            self.metric_combo.addItem(label, key)
        self.grain_combo = QComboBox()
        for key, label in GRAIN_CHOICES:
            self.grain_combo.addItem(label, key)
        self.group_combo = QComboBox()
        self.datastore_combo = QComboBox()
        self.service_type_combo = QComboBox()

        for label_text, widget in (
            ("Niveau d'analyse", self.level_combo),
            ("Métrique", self.metric_combo),
            ("Regroupement", self.grain_combo),
            ("Groupe", self.group_combo),
            ("Datastore", self.datastore_combo),
            ("Type de service", self.service_type_combo),
        ):
            controls.addWidget(QLabel(label_text))
            controls.addWidget(widget)
        root.addLayout(controls)

        for combo in (self.level_combo, self.metric_combo, self.grain_combo, self.group_combo, self.datastore_combo, self.service_type_combo):
            combo.currentIndexChanged.connect(self._recompute)

        self.state_caption = QLabel()
        self.state_caption.setWordWrap(True)
        self.state_caption.setStyleSheet("color: #555555; font-style: italic;")
        root.addWidget(self.state_caption)

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #990000; font-weight: bold;")
        root.addWidget(self.warning_label)

        self.kpi_box = QGroupBox("Indicateurs (niveau sélectionné uniquement)")
        self.kpi_layout = QGridLayout(self.kpi_box)
        root.addWidget(self.kpi_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        chart_host = QWidget()
        self.chart_layout = QGridLayout(chart_host)
        scroll.setWidget(chart_host)
        root.addWidget(scroll, 1)

        self._placeholder = QLabel("Interrogez une sélection pour alimenter le dashboard.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        root.addWidget(self._placeholder)
        self.kpi_box.setVisible(False)
        scroll.setVisible(False)
        self._scroll = scroll

    def _levels_present(self) -> list:
        kinds_present = {r.item.kind for r in self._results}
        levels = [key for key, _ in LEVEL_CHOICES if key != "user_group" and key in kinds_present]
        offering_ids_present = {r.item.offering_id for r in self._results if r.item.kind == OFFERING}
        if any(set(g.offering_ids) & offering_ids_present for g in self._groups):
            levels.append("user_group")
        return levels

    def set_data(self, results, groups, period) -> None:
        self._results = list(results)
        self._groups = list(groups)
        self._period = period
        has_data = bool(self._results)
        self._placeholder.setVisible(not has_data)
        self.kpi_box.setVisible(has_data)
        self._scroll.setVisible(has_data)
        if not has_data:
            return

        levels = self._levels_present()
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        for key, label in LEVEL_CHOICES:
            if key in levels:
                self.level_combo.addItem(label, key)
        self.level_combo.blockSignals(False)

        self.group_combo.blockSignals(True)
        self.group_combo.clear()
        self.group_combo.addItem("Tous les groupes (attention aux recouvrements)", "")
        for group in sorted(self._groups, key=lambda g: g.name.casefold()):
            self.group_combo.addItem(group.name, group.group_id)
        self.group_combo.blockSignals(False)

        datastores = sorted({r.item.datastore_name for r in self._results if r.item.datastore_name})
        self.datastore_combo.blockSignals(True)
        self.datastore_combo.clear()
        self.datastore_combo.addItem("Tous les datastores", "")
        for name in datastores:
            self.datastore_combo.addItem(name, name)
        self.datastore_combo.blockSignals(False)

        service_types = sorted({r.item.service_type for r in self._results if r.item.service_type})
        self.service_type_combo.blockSignals(True)
        self.service_type_combo.clear()
        self.service_type_combo.addItem("Tous les types de service", "")
        for name in service_types:
            self.service_type_combo.addItem(name, name)
        self.service_type_combo.blockSignals(False)

        self._recompute()

    def _clear_charts(self) -> None:
        while self.chart_layout.count():
            item = self.chart_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _clear_kpis(self) -> None:
        while self.kpi_layout.count():
            item = self.kpi_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _update_control_availability(self, level: str) -> None:
        """Grey out (and reset) filters that have no meaning for the selected
        level, instead of silently accepting a value that would just zero out
        every chart with no explanation."""
        datastore_ok = level in LEVELS_WITH_DATASTORE_FILTER
        service_type_ok = level in LEVELS_WITH_SERVICE_TYPE_FILTER
        group_ok = level == "user_group"

        for combo, enabled in (
            (self.group_combo, group_ok),
            (self.datastore_combo, datastore_ok),
            (self.service_type_combo, service_type_ok),
        ):
            combo.setEnabled(enabled)
            if not enabled and combo.currentIndex() != 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)

        self.group_combo.setToolTip("" if group_ok else "Disponible uniquement pour le niveau « Groupes utilisateur ».")
        self.datastore_combo.setToolTip("" if datastore_ok else "Ce niveau n'est pas rattaché à un datastore unique.")
        self.service_type_combo.setToolTip("" if service_type_ok else "Ce niveau n'a pas de type de service unique.")

    def _recompute(self) -> None:
        if not self._results or self._period is None:
            return
        level = self.level_combo.currentData()
        metric = self.metric_combo.currentData()
        grain = self.grain_combo.currentData()

        self._update_control_availability(level)
        group_filter = self.group_combo.currentData() or None
        datastore_filter = self.datastore_combo.currentData() or None
        service_type_filter = self.service_type_combo.currentData() or None

        series_all = aggregation_service.build_all_series(self._results, self._groups, grain)
        coverages = {result.item.item_id: assess_coverage(result, self._period) for result in self._results}

        self._clear_kpis()
        self.warning_label.setText("")
        if level == "user_group":
            group_rows = [r for r in series_all if r.series_level == "user_group"]
            kpi = dashboard_service.compute_group_level_kpis(self._groups, group_rows, self._period, group_filter)
        else:
            kpi = dashboard_service.compute_item_level_kpis(self._results, coverages, level, self._period)
        if kpi.warnings:
            self.warning_label.setText(" ".join(kpi.warnings))
        self._populate_kpi_labels(kpi)

        level_rows = [r for r in series_all if r.series_level == level]
        if datastore_filter:
            level_rows = [r for r in level_rows if r.datastore_name == datastore_filter]
        if service_type_filter:
            level_rows = [r for r in level_rows if r.service_type == service_type_filter]
        if level == "user_group" and group_filter:
            level_rows = [r for r in level_rows if r.series_key == group_filter]

        # The datastore / service-type breakdown is always computed on offerings
        # (the atomic usage unit) regardless of the level combo above - only the
        # group filter narrows it, since a group is itself a set of offerings.
        offering_results = [r for r in self._results if r.item.kind == OFFERING]
        selected_group = next((g for g in self._groups if g.group_id == group_filter), None) if group_filter else None
        if level == "user_group" and selected_group is not None:
            offering_results = [r for r in offering_results if r.item.offering_id in selected_group.offering_ids]
        datastore_rows = aggregation_service.datastore_series(offering_results, grain)
        service_rows = aggregation_service.service_type_series(offering_results, grain)

        level_label = dict(LEVEL_CHOICES)[level]
        metric_label = dict(METRIC_CHOICES)[metric]
        grain_label = dict(GRAIN_CHOICES)[grain]
        caption_parts = [f"Niveau : {level_label}", f"Métrique : {metric_label}", f"Regroupement : {grain_label} (n'affecte que l'évolution temporelle)"]
        caption_parts.append(f"Groupe : {self.group_combo.currentText()}" if group_filter else "Groupe : tous" if level == "user_group" else "Groupe : n/a pour ce niveau")
        caption_parts.append(f"Datastore : {datastore_filter}" if datastore_filter else ("Datastore : tous" if level in LEVELS_WITH_DATASTORE_FILTER else "Datastore : n/a pour ce niveau"))
        caption_parts.append(f"Type de service : {service_type_filter}" if service_type_filter else ("Type de service : tous" if level in LEVELS_WITH_SERVICE_TYPE_FILTER else "Type de service : n/a pour ce niveau"))
        self.state_caption.setText(" · ".join(caption_parts))

        self._clear_charts()
        evolution = dashboard_service.time_evolution(level_rows, metric)
        self.chart_layout.addWidget(
            self._chart_with_caption(
                make_line_chart(evolution, f"Évolution temporelle ({metric_label})", metric_label),
                f"Somme de « {metric_label.lower()} » par période ({grain_label.lower()}), pour le niveau « {level_label} » et les filtres ci-dessus.",
            ),
            0, 0, 1, 2,
        )
        ranking = dashboard_service.ranking(level_rows, metric, top_n=15)
        self.chart_layout.addWidget(
            self._chart_with_caption(
                make_bar_chart(ranking, f"Classement {level_label} ({metric_label})"),
                f"Top 15 « {level_label.lower()} » par « {metric_label.lower()} » cumulé sur toute la période, mêmes filtres.",
            ),
            1, 0,
        )
        self.chart_layout.addWidget(
            self._chart_with_caption(
                make_bar_chart(dashboard_service.ranking(datastore_rows, metric, top_n=None), "Répartition par datastore"),
                "Toujours calculée à partir des offerings (unité atomique), quel que soit le niveau sélectionné ci-dessus "
                + ("· restreinte au groupe sélectionné." if selected_group is not None else "· non affectée par le niveau, le datastore ou le type de service choisis."),
            ),
            1, 1,
        )
        self.chart_layout.addWidget(
            self._chart_with_caption(
                make_pie_chart(dashboard_service.ranking(service_rows, metric, top_n=None), "Répartition par type de service"),
                "Toujours calculée à partir des offerings, quel que soit le niveau sélectionné ci-dessus "
                + ("· restreinte au groupe sélectionné." if selected_group is not None else "· non affectée par le niveau, le datastore ou le type de service choisis."),
            ),
            2, 0,
        )

    def _chart_with_caption(self, chart_widget, caption_text: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(chart_widget, 1)
        caption = QLabel(caption_text)
        caption.setWordWrap(True)
        caption.setStyleSheet("color: #777777; font-size: 10px; font-style: italic;")
        layout.addWidget(caption)
        return container

    def _populate_kpi_labels(self, kpi) -> None:
        fields = [
            ("Objets interrogés", kpi.objects_queried),
            ("Réponses avec usage", kpi.responses_with_usage),
            ("Hits totaux", kpi.hits_total),
            ("Volume total", human_bytes(kpi.data_transfer_total)),
            ("Séries avec détail temporel", kpi.series_with_temporal_detail),
            ("Réponses sans détail temporel", kpi.responses_without_temporal_detail),
            ("Routes non raccordées", kpi.routes_not_connected),
            ("Période demandée", f"{kpi.requested_period_start} → {kpi.requested_period_end} ({kpi.duration_days} j.)"),
        ]
        for row, (label_text, value) in enumerate(fields):
            self.kpi_layout.addWidget(QLabel(f"<b>{label_text}</b>"), row, 0)
            self.kpi_layout.addWidget(QLabel(str(value)), row, 1)
