"""Temporal coverage classification (section 4 of the specification).

Deliberately keeps three things apart instead of collapsing them into a
single ``api_end - api_begin`` ratio:

1. whether the query itself succeeded for the requested window
   (``result.status`` / ``result.http_status``);
2. the *observed activity range* returned by the API
   (``first_activity`` / ``last_activity`` - these are activity bounds,
   not a technical "coverage window");
3. whether there was any usage at all.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import (
    CoverageAssessment,
    PeriodConfig,
    StatsResult,
    STATUS_ERROR,
    STATUS_NOT_CONNECTED,
    COVERAGE_COMPLETE,
    COVERAGE_ERROR,
    COVERAGE_NOT_CONNECTED,
    COVERAGE_NO_TEMPORAL_DETAIL,
    COVERAGE_NO_USAGE,
    COVERAGE_PARTIAL,
)
from .period_service import parse_iso


def period_bucket(value_iso: str, grain: str) -> str:
    parsed = parse_iso(value_iso)
    if parsed is None:
        return ""
    if grain == "day":
        return parsed.date().isoformat()
    if grain == "week":
        year, week, _ = parsed.isocalendar()
        return f"{year}-S{week:02d}"
    if grain == "month":
        return f"{parsed.year:04d}-{parsed.month:02d}"
    return value_iso


def _active_days_count(points) -> Optional[int]:
    if not points:
        return None
    days = set()
    for point in points:
        if point.hits or point.data_transfer:
            key = period_bucket(point.period_start, "day")
            if key:
                days.add(key)
    return len(days)


def assess_coverage(result: StatsResult, period: PeriodConfig) -> CoverageAssessment:
    requested_start = period.requested_start
    requested_end = period.requested_end

    if result.status == STATUS_NOT_CONNECTED:
        return CoverageAssessment(
            coverage_status=COVERAGE_NOT_CONNECTED,
            coverage_interpretation="Cet objet n'est pas raccordé à la route Stats (réponse HTTP 404).",
            requested_period_start=requested_start,
            requested_period_end=requested_end,
        )
    if result.status == STATUS_ERROR:
        return CoverageAssessment(
            coverage_status=COVERAGE_ERROR,
            coverage_interpretation=f"L'appel a échoué : {result.message or 'erreur inconnue'}.",
            requested_period_start=requested_start,
            requested_period_end=requested_end,
        )
    if not result.hits and not result.data_transfer:
        return CoverageAssessment(
            coverage_status=COVERAGE_NO_USAGE,
            coverage_interpretation="Aucun usage n'a été enregistré sur la période demandée.",
            requested_period_start=requested_start,
            requested_period_end=requested_end,
            first_activity=result.first_activity,
            last_activity=result.last_activity,
            active_days_count=0 if period.details_requested else None,
            temporal_points_count=len(result.points),
        )
    if period.details_requested and not result.points:
        return CoverageAssessment(
            coverage_status=COVERAGE_NO_TEMPORAL_DETAIL,
            coverage_interpretation=(
                "Le détail temporel a été demandé mais l'API n'a renvoyé aucun point : "
                "seul le total sur la période est exploitable."
            ),
            requested_period_start=requested_start,
            requested_period_end=requested_end,
            first_activity=result.first_activity,
            last_activity=result.last_activity,
            temporal_points_count=0,
        )

    active_days = _active_days_count(result.points)
    requested_start_dt = parse_iso(requested_start)
    requested_end_dt = parse_iso(requested_end)
    first_dt = parse_iso(result.first_activity)
    last_dt = parse_iso(result.last_activity)

    coverage_ratio = None
    coverage_status = COVERAGE_PARTIAL
    if first_dt and last_dt and requested_start_dt and requested_end_dt:
        requested_seconds = max(1.0, (requested_end_dt - requested_start_dt).total_seconds())
        observed_seconds = max(0.0, (last_dt - first_dt).total_seconds())
        coverage_ratio = min(1.0, observed_seconds / requested_seconds)
        tolerance = timedelta(seconds=min(86400.0, requested_seconds * 0.05))
        complete = (
            first_dt <= requested_start_dt + tolerance
            and last_dt >= requested_end_dt - tolerance
        )
        coverage_status = COVERAGE_COMPLETE if complete else COVERAGE_PARTIAL
    else:
        coverage_status = COVERAGE_NO_TEMPORAL_DETAIL

    interpretation = (
        f"Activité observée du {result.first_activity or '?'} au {result.last_activity or '?'}"
        f"{f', soit {active_days} jour(s) actif(s)' if active_days is not None else ''} "
        f"sur une période demandée de {period.duration_days} jour(s). "
        "Cette valeur reflète l'activité réelle constatée, pas une limite technique de l'API."
    )
    return CoverageAssessment(
        coverage_status=coverage_status,
        coverage_interpretation=interpretation,
        requested_period_start=requested_start,
        requested_period_end=requested_end,
        first_activity=result.first_activity,
        last_activity=result.last_activity,
        active_days_count=active_days,
        temporal_points_count=len(result.points),
        coverage_ratio=coverage_ratio,
    )
