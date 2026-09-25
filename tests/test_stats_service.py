from geoplateforme_usage_stats.core.models import CatalogItem, OFFERING, STATUS_ERROR, STATUS_NOT_CONNECTED, STATUS_WITH_USAGE, STATUS_WITHOUT_USAGE
from geoplateforme_usage_stats.net.api_client import TransportResponse
from geoplateforme_usage_stats.net.stats_service import fetch_many, fetch_stats

ITEM = CatalogItem(
    kind=OFFERING,
    label="Offre test · DS",
    stats_path="/datastores/ds/offerings/off-1/stats",
    datastore_name="DS",
    datastore_id="ds",
    offering_name="Offre test",
    offering_id="off-1",
)


def test_fetch_stats_with_usage_and_pagination(fake_transport, api_client):
    pages = {
        1: {"total": {"hits": 30, "data_transfer": 12345, "begin_date": "2026-08-01T00:00:00.000Z", "end_date": "2026-08-20T00:00:00.000Z"},
            "details": [{"begin_date": "2026-08-01T00:00:00.000Z", "end_date": "2026-08-01T23:59:59.000Z", "hits": 10, "data_transfer": 100}] * 50},
        2: {"details": [{"begin_date": "2026-08-02T00:00:00.000Z", "end_date": "2026-08-02T23:59:59.000Z", "hits": 5, "data_transfer": 50}] * 10},
    }

    def handler(params):
        return pages[int(params["page"])]

    fake_transport.when(ITEM.stats_path, handler)
    result = fetch_stats(api_client, ITEM, "2026-08-01T00:00:00.000Z", "2026-08-20T00:00:00.000Z", details_requested=True)

    assert result.status == STATUS_WITH_USAGE
    assert result.hits == 30
    assert result.data_transfer == 12345
    assert len(result.points) == 60
    assert fake_transport.call_count(ITEM.stats_path) == 2


def test_fetch_stats_without_usage(fake_transport, api_client):
    fake_transport.when(ITEM.stats_path, lambda params: {"total": {"hits": 0, "data_transfer": 0}, "details": []})
    result = fetch_stats(api_client, ITEM, "start", "end", details_requested=True)
    assert result.status == STATUS_WITHOUT_USAGE
    assert result.hits == 0


def test_fetch_stats_not_connected_on_404(fake_transport, api_client):
    fake_transport.when(ITEM.stats_path, lambda params: TransportResponse(status=404, headers={}, body=b""))
    result = fetch_stats(api_client, ITEM, "start", "end", details_requested=False)
    assert result.status == STATUS_NOT_CONNECTED
    assert result.http_status == 404


def test_fetch_stats_error_on_other_failure(fake_transport, api_client):
    fake_transport.when(ITEM.stats_path, lambda params: TransportResponse(status=500, headers={}, body=b""))
    result = fetch_stats(api_client, ITEM, "start", "end", details_requested=False)
    assert result.status == STATUS_ERROR


def test_fetch_many_isolates_item_failures(fake_transport, api_client):
    other = CatalogItem(
        kind=OFFERING, label="Autre", stats_path="/datastores/ds/offerings/off-2/stats",
        datastore_name="DS", datastore_id="ds", offering_id="off-2",
    )
    fake_transport.when(ITEM.stats_path, lambda params: TransportResponse(status=404, headers={}, body=b""))
    fake_transport.when(other.stats_path, lambda params: {"total": {"hits": 1, "data_transfer": 1}, "details": []})

    results = fetch_many(api_client, [ITEM, other], "start", "end", details_requested=False)
    statuses = {r.item.item_id: r.status for r in results}
    assert statuses["off-1"] == STATUS_NOT_CONNECTED
    assert statuses["off-2"] == STATUS_WITH_USAGE


def test_fetch_many_reports_progress(fake_transport, api_client):
    fake_transport.when(ITEM.stats_path, lambda params: {"total": {}, "details": []})
    events = []
    fetch_many(api_client, [ITEM], "start", "end", False, progress_callback=events.append)
    assert events and events[0].current == 1 and events[0].total == 1
