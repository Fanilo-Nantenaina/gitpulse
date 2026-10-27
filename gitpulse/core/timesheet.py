from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal, TypedDict

from .models import Commit, RepoActivity

DEFAULT_GAP_MINUTES = 120
DEFAULT_WARMUP_MINUTES = 30


@dataclass
class Session:
    author: str
    start: datetime
    end: datetime
    commits: list[Commit] = field(default_factory=list[Commit])
    warmup: timedelta = timedelta(minutes=DEFAULT_WARMUP_MINUTES)

    @property
    def duration(self) -> timedelta:
        return self.end - self.start + self.warmup

    @property
    def minutes(self) -> int:
        return round(self.duration.total_seconds() / 60)

    def repo_share(self) -> dict[str, float]:
        counts: dict[str, int] = defaultdict(int)
        for c in self.commits:
            counts[c.repo or ""] += 1
        total = len(self.commits)
        return {repo: n / total for repo, n in counts.items()}


class TimeRow(TypedDict):
    day: str
    author: str
    repo: str
    minutes: int
    commits: int
    sessions: int


@dataclass
class TimeReport:
    scope: str
    since: datetime
    until: datetime
    gap_minutes: int
    warmup_minutes: int
    sessions: list[Session]
    rows: list[TimeRow]

    @property
    def total_minutes(self) -> int:
        return sum(r["minutes"] for r in self.rows)

    @property
    def days(self) -> int:
        return len({r["day"] for r in self.rows})

    def by(self, key: Literal["day", "author", "repo"]) -> list[tuple[str, int, int]]:
        minutes: dict[str, int] = defaultdict(int)
        commits: dict[str, int] = defaultdict(int)
        for r in self.rows:
            k = r[key] or "-"
            minutes[k] += r["minutes"]
            commits[k] += r["commits"]
        return sorted(
            ((k, minutes[k], commits[k]) for k in minutes),
            key=lambda t: t[1],
            reverse=True,
        )

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["day", "author", "repo", "hours", "minutes", "commits", "sessions"])
        for r in self.rows:
            w.writerow(
                [
                    r["day"],
                    r["author"],
                    r["repo"],
                    f"{r['minutes'] / 60:.2f}",
                    r["minutes"],
                    r["commits"],
                    r["sessions"],
                ]
            )
        return buf.getvalue()

    def to_markdown(self) -> str:
        lines = [
            f"# Time report: {self.scope}",
            "",
            f"{self.since:%Y-%m-%d} → {self.until:%Y-%m-%d} · "
            f"**{format_hours(self.total_minutes)}** over {self.days} day(s) · "
            f"estimated from commit times (session gap {self.gap_minutes} min, "
            f"+{self.warmup_minutes} min warm-up per session)",
            "",
            "| Day | Author | Repository | Hours | Commits |",
            "| --- | --- | --- | ---: | ---: |",
        ]
        for r in self.rows:
            lines.append(
                f"| {r['day']} | {r['author']} | {r['repo'] or '-'} | "
                f"{r['minutes'] / 60:.2f} | {r['commits']} |"
            )
        return "\n".join(lines) + "\n"


def format_hours(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h{m:02d}"


def sessions(
    activity: RepoActivity,
    gap_minutes: int = DEFAULT_GAP_MINUTES,
    warmup_minutes: int = DEFAULT_WARMUP_MINUTES,
) -> list[Session]:
    gap = timedelta(minutes=gap_minutes)
    warmup = timedelta(minutes=warmup_minutes)
    by_author: dict[str, list[Commit]] = defaultdict(list)
    names: dict[str, str] = {}
    for c in activity.commits:
        key = (c.author_email or c.author_name).lower()
        by_author[key].append(c)
        names.setdefault(key, c.author_name)
    out: list[Session] = []
    for key, commits in by_author.items():
        commits.sort(key=lambda c: c.when)
        current: Session | None = None
        for c in commits:
            if current is None or c.when - current.end > gap:
                current = Session(names[key], c.when, c.when, [c], warmup)
                out.append(current)
            else:
                current.end = c.when
                current.commits.append(c)
    out.sort(key=lambda s: s.start)
    return out


def report(
    activity: RepoActivity,
    gap_minutes: int = DEFAULT_GAP_MINUTES,
    warmup_minutes: int = DEFAULT_WARMUP_MINUTES,
) -> TimeReport:
    found = sessions(activity, gap_minutes, warmup_minutes)
    minutes: dict[tuple[date, str, str], float] = defaultdict(float)
    commits: dict[tuple[date, str, str], int] = defaultdict(int)
    counted: dict[tuple[date, str, str], int] = defaultdict(int)
    for s in found:
        day = s.start.date()
        for repo, share in s.repo_share().items():
            key = (day, s.author, repo)
            minutes[key] += s.minutes * share
            counted[key] += 1
        for c in s.commits:
            commits[(day, s.author, c.repo or "")] += 1
    rows: list[TimeRow] = [
        {
            "day": day.isoformat(),
            "author": author,
            "repo": repo,
            "minutes": round(minutes[(day, author, repo)]),
            "commits": commits[(day, author, repo)],
            "sessions": counted[(day, author, repo)],
        }
        for day, author, repo in sorted(minutes)
    ]
    return TimeReport(
        scope=activity.repo_name,
        since=activity.since,
        until=activity.until,
        gap_minutes=gap_minutes,
        warmup_minutes=warmup_minutes,
        sessions=found,
        rows=rows,
    )
