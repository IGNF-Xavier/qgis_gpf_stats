"""Per-datastore detail (``GET /datastores/{id}``): storage usage/quota per
backend and every endpoint provisioned for it, whether or not it currently
has any offering attached.

This route is noticeably slow (observed 10-30s per datastore on production),
apparently because the server aggregates storage usage on the fly - there is
no lighter variant (``?fields=`` is ignored, ``/storages`` sub-route does not
exist). Callers must treat it as a per-datastore, potentially long-running
operation and let the user pick which datastores to fetch rather than
looping over all of them unconditionally.
"""
from __future__ import annotations

from urllib.parse import quote

from ..core.models import DatastoreEndpointInfo, DatastoreInfo, DatastoreLoadError, DatastoreRef, StorageUsage
from .api_client import ApiClient, extract_id
from .progress import CancelCheck, ProgressCallback, ProgressEvent, never_cancelled, noop_progress


def _quote(value: str) -> str:
    return quote(str(value), safe="")


def _parse_storage_usage(entry: dict) -> StorageUsage:
    storage = entry.get("storage") or {}
    try:
        use_bytes = int(entry.get("use") or 0)
    except (TypeError, ValueError):
        use_bytes = 0
    try:
        quota_bytes = int(entry.get("quota") or 0)
    except (TypeError, ValueError):
        quota_bytes = 0
    return StorageUsage(
        name=str(storage.get("name") or storage.get("type") or ""),
        type=str(storage.get("type") or ""),
        use_bytes=use_bytes,
        quota_bytes=quota_bytes,
    )


def _parse_endpoint_info(binding: dict) -> DatastoreEndpointInfo:
    endpoint = binding.get("endpoint") if isinstance(binding.get("endpoint"), dict) else binding
    try:
        use = int(binding.get("use") or 0)
    except (TypeError, ValueError):
        use = 0
    try:
        quota = int(binding.get("quota") or 0)
    except (TypeError, ValueError):
        quota = 0
    urls = tuple(str(u.get("url") or "") for u in (endpoint.get("urls") or []) if isinstance(u, dict))
    return DatastoreEndpointInfo(
        name=str(endpoint.get("name") or endpoint.get("technical_name") or extract_id(endpoint)),
        technical_name=str(endpoint.get("technical_name") or ""),
        type=str(endpoint.get("type") or ""),
        open=bool(endpoint.get("open", True)),
        use=use,
        quota=quota,
        urls=urls,
    )


def fetch_datastore_info(client: ApiClient, datastore_id: str, is_cancelled: CancelCheck = never_cancelled) -> DatastoreInfo:
    data, _, _ = client.get_json(f"/datastores/{_quote(datastore_id)}", is_cancelled=is_cancelled)
    storages = data.get("storages") or {}
    data_storages = [_parse_storage_usage(entry) for entry in storages.get("data") or []]
    uploads = storages.get("uploads")
    annexes = storages.get("annexes")
    endpoints = [_parse_endpoint_info(binding) for binding in data.get("endpoints") or []]
    return DatastoreInfo(
        datastore_id=datastore_id,
        name=str(data.get("name") or datastore_id),
        technical_name=str(data.get("technical_name") or ""),
        active=bool(data.get("active", True)),
        creation=str(data.get("creation") or ""),
        data_storages=data_storages,
        uploads_storage=_parse_storage_usage(uploads) if uploads else None,
        annexes_storage=_parse_storage_usage(annexes) if annexes else None,
        endpoints=endpoints,
    )


def fetch_many_datastore_info(
    client: ApiClient,
    refs: list[DatastoreRef],
    progress_callback: ProgressCallback = noop_progress,
    is_cancelled: CancelCheck = never_cancelled,
) -> tuple[list[DatastoreInfo], list[DatastoreLoadError]]:
    """One datastore's failure (this route can be slow enough to time out)
    never discards the others - matches the isolation already applied to the
    main catalog load."""
    infos: list[DatastoreInfo] = []
    errors: list[DatastoreLoadError] = []
    for index, ref in enumerate(refs, 1):
        if is_cancelled():
            break
        progress_callback(
            ProgressEvent(
                "datastore_info",
                f"Datastore {index}/{len(refs)} : {ref.name} (peut prendre jusqu'à 30 secondes)",
                current=index,
                total=len(refs),
                extra={"datastore_name": ref.name},
            )
        )
        try:
            infos.append(fetch_datastore_info(client, ref.datastore_id, is_cancelled))
        except Exception as exc:  # noqa: BLE001 - isolate per-datastore failures on purpose
            errors.append(DatastoreLoadError(datastore_id=ref.datastore_id, datastore_name=ref.name, stage="info", message=str(exc)))
    return infos, errors
