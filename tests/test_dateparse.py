from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from gitpulse.core.dateparse import parse_range, parse_interval


def test_parse_range_days():
    r = parse_range("7d")
    span = r.until - r.since
    assert 6 <= span.days <= 7


def test_parse_range_hours():
    r = parse_range("24h")
    span = r.until - r.since
    assert timedelta(hours=23) <= span <= timedelta(hours=25)


def test_parse_range_today_has_label():
    r = parse_range("today")
    assert r.label
    assert r.since <= r.until


def test_parse_range_yesterday():
    r = parse_range("yesterday")
    assert r.since < r.until


def test_parse_interval_returns_timedelta():
    d = parse_interval("7d")
    assert isinstance(d, timedelta)
    assert d.days == 7


def test_parse_interval_weeks_or_days():
    # a 30d interval should be about a month
    d = parse_interval("30d")
    assert d.days == 30


@pytest.mark.parametrize("expr", ["7d", "24h", "today", "yesterday"])
def test_common_windows_do_not_raise(expr):
    r = parse_range(expr)
    assert r.since is not None and r.until is not None
