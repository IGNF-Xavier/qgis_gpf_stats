from geoplateforme_usage_stats.core.export_context import build_export_context


def test_summary_rows_keep_business_names_and_uuids(synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    offering_row = next(r for r in context.summary_rows if r["offering_id"] == "off-1")
    assert offering_row["offering_name"] == "Offre off-1"
    assert offering_row["datastore_id"] == "ds1"
    assert offering_row["datastore_name"] == "IGN_Recette"


def test_no_temporal_detail_offering_flagged_in_coverage(synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    off3 = next(r for r in context.coverage_rows if r["offering_id"] == "off-3")
    assert off3["coverage_status"] == "no_usage"


def test_not_connected_consumer_permission(synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    row = next(r for r in context.summary_rows if r["kind"] == "consumer_permission")
    assert row["status"] == "not_connected"
    assert row["coverage_status"] == "not_connected"


def test_group_series_rows_present_for_group(synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    assert context.series_groupes_rows
    row = context.series_groupes_rows[0]
    assert row["group_id"] == "g1"
    assert row["group_name"] == "Groupe diffusion"


def test_composition_rows_reference_offering_names(synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    names = {r["offering_id"]: r["offering_name"] for r in context.composition_rows}
    assert names["off-1"] == "Offre off-1"


def test_kpis_isolated_by_level(synthetic_dataset):
    results, groups, period = synthetic_dataset
    context = build_export_context(results, groups, period, errors=[])
    assert context.kpis_by_level["offering"].hits_total == 18  # off-1 (15) + off-2 (3), not endpoint/permission
    assert context.kpis_by_level["endpoint"].hits_total == 13
    assert context.kpis_by_level["producer_permission"].hits_total == 13
