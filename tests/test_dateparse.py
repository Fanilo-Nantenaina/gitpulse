from __future__ import annotations

from datetime import timedelta

import pytest

from gitpulse.core.dateparse import parse_interval, parse_range


def test_parse_range_days() -> None:
    r = parse_range("7d")
    span = r.until - r.since
    assert 6 <= span.days <= 7


def test_parse_range_hours() -> None:
    r = parse_range("24h")
    span = r.until - r.since
    assert timedelta(hours=23) <= span <= timedelta(hours=25)


def test_parse_range_today_has_label() -> None:
    r = parse_range("today")
    assert r.label
    assert r.since <= r.until


def test_parse_range_yesterday() -> None:
    r = parse_range("yesterday")
    assert r.since < r.until


def test_parse_interval_returns_timedelta() -> None:
    d = parse_interval("7d")
    assert isinstance(d, timedelta)
    assert d.days == 7


def test_parse_interval_weeks_or_days() -> None:
    d = parse_interval("30d")
    assert d.days == 30


@pytest.mark.parametrize("expr", ["7d", "24h", "today", "yesterday"])
def test_common_windows_do_not_raise(expr: str) -> None:
    r = parse_range(expr)
    assert r.since is not None and r.until is not None


def test_all_time_range() -> None:
    from gitpulse.core.dateparse import parse_range

    r = parse_range("all")
    assert r.label == "all time"
    assert r.since.year == 1970
    assert parse_range("all-time").label == "all time"
    assert parse_range("tout").label == "all time"
    assert "7" in parse_range("7d").label


def test_parse_interval_weeks() -> None:
    d = parse_interval("2w")
    assert d == timedelta(weeks=2)
    r = parse_range("2w")
    assert 13 <= (r.until - r.since).days <= 15


def test_parse_range_avant_hier_to_today() -> None:
    r = parse_range("avant-hier..today")
    assert r.since <= r.until
    assert "->" in r.label

