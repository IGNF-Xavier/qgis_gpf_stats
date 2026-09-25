"""Core data models shared by every layer of the plugin.

This module has no dependency on Qt or QGIS so it can be imported and
unit-tested with a plain Python interpreter.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

CONSUMER_PERMISSION = "consumer_permission"
PRODUCER_PERMISSION = "producer_permission"
OFFERING = "offering"
ENDPOINT = "endpoint"
USER_GROUP = "user_group"

CATALOG_KINDS = (CONSUMER_PERMISSION, PRODUCER_PERMISSION, OFFERING, ENDPOINT)

STATUS_WITH_USAGE = "with_usage"
STATUS_WITHOUT_USAGE = "without_usage"
STATUS_NOT_CONNECTED = "not_connected"
STATUS_ERROR = "error"

COVERAGE_COMPLETE = "complete_coverage"
COVERAGE_PARTIAL = "partial_coverage"
COVERAGE_NO_TEMPORAL_DETAIL = "no_temporal_detail"
COVERAGE_NO_USAGE = "no_usage"
COVERAGE_NOT_CONNECTED = "not_connected"
COVERAGE_ERROR = "error"


@dataclass(frozen=True)
class CatalogItem:
    """One queryable statistics object (consumer permission, producer
    permission, offering or endpoint) as exposed by the Entrepot API.

    ``kind`` is one of the ``CATALOG_KINDS`` constants and is what the rest
    of the application uses to decide how an item may be aggregated
    (``series_level``); ``scope`` ("consumer"/"producer") is derived from it.
    """

    kind: str
    label: str
    stats_path: str
    permission_name: str = ""
    permission_id: str = ""
    datastore_name: str = ""
    datastore_id: str = ""
    offering_name: str = ""
    offering_id: str = ""
    endpoint_name: str = ""
    endpoint_id: str = ""
    service_type: str = ""
    endpoint_use: int = 0
    endpoint_quota: int = 0

    @property
    def scope(self) -> str:
        return "consumer" if self.kind == CONSUMER_PERMISSION else "producer"

    @property
    def item_id(self) -> str:
        """Stable identity used for de-duplication and group membership."""
        if self.kind == OFFERING:
            return self.offering_id
        if self.kind == ENDPOINT:
            return f"{self.datastore_id}:{self.endpoint_id}"
        if self.kind == PRODUCER_PERMISSION:
            return f"{self.datastore_id}:{self.permission_id}"
        return self.permission_id

    def as_dict(self) -> dict:
        data = asdict(self)
        data["scope"] = self.scope
        data["item_id"] = self.item_id
        return data


@dataclass
class DatastoreLoadError:
    datastore_id: str
    datastore_name: str
    stage: str
    message: str


@dataclass
class Catalog:
    """Full producer + consumer catalog, plus any partial-load errors."""

    items: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    loaded_at: Optional[str] = None
    from_cache: bool = False

    def offerings(self) -> list:
        return [item for item in self.items if item.kind == OFFERING]

    def by_scope(self, scope: str) -> list:
        return [item for item in self.items if item.scope == scope]


@dataclass
class PeriodConfig:
    preset: str
    requested_start: str
    requested_end: str
    duration_days: int
    details_requested: bool
    fine_requested: bool
    analysis_grain: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class StatsPoint:
    period_start: str
    period_end: str
    hits: int
    data_transfer: int


@dataclass
class StatsResult:
    item: CatalogItem
    http_status: Optional[int]
    status: str
    hits: int = 0
    data_transfer: int = 0
    points: list = field(default_factory=list)
    first_activity: str = ""
    last_activity: str = ""
    message: str = ""


@dataclass
class CoverageAssessment:
    coverage_status: str
    coverage_interpretation: str
    requested_period_start: str
    requested_period_end: str
    first_activity: str = ""
    last_activity: str = ""
    active_days_count: Optional[int] = None
    temporal_points_count: int = 0
    coverage_ratio: Optional[float] = None


@dataclass
class Group:
    group_id: str
    name: str
    description: str = ""
    color: str = ""
    offering_ids: list = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def as_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Group":
        return Group(
            group_id=str(data.get("group_id") or data.get("id") or ""),
            name=str(data.get("name") or ""),
            description=str(data.get("description") or ""),
            color=str(data.get("color") or ""),
            offering_ids=list(data.get("offering_ids") or []),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


@dataclass
class SeriesRow:
    """One aggregated (offering/endpoint/group/...) x (period bucket) row."""

    series_level: str
    series_key: str
    label: str
    period_key: str
    analysis_grain: str
    hits: int
    data_transfer: int
    contributor_count: int = 1
    incomplete: bool = False
    datastore_name: str = ""
    datastore_id: str = ""
    service_type: str = ""
