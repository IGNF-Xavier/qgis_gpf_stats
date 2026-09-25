"""User-defined offering groups: CRUD, persistence and 6.1.0 migration.

Persistence is abstracted behind :class:`GroupStore` so this module can be
unit-tested without QGIS. The real runtime plugs in a ``QgsSettings``-backed
store (see ``ui/settings_store.py``).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable, Iterable, Optional, Protocol

from .models import Group

SETTINGS_KEY_V7 = "geoplateforme_usage_stats/groups_v7"
SETTINGS_KEY_V61 = "geoplateforme_usage_stats/groups_61"


class GroupStore(Protocol):
    def get_raw(self, key: str) -> str: ...
    def set_raw(self, key: str, value: str) -> None: ...


class InMemoryGroupStore:
    """Simple dict-backed store, used by tests and as a safe default."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def get_raw(self, key: str) -> str:
        return self._data.get(key, "")

    def set_raw(self, key: str, value: str) -> None:
        self._data[key] = value


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class GroupService:
    def __init__(
        self,
        store: GroupStore,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        clock: Callable[[], str] = _now_iso,
    ) -> None:
        self._store = store
        self._id_factory = id_factory
        self._clock = clock

    # -- persistence ---------------------------------------------------
    def load(self) -> list[Group]:
        raw = self._store.get_raw(SETTINGS_KEY_V7)
        if not raw:
            legacy = self._store.get_raw(SETTINGS_KEY_V61)
            if legacy:
                groups = migrate_from_v61(legacy, self._id_factory, self._clock)
                self.save(groups)
                return groups
            return []
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError):
            return []
        return [Group.from_dict(item) for item in payload]

    def save(self, groups: Iterable[Group]) -> None:
        payload = [group.as_dict() for group in groups]
        self._store.set_raw(SETTINGS_KEY_V7, json.dumps(payload, ensure_ascii=False))

    # -- CRUD ------------------------------------------------------------
    def create(self, groups: list[Group], name: str, description: str = "", color: str = "") -> list[Group]:
        name = name.strip()
        if not name:
            raise ValueError("Le nom du groupe ne peut pas être vide.")
        if any(group.name.casefold() == name.casefold() for group in groups):
            raise ValueError(f"Un groupe nommé « {name} » existe déjà.")
        now = self._clock()
        new_group = Group(
            group_id=self._id_factory(),
            name=name,
            description=description,
            color=color,
            offering_ids=[],
            created_at=now,
            updated_at=now,
        )
        return [*groups, new_group]

    def rename(self, groups: list[Group], group_id: str, new_name: str) -> list[Group]:
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Le nom du groupe ne peut pas être vide.")
        if any(g.name.casefold() == new_name.casefold() and g.group_id != group_id for g in groups):
            raise ValueError(f"Un groupe nommé « {new_name} » existe déjà.")
        return [
            replace(g, name=new_name, updated_at=self._clock()) if g.group_id == group_id else g
            for g in groups
        ]

    def delete(self, groups: list[Group], group_id: str) -> list[Group]:
        return [g for g in groups if g.group_id != group_id]

    def duplicate(self, groups: list[Group], group_id: str) -> list[Group]:
        source = next((g for g in groups if g.group_id == group_id), None)
        if source is None:
            return groups
        base_name = f"{source.name} (copie)"
        name = base_name
        suffix = 2
        existing = {g.name.casefold() for g in groups}
        while name.casefold() in existing:
            name = f"{base_name} {suffix}"
            suffix += 1
        now = self._clock()
        clone = Group(
            group_id=self._id_factory(),
            name=name,
            description=source.description,
            color=source.color,
            offering_ids=list(source.offering_ids),
            created_at=now,
            updated_at=now,
        )
        return [*groups, clone]

    def set_offering_ids(self, groups: list[Group], group_id: str, offering_ids: Iterable[str]) -> list[Group]:
        ids = sorted(set(offering_ids))
        return [
            replace(g, offering_ids=ids, updated_at=self._clock()) if g.group_id == group_id else g
            for g in groups
        ]

    def find(self, groups: list[Group], group_id: str) -> Optional[Group]:
        return next((g for g in groups if g.group_id == group_id), None)


def migrate_from_v61(raw_json: str, id_factory: Callable[[], str], clock: Callable[[], str]) -> list[Group]:
    """Convert the 6.1.0 ``{name: [offering_id, ...]}`` mapping."""
    try:
        legacy = json.loads(raw_json)
    except (ValueError, TypeError):
        return []
    if not isinstance(legacy, dict):
        return []
    now = clock()
    groups: list[Group] = []
    for name, offering_ids in legacy.items():
        if not isinstance(offering_ids, list):
            continue
        groups.append(
            Group(
                group_id=id_factory(),
                name=str(name),
                description="Groupe migré depuis la version 6.1.0.",
                color="",
                offering_ids=sorted({str(i) for i in offering_ids}),
                created_at=now,
                updated_at=now,
            )
        )
    return groups


def overlapping_pairs(groups: Iterable[Group]) -> list[tuple[Group, Group, set[str]]]:
    """Pairs of groups sharing at least one offering, for the UI warning."""
    groups = list(groups)
    pairs = []
    for i, first in enumerate(groups):
        for second in groups[i + 1 :]:
            common = set(first.offering_ids) & set(second.offering_ids)
            if common:
                pairs.append((first, second, common))
    return pairs
