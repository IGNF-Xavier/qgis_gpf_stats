"""Period presets, ISO formatting and fine-step eligibility rules.

Pure Python / ``datetime`` only: no Qt dependency, so it is unit-testable
without QGIS installed. The UI layer converts ``QDateTime`` <-> ``datetime``
at its boundary and calls into this module for every rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .models import PeriodConfig

PRESETS = (
    ("last7", "7 derniers jours"),
    ("last30", "30 derniers jours"),
    ("current_month", "Mois en cours"),
    ("previous_month", "Mois précédent"),
    ("current_year", "Année en cours"),
    ("last12months", "12 derniers mois"),
    ("custom", "Période personnalisée"),
)

GRAIN_CHOICES = (
    ("auto", "Automatique"),
    ("raw", "Brut API"),
    ("day", "Jour"),
    ("week", "Semaine"),
    ("month", "Mois"),
)

FINE_STEP_MAX_DAYS = 30
ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.strftime(ISO_FORMAT)[:-3] + "Z"


def parse_iso(value: str) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    for candidate in (text, text.split(".")[0] + "+00:00" if "." in text else text):
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def compute_preset_range(preset: str, now: datetime) -> tuple[datetime, datetime]:
    """Return (start, end) for every preset except ``custom``."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.date()
    if preset == "last7":
        return now - timedelta(days=7), now
    if preset == "last30":
        return now - timedelta(days=30), now
    if preset == "current_month":
        start = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
        return start, now
    if preset == "previous_month":
        first_of_this_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
        last_of_previous = first_of_this_month - timedelta(seconds=1)
        first_of_previous = datetime(last_of_previous.year, last_of_previous.month, 1, tzinfo=timezone.utc)
        return first_of_previous, last_of_previous
    if preset == "current_year":
        return datetime(today.year, 1, 1, tzinfo=timezone.utc), now
    if preset == "last12months":
        return now - timedelta(days=365), now
    raise ValueError(f"Préréglage inconnu ou personnalisé : {preset}")


def duration_days(start: datetime, end: datetime) -> int:
    return max(0, int((end - start).total_seconds() // 86400))


def fine_step_allowed(duration: int, max_days: int = FINE_STEP_MAX_DAYS) -> bool:
    return 0 <= duration <= max_days


def resolve_grain(grain_choice: str, duration: int) -> str:
    if grain_choice != "auto":
        return grain_choice
    return "day" if duration <= 31 else "month"


@dataclass
class PeriodValidationError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def build_period_config(
    preset: str,
    start: datetime,
    end: datetime,
    details_requested: bool,
    fine_requested: bool,
    grain_choice: str,
) -> PeriodConfig:
    if start >= end:
        raise PeriodValidationError("La date de début doit précéder la date de fin.")
    duration = duration_days(start, end)
    if fine_requested and not fine_step_allowed(duration):
        raise PeriodValidationError(
            f"Le pas fin de cinq minutes est réservé aux périodes de {FINE_STEP_MAX_DAYS} jours au plus."
        )
    return PeriodConfig(
        preset=preset,
        requested_start=iso(start),
        requested_end=iso(end),
        duration_days=duration,
        details_requested=bool(details_requested),
        fine_requested=bool(fine_requested),
        analysis_grain=resolve_grain(grain_choice, duration),
    )
