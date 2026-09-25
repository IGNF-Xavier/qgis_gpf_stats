import json

import pytest

from geoplateforme_usage_stats.net.api_client import ApiError, TransportResponse
from geoplateforme_usage_stats.net.progress import OperationCancelled


def test_pagination_stops_on_x_total_count(fake_transport, api_client):
    all_items = [{"_id": str(i)} for i in range(125)]

    def handler(params):
        page = int(params["page"])
        limit = int(params["limit"])
        chunk = all_items[(page - 1) * limit : page * limit]
        return {"items": chunk}, {"x-total-count": str(len(all_items))}

    def wrapped(params):
        payload, headers = handler(params)
        return TransportResponse(status=200, headers=headers, body=json.dumps(payload).encode())

    fake_transport.when("/things", wrapped)
    result = api_client.get_all_pages("/things", page_size=50)
    assert len(result) == 125
    assert fake_transport.call_count("/things") == 3


def test_pagination_stops_on_short_page_without_total_count(fake_transport, api_client):
    all_items = [{"_id": str(i)} for i in range(30)]

    def wrapped(params):
        return {"items": all_items}

    fake_transport.when("/things", wrapped)
    result = api_client.get_all_pages("/things", page_size=50)
    assert len(result) == 30
    assert fake_transport.call_count("/things") == 1


def test_retryable_status_is_retried_then_succeeds(fake_transport, api_client):
    calls = {"n": 0}

    def wrapped(_params):
        calls["n"] += 1
        if calls["n"] < 3:
            return TransportResponse(status=503, headers={}, body=b"")
        return TransportResponse(status=200, headers={}, body=b'{"ok": true}')

    fake_transport.when("/flaky", wrapped)
    data, _, status = api_client.get_json("/flaky")
    assert status == 200
    assert data == {"ok": True}
    assert calls["n"] == 3


def test_non_retryable_status_raises_immediately(fake_transport, api_client):
    calls = {"n": 0}

    def wrapped(_params):
        calls["n"] += 1
        return TransportResponse(status=403, headers={}, body=b"")

    fake_transport.when("/forbidden", wrapped)
    with pytest.raises(ApiError) as excinfo:
        api_client.get_json("/forbidden")
    assert excinfo.value.status == 403
    assert calls["n"] == 1


def test_404_raises_api_error_with_status(fake_transport, api_client):
    fake_transport.when("/missing", lambda params: TransportResponse(status=404, headers={}, body=b""))
    with pytest.raises(ApiError) as excinfo:
        api_client.get_json("/missing")
    assert excinfo.value.status == 404


def test_cancellation_stops_pagination(fake_transport, api_client):
    fake_transport.when("/things", lambda params: {"items": [{"_id": "1"}] * 50})
    with pytest.raises(OperationCancelled):
        api_client.get_all_pages("/things", is_cancelled=lambda: True)
    assert fake_transport.call_count("/things") == 0
