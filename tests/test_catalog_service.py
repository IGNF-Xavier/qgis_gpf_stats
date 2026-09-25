from geoplateforme_usage_stats.core.models import CONSUMER_PERMISSION, ENDPOINT, OFFERING, PRODUCER_PERMISSION
from geoplateforme_usage_stats.net.catalog_service import build_catalog
from geoplateforme_usage_stats.net.progress import ProgressEvent


def _wire_two_datastores(fake_transport):
    fake_transport.when(
        "/users/me",
        lambda params: {
            "communities_member": [
                {"community": {"datastore": "ds-1", "name": "IGN_Recette"}},
                {"community": {"datastore": "ds-2", "name": "IGN_Prod"}},
            ]
        },
    )
    fake_transport.when(
        "/users/me/permissions",
        lambda params: {"items": [{"_id": "perm-consumer-1", "offerings": [{"layer_name": "COUCHE.A", "type": "WMTS-TMS"}]}]},
    )
    fake_transport.when(
        "/datastores/ds-1/offerings",
        lambda params: {"items": [{"_id": "off-1"}, {"_id": "off-2"}]},
    )
    fake_transport.when(
        "/datastores/ds-1/offerings/off-1",
        lambda params: {"configuration": {"name": "Offre 1"}, "type": "WMS-VECTOR", "endpoint": {"_id": "ep-1", "name": "Diffusion principale"}},
    )
    fake_transport.when(
        "/datastores/ds-1/offerings/off-2",
        lambda params: {"configuration": {"name": "Offre 2"}, "type": "WFS", "endpoint": {"_id": "ep-1", "name": "Diffusion principale"}},
    )
    fake_transport.when(
        "/datastores/ds-1/endpoints",
        # real API shape: a datastore/endpoint *binding*, not the endpoint itself
        lambda params: {"items": [{"use": 1, "quota": 10, "endpoint": {"_id": "ep-1", "name": "Diffusion principale", "type": "WFS"}}]},
    )
    fake_transport.when(
        "/datastores/ds-1/permissions",
        lambda params: {"items": [{"_id": "perm-prod-1", "offerings": [{"_id": "off-1"}]}]},
    )
    # ds-2 fails on offerings
    return fake_transport


def test_build_catalog_multiple_datastores(fake_transport, api_client):
    _wire_two_datastores(fake_transport)
    fake_transport.when("/datastores/ds-2/offerings", lambda params: (_ for _ in ()).throw(RuntimeError("boom")))

    events = []
    catalog = build_catalog(api_client, progress_callback=events.append)

    kinds = {item.kind for item in catalog.items}
    assert kinds == {CONSUMER_PERMISSION, OFFERING, ENDPOINT, PRODUCER_PERMISSION}
    assert len(catalog.offerings()) == 2
    assert len(catalog.errors) == 1
    assert catalog.errors[0].datastore_id == "ds-2"
    assert any(isinstance(e, ProgressEvent) and e.stage == "datastore_error" for e in events)


def test_offering_labels_are_contextualised_by_datastore(fake_transport, api_client):
    _wire_two_datastores(fake_transport)
    fake_transport.when("/datastores/ds-2/offerings", lambda params: {"items": []})
    fake_transport.when("/datastores/ds-2/endpoints", lambda params: {"items": []})
    fake_transport.when("/datastores/ds-2/permissions", lambda params: {"items": []})

    catalog = build_catalog(api_client)
    endpoint_item = next(i for i in catalog.items if i.kind == ENDPOINT)
    assert endpoint_item.label == "Diffusion principale · IGN_Recette"
    assert endpoint_item.stats_path == "/datastores/ds-1/endpoints/ep-1/stats"
    assert endpoint_item.endpoint_use == 1
    assert endpoint_item.endpoint_quota == 10


def test_no_duplicate_calls_on_same_route(fake_transport, api_client):
    _wire_two_datastores(fake_transport)
    fake_transport.when("/datastores/ds-2/offerings", lambda params: {"items": []})
    fake_transport.when("/datastores/ds-2/endpoints", lambda params: {"items": []})
    fake_transport.when("/datastores/ds-2/permissions", lambda params: {"items": []})

    build_catalog(api_client)
    assert fake_transport.call_count("/datastores/ds-1/offerings") == 1
    assert fake_transport.call_count("/datastores/ds-1/offerings/off-1") == 1
    assert fake_transport.call_count("/datastores/ds-1/offerings/off-2") == 1
    assert fake_transport.call_count("/datastores/ds-1/endpoints") == 1
    assert fake_transport.call_count("/datastores/ds-1/permissions") == 1
    assert fake_transport.call_count("/users/me") == 1
    assert fake_transport.call_count("/users/me/permissions") == 1


def test_endpoint_binding_is_unwrapped(fake_transport, api_client):
    # regression test: /datastores/{id}/endpoints returns {"use", "quota", "endpoint": {...}}
    # bindings, not endpoint objects directly - a naive read produced empty labels ("· DS_NAME")
    # against the real production API.
    _wire_two_datastores(fake_transport)
    fake_transport.when("/datastores/ds-2/offerings", lambda params: {"items": []})
    fake_transport.when("/datastores/ds-2/endpoints", lambda params: {"items": []})
    fake_transport.when("/datastores/ds-2/permissions", lambda params: {"items": []})

    catalog = build_catalog(api_client)
    endpoint_item = next(i for i in catalog.items if i.kind == ENDPOINT)
    assert endpoint_item.endpoint_id == "ep-1"
    assert endpoint_item.endpoint_name == "Diffusion principale"
    assert endpoint_item.service_type == "WFS"
    assert not endpoint_item.label.startswith("·")


def test_cancellation_stops_before_second_datastore(fake_transport, api_client):
    _wire_two_datastores(fake_transport)
    calls = {"n": 0}

    def is_cancelled():
        calls["n"] += 1
        return calls["n"] > 6

    catalog = build_catalog(api_client, is_cancelled=is_cancelled)
    assert isinstance(catalog.items, list)
