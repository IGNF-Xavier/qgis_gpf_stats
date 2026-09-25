"""Flattens the in-memory query results into the row shapes every exporter
(CSV and XLSX) and the dashboard consume, so both stay in lock-step and
never invent their own column sets (section 7/8 requirement that every
export keeps business names *and* UUIDs together).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import aggregation_service, dashboard_service
from .coverage_service import assess_coverage
from .models import (
    Catalog,
    CoverageAssessment,
    DatastoreLoadError,
    Group,
    OFFERING,
    PeriodConfig,
    StatsResult,
)

IDENTITY_FIELDS = (
    "scope",
    "kind",
    "label",
    "permission_name",
    "permission_id",
    "datastore_name",
    "datastore_id",
    "offering_name",
    "offering_id",
    "endpoint_name",
    "endpoint_id",
    "service_type",
)


def _identity_row(item) -> dict:
    return {field_name: getattr(item, field_name) for field_name in IDENTITY_FIELDS}


@dataclass
class ExportContext:
    period: PeriodConfig
    groups: list
    results: list
    coverages: dict
    series_all: list
    errors: list
    summary_rows: list = field(default_factory=list)
    series_api_rows: list = field(default_factory=list)
    series_analytiques_rows: list = field(default_factory=list)
    series_groupes_rows: list = field(default_factory=list)
    coverage_rows: list = field(default_factory=list)
    groups_rows: list = field(default_factory=list)
    composition_rows: list = field(default_factory=list)
    errors_rows: list = field(default_factory=list)
    kpis_by_level: dict = field(default_factory=dict)


def build_export_context(
    results: list[StatsResult],
    groups: list[Group],
    period: PeriodConfig,
    errors: list[DatastoreLoadError],
) -> ExportContext:
    coverages: dict[str, CoverageAssessment] = {
        result.item.item_id: assess_coverage(result, period) for result in results
    }
    series_all = aggregation_service.build_all_series(results, groups, period.analysis_grain)

    offerings_by_id = {r.item.offering_id: r.item for r in results if r.item.kind == OFFERING}

    summary_rows = []
    series_api_rows = []
    coverage_rows = []
    for result in results:
        item = result.item
        coverage = coverages[item.item_id]
        identity = _identity_row(item)
        summary_rows.append(
            {
                **identity,
                "requested_start": period.requested_start,
                "requested_end": period.requested_end,
                "duration_days": period.duration_days,
                "details_requested": period.details_requested,
                "fine_requested": period.fine_requested,
                "analysis_grain": period.analysis_grain,
                "first_activity": result.first_activity,
                "last_activity": result.last_activity,
                "coverage_status": coverage.coverage_status,
                "coverage_ratio": coverage.coverage_ratio,
                "http_status": result.http_status,
                "status": result.status,
                "hits": result.hits,
                "data_transfer": result.data_transfer,
                "details_count": len(result.points),
                "message": result.message,
            }
        )
        coverage_rows.append(
            {
                **identity,
                "requested_start": period.requested_start,
                "requested_end": period.requested_end,
                "first_activity": result.first_activity,
                "last_activity": result.last_activity,
                "coverage_status": coverage.coverage_status,
                "coverage_ratio": coverage.coverage_ratio,
                "active_days_count": coverage.active_days_count,
                "temporal_points_count": coverage.temporal_points_count,
                "coverage_interpretation": coverage.coverage_interpretation,
                "hits": result.hits,
                "data_transfer": result.data_transfer,
            }
        )
        for index, point in enumerate(result.points, 1):
            series_api_rows.append(
                {
                    **identity,
                    "requested_start": period.requested_start,
                    "requested_end": period.requested_end,
                    "duration_days": period.duration_days,
                    "coverage_status": coverage.coverage_status,
                    "period_index": index,
                    "period_start": point.period_start,
                    "period_end": point.period_end,
                    "hits": point.hits,
                    "data_transfer": point.data_transfer,
                }
            )

    series_analytiques_rows = []
    series_groupes_rows = []
    for row in series_all:
        base = {
            "series_level": row.series_level,
            "series_key": row.series_key,
            "label": row.label,
            "datastore_name": row.datastore_name,
            "datastore_id": row.datastore_id,
            "service_type": row.service_type,
            "period_key": row.period_key,
            "analysis_grain": row.analysis_grain,
            "hits": row.hits,
            "data_transfer": row.data_transfer,
            "contributor_count": row.contributor_count,
            "incomplete": row.incomplete,
        }
        if row.series_level == "user_group":
            series_groupes_rows.append({**base, "group_id": row.series_key, "group_name": row.label})
        else:
            series_analytiques_rows.append(base)

    groups_rows = []
    composition_rows = []
    for group in groups:
        groups_rows.append(
            {
                "group_id": group.group_id,
                "group_name": group.name,
                "description": group.description,
                "color": group.color,
                "offering_count": len(group.offering_ids),
                "created_at": group.created_at,
                "updated_at": group.updated_at,
            }
        )
        for offering_id in group.offering_ids:
            offering = offerings_by_id.get(offering_id)
            composition_rows.append(
                {
                    "group_id": group.group_id,
                    "group_name": group.name,
                    "offering_id": offering_id,
                    "offering_name": offering.offering_name if offering else "",
                    "datastore_name": offering.datastore_name if offering else "",
                    "service_type": offering.service_type if offering else "",
                }
            )

    errors_rows = [
        {
            "datastore_id": error.datastore_id,
            "datastore_name": error.datastore_name,
            "stage": error.stage,
            "message": error.message,
        }
        for error in errors
    ]

    kpis_by_level = {}
    for level in dashboard_service.LEVELS:
        if level == "user_group":
            group_rows = [r for r in series_all if r.series_level == "user_group"]
            kpis_by_level[level] = dashboard_service.compute_group_level_kpis(groups, group_rows, period)
        else:
            kpis_by_level[level] = dashboard_service.compute_item_level_kpis(results, coverages, level, period)

    return ExportContext(
        period=period,
        groups=groups,
        results=results,
        coverages=coverages,
        series_all=series_all,
        errors=errors,
        summary_rows=summary_rows,
        series_api_rows=series_api_rows,
        series_analytiques_rows=series_analytiques_rows,
        series_groupes_rows=series_groupes_rows,
        coverage_rows=coverage_rows,
        groups_rows=groups_rows,
        composition_rows=composition_rows,
        errors_rows=errors_rows,
        kpis_by_level=kpis_by_level,
    )
