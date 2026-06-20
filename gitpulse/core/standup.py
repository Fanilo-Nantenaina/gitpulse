from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, time, timezone
from pathlib import Path

import pygit2

from .collector import collect_activity
from .models import RepoActivity


@dataclass
class StandupContext:
    repo_name: str
    yesterday: RepoActivity
    current_branch: str | None
    uncommitted: list[str] = field(default_factory=list)
    recent_branches: list[str] = field(default_factory=list)


def _day_window(target: datetime) -> tuple[datetime, datetime]:
    tz = target.tzinfo or timezone.utc
    start = datetime.combine(target.date(), time.min, tzinfo=tz)
    end = datetime.combine(target.date(), time.max, tzinfo=tz)
    return start, end


def gather(
    repo_path, name: str | None = None, now: datetime | None = None
) -> StandupContext:
    now = now or datetime.now().astimezone()
    repo_path = Path(repo_path).resolve()
    repo_name = name or repo_path.name

    yesterday = now - timedelta(days=1)
    if yesterday.weekday() == 6:
        yesterday = now - timedelta(days=3)
    elif yesterday.weekday() == 5:
        yesterday = now - timedelta(days=2)
    y_start, y_end = _day_window(yesterday)
    activity = collect_activity(repo_path, y_start, y_end, name=repo_name)

    discovered = pygit2.discover_repository(str(repo_path))
    repo = pygit2.Repository(discovered)

    current_branch = None
    if not repo.head_is_unborn and not repo.head_is_detached:
        current_branch = repo.head.shorthand

    uncommitted: list[str] = []
    try:
        for filepath, flags in repo.status().items():
            if flags != pygit2.GIT_STATUS_IGNORED:
                uncommitted.append(filepath)
    except Exception:
        pass

    recent: list[tuple[str, int]] = []
    for bname in repo.branches.local:
        try:
            ref = repo.branches[bname]
            commit = repo[ref.target]
            recent.append((bname, commit.commit_time))
        except Exception:
            continue
    recent.sort(key=lambda x: x[1], reverse=True)
    recent_branches = [b for b, _ in recent[:5]]

    return StandupContext(
        repo_name=repo_name,
        yesterday=activity,
        current_branch=current_branch,
        uncommitted=uncommitted[:20],
        recent_branches=recent_branches,
    )
