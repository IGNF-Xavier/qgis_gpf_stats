import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from geoplateforme_usage_stats.net.api_client import ApiClient, TransportResponse


def json_response(status: int, payload, headers: dict | None = None) -> TransportResponse:
    return TransportResponse(status=status, headers=headers or {}, body=json.dumps(payload).encode("utf-8"))


class FakeTransport:
    """Records every call and dispatches by exact path to a handler."""

    def __init__(self):
        self.handlers = {}
        self.call_log: list[tuple[str, dict]] = []

    def when(self, path: str, handler):
        self.handlers[path] = handler
        return self

    def request(self, path: str, params) -> TransportResponse:
        params_dict = dict(params)
        self.call_log.append((path, params_dict))
        handler = self.handlers.get(path)
        if handler is None:
            return json_response(404, {"message": "not found"})
        result = handler(params_dict)
        if isinstance(result, TransportResponse):
            return result
        return json_response(200, result)

    def call_count(self, path: str) -> int:
        return sum(1 for logged_path, _ in self.call_log if logged_path == path)


@pytest.fixture
def fake_transport() -> FakeTransport:
    return FakeTransport()


@pytest.fixture
def api_client(fake_transport: FakeTransport) -> ApiClient:
    return ApiClient(fake_transport, retries=3, backoff_base_seconds=0.0, sleep=lambda seconds: None)


def _synthetic_dataset():
    from geoplateforme_usage_stats.core.models import (
        CONSUMER_PERMISSION,
        CatalogItem,
        ENDPOINT,
        Group,
        OFFERING,
        PeriodConfig,
        PRODUCER_PERMISSION,
        STATUS_NOT_CONNECTED,
        STATUS_WITH_USAGE,
        STATUS_WITHOUT_USAGE,
        StatsPoint,
        StatsResult,
    )

    period = PeriodConfig(
        preset="last30", requested_start="2026-08-23T00:00:00.000Z", requested_end="2026-09-22T00:00:00.000Z",
        duration_days=30, details_requested=True, fine_requested=False, analysis_grain="day",
    )

    def offering(offering_id, datastore_id, datastore_name, service_type, endpoint_id, points):
        item = CatalogItem(
            kind=OFFERING, label=f"Offre {offering_id} · {datastore_name}", stats_path=f"/datastores/{datastore_id}/offerings/{offering_id}/stats",
            offering_id=offering_id, offering_name=f"Offre {offering_id}", datastore_id=datastore_id, datastore_name=datastore_name,
            service_type=service_type, endpoint_id=endpoint_id, endpoint_name=f"Diffusion {endpoint_id}",
        )
        hits = sum(p.hits for p in points)
        data_transfer = sum(p.data_transfer for p in points)
        status = STATUS_WITH_USAGE if hits or data_transfer else STATUS_WITHOUT_USAGE
        return StatsResult(item=item, http_status=200, status=status, hits=hits, data_transfer=data_transfer, points=points,
                            first_activity=points[0].period_start if points else "", last_activity=points[-1].period_start if points else "")

    results = [
        offering("off-1", "ds1", "IGN_Recette", "WFS", "ep-1", [
            StatsPoint("2026-08-24T00:00:00.000Z", "2026-08-24T00:05:00.000Z", 10, 1000),
            StatsPoint("2026-09-20T00:00:00.000Z", "2026-09-20T00:05:00.000Z", 5, 500),
        ]),
        offering("off-2", "ds1", "IGN_Recette", "WMTS-TMS", "ep-1", [
            StatsPoint("2026-08-25T00:00:00.000Z", "2026-08-25T00:05:00.000Z", 3, 300),
        ]),
        offering("off-3", "ds2", "IGN_Prod", "WMS-VECTOR", "ep-2", []),
        StatsResult(
            item=CatalogItem(kind=ENDPOINT, label="Diffusion ep-1 · IGN_Recette", stats_path="/datastores/ds1/endpoints/ep-1/stats", datastore_id="ds1", datastore_name="IGN_Recette", endpoint_id="ep-1", endpoint_name="Diffusion ep-1"),
            http_status=200, status=STATUS_WITH_USAGE, hits=13, data_transfer=1300,
            points=[StatsPoint("2026-08-24T00:00:00.000Z", "x", 13, 1300)],
            first_activity="2026-08-24T00:00:00.000Z", last_activity="2026-08-24T00:00:00.000Z",
        ),
        StatsResult(
            item=CatalogItem(kind=PRODUCER_PERMISSION, label="Perm producteur · IGN_Recette", stats_path="/datastores/ds1/permissions/perm-1/stats", datastore_id="ds1", datastore_name="IGN_Recette", permission_id="perm-1", permission_name="Perm producteur"),
            http_status=200, status=STATUS_WITH_USAGE, hits=13, data_transfer=1300,
            points=[StatsPoint("2026-08-24T00:00:00.000Z", "x", 13, 1300)],
        ),
        StatsResult(
            item=CatalogItem(kind=CONSUMER_PERMISSION, label="COUCHE.A", stats_path="/users/me/permissions/perm-c/stats", permission_id="perm-c", permission_name="COUCHE.A"),
            http_status=404, status=STATUS_NOT_CONNECTED, message="Non raccordé à Stats",
        ),
    ]
    groups = [Group(group_id="g1", name="Groupe diffusion", description="", color="", offering_ids=["off-1", "off-2"], created_at="now", updated_at="now")]
    return results, groups, period


@pytest.fixture
def synthetic_dataset():
    return _synthetic_dataset()
