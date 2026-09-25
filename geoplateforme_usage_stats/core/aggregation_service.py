"""Reclassification of raw API points into analytical series (section 5).

The API does not guarantee that two offerings return identical
``period_start`` boundaries, so points are never summed by strict equality
of ``period_start``: each point is first reclassified into the chosen
analysis grain (day/week/month, or left "raw") and only then summed.

Series are produced per independent "lens" (``series_level``): individual
catalog items, user groups, datastores and service types. Offerings,
endpoints and permissions are never mixed together inside one sum, because
they are overlapping views of the same underlying usage - see
``dashboard_service`` for the corresponding KPI-isolation rule.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable

from .coverage_service import period_bucket
from .models import Group, OFFERING, SeriesRow, StatsResult

RAW_GRAIN = "raw"


def _bucket_key(point_start: str, grain: str) -> str:
    if grain == RAW_GRAIN:
        return point_start
    return period_bucket(point_start, grain)


def individual_series(results: Iterable[StatsResult], grain: str) -> list[SeriesRow]:
    rows: list[SeriesRow] = []
    for result in results:
        item = result.item
        buckets: dict[str, list] = defaultdict(lambda: [0, 0])
        for point in result.points:
            key = _bucket_key(point.period_start, grain)
            if not key:
                continue
            bucket = buckets[key]
            bucket[0] += point.hits
            bucket[1] += point.data_transfer
        incomplete = bool(result.hits or result.data_transfer) and not result.points
        for period_key, (hits, data_transfer) in sorted(buckets.items()):
            rows.append(
                SeriesRow(
                    series_level=item.kind,
                    series_key=item.item_id,
                    label=item.label,
                    period_key=period_key,
                    analysis_grain=grain,
                    hits=hits,
                    data_transfer=data_transfer,
                    contributor_count=1,
                    incomplete=incomplete,
                    datastore_name=item.datastore_name,
                    datastore_id=item.datastore_id,
                    service_type=item.service_type,
                )
            )
    return rows


def _aggregate_offering_results(
    entries: Iterable[tuple[str, str, str, str, str, StatsResult]],
    grain: str,
) -> list[SeriesRow]:
    """``entries`` yields (key, label, datastore_name, datastore_id, service_type, result)."""
    buckets: dict[tuple[str, str], list] = defaultdict(lambda: [0, 0, set()])
    metadata: dict[str, tuple[str, str, str, str]] = {}
    incomplete_keys: set[str] = set()

    for key, label, datastore_name, datastore_id, service_type, result in entries:
        metadata.setdefault(key, (label, datastore_name, datastore_id, service_type))
        if bool(result.hits or result.data_transfer) and not result.points:
            incomplete_keys.add(key)
        for point in result.points:
            period_key = _bucket_key(point.period_start, grain)
            if not period_key:
                continue
            bucket = buckets[(key, period_key)]
            bucket[0] += point.hits
            bucket[1] += point.data_transfer
            bucket[2].add(result.item.item_id)

    rows: list[SeriesRow] = []
    for (key, period_key), (hits, data_transfer, contributors) in sorted(buckets.items()):
        label, datastore_name, datastore_id, service_type = metadata[key]
        rows.append(
            SeriesRow(
                series_level="",
                series_key=key,
                label=label,
                period_key=period_key,
                analysis_grain=grain,
                hits=hits,
                data_transfer=data_transfer,
                contributor_count=len(contributors),
                incomplete=key in incomplete_keys,
                datastore_name=datastore_name,
                datastore_id=datastore_id,
                service_type=service_type,
            )
        )
    return rows


def group_series(results: Iterable[StatsResult], groups: Iterable[Group], grain: str) -> list[SeriesRow]:
    offering_results = {r.item.offering_id: r for r in results if r.item.kind == OFFERING}
    entries = []
    for group in groups:
        for offering_id in group.offering_ids:
            result = offering_results.get(offering_id)
            if result is None:
                continue
            entries.append((group.group_id, group.name, "", "", "", result))
    rows = _aggregate_offering_results(entries, grain)
    for row in rows:
        row.series_level = "user_group"
    return rows


def datastore_series(results: Iterable[StatsResult], grain: str) -> list[SeriesRow]:
    entries = [
        (r.item.datastore_id, r.item.datastore_name, r.item.datastore_name, r.item.datastore_id, "", r)
        for r in results
        if r.item.kind == OFFERING and r.item.datastore_id
    ]
    rows = _aggregate_offering_results(entries, grain)
    for row in rows:
        row.series_level = "datastore"
    return rows


def service_type_series(results: Iterable[StatsResult], grain: str) -> list[SeriesRow]:
    entries = [
        (r.item.service_type or "(non renseigné)", r.item.service_type or "(non renseigné)", "", "", r.item.service_type, r)
        for r in results
        if r.item.kind == OFFERING
    ]
    rows = _aggregate_offering_results(entries, grain)
    for row in rows:
        row.series_level = "service_type"
    return rows


def build_all_series(results: Iterable[StatsResult], groups: Iterable[Group], grain: str) -> list[SeriesRow]:
    results = list(results)
    groups = list(groups)
    return [
        *individual_series(results, grain),
        *group_series(results, groups, grain),
        *datastore_series(results, grain),
        *service_type_series(results, grain),
    ]
