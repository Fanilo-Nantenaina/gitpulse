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

    def add_commit(target):
        try:
            obj = repo[target]
            commit = obj.peel(pygit2.Commit)
        except Exception:
            return
        s = str(commit.id)
        if s not in seen:
            seen.add(s)
            oids.append(commit.id)

    if not repo.head_is_unborn:
        add_commit(repo.head.target)
    for coll in (repo.branches.local, repo.branches.remote):
        for bname in coll:
            if bname.endswith("/HEAD"):
                continue
            try:
                add_commit(repo.branches[bname].target)
            except Exception:
                continue
    return oids


def graph(
    repo_path,
    limit: int = 0,
    offset: int = 0,
    branch: str | None = None,
    all_commits: bool = True,
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
    walker = repo.walk(repo.head.target, flags)
    for oid in _tips(repo):
        try:
            walker.push(oid)
        except Exception:
            continue

    lanes: list[str | None] = []
    nodes = []

    def first_free():
        for i, v in enumerate(lanes):
            if v is None:
                return i
        lanes.append(None)
        return len(lanes) - 1

    for c in walker:
        sha = str(c.id)
        parents = [str(p) for p in c.parent_ids]

        my_lane = None
        for i, v in enumerate(lanes):
            if v == sha:
                my_lane = i
                break
        if my_lane is None:
            my_lane = first_free()
            lanes[my_lane] = sha

        before = list(lanes)

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

        edges = []
        if parents:
            to = next((j for j, w in enumerate(after) if w == parents[0]), my_lane)
            edges.append({"from": my_lane, "to": to, "kind": "commit"})
        for ml in merge_targets:
            edges.append({"from": my_lane, "to": ml, "kind": "merge"})
        for k, v in enumerate(before):
            if v is None or k == my_lane:
                continue
            to = next((j for j, w in enumerate(after) if w == v), None)
            if to is not None:
                edges.append({"from": k, "to": to, "kind": "pass"})

        incoming = [k for k, v in enumerate(before) if v is not None]

        msg = c.message.strip()
        nodes.append(
            {
                "sha": sha,
                "short": sha[:8],
                "lane": my_lane,
                "parents": parents,
                "incoming": incoming,
                "edges": edges,
                "is_merge": len(parents) > 1,
                "summary": msg.splitlines()[0] if msg else "",
                "body": msg,
                "author": c.author.name,
                "email": c.author.email,
                "committer": c.committer.name,
                "when": datetime.fromtimestamp(
                    c.commit_time, timezone(timedelta(minutes=c.commit_time_offset))
                ).isoformat(),
                "refs": refs.get(sha, []),
                "width": len(after),
            }
        )

    max_w = max((n["width"] for n in nodes), default=1)
    max_w = max(max_w, max((n["lane"] for n in nodes), default=0) + 1)

    for i, n in enumerate(nodes):
        if i == 0:
            n["incoming"] = [n["lane"]]
        else:
            n["incoming"] = sorted(set(e["to"] for e in nodes[i - 1]["edges"]))
        if n["lane"] not in n["incoming"]:
            n["incoming"].append(n["lane"])

    return {
        "nodes": nodes,
        "branches": sorted(repo.branches.local),
        "remote_branches": sorted(repo.branches.remote),
        "head": head,
        "returned": len(nodes),
        "lanes": max_w,
        "has_more": False,
    }
