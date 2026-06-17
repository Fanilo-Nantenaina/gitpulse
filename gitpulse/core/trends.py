from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .collector import collect_activity
from .models import RepoActivity


@dataclass
class Metric:
    name: str
    current: float
    baseline: float

    @property
    def delta(self) -> float:
        return self.current - self.baseline

    @property
    def pct(self) -> float | None:
        if self.baseline == 0:
            return None
        return (self.current - self.baseline) / self.baseline * 100

    @property
    def direction(self) -> str:
        if self.current > self.baseline:
            return "up"
        if self.current < self.baseline:
            return "down"
        return "flat"


@dataclass
class Comparison:
    repo_name: str
    period_len: timedelta
    periods_back: int
    current: RepoActivity
    baseline_periods: list[RepoActivity]
    metrics: list[Metric]


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def compare(repo_path, period: timedelta, periods_back: int = 4,
            branch: str | None = None, now: datetime | None = None,
            name: str | None = None) -> Comparison:
    now = now or datetime.now().astimezone()
    cur_since = now - period
    current = collect_activity(repo_path, cur_since, now, branch=branch, name=name)

    baselines: list[RepoActivity] = []
    for i in range(1, periods_back + 1):
        until = now - period * i
        since = now - period * (i + 1)
        baselines.append(collect_activity(repo_path, since, until, branch=branch, name=name))

    def metric(label, fn):
        return Metric(label, fn(current), _avg([fn(b) for b in baselines]))

    metrics = [
        metric("Commits", lambda a: a.commit_count),
        metric("Lines added", lambda a: a.total_additions),
        metric("Lines deleted", lambda a: a.total_deletions),
        metric("Files touched", lambda a: a.files_touched),
        metric("Active days", lambda a: a.active_days),
    ]

    return Comparison(
        repo_name=current.repo_name,
        period_len=period,
        periods_back=periods_back,
        current=current,
        baseline_periods=baselines,
        metrics=metrics,
    )
