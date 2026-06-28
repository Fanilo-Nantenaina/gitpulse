from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta, date, time


@dataclass
class DateRange:
    since: datetime
    until: datetime
    label: str


_WEEKDAYS = {
    "monday": 0,
    "lundi": 0,
    "tuesday": 1,
    "mardi": 1,
    "wednesday": 2,
    "mercredi": 2,
    "thursday": 3,
    "jeudi": 3,
    "friday": 4,
    "vendredi": 4,
    "saturday": 5,
    "samedi": 5,
    "sunday": 6,
    "dimanche": 6,
}

_INTERVAL = re.compile(r"^(\d+)\s*([dhm])$")
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    end = datetime.combine(d, time.max, tzinfo=timezone.utc)
    return start, end


def parse_interval(s: str) -> timedelta:
    m = _INTERVAL.match(s.strip().lower())
    if not m:
        raise ValueError(f"Invalid interval: {s!r}")
    n, unit = int(m.group(1)), m.group(2)
    return {"d": timedelta(days=n), "h": timedelta(hours=n), "m": timedelta(minutes=n)}[
        unit
    ]


def parse_range(spec: str, now: datetime | None = None) -> DateRange:
    now = now or _now()
    today = now.date()
    s = spec.strip().lower()

    if s in ("all", "all-time", "alltime", "tout", "tout-l'historique", "__all"):
        epoch = datetime(1970, 1, 1, tzinfo=now.tzinfo)
        return DateRange(epoch, now, "all time")

    if ".." in s:
        left, right = (p.strip() for p in s.split("..", 1))
        a = _resolve_date(left, today)
        b = _resolve_date(right, today) if right else today
        lo, hi = sorted((a, b))
        start, _ = _day_bounds(lo)
        _, end = _day_bounds(hi)
        return DateRange(start, end, f"{lo.isoformat()} -> {hi.isoformat()}")

    if _INTERVAL.match(s):
        delta = parse_interval(s)
        return DateRange(now - delta, now, f"last {s}")

    relative = {
        "today": 0,
        "aujourd'hui": 0,
        "aujourdhui": 0,
        "yesterday": 1,
        "hier": 1,
    }
    if s in relative:
        d = today - timedelta(days=relative[s])
        start, end = _day_bounds(d)
        return DateRange(start, end, d.isoformat())

    if s in ("day-before-yesterday", "avant-hier", "avant hier"):
        d = today - timedelta(days=2)
        start, end = _day_bounds(d)
        return DateRange(start, end, d.isoformat())

    if s in ("this-week", "this week", "cette-semaine", "cette semaine"):
        monday = today - timedelta(days=today.weekday())
        start, _ = _day_bounds(monday)
        return DateRange(start, now, f"week of {monday.isoformat()}")

    if s in ("last-week", "last week", "semaine-derniere", "semaine derniere"):
        this_monday = today - timedelta(days=today.weekday())
        last_monday = this_monday - timedelta(days=7)
        last_sunday = this_monday - timedelta(days=1)
        start, _ = _day_bounds(last_monday)
        _, end = _day_bounds(last_sunday)
        return DateRange(
            start, end, f"{last_monday.isoformat()} -> {last_sunday.isoformat()}"
        )

    base = s
    last = False
    for prefix in ("last ", "last-", "dernier ", "derniere "):
        if base.startswith(prefix):
            base, last = base[len(prefix) :], True
    for suffix in (" dernier", " derniere", "-dernier", "-derniere"):
        if base.endswith(suffix):
            base, last = base[: -len(suffix)], True
    base = base.strip()
    if base in _WEEKDAYS:
        target = _WEEKDAYS[base]
        delta = (today.weekday() - target) % 7
        if delta == 0:
            delta = 7 if last else 0
        d = today - timedelta(days=delta)
        start, end = _day_bounds(d)
        return DateRange(start, end, d.isoformat())

    if _ISO.match(s):
        d = date.fromisoformat(s)
        start, end = _day_bounds(d)
        return DateRange(start, end, d.isoformat())

    raise ValueError(f"Unrecognized date spec: {spec!r}")


def _resolve_date(token: str, today: date) -> date:
    token = token.strip().lower()
    if not token or token == "today":
        return today
    if token in ("yesterday", "hier"):
        return today - timedelta(days=1)
    if _ISO.match(token):
        return date.fromisoformat(token)
    if token in _WEEKDAYS:
        delta = (today.weekday() - _WEEKDAYS[token]) % 7
        return today - timedelta(days=delta)
    raise ValueError(f"Unrecognized date in range: {token!r}")


def suggestions(now: datetime | None = None) -> list[tuple[str, str]]:
    now = now or _now()
    today = now.date()
    out = [
        ("today", today.isoformat()),
        ("yesterday", (today - timedelta(days=1)).isoformat()),
        ("avant-hier", (today - timedelta(days=2)).isoformat()),
    ]
    names = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    for i in range(3, 7):
        d = today - timedelta(days=i)
        out.append((f"{names[d.weekday()]} (last)", d.isoformat()))
    out.append(
        ("this-week", f"since {(today - timedelta(days=today.weekday())).isoformat()}")
    )
    out.append(("last-week", "previous Mon-Sun"))
    return out
