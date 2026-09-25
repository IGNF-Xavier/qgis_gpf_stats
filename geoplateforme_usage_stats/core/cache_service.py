"""Timestamped local cache of the producer/consumer catalog.

The cache is a single JSON file. Storage access is abstracted behind
:class:`CacheStore` so the module can be unit-tested with a plain temporary
directory instead of QGIS's settings directory.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

from .models import Catalog, CatalogItem, DatastoreLoadError

CACHE_FILE_NAME = "catalog_cache_v7.json"
DEFAULT_MAX_AGE_SECONDS = 6 * 3600


class CacheStore(Protocol):
    def read_text(self) -> Optional[str]: ...
    def write_text(self, text: str) -> None: ...
    def remove(self) -> None: ...


class FileCacheStore:
    def __init__(self, directory: str, file_name: str = CACHE_FILE_NAME) -> None:
        self._path = Path(directory) / file_name
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def read_text(self) -> Optional[str]:
        if not self._path.exists():
            return None
        return self._path.read_text(encoding="utf-8")

    def write_text(self, text: str) -> None:
        self._path.write_text(text, encoding="utf-8")

    def remove(self) -> None:
        if self._path.exists():
            self._path.unlink()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def save_catalog(store: CacheStore, catalog: Catalog) -> None:
    payload = {
        "loaded_at": catalog.loaded_at or now_iso(),
        "items": [asdict(item) for item in catalog.items],
        "errors": [asdict(error) for error in catalog.errors],
    }
    store.write_text(json.dumps(payload, ensure_ascii=False))


def load_catalog(store: CacheStore) -> Optional[Catalog]:
    raw = store.read_text()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    items = [CatalogItem(**item) for item in payload.get("items", [])]
    errors = [DatastoreLoadError(**error) for error in payload.get("errors", [])]
    return Catalog(items=items, errors=errors, loaded_at=payload.get("loaded_at"), from_cache=True)


def is_stale(loaded_at: Optional[str], max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS, now: Optional[datetime] = None) -> bool:
    if not loaded_at:
        return True
    try:
        loaded = datetime.fromisoformat(str(loaded_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return (reference - loaded).total_seconds() > max_age_seconds


def clear(store: CacheStore) -> None:
    store.remove()
