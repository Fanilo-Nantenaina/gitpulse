from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pygit2
from pygit2.enums import SortMode


class RefLabel(TypedDict):
    name: str
    kind: str
    head: bool


GraphEdge = TypedDict("GraphEdge", {"from": int, "to": int, "kind": str})


class _GraphNodeBase(TypedDict):
    sha: str
    short: str
    lane: int
    parents: list[str]
    incoming: list[int]
    edges: list[GraphEdge]
    is_merge: bool
    summary: str
    body: str
    author: str
    email: str
    committer: str
    when: str
    refs: list[RefLabel]
    width: int


class GraphNode(_GraphNodeBase, total=False):
    tip: bool


class Graph(TypedDict):
    nodes: list[GraphNode]
    branches: list[str]
    remote_branches: list[str]
    head: str | None
    returned: int
    lanes: int
    has_more: bool


def _refs_by_oid(repo: pygit2.Repository) -> dict[str, list[RefLabel]]:
    out: dict[str, list[RefLabel]] = {}
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


def _tips(repo: pygit2.Repository) -> list[pygit2.Oid]:
    oids: list[pygit2.Oid] = []
    seen: set[str] = set()

    def add_commit(target: pygit2.Oid | str) -> None:
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
    repo_path: str | os.PathLike[str],
    limit: int = 0,
    offset: int = 0,
    branch: str | None = None,
    all_commits: bool = True,
) -> Graph:
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

    flags = SortMode.TIME | SortMode.TOPOLOGICAL
    tips: list[pygit2.Oid | str] = []
    if branch and not all_commits:
        try:
            target = repo.branches[branch]
        except KeyError:
            raise ValueError(f"Branch '{branch}' not found")
        tips = [target.target]
    else:
        tips = list(_tips(repo))

    if not tips:
        walker = repo.walk(repo.head.target, flags)
    else:
        walker = repo.walk(tips[0], flags)
        for oid in tips[1:]:
            try:
                walker.push(oid)
            except Exception:
                continue

    lanes: list[str | None] = []
    nodes: list[GraphNode] = []
    stop_at = (offset + limit) if limit > 0 else 0
    has_more = False

    def first_free(state: list[str | None]) -> int:
        for i, v in enumerate(state):
            if v is None:
                return i
        state.append(None)
        return len(state) - 1

    for c in walker:
        if stop_at > 0 and len(nodes) >= stop_at:
            has_more = True
            break
        sha = str(c.id)
        parents = [str(p) for p in c.parent_ids]

        before = list(lanes)

        waiting = [i for i, v in enumerate(before) if v == sha]
        if waiting:
            my_lane = waiting[0]
        else:
            my_lane = first_free(lanes)
            before = list(lanes)
            lanes[my_lane] = sha
            before[my_lane] = sha

        after = list(before)
        for i in waiting:
            after[i] = None
        if my_lane < len(after):
            after[my_lane] = None

        first_parent_lane = my_lane
        if parents:
            p0 = parents[0]
            existing0 = next((i for i, v in enumerate(after) if v == p0), None)
            if existing0 is not None:
                first_parent_lane = existing0
            else:
                after[my_lane] = p0
                first_parent_lane = my_lane

        merge_targets: list[int] = []
        for p in parents[1:]:
            tgt = next((i for i, v in enumerate(after) if v == p), None)
            if tgt is None:
                tgt = first_free(after)
            after[tgt] = p
            merge_targets.append(tgt)

        lanes = list(after)

        incoming = [i for i, v in enumerate(before) if v is not None]

        edges: list[GraphEdge] = []
        for i, v in enumerate(before):
            if v is None:
                continue
            if i == my_lane:
                if parents:
                    edges.append(
                        {"from": my_lane, "to": first_parent_lane, "kind": "commit"}
                    )
            elif v == sha:
                edges.append({"from": i, "to": my_lane, "kind": "converge"})
            else:
                to = next((j for j, w in enumerate(after) if w == v), None)
                if to is not None:
                    edges.append({"from": i, "to": to, "kind": "pass"})
        for tgt in merge_targets[: max(0, len(parents) - 1)]:
            edges.append({"from": my_lane, "to": tgt, "kind": "merge"})

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
                "width": len([v for v in lanes if v is not None]) or 1,
            }
        )

    for i, n in enumerate(nodes):
        if i == 0:
            n["incoming"] = []
        else:
            n["incoming"] = sorted({e["to"] for e in nodes[i - 1]["edges"]})
        n["tip"] = n["lane"] not in n["incoming"]

    if offset > 0:
        nodes = nodes[offset:]

    max_w = 1
    for n in nodes:
        used = (
            set(n["incoming"])
            | {e["from"] for e in n["edges"]}
            | {e["to"] for e in n["edges"]}
            | {n["lane"]}
        )
        max_w = max(max_w, (max(used) + 1) if used else 1)

    return {
        "nodes": nodes,
        "branches": sorted(repo.branches.local),
        "remote_branches": sorted(repo.branches.remote),
        "head": head,
        "returned": len(nodes),
        "lanes": max_w,
        "has_more": has_more,
    }
