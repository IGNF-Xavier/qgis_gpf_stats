"""Generates the synthetic sample XLSX deliverable .

Deliberately distinct from the real ``stats_geoplateforme_6_1.xlsx`` export
: fabricated datastores/offerings/permissions/UUIDs, but the
same shape and the same range of coverage statuses, so the workbook is a
faithful demo of every sheet and chart without touching real usage data.
"""
from __future__ import annotations

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from geoplateforme_usage_stats.core.export_context import build_export_context
from geoplateforme_usage_stats.core.models import (
    CatalogItem,
    CONSUMER_PERMISSION,
    ENDPOINT,
    Group,
    OFFERING,
    PRODUCER_PERMISSION,
    PeriodConfig,
    STATUS_ERROR,
    STATUS_NOT_CONNECTED,
    STATUS_WITH_USAGE,
    STATUS_WITHOUT_USAGE,
    StatsPoint,
    StatsResult,
)
from geoplateforme_usage_stats.exporters import csv_exporter, xlsx_exporter

random.seed(20260922)

DATASTORES = [
    ("ds-" + str(uuid.uuid4()), "IGN_Recette"),
    ("ds-" + str(uuid.uuid4()), "IGN_Prod"),
    ("ds-" + str(uuid.uuid4()), "IGN_Sandbox"),
]
SERVICE_TYPES = ["WMTS-TMS", "WFS", "WMS-VECTOR", "WMS-RASTER"]
PERIOD = PeriodConfig(
    preset="last30",
    requested_start="2026-08-23T00:00:00.000Z",
    requested_end="2026-09-22T00:00:00.000Z",
    duration_days=30,
    details_requested=True,
    fine_requested=False,
    analysis_grain="day",
)


REQUESTED_START = datetime(2026, 8, 23, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _points(base_hits: int, days: int, start_day: int = 0) -> list[StatsPoint]:
    points = []
    for offset in range(start_day, start_day + days):
        day_start = REQUESTED_START + timedelta(days=offset)
        hits = max(0, base_hits + random.randint(-3, 6))
        if hits == 0:
            continue
        points.append(
            StatsPoint(
                period_start=_iso(day_start),
                period_end=_iso(day_start + timedelta(hours=23, minutes=59, seconds=59)),
                hits=hits,
                data_transfer=hits * random.randint(80, 400),
            )
        )
    return points


def build_dataset():
    results: list[StatsResult] = []
    offering_pool: list[CatalogItem] = []

    for ds_id, ds_name in DATASTORES:
        endpoint_ids = [f"ep-{uuid.uuid4()}" for _ in range(2)]
        for endpoint_id in endpoint_ids:
            endpoint_item = CatalogItem(
                kind=ENDPOINT,
                label=f"Diffusion {endpoint_id[:8]} · {ds_name}",
                stats_path=f"/datastores/{ds_id}/endpoints/{endpoint_id}/stats",
                datastore_id=ds_id,
                datastore_name=ds_name,
                endpoint_id=endpoint_id,
                endpoint_name=f"Diffusion {endpoint_id[:8]}",
                service_type=random.choice(SERVICE_TYPES),
            )
            points = _points(random.randint(5, 40), PERIOD.duration_days)
            results.append(
                StatsResult(
                    item=endpoint_item, http_status=200,
                    status=STATUS_WITH_USAGE if points else STATUS_WITHOUT_USAGE,
                    hits=sum(p.hits for p in points), data_transfer=sum(p.data_transfer for p in points),
                    points=points,
                    first_activity=points[0].period_start if points else "",
                    last_activity=points[-1].period_start if points else "",
                )
            )

        for index in range(random.randint(15, 25)):
            offering_id = f"off-{uuid.uuid4()}"
            offering_item = CatalogItem(
                kind=OFFERING,
                label=f"Couche {ds_name}-{index} · {ds_name}",
                stats_path=f"/datastores/{ds_id}/offerings/{offering_id}/stats",
                datastore_id=ds_id,
                datastore_name=ds_name,
                offering_id=offering_id,
                offering_name=f"Couche {ds_name}-{index}",
                endpoint_id=random.choice(endpoint_ids),
                endpoint_name="Diffusion",
                service_type=random.choice(SERVICE_TYPES),
            )
            offering_pool.append(offering_item)

            roll = random.random()
            if roll < 0.08:
                results.append(StatsResult(item=offering_item, http_status=404, status=STATUS_NOT_CONNECTED, message="Non raccordé à Stats"))
            elif roll < 0.12:
                results.append(StatsResult(item=offering_item, http_status=503, status=STATUS_ERROR, message="Service temporairement indisponible (503)"))
            elif roll < 0.45:
                results.append(StatsResult(item=offering_item, http_status=200, status=STATUS_WITHOUT_USAGE, hits=0, data_transfer=0))
            elif roll < 0.55:
                # usage present but the API returned no temporal detail
                results.append(StatsResult(item=offering_item, http_status=200, status=STATUS_WITH_USAGE, hits=random.randint(5, 40), data_transfer=random.randint(500, 5000)))
            else:
                start_day = 0 if roll < 0.75 else random.randint(10, 20)
                days = PERIOD.duration_days if roll < 0.75 else random.randint(3, 10)
                points = _points(random.randint(2, 15), days, start_day)
                results.append(
                    StatsResult(
                        item=offering_item, http_status=200,
                        status=STATUS_WITH_USAGE if points else STATUS_WITHOUT_USAGE,
                        hits=sum(p.hits for p in points), data_transfer=sum(p.data_transfer for p in points),
                        points=points,
                        first_activity=points[0].period_start if points else "",
                        last_activity=points[-1].period_start if points else "",
                    )
                )

        for _ in range(3):
            members = random.sample(offering_pool[-10:], k=min(3, len(offering_pool)))
            permission_item = CatalogItem(
                kind=PRODUCER_PERMISSION,
                label=" + ".join(m.offering_name for m in members) + f" · {ds_name}",
                stats_path=f"/datastores/{ds_id}/permissions/perm-{uuid.uuid4()}/stats",
                datastore_id=ds_id,
                datastore_name=ds_name,
                permission_id=f"perm-{uuid.uuid4()}",
                permission_name=" + ".join(m.offering_name for m in members),
            )
            points = _points(random.randint(1, 10), PERIOD.duration_days)
            results.append(
                StatsResult(
                    item=permission_item, http_status=200,
                    status=STATUS_WITH_USAGE if points else STATUS_WITHOUT_USAGE,
                    hits=sum(p.hits for p in points), data_transfer=sum(p.data_transfer for p in points),
                    points=points,
                    first_activity=points[0].period_start if points else "",
                    last_activity=points[-1].period_start if points else "",
                )
            )

    for _ in range(4):
        offerings = random.sample(offering_pool, k=min(4, len(offering_pool)))
        consumer_item = CatalogItem(
            kind=CONSUMER_PERMISSION,
            label=" + ".join(o.offering_name for o in offerings),
            stats_path=f"/users/me/permissions/perm-{uuid.uuid4()}/stats",
            permission_id=f"perm-{uuid.uuid4()}",
            permission_name=" + ".join(o.offering_name for o in offerings),
            service_type=random.choice(SERVICE_TYPES),
        )
        points = _points(random.randint(1, 6), PERIOD.duration_days)
        results.append(
            StatsResult(
                item=consumer_item, http_status=200,
                status=STATUS_WITH_USAGE if points else STATUS_WITHOUT_USAGE,
                hits=sum(p.hits for p in points), data_transfer=sum(p.data_transfer for p in points),
                points=points,
                first_activity=points[0].period_start if points else "",
                last_activity=points[-1].period_start if points else "",
            )
        )

    groups = [
        Group(
            group_id=str(uuid.uuid4()), name="Diffusion grand public",
            description="Offres WMTS/WMS destinées au portail cartographique.",
            color="#1F4E78",
            offering_ids=[o.offering_id for o in offering_pool if o.service_type in ("WMTS-TMS", "WMS-RASTER")][:12],
            created_at="2026-01-10T09:00:00.000Z", updated_at="2026-08-01T09:00:00.000Z",
        ),
        Group(
            group_id=str(uuid.uuid4()), name="Flux vecteur partenaires",
            description="Offres WFS partagées avec les partenaires institutionnels.",
            color="#93C47D",
            offering_ids=[o.offering_id for o in offering_pool if o.service_type == "WFS"][:10],
            created_at="2026-02-15T09:00:00.000Z", updated_at="2026-08-10T09:00:00.000Z",
        ),
    ]
    # deliberately overlap the two groups on a couple of offerings to demo the warning
    if groups[0].offering_ids and groups[1].offering_ids:
        groups[1].offering_ids.append(groups[0].offering_ids[0])

    return results, groups


def main() -> None:
    results, groups = build_dataset()
    context = build_export_context(results, groups, PERIOD, errors=[])

    out_dir = ROOT / "samples"
    out_dir.mkdir(exist_ok=True)
    xlsx_path = out_dir / "stats_geoplateforme_7_0_synthetic.xlsx"
    xlsx_exporter.export_workbook(str(xlsx_path), context)
    csv_exporter.export_all_csv(str(out_dir), "stats_geoplateforme_7_0_synthetic", context)
    print(f"Généré : {xlsx_path}")
    print(f"Objets interrogés : {len(results)} · Offerings : {len(offering_pool_size(results))}")


def offering_pool_size(results):
    return [r for r in results if r.item.kind == OFFERING]


if __name__ == "__main__":
    main()
