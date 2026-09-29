from geoplateforme_usage_stats.core.models import DatastoreRef
from geoplateforme_usage_stats.net.api_client import TransportResponse
from geoplateforme_usage_stats.net.datastore_info_service import fetch_datastore_info, fetch_many_datastore_info

DATASTORE_ID = "342f9301-d2a8-455f-adf5-e2cc73b90423"

REAL_SHAPED_RESPONSE = {
    "name": "Recette cartes.gouv",
    "technical_name": "recette-cartes-gouv",
    "active": True,
    "creation": "2024-02-23T14:28:44.104369Z",
    "_id": DATASTORE_ID,
    "endpoints": [
        {
            "use": 4,
            "quota": 10,
            "endpoint": {
                "name": "Service de diffusion WFS principal",
                "technical_name": "gpf-geoserver-wfs",
                "type": "WFS",
                "open": True,
                "urls": [{"type": "WFS", "url": "https://data.geopf.fr/wfs"}],
                "_id": "ae012611-13eb-4a18-8d04-9b7604a031cc",
            },
        },
        {
            "use": 0,
            "quota": 10,
            "endpoint": {
                "name": "Service de diffusion WFS privé",
                "technical_name": "gpf-geoserver-wfs-private",
                "type": "WFS",
                "open": False,
                "urls": [{"type": "WFS", "url": "https://data.geopf.fr/private/wfs/"}],
                "_id": "d02feec9-1169-403f-bfc3-7ba6d6015ed4",
            },
        },
    ],
    "storages": {
        "data": [
            {
                "use": 63471616,
                "quota": 10000000000,
                "storage": {"name": "Stockage PostgreSQL standard IGN", "type": "POSTGRESQL", "_id": "x"},
            },
            {
                "use": 10619129755,
                "quota": 10000000000,
                "storage": {"name": "Stockage OpenIO archives", "type": "S3", "_id": "y"},
            },
        ],
        "uploads": {"use": 569881822, "quota": 10000000000, "storage": {"name": "Stockage NAS-HA", "type": "FILESYSTEM", "_id": "z"}},
        "annexes": {"use": 2273317, "quota": 10000000000, "storage": {"name": "Stockage annexes", "type": "S3", "_id": "w"}},
    },
}


def test_fetch_datastore_info_parses_real_api_shape(fake_transport, api_client):
    fake_transport.when(f"/datastores/{DATASTORE_ID}", lambda params: REAL_SHAPED_RESPONSE)
    info = fetch_datastore_info(api_client, DATASTORE_ID)

    assert info.name == "Recette cartes.gouv"
    assert info.active is True
    assert len(info.data_storages) == 2
    assert info.data_storages[0].use_bytes == 63471616
    assert info.uploads_storage.use_bytes == 569881822
    assert info.annexes_storage.use_bytes == 2273317
    assert info.total_use_bytes() == 63471616 + 10619129755 + 569881822 + 2273317
    assert info.total_quota_bytes() == 4 * 10000000000

    assert len(info.endpoints) == 2
    public_wfs = next(e for e in info.endpoints if e.open)
    private_wfs = next(e for e in info.endpoints if not e.open)
    assert public_wfs.name == "Service de diffusion WFS principal"
    assert public_wfs.use == 4 and public_wfs.quota == 10
    assert private_wfs.use == 0
    assert public_wfs.urls == ("https://data.geopf.fr/wfs",)


def test_fetch_datastore_info_tolerates_missing_storage_sections(fake_transport, api_client):
    fake_transport.when(
        f"/datastores/{DATASTORE_ID}",
        lambda params: {"name": "Vide", "technical_name": "vide", "active": False, "endpoints": [], "storages": {}},
    )
    info = fetch_datastore_info(api_client, DATASTORE_ID)
    assert info.active is False
    assert info.data_storages == []
    assert info.uploads_storage is None
    assert info.annexes_storage is None
    assert info.total_use_bytes() == 0
    assert info.total_quota_bytes() == 0


def test_fetch_many_datastore_info_isolates_failures(fake_transport, api_client):
    refs = [
        DatastoreRef(datastore_id="ds-ok", name="OK"),
        DatastoreRef(datastore_id="ds-bad", name="Bad"),
    ]
    fake_transport.when("/datastores/ds-ok", lambda params: {"name": "OK", "technical_name": "ok", "active": True})
    fake_transport.when("/datastores/ds-bad", lambda params: TransportResponse(status=500, headers={}, body=b""))

    infos, errors = fetch_many_datastore_info(api_client, refs)
    assert [i.datastore_id for i in infos] == ["ds-ok"]
    assert [(e.datastore_id, e.stage) for e in errors] == [("ds-bad", "info")]


def test_fetch_many_datastore_info_reports_progress(fake_transport, api_client):
    refs = [DatastoreRef(datastore_id="ds-ok", name="OK")]
    fake_transport.when("/datastores/ds-ok", lambda params: {"name": "OK", "technical_name": "ok", "active": True})
    events = []
    fetch_many_datastore_info(api_client, refs, progress_callback=events.append)
    assert events and events[0].current == 1 and events[0].total == 1
