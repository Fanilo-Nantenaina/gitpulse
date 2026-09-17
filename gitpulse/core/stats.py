from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TypedDict

from .models import RepoActivity, qualified_path


class DayStat(TypedDict):
    date: str
    commits: int
    additions: int
    deletions: int


class _AuthorTotals(TypedDict):
    commits: int
    additions: int
    deletions: int


class AuthorStat(_AuthorTotals):
    name: str


class FileChurn(TypedDict):
    path: str
    churn: int


class Totals(TypedDict):
    commits: int
    additions: int
    deletions: int
    files_touched: int
    active_days: int
    authors: int


class RepoStat(TypedDict):
    name: str
    commits: int
    additions: int
    deletions: int
    authors: int


class Stats(TypedDict):
    totals: Totals
    daily: list[DayStat]
    authors: list[AuthorStat]
    by_hour: list[int]
    by_weekday: list[int]
    top_files: list[FileChurn]
    repos: list[RepoStat]


def compute_stats(activity: RepoActivity) -> Stats:
    commits = activity.commits

    per_day_commits: dict[str, int] = defaultdict(int)
    per_day_add: dict[str, int] = defaultdict(int)
    per_day_del: dict[str, int] = defaultdict(int)
    for c in commits:
        day = c.when.strftime("%Y-%m-%d")
        per_day_commits[day] += 1
        per_day_add[day] += c.additions
        per_day_del[day] += c.deletions

    days: list[str] = []
    if commits:
        start = min(c.when.date() for c in commits)
        end = max(c.when.date() for c in commits)
        d = start
        while d <= end:
            days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

    daily: list[DayStat] = [
        {
            "date": day,
            "commits": per_day_commits.get(day, 0),
            "additions": per_day_add.get(day, 0),
            "deletions": per_day_del.get(day, 0),
        }
        for day in days
    ]

    by_author: defaultdict[str, _AuthorTotals] = defaultdict(
        lambda: {"commits": 0, "additions": 0, "deletions": 0}
    )
    for c in commits:
        a = by_author[c.author_name]
        a["commits"] += 1
        a["additions"] += c.additions
        a["deletions"] += c.deletions
    authors: list[AuthorStat] = sorted(
        ({"name": k, **v} for k, v in by_author.items()),
        key=lambda x: x["commits"],
        reverse=True,
    )

    by_hour = [0] * 24
    for c in commits:
        by_hour[c.when.hour] += 1

    by_weekday = [0] * 7
    for c in commits:
        by_weekday[c.when.weekday()] += 1

    file_churn: dict[str, int] = defaultdict(int)
    for c in commits:
        for f in c.files:
            file_churn[qualified_path(c, f)] += f.additions + f.deletions
    top_files = sorted(
        (FileChurn(path=p, churn=n) for p, n in file_churn.items()),
        key=lambda x: x["churn"],
        reverse=True,
    )[:10]

    return {
        "totals": {
            "commits": activity.commit_count,
            "additions": activity.total_additions,
            "deletions": activity.total_deletions,
            "files_touched": activity.files_touched,
            "active_days": len({c.when.date() for c in commits}),
            "authors": len(by_author),
        },
        "daily": daily,
        "authors": authors,
        "by_hour": by_hour,
        "by_weekday": by_weekday,
        "top_files": top_files,
        "repos": _repo_stats(activity),
    }


def _repo_stats(activity: RepoActivity) -> list[RepoStat]:
    if not activity.is_workspace:
        return []
    rows: dict[str, RepoStat] = {
        r.name: {
            "name": r.name,
            "commits": 0,
            "additions": 0,
            "deletions": 0,
            "authors": 0,
        }
        for r in activity.repos
    }
    seen_authors: dict[str, set[str]] = {r.name: set() for r in activity.repos}
    for c in activity.commits:
        row = rows.get(c.repo)
        if row is None:
            continue
        row["commits"] += 1
        row["additions"] += c.additions
        row["deletions"] += c.deletions
        seen_authors[c.repo].add(c.author_name)
    for name, row in rows.items():
        row["authors"] = len(seen_authors[name])
    return sorted(rows.values(), key=lambda r: r["commits"], reverse=True)
