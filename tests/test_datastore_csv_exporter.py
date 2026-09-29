import csv

from geoplateforme_usage_stats.core.models import DatastoreEndpointInfo, DatastoreInfo, StorageUsage
from geoplateforme_usage_stats.exporters import datastore_csv_exporter


def _sample_info() -> DatastoreInfo:
    return DatastoreInfo(
        datastore_id="ds-1",
        name="Recette cartes.gouv",
        technical_name="recette-cartes-gouv",
        active=True,
        data_storages=[StorageUsage(name="PG", type="POSTGRESQL", use_bytes=100, quota_bytes=1000)],
        uploads_storage=StorageUsage(name="NAS", type="FILESYSTEM", use_bytes=50, quota_bytes=1000),
        annexes_storage=StorageUsage(name="Annexes", type="S3", use_bytes=10, quota_bytes=1000),
        endpoints=[
            DatastoreEndpointInfo(
                name="WFS principal", technical_name="gpf-geoserver-wfs", type="WFS",
                open=True, use=4, quota=10, urls=("https://data.geopf.fr/wfs",),
            ),
        ],
    )


def test_export_writes_both_files(tmp_path):
    written = datastore_csv_exporter.export_datastore_info_csv(str(tmp_path), "stats", [_sample_info()])
    names = {p.split("stats_")[-1] for p in written}
    assert names == {"stockage.csv", "endpoints.csv"}


def test_storage_csv_has_total_and_per_storage_rows(tmp_path):
    datastore_csv_exporter.export_datastore_info_csv(str(tmp_path), "stats", [_sample_info()])
    with open(tmp_path / "stats_stockage.csv", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    roles = {row["role"] for row in rows}
    assert roles == {"total", "donnees", "depots_uploads", "annexes"}
    total_row = next(row for row in rows if row["role"] == "total")
    assert total_row["utilise_octets"] == "160"
    assert total_row["datastore_name"] == "Recette cartes.gouv"


def test_endpoints_csv_content(tmp_path):
    datastore_csv_exporter.export_datastore_info_csv(str(tmp_path), "stats", [_sample_info()])
    with open(tmp_path / "stats_endpoints.csv", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    assert len(rows) == 1
    assert rows[0]["endpoint_name"] == "WFS principal"
    assert rows[0]["urls"] == "https://data.geopf.fr/wfs"


def test_export_skipped_when_no_infos(tmp_path):
    written = datastore_csv_exporter.export_datastore_info_csv(str(tmp_path), "stats", [])
    assert written == []
