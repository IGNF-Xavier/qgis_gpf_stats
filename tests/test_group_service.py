import itertools

import pytest

from geoplateforme_usage_stats.core.group_service import (
    GroupService,
    InMemoryGroupStore,
    migrate_from_v61,
    overlapping_pairs,
)


def make_service():
    counter = itertools.count(1)
    return GroupService(InMemoryGroupStore(), id_factory=lambda: f"id-{next(counter)}", clock=lambda: "2026-09-22T00:00:00.000Z")


def test_create_group():
    service = make_service()
    groups = service.create([], "Diffusion WMTS")
    assert len(groups) == 1
    assert groups[0].name == "Diffusion WMTS"
    assert groups[0].offering_ids == []


def test_create_rejects_duplicate_name():
    service = make_service()
    groups = service.create([], "A")
    with pytest.raises(ValueError):
        service.create(groups, "a")


def test_create_rejects_empty_name():
    service = make_service()
    with pytest.raises(ValueError):
        service.create([], "   ")


def test_set_offering_ids_assigns_offers():
    service = make_service()
    groups = service.create([], "A")
    group_id = groups[0].group_id
    groups = service.set_offering_ids(groups, group_id, ["off-1", "off-2", "off-1"])
    assert service.find(groups, group_id).offering_ids == ["off-1", "off-2"]


def test_empty_group_has_no_offerings():
    service = make_service()
    groups = service.create([], "Vide")
    assert service.find(groups, groups[0].group_id).offering_ids == []


def test_persistence_round_trip():
    service = make_service()
    groups = service.create([], "A")
    groups = service.set_offering_ids(groups, groups[0].group_id, ["off-1"])
    service.save(groups)
    reloaded = service.load()
    assert len(reloaded) == 1
    assert reloaded[0].name == "A"
    assert reloaded[0].offering_ids == ["off-1"]


def test_rename_and_delete():
    service = make_service()
    groups = service.create([], "A")
    group_id = groups[0].group_id
    groups = service.rename(groups, group_id, "B")
    assert service.find(groups, group_id).name == "B"
    groups = service.delete(groups, group_id)
    assert service.find(groups, group_id) is None


def test_duplicate_group():
    service = make_service()
    groups = service.create([], "A")
    groups = service.set_offering_ids(groups, groups[0].group_id, ["off-1"])
    groups = service.duplicate(groups, groups[0].group_id)
    assert len(groups) == 2
    assert groups[1].name == "A (copie)"
    assert groups[1].offering_ids == ["off-1"]


def test_migration_from_v61_dict():
    legacy_json = '{"Groupe WMTS": ["off-1", "off-2"], "Vide": []}'
    groups = migrate_from_v61(legacy_json, id_factory=lambda: "g1", clock=lambda: "now")
    names = {g.name: g.offering_ids for g in groups}
    assert names["Groupe WMTS"] == ["off-1", "off-2"]
    assert names["Vide"] == []


def test_service_loads_and_migrates_legacy_store():
    store = InMemoryGroupStore()
    store.set_raw("geoplateforme_usage_stats/groups_61", '{"Legacy": ["off-9"]}')
    service = GroupService(store, id_factory=lambda: "migrated-1", clock=lambda: "now")
    groups = service.load()
    assert len(groups) == 1
    assert groups[0].name == "Legacy"
    assert groups[0].offering_ids == ["off-9"]
    # migration is persisted under the v7 key so it only happens once
    assert store.get_raw("geoplateforme_usage_stats/groups_v7")


def test_overlapping_pairs_detected():
    service = make_service()
    groups = service.create([], "A")
    groups = service.create(groups, "B")
    groups = service.set_offering_ids(groups, groups[0].group_id, ["off-1", "off-2"])
    groups = service.set_offering_ids(groups, groups[1].group_id, ["off-2", "off-3"])
    pairs = overlapping_pairs(groups)
    assert len(pairs) == 1
    assert pairs[0][2] == {"off-2"}


def test_group_spanning_multiple_datastores_keeps_all_ids():
    service = make_service()
    groups = service.create([], "Multi-datastore")
    groups = service.set_offering_ids(groups, groups[0].group_id, ["ds1:off-1", "ds2:off-9"])
    assert service.find(groups, groups[0].group_id).offering_ids == ["ds1:off-1", "ds2:off-9"]
