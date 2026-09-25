from geoplateforme_usage_stats.core.coverage_service import assess_coverage, period_bucket
from geoplateforme_usage_stats.core.models import (
    CatalogItem,
    OFFERING,
    PeriodConfig,
    STATUS_ERROR,
    STATUS_NOT_CONNECTED,
    STATUS_WITH_USAGE,
    STATUS_WITHOUT_USAGE,
    StatsPoint,
    StatsResult,
)

ITEM = CatalogItem(kind=OFFERING, label="Offre", stats_path="/x", offering_id="off-1")
PERIOD = PeriodConfig(
    preset="last30",
    requested_start="2026-08-23T00:00:00.000Z",
    requested_end="2026-09-22T00:00:00.000Z",
    duration_days=30,
    details_requested=True,
    fine_requested=False,
    analysis_grain="day",
)


def test_period_bucket_day_week_month():
    assert period_bucket("2026-08-24T13:09:05.384Z", "day") == "2026-08-24"
    assert period_bucket("2026-08-24T13:09:05.384Z", "month") == "2026-08"
    assert period_bucket("2026-08-24T13:09:05.384Z", "week").startswith("2026-S")


def test_not_connected():
    result = StatsResult(item=ITEM, http_status=404, status=STATUS_NOT_CONNECTED, message="404")
    coverage = assess_coverage(result, PERIOD)
    assert coverage.coverage_status == "not_connected"


def test_error_status():
    result = StatsResult(item=ITEM, http_status=500, status=STATUS_ERROR, message="boom")
    coverage = assess_coverage(result, PERIOD)
    assert coverage.coverage_status == "error"


def test_no_usage():
    result = StatsResult(item=ITEM, http_status=200, status=STATUS_WITHOUT_USAGE, hits=0, data_transfer=0)
    coverage = assess_coverage(result, PERIOD)
    assert coverage.coverage_status == "no_usage"


def test_no_temporal_detail_when_points_missing_but_hits_present():
    result = StatsResult(item=ITEM, http_status=200, status=STATUS_WITH_USAGE, hits=5, data_transfer=500, points=[])
    coverage = assess_coverage(result, PERIOD)
    assert coverage.coverage_status == "no_temporal_detail"


def test_partial_coverage_when_activity_concentrated():
    result = StatsResult(
        item=ITEM, http_status=200, status=STATUS_WITH_USAGE, hits=5, data_transfer=500,
        points=[StatsPoint("2026-09-01T00:00:00.000Z", "2026-09-01T00:05:00.000Z", 5, 500)],
        first_activity="2026-09-01T00:00:00.000Z", last_activity="2026-09-01T00:05:00.000Z",
    )
    coverage = assess_coverage(result, PERIOD)
    assert coverage.coverage_status == "partial_coverage"
    assert coverage.active_days_count == 1


def test_complete_coverage_when_activity_spans_full_period():
    result = StatsResult(
        item=ITEM, http_status=200, status=STATUS_WITH_USAGE, hits=100, data_transfer=5000,
        points=[
            StatsPoint("2026-08-23T01:00:00.000Z", "2026-08-23T02:00:00.000Z", 1, 10),
            StatsPoint("2026-09-21T23:00:00.000Z", "2026-09-21T23:59:00.000Z", 99, 4990),
        ],
        first_activity="2026-08-23T01:00:00.000Z", last_activity="2026-09-21T23:59:00.000Z",
    )
    coverage = assess_coverage(result, PERIOD)
    assert coverage.coverage_status == "complete_coverage"
