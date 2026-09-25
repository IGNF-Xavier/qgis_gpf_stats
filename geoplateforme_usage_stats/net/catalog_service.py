"""Build the full producer + consumer catalog (sections 1 and 3).

Route map (never invented - taken from the Entrepot API as specified):

* consumer: ``GET /users/me/permissions``
* producer datastores: ``GET /users/me`` (``communities_member[].community.datastore``)
* per datastore: ``GET /datastores/{id}/offerings``,
  ``GET /datastores/{id}/offerings/{offering}``,
  ``GET /datastores/{id}/permissions``,
  ``GET /datastores/{id}/endpoints``

A failure on one datastore is recorded as a :class:`DatastoreLoadError` and
does not abort the rest of the load (section 3 requirement). Progress is
reported through ``progress_callback`` at each meaningful step.
"""
from __future__ import annotations

from urllib.parse import quote

from ..core.cache_service import now_iso
from ..core.models import (
    Catalog,
    CatalogItem,
    CONSUMER_PERMISSION,
    DatastoreLoadError,
    ENDPOINT,
    OFFERING,
    PRODUCER_PERMISSION,
)
from .api_client import ApiClient, extract_id
from .progress import CancelCheck, ProgressCallback, ProgressEvent, never_cancelled, noop_progress


def _quote(value: str) -> str:
    return quote(str(value), safe="")


def _list_datastores(client: ApiClient, is_cancelled: CancelCheck) -> dict[str, str]:
    user, _, _ = client.get_json("/users/me", is_cancelled=is_cancelled)
    datastores: dict[str, str] = {}
    for membership in user.get("communities_member", []) if isinstance(user, dict) else []:
        community = membership.get("community") or {}
        datastore_id = extract_id(community.get("datastore"))
        if datastore_id:
            datastores[datastore_id] = str(community.get("name") or community.get("technical_name") or datastore_id)
    return datastores


def _consumer_permissions(client: ApiClient, is_cancelled: CancelCheck) -> list[CatalogItem]:
    items = []
    for permission in client.get_all_pages("/users/me/permissions", is_cancelled=is_cancelled):
        permission_id = extract_id(permission)
        offerings = permission.get("offerings") or []
        names = [str(o.get("layer_name") or o.get("name") or extract_id(o)) for o in offerings]
        label = " + ".join(names) or permission_id
        service_types = sorted({str(o.get("type") or "") for o in offerings if o.get("type")})
        items.append(
            CatalogItem(
                kind=CONSUMER_PERMISSION,
                label=label,
                stats_path=f"/users/me/permissions/{_quote(permission_id)}/stats",
                permission_name=label,
                permission_id=permission_id,
                service_type=", ".join(service_types),
            )
        )
    return items


def _datastore_offerings(
    client: ApiClient,
    datastore_id: str,
    datastore_name: str,
    is_cancelled: CancelCheck,
    progress_callback: ProgressCallback,
) -> tuple[list[CatalogItem], dict[str, str]]:
    basics = client.get_all_pages(f"/datastores/{_quote(datastore_id)}/offerings", is_cancelled=is_cancelled)
    items = []
    offering_names: dict[str, str] = {}
    for index, basic in enumerate(basics, 1):
        offering_id = extract_id(basic)
        try:
            detail, _, _ = client.get_json(
                f"/datastores/{_quote(datastore_id)}/offerings/{_quote(offering_id)}", is_cancelled=is_cancelled
            )
        except Exception:
            detail = basic
        configuration = detail.get("configuration") or {}
        endpoint = detail.get("endpoint") or {}
        label = str(configuration.get("name") or detail.get("layer_name") or offering_id)
        service_type = str(detail.get("type") or "")
        offering_names[offering_id] = label
        items.append(
            CatalogItem(
                kind=OFFERING,
                label=f"{label} · {datastore_name}",
                stats_path=f"/datastores/{_quote(datastore_id)}/offerings/{_quote(offering_id)}/stats",
                datastore_name=datastore_name,
                datastore_id=datastore_id,
                offering_name=label,
                offering_id=offering_id,
                endpoint_name=str(endpoint.get("name") or extract_id(endpoint)),
                endpoint_id=extract_id(endpoint),
                service_type=service_type,
            )
        )
        progress_callback(
            ProgressEvent(
                "offering_detail",
                f"Détail des offerings : {index}/{len(basics)}",
                current=index,
                total=len(basics),
                extra={"datastore_name": datastore_name},
            )
        )
    return items, offering_names


def _datastore_endpoints(
    client: ApiClient, datastore_id: str, datastore_name: str, is_cancelled: CancelCheck
) -> list[CatalogItem]:
    items = []
    for binding in client.get_all_pages(f"/datastores/{_quote(datastore_id)}/endpoints", is_cancelled=is_cancelled):
        # the route returns a datastore/endpoint *binding* ({"use", "quota", "endpoint": {...}}),
        # not the endpoint object itself - the actual name/id/type live one level deeper.
        endpoint = binding.get("endpoint") if isinstance(binding.get("endpoint"), dict) else binding
        endpoint_id = extract_id(endpoint)
        endpoint_name = str(endpoint.get("name") or endpoint.get("technical_name") or endpoint_id)
        try:
            endpoint_use = int(binding.get("use") or 0)
        except (TypeError, ValueError):
            endpoint_use = 0
        try:
            endpoint_quota = int(binding.get("quota") or 0)
        except (TypeError, ValueError):
            endpoint_quota = 0
        items.append(
            CatalogItem(
                kind=ENDPOINT,
                label=f"{endpoint_name} · {datastore_name}",
                stats_path=f"/datastores/{_quote(datastore_id)}/endpoints/{_quote(endpoint_id)}/stats",
                datastore_name=datastore_name,
                datastore_id=datastore_id,
                endpoint_name=endpoint_name,
                endpoint_id=endpoint_id,
                service_type=str(endpoint.get("type") or ""),
                endpoint_use=endpoint_use,
                endpoint_quota=endpoint_quota,
            )
        )
    return items


def _datastore_permissions(
    client: ApiClient,
    datastore_id: str,
    datastore_name: str,
    offering_names: dict[str, str],
    is_cancelled: CancelCheck,
) -> list[CatalogItem]:
    items = []
    for permission in client.get_all_pages(f"/datastores/{_quote(datastore_id)}/permissions", is_cancelled=is_cancelled):
        permission_id = extract_id(permission)
        offering_ids = [extract_id(o) for o in permission.get("offerings") or []]
        label = " + ".join(offering_names.get(i, i) for i in offering_ids) or permission_id
        items.append(
            CatalogItem(
                kind=PRODUCER_PERMISSION,
                label=f"{label} · {datastore_name}",
                stats_path=f"/datastores/{_quote(datastore_id)}/permissions/{_quote(permission_id)}/stats",
                permission_name=label,
                permission_id=permission_id,
                datastore_name=datastore_name,
                datastore_id=datastore_id,
            )
        )
    return items


def build_catalog(
    client: ApiClient,
    progress_callback: ProgressCallback = noop_progress,
    is_cancelled: CancelCheck = never_cancelled,
) -> Catalog:
    items: list[CatalogItem] = []
    errors: list[DatastoreLoadError] = []

    progress_callback(ProgressEvent("connect", "Connexion et récupération de /users/me"))
    datastores = _list_datastores(client, is_cancelled)

    progress_callback(ProgressEvent("consumer_permissions", "Récupération des permissions consommateur"))
    items.extend(_consumer_permissions(client, is_cancelled))

    datastore_list = list(datastores.items())
    for index, (datastore_id, datastore_name) in enumerate(datastore_list, 1):
        if is_cancelled():
            break
        progress_callback(
            ProgressEvent(
                "datastore",
                f"Datastore {index}/{len(datastore_list)} : {datastore_name}",
                current=index,
                total=len(datastore_list),
                extra={"datastore_name": datastore_name},
            )
        )
        def run_stage(stage, func, message):
            """One failing stage (e.g. HTTP 500 on /endpoints) must not discard
            what the other stages of the same datastore already returned."""
            progress_callback(ProgressEvent(stage, message, extra={"datastore_name": datastore_name}))
            try:
                return func()
            except Exception as exc:  # noqa: BLE001 - isolate per-stage failures on purpose
                errors.append(
                    DatastoreLoadError(datastore_id=datastore_id, datastore_name=datastore_name, stage=stage, message=str(exc))
                )
                progress_callback(
                    ProgressEvent(
                        "datastore_error",
                        f"Échec ({stage}) pour le datastore {datastore_name} : {exc}",
                        extra={"datastore_name": datastore_name},
                    )
                )
                return None

        offerings_result = run_stage(
            "offerings",
            lambda: _datastore_offerings(client, datastore_id, datastore_name, is_cancelled, progress_callback),
            f"Offerings : récupération pour {datastore_name}",
        )
        if offerings_result is None:
            continue  # datastore unusable: the other stages would only add noise
        offering_items, offering_names = offerings_result
        items.extend(offering_items)
        endpoint_items = run_stage(
            "endpoints",
            lambda: _datastore_endpoints(client, datastore_id, datastore_name, is_cancelled),
            f"Endpoints : récupération pour {datastore_name}",
        ) or []
        items.extend(endpoint_items)
        permission_items = run_stage(
            "permissions",
            lambda: _datastore_permissions(client, datastore_id, datastore_name, offering_names, is_cancelled),
            f"Permissions producteur : {len(offering_names)} offering(s) référencé(s)",
        ) or []
        items.extend(permission_items)
        progress_callback(
            ProgressEvent(
                "datastore_done",
                f"Datastore {datastore_name} : {len(offering_items)} offering(s), "
                f"{len(endpoint_items)} endpoint(s), {len(permission_items)} permission(s)",
                extra={
                    "datastore_name": datastore_name,
                    "offerings_count": len(offering_items),
                    "endpoints_count": len(endpoint_items),
                    "permissions_count": len(permission_items),
                },
            )
        )

    progress_callback(ProgressEvent("build", "Construction du catalogue…"))
    return Catalog(items=items, errors=errors, loaded_at=now_iso(), from_cache=False)
