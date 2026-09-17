from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import RepoActivity
from .workspace import DEFAULT_DEPTH, AuthorScope, collect


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


def compare(
    repo_path: str | os.PathLike[str],
    period: timedelta,
    periods_back: int = 4,
    branch: str | None = None,
    now: datetime | None = None,
    name: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScope = "window",
    max_depth: int = DEFAULT_DEPTH,
) -> Comparison:
    now = now or datetime.now().astimezone()
    total_since = now - period * (periods_back + 1)
    total_activity, _ = collect(
        repo_path,
        total_since,
        now,
        branch=branch,
        name=name,
        authors=authors,
        author_scope=author_scope,
        max_depth=max_depth,
    )

    cur_since = now - period
    current_commits = [c for c in total_activity.commits if c.when >= cur_since]
    current = RepoActivity(
        repo_name=total_activity.repo_name,
        repo_path=total_activity.repo_path,
        since=cur_since,
        until=now,
        commits=current_commits,
        repos=total_activity.repos,
    )

    baselines: list[RepoActivity] = []
    for i in range(1, periods_back + 1):
        until = now - period * i
        since = now - period * (i + 1)
        b_commits = [c for c in total_activity.commits if since <= c.when < until]
        baselines.append(
            RepoActivity(
                repo_name=total_activity.repo_name,
                repo_path=total_activity.repo_path,
                since=since,
                until=until,
                commits=b_commits,
                repos=total_activity.repos,
            )
        )

    def metric(label: str, fn: Callable[[RepoActivity], float]) -> Metric:
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
