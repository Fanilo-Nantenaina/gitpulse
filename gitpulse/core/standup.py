from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pygit2

from . import workspace
from .models import RepoActivity


@dataclass
class RepoState:
    name: str
    current_branch: str | None
    uncommitted: list[str] = field(default_factory=list[str])
    recent_branches: list[str] = field(default_factory=list[str])


@dataclass
class StandupContext:
    repo_name: str
    yesterday: RepoActivity
    current_branch: str | None
    uncommitted: list[str] = field(default_factory=list[str])
    recent_branches: list[str] = field(default_factory=list[str])
    repos: list[RepoState] = field(default_factory=list[RepoState])


def _day_window(target: datetime) -> tuple[datetime, datetime]:
    tz = target.tzinfo or timezone.utc
    start = datetime.combine(target.date(), time.min, tzinfo=tz)
    end = datetime.combine(target.date(), time.max, tzinfo=tz)
    return start, end


def _repo_state(repo_path: Path, name: str) -> RepoState:
    discovered = pygit2.discover_repository(str(repo_path))
    if discovered is None:
        raise ValueError(f"No git repository found at {repo_path}")
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
            commit = repo[ref.target].peel(pygit2.Commit)
            recent.append((bname, commit.commit_time))
        except Exception:
            continue
    recent.sort(key=lambda x: x[1], reverse=True)

    return RepoState(
        name=name,
        current_branch=current_branch,
        uncommitted=uncommitted[:20],
        recent_branches=[b for b, _ in recent[:5]],
    )


def gather(
    repo_path: str | os.PathLike[str],
    name: str | None = None,
    now: datetime | None = None,
    max_depth: int = workspace.DEFAULT_DEPTH,
) -> StandupContext:
    now = now or datetime.now().astimezone()
    root = Path(repo_path).resolve()
    repo_name = name or root.name

    yesterday = now - timedelta(days=1)
    if yesterday.weekday() == 6:
        yesterday = now - timedelta(days=3)
    elif yesterday.weekday() == 5:
        yesterday = now - timedelta(days=2)
    y_start, y_end = _day_window(yesterday)
    activity, _ = workspace.collect(
        root, y_start, y_end, name=repo_name, max_depth=max_depth
    )

    if activity.is_workspace:
        states: list[RepoState] = []
        for ref in activity.repos:
            try:
                states.append(_repo_state(Path(ref.path), ref.name))
            except (ValueError, pygit2.GitError):
                continue
        return StandupContext(
            repo_name=repo_name,
            yesterday=activity,
            current_branch=None,
            repos=states,
        )

    state = _repo_state(root, repo_name)
    return StandupContext(
        repo_name=repo_name,
        yesterday=activity,
        current_branch=state.current_branch,
        uncommitted=state.uncommitted,
        recent_branches=state.recent_branches,
    )
