from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pygit2


def graph(repo_path, limit: int = 120, branch: str | None = None) -> dict:
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        raise ValueError("No git repository found")
    repo = pygit2.Repository(discovered)

    if repo.head_is_unborn:
        return {"nodes": [], "branches": [], "head": None}

    tip_by_oid: dict[str, list[str]] = {}
    for bname in repo.branches.local:
        try:
            ref = repo.branches[bname]
            tip_by_oid.setdefault(str(ref.target), []).append(bname)
        except Exception:
            continue

    head = repo.head.shorthand if not repo.head_is_detached else None
    start = repo.branches[branch].target if branch else repo.head.target

    nodes = []
    for i, c in enumerate(repo.walk(start, pygit2.GIT_SORT_TIME)):
        if i >= limit:
            break
        tz = timezone(timedelta(minutes=c.commit_time_offset))
        when = datetime.fromtimestamp(c.commit_time, tz)
        nodes.append(
            {
                "sha": str(c.id),
                "short": str(c.id)[:8],
                "parents": [str(p) for p in c.parent_ids],
                "summary": (
                    c.message.strip().splitlines()[0] if c.message.strip() else ""
                ),
                "author": c.author.name,
                "when": when.isoformat(),
                "refs": tip_by_oid.get(str(c.id), []),
            }
        )

    return {
        "nodes": nodes,
        "branches": sorted(repo.branches.local),
        "head": head,
    }
