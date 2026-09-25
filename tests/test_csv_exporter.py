import csv

from geoplateforme_usage_stats.core.export_context import build_export_context
from geoplateforme_usage_stats.exporters import csv_exporter


def test_export_all_csv_writes_named_files(tmp_path, synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    written = csv_exporter.export_all_csv(str(tmp_path), "stats", context)
    names = {p.split("stats_")[-1] for p in written}
    assert "synthese.csv" in names
    assert "series_api.csv" in names
    assert "series_groupes.csv" in names
    assert "composition_groupes.csv" in names


def test_csv_content_has_uuid_and_business_name_columns(tmp_path, synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    path = tmp_path / "synthese.csv"
    csv_exporter.write_csv(str(path), context.summary_rows)

    with open(path, encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter=";"))
    assert any(row["offering_id"] == "off-1" and row["offering_name"] == "Offre off-1" for row in rows)


def test_csv_export_skipped_when_no_rows(tmp_path, synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context([], [], period, errors=[])
    written = csv_exporter.export_all_csv(str(tmp_path), "empty", context)
    assert written == []
