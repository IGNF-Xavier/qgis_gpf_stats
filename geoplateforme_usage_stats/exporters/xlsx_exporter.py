"""Analytical XLSX report (section 8): 9 sheets, structured Excel tables,
frozen headers, filters, human-readable volumes and embedded charts. The
workbook must stand on its own once produced - opening it in Excel with the
plugin never installed must still make sense.
"""
from __future__ import annotations

from datetime import datetime, timezone

try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
except ImportError:  # pragma: no cover - exercised only inside QGIS without system openpyxl
    from ..vendor.openpyxl import Workbook
    from ..vendor.openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from ..vendor.openpyxl.styles import Alignment, Font, PatternFill
    from ..vendor.openpyxl.utils import get_column_letter
    from ..vendor.openpyxl.worksheet.table import Table, TableStyleInfo

from ..core import dashboard_service
from ..core.export_context import ExportContext
from ..core.glossary import GLOSSARY

NAVY = "1F4E78"
WHITE = "FFFFFF"
GREEN = "D9EAD3"
ORANGE = "F4B183"
RED = "F4CCCC"
GREY = "F3F3F3"

COVERAGE_COLORS = {
    "complete_coverage": GREEN,
    "partial_coverage": ORANGE,
    "no_temporal_detail": GREY,
    "no_usage": GREY,
    "not_connected": RED,
    "error": RED,
}


def human_bytes(value) -> str:
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return "0 o"
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "o" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.1f} To"


def _ordered_fieldnames(rows: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(key, None)
    return list(seen)


def _autosize(ws, max_row_scan: int = 300) -> None:
    for col in range(1, ws.max_column + 1):
        longest = 10
        for row in range(1, min(ws.max_row, max_row_scan) + 1):
            value = ws.cell(row, col).value
            if value is not None:
                longest = max(longest, len(str(value)))
        ws.column_dimensions[get_column_letter(col)].width = max(10, min(48, longest + 2))


def _style_header(ws, header_row: int = 1) -> None:
    for cell in ws[header_row]:
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(color=WHITE, bold=True)
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _data_sheet(wb, name: str, rows: list[dict], headers=None):
    ws = wb.create_sheet(name)
    headers = headers or _ordered_fieldnames(rows)
    if not headers:
        ws.append(["(aucune donnée)"])
        return ws
    ws.append(headers)
    for row in rows:
        ws.append([row.get(header) for header in headers])
    _style_header(ws)
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        table_ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
        table = Table(displayName=f"Tbl_{name}", ref=table_ref)
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showRowStripes=True, showFirstColumn=False
        )
        ws.add_table(table)
    else:
        ws.auto_filter.ref = ws.dimensions
    ws.sheet_view.showGridLines = False
    _autosize(ws)
    return ws


def _color_column(ws, header_name: str, colors: dict) -> None:
    headers = [cell.value for cell in ws[1]]
    if header_name not in headers:
        return
    col = headers.index(header_name) + 1
    for row in range(2, ws.max_row + 1):
        value = ws.cell(row, col).value
        color = colors.get(value)
        if color:
            ws.cell(row, col).fill = PatternFill("solid", fgColor=color)


def _write_table(ws, top_row: int, left_col: int, title: str, headers: list[str], rows: list[tuple], caption: str = "") -> int:
    title_cell = ws.cell(top_row, left_col, title)
    title_cell.font = Font(bold=True, size=12, color=NAVY)
    if caption:
        caption_cell = ws.cell(top_row, left_col + len(headers) + 1, caption)
        caption_cell.font = Font(italic=True, size=9, color="777777")
        caption_cell.alignment = Alignment(wrap_text=True)
    header_row = top_row + 1
    for offset, header in enumerate(headers):
        cell = ws.cell(header_row, left_col + offset, header)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
    for row_offset, row_values in enumerate(rows, 1):
        for col_offset, value in enumerate(row_values):
            ws.cell(header_row + row_offset, left_col + col_offset, value)
    return header_row + len(rows)


def _dashboard_sheet(wb, context: ExportContext):
    ws = wb.create_sheet("Dashboard", 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 28
    for col in "BCDEFG":
        ws.column_dimensions[col].width = 16

    ws["A1"] = "Statistiques analytiques Géoplateforme — Dashboard"
    ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    period = context.period
    ws["A3"] = "Période demandée"
    ws["B3"] = f"{period.requested_start} → {period.requested_end}"
    ws["A4"] = "Durée (jours)"
    ws["B4"] = period.duration_days
    ws["A5"] = "Préréglage"
    ws["B5"] = period.preset
    ws["A6"] = "Regroupement analytique"
    ws["B6"] = period.analysis_grain
    ws["A7"] = "Détails temporels demandés"
    ws["B7"] = "Oui" if period.details_requested else "Non"
    ws["A8"] = "Pas fin (5 min) demandé"
    ws["B8"] = "Oui" if period.fine_requested else "Non"
    ws["A9"] = "Erreurs de chargement de datastore"
    ws["B9"] = len(context.errors)
    ws["A10"] = "Définitions (offering, datastore, endpoint, permission…)"
    ws["B10"] = "→ voir la feuille Glossaire"

    warning = ws.cell(11, 1, (
        "⚠ Chaque indicateur ci-dessous porte sur UN SEUL niveau d'analyse (offerings, endpoints, "
        "permissions ou groupes utilisateur). Ces niveaux se recouvrent : ne jamais additionner leurs "
        "totaux entre eux, ni additionner les totaux de plusieurs groupes qui partagent des offres."
    ))
    warning.font = Font(bold=True, color="990000")
    warning.alignment = Alignment(wrap_text=True)
    ws.merge_cells(start_row=11, start_column=1, end_row=11, end_column=7)
    ws.row_dimensions[11].height = 30

    kpi_headers = [
        "Niveau", "Objets interrogés", "Réponses avec usage", "Hits totaux",
        "Volume total", "Séries avec détail temporel", "Réponses sans détail temporel",
        "Routes non raccordées",
    ]
    level_labels = {
        "consumer_permission": "Permissions consommateur",
        "producer_permission": "Permissions producteur",
        "offering": "Offerings",
        "endpoint": "Endpoints",
        "user_group": "Groupes utilisateur",
    }
    kpi_rows = []
    for level in dashboard_service.LEVELS:
        kpi = context.kpis_by_level.get(level)
        if kpi is None or kpi.objects_queried == 0:
            continue  # this level was not part of the selection - no row, not a row of zeros
        kpi_rows.append(
            (
                level_labels.get(level, level),
                kpi.objects_queried,
                kpi.responses_with_usage,
                kpi.hits_total,
                human_bytes(kpi.data_transfer_total),
                kpi.series_with_temporal_detail,
                kpi.responses_without_temporal_detail,
                kpi.routes_not_connected,
            )
        )
    next_row = _write_table(ws, 13, 1, "Indicateurs par niveau d'analyse", kpi_headers, kpi_rows) + 2

    group_warnings = [w for kpi in context.kpis_by_level.values() for w in kpi.warnings]
    if group_warnings:
        cell = ws.cell(next_row, 1, "⚠ " + " ".join(sorted(set(group_warnings))))
        cell.font = Font(italic=True, color="990000")
        cell.alignment = Alignment(wrap_text=True)
        ws.merge_cells(start_row=next_row, start_column=1, end_row=next_row, end_column=7)
        next_row += 2

    offering_series = [r for r in context.series_all if r.series_level == "offering"]
    endpoint_series = [r for r in context.series_all if r.series_level == "endpoint"]
    group_series_rows = [r for r in context.series_all if r.series_level == "user_group"]
    datastore_series = [r for r in context.series_all if r.series_level == "datastore"]
    service_series = [r for r in context.series_all if r.series_level == "service_type"]
    producer_permission_series = [r for r in context.series_all if r.series_level == "producer_permission"]
    consumer_permission_series = [r for r in context.series_all if r.series_level == "consumer_permission"]

    # Every table below is written only if that level/lens was actually part
    # of the selection - an empty "Top 15 offerings" table when nothing but
    # endpoints was queried would be noise, not information.
    evolution_rows = []
    evolution_start = None
    if offering_series:
        evolution = dashboard_service.time_evolution(offering_series, "hits")
        evolution_volume = dict(dashboard_service.time_evolution(offering_series, "data_transfer"))
        evolution_rows = [(period_key, hits, evolution_volume.get(period_key, 0)) for period_key, hits in evolution]
        evolution_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Évolution temporelle (niveau offerings)",
            ["period_key", "hits", "data_transfer"], evolution_rows,
            caption="Somme des hits/volume par période, offerings uniquement (unité atomique) - le regroupement jour/semaine/mois vient de la période choisie lors de l'interrogation.",
        ) + 2

    top_offerings, top_offerings_start = [], None
    if offering_series:
        top_offerings = dashboard_service.ranking(offering_series, "hits", top_n=15)
        top_offerings_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Top 15 offerings (hits)", ["label", "hits"], top_offerings,
            caption="Niveau offerings uniquement - ne pas additionner avec les classements endpoints/permissions/groupes ci-dessous (vues qui se recouvrent).",
        ) + 2

    top_endpoints, top_endpoints_start = [], None
    if endpoint_series:
        top_endpoints = dashboard_service.ranking(endpoint_series, "hits", top_n=15)
        top_endpoints_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Top 15 endpoints (hits)", ["label", "hits"], top_endpoints,
            caption="Niveau endpoints uniquement (canaux de diffusion techniques, voir feuille Glossaire) - route Stats propre à chaque endpoint.",
        ) + 2

    top_producer_permissions, top_producer_permissions_start = [], None
    if producer_permission_series:
        top_producer_permissions = dashboard_service.ranking(producer_permission_series, "hits", top_n=15)
        top_producer_permissions_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Top 15 permissions producteur (hits)", ["label", "hits"], top_producer_permissions,
            caption="Niveau permissions producteur uniquement - une permission peut couvrir plusieurs offerings à la fois.",
        ) + 2

    top_consumer_permissions, top_consumer_permissions_start = [], None
    if consumer_permission_series:
        top_consumer_permissions = dashboard_service.ranking(consumer_permission_series, "hits", top_n=15)
        top_consumer_permissions_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Top 15 permissions consommateur (hits)", ["label", "hits"], top_consumer_permissions,
            caption="Niveau permissions consommateur uniquement - offres dont vous bénéficiez auprès d'un autre producteur.",
        ) + 2

    top_groups, top_groups_start = [], None
    if group_series_rows:
        top_groups = dashboard_service.ranking(group_series_rows, "hits", top_n=15)
        top_groups_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Top 15 groupes (hits, non cumulables entre eux)", ["label", "hits"], top_groups,
            caption="Groupes locaux définis dans le plugin - deux groupes qui partagent une offre se chevauchent, voir la feuille Groupes.",
        ) + 2

    by_datastore, by_datastore_start = [], None
    if datastore_series:
        by_datastore = dashboard_service.ranking(datastore_series, "hits", top_n=None)
        by_datastore_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Répartition par datastore (offerings)", ["label", "hits"], by_datastore,
            caption="Toujours calculée à partir des offerings, indépendamment des autres niveaux ci-dessus.",
        ) + 2

    by_service_type, by_service_start = [], None
    if service_series:
        by_service_type = dashboard_service.ranking(service_series, "hits", top_n=None)
        by_service_start = next_row
        next_row = _write_table(
            ws, next_row, 1, "Répartition par type de service (offerings)", ["label", "hits"], by_service_type,
            caption="Toujours calculée à partir des offerings, indépendamment des autres niveaux ci-dessus.",
        ) + 2

    i_chart_row, q_chart_row = 13, 13
    CHART_STEP = 21

    def _add_bar_or_pie(chart, data_col, start_row, count, anchor, width=18, height=10):
        chart.add_data(Reference(ws, min_col=data_col, min_row=start_row + 2, max_row=start_row + 1 + count), titles_from_data=False)
        chart.set_categories(Reference(ws, min_col=1, min_row=start_row + 2, max_row=start_row + 1 + count))
        chart.width, chart.height = width, height
        ws.add_chart(chart, anchor)

    if evolution_rows:
        hits_chart = LineChart()
        hits_chart.title = "Évolution des hits (offerings)"
        hits_chart.y_axis.title = "Hits"
        hits_chart.x_axis.title = "Période"
        _add_bar_or_pie(hits_chart, 2, evolution_start, len(evolution_rows), f"I{i_chart_row}", height=8)
        i_chart_row += CHART_STEP

        volume_chart = LineChart()
        volume_chart.title = "Évolution du volume transféré (offerings)"
        volume_chart.y_axis.title = "Octets"
        _add_bar_or_pie(volume_chart, 3, evolution_start, len(evolution_rows), f"I{i_chart_row}", height=8)
        i_chart_row += CHART_STEP

    if top_offerings:
        chart = BarChart()
        chart.title = "Top offerings (hits)"
        _add_bar_or_pie(chart, 2, top_offerings_start, len(top_offerings), f"I{i_chart_row}")
        i_chart_row += CHART_STEP

    if top_endpoints:
        chart = BarChart()
        chart.title = "Top endpoints (hits)"
        _add_bar_or_pie(chart, 2, top_endpoints_start, len(top_endpoints), f"I{i_chart_row}")
        i_chart_row += CHART_STEP

    if top_producer_permissions:
        chart = BarChart()
        chart.title = "Top permissions producteur (hits)"
        _add_bar_or_pie(chart, 2, top_producer_permissions_start, len(top_producer_permissions), f"I{i_chart_row}")
        i_chart_row += CHART_STEP

    if top_consumer_permissions:
        chart = BarChart()
        chart.title = "Top permissions consommateur (hits)"
        _add_bar_or_pie(chart, 2, top_consumer_permissions_start, len(top_consumer_permissions), f"I{i_chart_row}")
        i_chart_row += CHART_STEP

    if top_groups:
        chart = BarChart()
        chart.title = "Top groupes (hits)"
        _add_bar_or_pie(chart, 2, top_groups_start, len(top_groups), f"I{i_chart_row}")
        i_chart_row += CHART_STEP

    if by_datastore:
        chart = PieChart()
        chart.title = "Répartition par datastore"
        _add_bar_or_pie(chart, 2, by_datastore_start, len(by_datastore), f"Q{q_chart_row}", width=14)
        q_chart_row += CHART_STEP

    if by_service_type:
        chart = PieChart()
        chart.title = "Répartition par type de service"
        _add_bar_or_pie(chart, 2, by_service_start, len(by_service_type), f"Q{q_chart_row}", width=14)
        q_chart_row += CHART_STEP

    return ws


def _glossary_sheet(wb):
    ws = wb.create_sheet("Glossaire")
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 100
    ws.append(["Terme", "Définition"])
    for term, definition in GLOSSARY:
        ws.append([term, definition])
    _style_header(ws)
    ws.freeze_panes = "A2"
    for row in range(2, ws.max_row + 1):
        ws.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 45
    return ws


def export_workbook(path: str, context: ExportContext) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    _dashboard_sheet(wb, context)
    _data_sheet(wb, "Synthese", context.summary_rows)
    _data_sheet(wb, "Series_API", context.series_api_rows)
    _data_sheet(wb, "Series_analytiques", context.series_analytiques_rows)
    _data_sheet(wb, "Series_groupes", context.series_groupes_rows)
    coverage_ws = _data_sheet(wb, "Controle_couverture", context.coverage_rows)
    _color_column(coverage_ws, "coverage_status", COVERAGE_COLORS)
    _data_sheet(wb, "Groupes", context.groups_rows)
    _data_sheet(
        wb, "Periode",
        [{"parametre": key, "valeur": value} for key, value in context.period.as_dict().items()],
        headers=["parametre", "valeur"],
    )
    _data_sheet(wb, "Journal_erreurs", context.errors_rows)
    _glossary_sheet(wb)

    wb.properties.title = "Statistiques analytiques Géoplateforme"
    wb.properties.created = datetime.now(timezone.utc)
    wb.save(path)
