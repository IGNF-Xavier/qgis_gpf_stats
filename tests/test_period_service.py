from datetime import datetime, timezone

import pytest

from geoplateforme_usage_stats.core import period_service as ps


def test_iso_round_trip():
    dt = datetime(2026, 8, 23, 10, 45, 46, 79000, tzinfo=timezone.utc)
    text = ps.iso(dt)
    assert text == "2026-08-23T10:45:46.079Z"
    assert ps.parse_iso(text) == dt


def test_last30_preset():
    now = datetime(2026, 9, 22, 10, 45, 46, tzinfo=timezone.utc)
    start, end = ps.compute_preset_range("last30", now)
    assert end == now
    assert (end - start).days == 30


def test_previous_month_preset():
    now = datetime(2026, 9, 15, tzinfo=timezone.utc)
    start, end = ps.compute_preset_range("previous_month", now)
    assert start.month == 8 and start.day == 1
    assert end.month == 8 and end.day == 31


def test_fine_step_allowed_boundaries():
    assert ps.fine_step_allowed(30) is True
    assert ps.fine_step_allowed(31) is False
    assert ps.fine_step_allowed(0) is True


def test_resolve_grain_auto():
    assert ps.resolve_grain("auto", 10) == "day"
    assert ps.resolve_grain("auto", 90) == "month"
    assert ps.resolve_grain("week", 90) == "week"


def test_build_period_config_rejects_fine_step_over_limit():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, tzinfo=timezone.utc)
    with pytest.raises(ps.PeriodValidationError):
        ps.build_period_config("custom", start, end, True, True, "auto")


def test_build_period_config_rejects_inverted_range():
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ps.PeriodValidationError):
        ps.build_period_config("custom", start, end, True, False, "auto")


def test_build_period_config_happy_path():
    start = datetime(2026, 8, 23, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)
    config = ps.build_period_config("last30", start, end, True, False, "auto")
    assert config.duration_days == 30
    assert config.analysis_grain == "day"
    assert config.requested_start.endswith("Z")
