"""Dashboard KPI and chart-data computation (section 6).

The one rule this module exists to enforce: **never sum together objects
from different analysis levels**. A KPI or chart is always computed for a
single ``level`` among ``offering``, ``endpoint``, ``consumer_permission``,
``producer_permission`` or ``user_group`` - offerings, endpoints and
permissions are overlapping views of the same underlying usage, and groups
may themselves overlap each other.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from .models import (
    CoverageAssessment,
    Group,
    PeriodConfig,
    SeriesRow,
    StatsResult,
    STATUS_NOT_CONNECTED,
    STATUS_WITH_USAGE,
    COVERAGE_NO_TEMPORAL_DETAIL,
)

LEVELS = ("consumer_permission", "producer_permission", "offering", "endpoint", "user_group")


@dataclass
class KpiSet:
    level: str
    objects_queried: int = 0
    responses_with_usage: int = 0
    responses_without_usage: int = 0
    hits_total: int = 0
    data_transfer_total: int = 0
    series_with_temporal_detail: int = 0
    responses_without_temporal_detail: int = 0
    routes_not_connected: int = 0
    requested_period_start: str = ""
    requested_period_end: str = ""
    duration_days: int = 0
    warnings: list = field(default_factory=list)


def compute_item_level_kpis(
    results: Iterable[StatsResult],
    coverages: dict,
    level: str,
    period: PeriodConfig,
) -> KpiSet:
    filtered = [r for r in results if r.item.kind == level]
    kpi = KpiSet(
        level=level,
        objects_queried=len(filtered),
        responses_with_usage=sum(1 for r in filtered if r.status == STATUS_WITH_USAGE),
        responses_without_usage=sum(1 for r in filtered if r.status not in (STATUS_WITH_USAGE, STATUS_NOT_CONNECTED, "error")),
        hits_total=sum(r.hits for r in filtered),
        data_transfer_total=sum(r.data_transfer for r in filtered),
        series_with_temporal_detail=sum(1 for r in filtered if r.points),
        routes_not_connected=sum(1 for r in filtered if r.status == STATUS_NOT_CONNECTED),
        requested_period_start=period.requested_start,
        requested_period_end=period.requested_end,
        duration_days=period.duration_days,
    )
    kpi.responses_without_temporal_detail = sum(
        1 for r in filtered if coverages.get(r.item.item_id) and coverages[r.item.item_id].coverage_status == COVERAGE_NO_TEMPORAL_DETAIL
    )
    return kpi


def compute_group_level_kpis(
    groups: Iterable[Group],
    group_series_rows: Iterable[SeriesRow],
    period: PeriodConfig,
    selected_group_id: Optional[str] = None,
) -> KpiSet:
    groups = list(groups)
    rows = [r for r in group_series_rows if not selected_group_id or r.series_key == selected_group_id]
    totals: dict[str, list] = defaultdict(lambda: [0, 0])
    for row in rows:
        totals[row.series_key][0] += row.hits
        totals[row.series_key][1] += row.data_transfer

    kpi = KpiSet(
        level="user_group",
        objects_queried=1 if selected_group_id else len(groups),
        responses_with_usage=sum(1 for values in totals.values() if values[0] or values[1]),
        hits_total=sum(values[0] for values in totals.values()),
        data_transfer_total=sum(values[1] for values in totals.values()),
        series_with_temporal_detail=len(totals),
        requested_period_start=period.requested_start,
        requested_period_end=period.requested_end,
        duration_days=period.duration_days,
    )
    if not selected_group_id and len(groups) > 1:
        kpi.warnings.append(
            "Plusieurs groupes peuvent partager des offres : ce total agrège des groupes qui se "
            "chevauchent peut-être. Sélectionnez un groupe pour un chiffre non ambigu."
        )
    return kpi


def time_evolution(series_rows: Iterable[SeriesRow], metric: str = "hits") -> list[tuple[str, int]]:
    totals: dict[str, int] = defaultdict(int)
    for row in series_rows:
        totals[row.period_key] += getattr(row, metric)
    return sorted(totals.items())


def ranking(series_rows: Iterable[SeriesRow], metric: str = "hits", top_n: Optional[int] = 15) -> list[tuple[str, int]]:
    totals: dict[str, int] = defaultdict(int)
    labels: dict[str, str] = {}
    for row in series_rows:
        totals[row.series_key] += getattr(row, metric)
        labels[row.series_key] = row.label
    ordered = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    if top_n is not None:
        ordered = ordered[:top_n]
    return [(labels[key], value) for key, value in ordered]
