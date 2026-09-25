"""Fetch usage statistics for catalog items (Stats routes, section 1/10).

One item's failure never aborts the batch: a 404 becomes ``not_connected``
and any other failure becomes ``error`` on that item's :class:`StatsResult`,
while the rest of the selection keeps being processed.
"""
from __future__ import annotations

from typing import Iterable

from ..core.models import CatalogItem, STATUS_ERROR, STATUS_NOT_CONNECTED, STATUS_WITH_USAGE, STATUS_WITHOUT_USAGE, StatsPoint, StatsResult
from .api_client import ApiClient, ApiError
from .progress import CancelCheck, ProgressCallback, ProgressEvent, never_cancelled, noop_progress

PAGE_SIZE = 50
MAX_PAGES = 1000


def fetch_stats(
    client: ApiClient,
    item: CatalogItem,
    requested_start: str,
    requested_end: str,
    details_requested: bool,
    is_cancelled: CancelCheck = never_cancelled,
) -> StatsResult:
    points: list[StatsPoint] = []
    total: dict = {}
    try:
        for page in range(1, MAX_PAGES + 1):
            data, _, http_status = client.get_json(
                item.stats_path,
                (
                    ("start", requested_start),
                    ("end", requested_end),
                    ("details", "true" if details_requested else "false"),
                    ("page", str(page)),
                    ("limit", str(PAGE_SIZE)),
                ),
                is_cancelled=is_cancelled,
            )
            if page == 1:
                total = data.get("total") or {} if isinstance(data, dict) else {}
            current_details = data.get("details") or [] if isinstance(data, dict) else []
            points.extend(
                StatsPoint(
                    period_start=str(row.get("begin_date") or ""),
                    period_end=str(row.get("end_date") or ""),
                    hits=int(row.get("hits") or 0),
                    data_transfer=int(row.get("data_transfer") or 0),
                )
                for row in current_details
            )
            if not details_requested or len(current_details) < PAGE_SIZE:
                hits = int(total.get("hits") or 0)
                data_transfer = int(total.get("data_transfer") or 0)
                return StatsResult(
                    item=item,
                    http_status=http_status,
                    status=STATUS_WITH_USAGE if (hits or data_transfer) else STATUS_WITHOUT_USAGE,
                    hits=hits,
                    data_transfer=data_transfer,
                    points=points,
                    first_activity=str(total.get("begin_date") or ""),
                    last_activity=str(total.get("end_date") or ""),
                )
    except ApiError as exc:
        status = STATUS_NOT_CONNECTED if exc.status == 404 else STATUS_ERROR
        return StatsResult(item=item, http_status=exc.status, status=status, message=exc.message)
    return StatsResult(item=item, http_status=None, status=STATUS_ERROR, message="Pagination interrompue sans réponse finale.")


def fetch_many(
    client: ApiClient,
    items: Iterable[CatalogItem],
    requested_start: str,
    requested_end: str,
    details_requested: bool,
    progress_callback: ProgressCallback = noop_progress,
    is_cancelled: CancelCheck = never_cancelled,
) -> list[StatsResult]:
    items = list(items)
    results = []
    for index, item in enumerate(items, 1):
        if is_cancelled():
            break
        progress_callback(
            ProgressEvent("stats_item", f"{index}/{len(items)} · {item.label}", current=index, total=len(items))
        )
        results.append(fetch_stats(client, item, requested_start, requested_end, details_requested, is_cancelled))
    return results
