from geoplateforme_usage_stats.core import aggregation_service as agg
from geoplateforme_usage_stats.core.models import (
    CatalogItem,
    ENDPOINT,
    Group,
    OFFERING,
    STATUS_WITH_USAGE,
    StatsPoint,
    StatsResult,
)


def offering(offering_id, datastore_id, datastore_name, service_type, points):
    item = CatalogItem(
        kind=OFFERING, label=f"{offering_id} · {datastore_name}", stats_path="/x",
        offering_id=offering_id, datastore_id=datastore_id, datastore_name=datastore_name,
        service_type=service_type,
    )
    return StatsResult(item=item, http_status=200, status=STATUS_WITH_USAGE, hits=sum(p.hits for p in points), data_transfer=sum(p.data_transfer for p in points), points=points)


def test_individual_series_buckets_by_day():
    result = offering(
        "off-1", "ds1", "DS1", "WFS",
        [
            StatsPoint("2026-08-24T10:00:00.000Z", "2026-08-24T10:05:00.000Z", 2, 100),
            StatsPoint("2026-08-24T18:00:00.000Z", "2026-08-24T18:05:00.000Z", 3, 150),
            StatsPoint("2026-08-25T10:00:00.000Z", "2026-08-25T10:05:00.000Z", 4, 200),
        ],
    )
    rows = agg.individual_series([result], "day")
    by_period = {r.period_key: (r.hits, r.data_transfer) for r in rows}
    assert by_period["2026-08-24"] == (5, 250)
    assert by_period["2026-08-25"] == (4, 200)


def test_individual_series_raw_grain_keeps_points_separate():
    result = offering("off-1", "ds1", "DS1", "WFS", [
        StatsPoint("2026-08-24T10:00:00.000Z", "2026-08-24T10:05:00.000Z", 2, 100),
        StatsPoint("2026-08-24T18:00:00.000Z", "2026-08-24T18:05:00.000Z", 3, 150),
    ])
    rows = agg.individual_series([result], "raw")
    assert len(rows) == 2


def test_group_series_sums_non_aligned_periods_across_offerings():
    # Two offerings whose API period_start values never match exactly.
    off_a = offering("off-1", "ds1", "DS1", "WFS", [
        StatsPoint("2026-08-24T00:00:00.000Z", "2026-08-24T08:00:00.000Z", 2, 100),
    ])
    off_b = offering("off-2", "ds1", "DS1", "WMTS-TMS", [
        StatsPoint("2026-08-24T09:00:00.000Z", "2026-08-24T23:59:00.000Z", 5, 500),
    ])
    group = Group(group_id="g1", name="Groupe A", offering_ids=["off-1", "off-2"])
    rows = agg.group_series([off_a, off_b], [group], "day")
    assert len(rows) == 1
    assert rows[0].hits == 7
    assert rows[0].data_transfer == 600
    assert rows[0].contributor_count == 2
    assert rows[0].series_level == "user_group"


def test_group_series_empty_group_has_no_rows():
    off_a = offering("off-1", "ds1", "DS1", "WFS", [StatsPoint("2026-08-24T00:00:00.000Z", "x", 1, 1)])
    group = Group(group_id="g1", name="Vide", offering_ids=[])
    rows = agg.group_series([off_a], [group], "day")
    assert rows == []


def test_group_spanning_multiple_datastores():
    off_a = offering("off-1", "ds1", "DS1", "WFS", [StatsPoint("2026-08-24T00:00:00.000Z", "x", 1, 10)])
    off_b = offering("off-2", "ds2", "DS2", "WMTS-TMS", [StatsPoint("2026-08-24T01:00:00.000Z", "x", 2, 20)])
    group = Group(group_id="g1", name="Multi", offering_ids=["off-1", "off-2"])
    rows = agg.group_series([off_a, off_b], [group], "day")
    assert len(rows) == 1
    assert rows[0].hits == 3
    assert rows[0].contributor_count == 2


def test_overlapping_groups_are_not_summed_together():
    off_a = offering("off-1", "ds1", "DS1", "WFS", [StatsPoint("2026-08-24T00:00:00.000Z", "x", 10, 10)])
    group_a = Group(group_id="ga", name="A", offering_ids=["off-1"])
    group_b = Group(group_id="gb", name="B", offering_ids=["off-1"])
    rows = agg.group_series([off_a], [group_a, group_b], "day")
    per_group = {r.series_key: r.hits for r in rows}
    assert per_group == {"ga": 10, "gb": 10}  # each group keeps its own total, never merged


def test_datastore_series_only_uses_offerings():
    off_a = offering("off-1", "ds1", "DS1", "WFS", [StatsPoint("2026-08-24T00:00:00.000Z", "x", 1, 1)])
    endpoint_item = CatalogItem(kind=ENDPOINT, label="EP", stats_path="/y", datastore_id="ds1", datastore_name="DS1")
    endpoint_result = StatsResult(item=endpoint_item, http_status=200, status=STATUS_WITH_USAGE, hits=999, data_transfer=999, points=[StatsPoint("2026-08-24T00:00:00.000Z", "x", 999, 999)])
    rows = agg.datastore_series([off_a, endpoint_result], "day")
    assert len(rows) == 1
    assert rows[0].hits == 1  # endpoint-level result never mixed into the offering-only datastore lens


def test_service_type_series_groups_by_type():
    off_a = offering("off-1", "ds1", "DS1", "WFS", [StatsPoint("2026-08-24T00:00:00.000Z", "x", 1, 1)])
    off_b = offering("off-2", "ds1", "DS1", "WFS", [StatsPoint("2026-08-24T01:00:00.000Z", "x", 2, 2)])
    off_c = offering("off-3", "ds1", "DS1", "WMTS-TMS", [StatsPoint("2026-08-24T02:00:00.000Z", "x", 3, 3)])
    rows = agg.service_type_series([off_a, off_b, off_c], "day")
    per_type = {r.series_key: r.hits for r in rows}
    assert per_type["WFS"] == 3
    assert per_type["WMTS-TMS"] == 3
