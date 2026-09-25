from geoplateforme_usage_stats.core import dashboard_service as dash
from geoplateforme_usage_stats.core.coverage_service import assess_coverage
from geoplateforme_usage_stats.core.models import (
    CatalogItem,
    ENDPOINT,
    Group,
    OFFERING,
    PeriodConfig,
    STATUS_WITH_USAGE,
    StatsResult,
)

PERIOD = PeriodConfig("last30", "2026-08-23T00:00:00.000Z", "2026-09-22T00:00:00.000Z", 30, True, False, "day")


def result(kind, item_id, hits, data_transfer=0, **extra):
    item = CatalogItem(kind=kind, label=item_id, stats_path="/x", offering_id=item_id if kind == OFFERING else "", endpoint_id=item_id if kind == ENDPOINT else "", **extra)
    return StatsResult(item=item, http_status=200, status=STATUS_WITH_USAGE, hits=hits, data_transfer=data_transfer)


def test_kpis_never_mix_offerings_and_endpoints():
    results = [result(OFFERING, "off-1", 100), result(ENDPOINT, "ep-1", 999)]
    coverages = {r.item.item_id: assess_coverage(r, PERIOD) for r in results}
    offering_kpi = dash.compute_item_level_kpis(results, coverages, "offering", PERIOD)
    endpoint_kpi = dash.compute_item_level_kpis(results, coverages, "endpoint", PERIOD)
    assert offering_kpi.hits_total == 100
    assert endpoint_kpi.hits_total == 999
    assert offering_kpi.objects_queried == 1
    assert endpoint_kpi.objects_queried == 1


def test_group_kpi_warns_on_overlap_when_no_group_selected():
    group_a = Group(group_id="ga", name="A", offering_ids=["off-1"])
    group_b = Group(group_id="gb", name="B", offering_ids=["off-1"])
    from geoplateforme_usage_stats.core.aggregation_service import group_series
    from geoplateforme_usage_stats.core.models import StatsPoint

    off_result = result(OFFERING, "off-1", 0)
    off_result.points = [StatsPoint("2026-08-24T00:00:00.000Z", "x", 10, 10)]
    off_result.hits = 10
    off_result.data_transfer = 10
    rows = group_series([off_result], [group_a, group_b], "day")

    kpi_all = dash.compute_group_level_kpis([group_a, group_b], rows, PERIOD)
    assert kpi_all.warnings, "expected an overlap warning when aggregating multiple groups"

    kpi_single = dash.compute_group_level_kpis([group_a, group_b], rows, PERIOD, selected_group_id="ga")
    assert kpi_single.warnings == []
    assert kpi_single.hits_total == 10


def test_ranking_and_time_evolution():
    from geoplateforme_usage_stats.core.models import SeriesRow

    rows = [
        SeriesRow("offering", "off-1", "Offre 1", "2026-08-24", "day", 10, 100),
        SeriesRow("offering", "off-1", "Offre 1", "2026-08-25", "day", 5, 50),
        SeriesRow("offering", "off-2", "Offre 2", "2026-08-24", "day", 20, 200),
    ]
    assert dash.time_evolution(rows, "hits") == [("2026-08-24", 30), ("2026-08-25", 5)]
    assert dash.ranking(rows, "hits") == [("Offre 2", 20), ("Offre 1", 15)]
