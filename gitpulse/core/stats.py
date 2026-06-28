from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from .models import RepoActivity


def compute_stats(activity: RepoActivity) -> dict:
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

    daily = [
        {
            "date": day,
            "commits": per_day_commits.get(day, 0),
            "additions": per_day_add.get(day, 0),
            "deletions": per_day_del.get(day, 0),
        }
        for day in days
    ]

    by_author: dict[str, dict] = defaultdict(
        lambda: {"commits": 0, "additions": 0, "deletions": 0}
    )
    for c in commits:
        a = by_author[c.author_name]
        a["commits"] += 1
        a["additions"] += c.additions
        a["deletions"] += c.deletions
    authors = sorted(
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
            file_churn[f.path] += f.additions + f.deletions
    top_files = sorted(
        ({"path": p, "churn": n} for p, n in file_churn.items()),
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
    }
