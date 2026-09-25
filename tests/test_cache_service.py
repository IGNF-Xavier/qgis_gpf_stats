from datetime import datetime, timedelta, timezone

from geoplateforme_usage_stats.core import cache_service
from geoplateforme_usage_stats.core.models import Catalog, CatalogItem, DatastoreLoadError, OFFERING


def make_catalog():
    return Catalog(
        items=[CatalogItem(kind=OFFERING, label="Offre · DS", stats_path="/x", offering_id="off-1", datastore_id="ds")],
        errors=[DatastoreLoadError(datastore_id="ds2", datastore_name="DS2", stage="offerings", message="boom")],
        loaded_at="2026-09-22T00:00:00.000Z",
    )


def test_save_and_load_round_trip(tmp_path):
    store = cache_service.FileCacheStore(str(tmp_path))
    cache_service.save_catalog(store, make_catalog())
    reloaded = cache_service.load_catalog(store)
    assert reloaded is not None
    assert reloaded.from_cache is True
    assert len(reloaded.items) == 1
    assert reloaded.items[0].offering_id == "off-1"
    assert len(reloaded.errors) == 1


def test_load_returns_none_when_absent(tmp_path):
    store = cache_service.FileCacheStore(str(tmp_path))
    assert cache_service.load_catalog(store) is None


def test_clear_removes_file(tmp_path):
    store = cache_service.FileCacheStore(str(tmp_path))
    cache_service.save_catalog(store, make_catalog())
    cache_service.clear(store)
    assert cache_service.load_catalog(store) is None


def test_is_stale_true_when_missing():
    assert cache_service.is_stale(None) is True


def test_is_stale_respects_max_age():
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    loaded_at = (now - timedelta(hours=1)).isoformat()
    assert cache_service.is_stale(loaded_at, max_age_seconds=3600 * 6, now=now) is False
    assert cache_service.is_stale(loaded_at, max_age_seconds=1800, now=now) is True
