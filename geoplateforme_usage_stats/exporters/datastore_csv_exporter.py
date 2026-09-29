"""CSV export dedicated to the « Datastores » tab: storage usage and
endpoints for every datastore whose detail has actually been fetched there -
independent of any stats query, period or the main CSV/XLSX exports (section
7), which cover query results and have nothing to do with this tab.
"""
from __future__ import annotations

from pathlib import Path

from ..core.models import DatastoreInfo
from .csv_exporter import write_csv


def _storage_rows(infos: list[DatastoreInfo]) -> list[dict]:
    rows = []
    for info in infos:
        rows.append({
            "datastore_id": info.datastore_id,
            "datastore_name": info.name,
            "datastore_technical_name": info.technical_name,
            "actif": info.active,
            "role": "total",
            "nom_stockage": "",
            "type_stockage": "",
            "utilise_octets": info.total_use_bytes(),
            "quota_octets": info.total_quota_bytes(),
        })
        for storage in info.data_storages:
            rows.append({
                "datastore_id": info.datastore_id,
                "datastore_name": info.name,
                "datastore_technical_name": info.technical_name,
                "actif": info.active,
                "role": "donnees",
                "nom_stockage": storage.name,
                "type_stockage": storage.type,
                "utilise_octets": storage.use_bytes,
                "quota_octets": storage.quota_bytes,
            })
        for role, storage in (("depots_uploads", info.uploads_storage), ("annexes", info.annexes_storage)):
            if storage is not None:
                rows.append({
                    "datastore_id": info.datastore_id,
                    "datastore_name": info.name,
                    "datastore_technical_name": info.technical_name,
                    "actif": info.active,
                    "role": role,
                    "nom_stockage": storage.name,
                    "type_stockage": storage.type,
                    "utilise_octets": storage.use_bytes,
                    "quota_octets": storage.quota_bytes,
                })
    return rows


def _endpoint_rows(infos: list[DatastoreInfo]) -> list[dict]:
    rows = []
    for info in infos:
        for endpoint in info.endpoints:
            rows.append({
                "datastore_id": info.datastore_id,
                "datastore_name": info.name,
                "datastore_technical_name": info.technical_name,
                "endpoint_name": endpoint.name,
                "endpoint_technical_name": endpoint.technical_name,
                "type": endpoint.type,
                "ouvert": endpoint.open,
                "offres_raccordees": endpoint.use,
                "quota_offres": endpoint.quota,
                "urls": " | ".join(endpoint.urls),
            })
    return rows


def export_datastore_info_csv(directory: str, base_name: str, infos: list[DatastoreInfo]) -> list[str]:
    """Writes one file for storage usage and one for endpoints - only the
    non-empty ones - covering every datastore in ``infos`` (the caller
    decides which datastores that is; typically every one whose detail is
    currently loaded in the tab)."""
    written = []
    storage_rows = _storage_rows(infos)
    if storage_rows:
        target = Path(directory) / f"{base_name}_stockage.csv"
        write_csv(str(target), storage_rows)
        written.append(str(target))
    endpoint_rows = _endpoint_rows(infos)
    if endpoint_rows:
        target = Path(directory) / f"{base_name}_endpoints.csv"
        write_csv(str(target), endpoint_rows)
        written.append(str(target))
    return written
