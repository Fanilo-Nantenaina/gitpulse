from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pygit2


def _refs_by_oid(repo) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    head = None
    if not repo.head_is_unborn and not repo.head_is_detached:
        head = repo.head.shorthand
    for bname in repo.branches.local:
        try:
            out.setdefault(str(repo.branches[bname].target), []).append(
                {"name": bname, "kind": "local", "head": bname == head}
            )
        except Exception:
            continue
    for bname in repo.branches.remote:
        try:
            out.setdefault(str(repo.branches[bname].target), []).append(
                {"name": bname, "kind": "remote", "head": False}
            )
        except Exception:
            continue
    try:
        for ref_name in repo.references:
            if ref_name.startswith("refs/tags/"):
                target = repo.references[ref_name].peel(pygit2.Commit).id
                out.setdefault(str(target), []).append(
                    {
                        "name": ref_name.split("refs/tags/")[-1],
                        "kind": "tag",
                        "head": False,
                    }
                )
    except Exception:
        pass
    return out


def _tips(repo):
    oids = []
    seen = set()

    def add(o):
        s = str(o)
        if s not in seen:
            seen.add(s)
            oids.append(o)

    if not repo.head_is_unborn:
        add(repo.head.target)
    for coll in (repo.branches.local, repo.branches.remote):
        for bname in coll:
            try:
                add(repo.branches[bname].target)
            except Exception:
                continue
    return oids


def graph(
    repo_path,
    limit: int = 100,
    offset: int = 0,
    branch: str | None = None,
    all_commits: bool = False,
) -> dict:
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        raise ValueError("No git repository found")
    repo = pygit2.Repository(discovered)
    if repo.head_is_unborn:
        return {
            "nodes": [],
            "branches": [],
            "remote_branches": [],
            "head": None,
            "returned": 0,
            "lanes": 1,
            "has_more": False,
        }

    refs = _refs_by_oid(repo)
    head = repo.head.shorthand if not repo.head_is_detached else None

    flags = pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_TOPOLOGICAL
    if branch:
        b = repo.branches.get(branch)
        if b is None:
            raise ValueError(f"Branch '{branch}' not found")
        walker = repo.walk(b.target, flags)
    else:
        walker = repo.walk(repo.head.target, flags)
        for oid in _tips(repo):
            walker.push(oid)

    # lanes[i] holds the sha that lane i is currently "waiting" to draw, or None.
    lanes: list[str | None] = []
    nodes = []
    seen = 0
    produced = 0
    stop = offset + limit

    def first_free():
        for i, v in enumerate(lanes):
            if v is None:
                return i
        lanes.append(None)
        return len(lanes) - 1

    for c in walker:
        sha = str(c.id)
        parents = [str(p) for p in c.parent_ids]

        # this commit's lane = a lane already expecting it, else a fresh lane
        my_lane = None
        for i, v in enumerate(lanes):
            if v == sha:
                my_lane = i
                break
        if my_lane is None:
            my_lane = first_free()
            lanes[my_lane] = sha

        in_window = offset <= seen and (all_commits or seen < stop)

        # snapshot lanes BEFORE routing (the row's "passing" lanes)
        before = list(lanes)

        # route: first parent continues my lane; clear duplicates of this sha
        for i, v in enumerate(lanes):
            if v == sha:
                lanes[i] = None
        if parents:
            lanes[my_lane] = parents[0]
        merge_targets = []
        for p in parents[1:]:
            existing = None
            for i, v in enumerate(lanes):
                if v == p:
                    existing = i
                    break
            if existing is None:
                existing = first_free()
                lanes[existing] = p
            merge_targets.append(existing)

        after = list(lanes)

        if in_window:
            # routing[k] = lane index in `after` that lane k of `before` flows into
            routing = []
            for k, v in enumerate(before):
                if v is None:
                    continue
                if k == my_lane:
                    # continues to wherever first parent sits
                    if parents:
                        for j, w in enumerate(after):
                            if w == parents[0]:
                                routing.append({"from": k, "to": j})
                                break
                    continue
                # other lanes keep flowing to the same sha
                for j, w in enumerate(after):
                    if w == v:
                        routing.append({"from": k, "to": j})
                        break
            nodes.append(
                {
                    "sha": sha,
                    "short": sha[:8],
                    "lane": my_lane,
                    "parents": parents,
                    "routing": routing,
                    "merge_targets": merge_targets,
                    "is_merge": len(parents) > 1,
                    "summary": (
                        c.message.strip().splitlines()[0] if c.message.strip() else ""
                    ),
                    "author": c.author.name,
                    "when": datetime.fromtimestamp(
                        c.commit_time, timezone(timedelta(minutes=c.commit_time_offset))
                    ).isoformat(),
                    "refs": refs.get(sha, []),
                    "width": len(after),
                }
            )
            produced += 1

        seen += 1
        if not all_commits and produced >= limit:
            break

    max_w = max((n["width"] for n in nodes), default=1)
    max_w = max(max_w, max((n["lane"] for n in nodes), default=0) + 1)

    return {
        "nodes": nodes,
        "branches": sorted(repo.branches.local),
        "remote_branches": sorted(repo.branches.remote),
        "head": head,
        "offset": offset,
        "returned": len(nodes),
        "lanes": max_w,
        "has_more": (not all_commits) and produced >= limit,
    }
