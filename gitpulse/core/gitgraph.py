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


Segment = TypedDict("Segment", {"from": int, "to": int, "color": int})


class GraphNode(TypedDict):
    sha: str
    short: str
    lane: int
    color: int
    parents: list[str]
    segments: list[Segment]
    is_merge: bool
    summary: str
    body: str
    author: str
    email: str
    committer: str
    committer_email: str
    when: str
    author_when: str
    refs: list[RefLabel]


class Graph(TypedDict):
    nodes: list[GraphNode]
    incoming: list[Segment]
    branches: list[str]
    remote_branches: list[str]
    head: str | None
    head_sha: str | None
    returned: int
    lanes: int
    has_more: bool


def _when(t: int, offset: int) -> str:
    return datetime.fromtimestamp(t, timezone(timedelta(minutes=offset))).isoformat()


def _refs_by_oid(repo: pygit2.Repository) -> dict[str, list[RefLabel]]:
    out: dict[str, list[RefLabel]] = {}
    head = None
    if not repo.head_is_unborn and not repo.head_is_detached:
        head = repo.head.shorthand
    for bname in repo.branches.local:
        try:
            target = repo.branches.local[bname].peel(pygit2.Commit).id
        except Exception:
            continue
        out.setdefault(str(target), []).append(
            {"name": bname, "kind": "local", "head": bname == head}
        )
    for bname in repo.branches.remote:
        try:
            target = repo.branches.remote[bname].peel(pygit2.Commit).id
        except Exception:
            continue
        out.setdefault(str(target), []).append(
            {"name": bname, "kind": "remote", "head": False}
        )
    for ref_name in repo.references:
        if not ref_name.startswith("refs/tags/"):
            continue
        try:
            target = repo.references[ref_name].peel(pygit2.Commit).id
        except Exception:
            continue
        out.setdefault(str(target), []).append(
            {"name": ref_name[len("refs/tags/") :], "kind": "tag", "head": False}
        )
    if repo.head_is_detached:
        out.setdefault(str(repo.head.target), []).insert(
            0, {"name": "HEAD", "kind": "head", "head": True}
        )
    return out


def _tips(repo: pygit2.Repository) -> list[pygit2.Oid]:
    oids: list[pygit2.Oid] = []
    seen: set[str] = set()

    def add_commit(target: pygit2.Oid | str) -> None:
        try:
            commit = repo[target].peel(pygit2.Commit)
        except Exception:
            return
        s = str(commit.id)
        if s not in seen:
            seen.add(s)
            oids.append(commit.id)

    if not repo.head_is_unborn:
        add_commit(repo.head.target)
    for ref_name in repo.references:
        if not ref_name.startswith(("refs/heads/", "refs/remotes/", "refs/tags/")):
            continue
        try:
            ref = repo.references[ref_name]
            if ref.type == pygit2.enums.ReferenceType.SYMBOLIC:
                continue
            add_commit(ref.target)
        except Exception:
            continue
    return oids


class _Line:

    __slots__ = ("target", "color", "first", "x", "next_x")

    def __init__(self, target: str, color: int, first: bool, x: int) -> None:
        self.target = target
        self.color = color
        self.first = first
        self.x = x
        self.next_x = x


class _Layout:

    def __init__(self) -> None:
        self.active: list[_Line] = []

    def _free_color(self, ended: set[int]) -> int:
        used = {line.color for line in self.active} | ended
        c = 0
        while c in used:
            c += 1
        return c

    def row(
        self, sha: str, parents: list[str], segments: bool = True
    ) -> tuple[int, int, list[Segment]]:
        arriving = [line for line in self.active if line.target == sha]
        node_line = next((line for line in arriving if line.first), None)
        if node_line is None and arriving:
            node_line = arriving[0]
        present = [
            line for line in self.active if line.target != sha or line is node_line
        ]
        for x, line in enumerate(present):
            line.next_x = x
        ended = {line.color for line in arriving if line is not node_line}
        if node_line is None:
            node_x = len(present)
            color = self._free_color(ended)
        else:
            node_x = node_line.next_x
            color = node_line.color

        entering: list[Segment] = []
        for line in self.active:
            to = node_x if line.target == sha else line.next_x
            if segments:
                entering.append({"from": line.x, "to": to, "color": line.color})
            line.x = to

        self.active = [line for line in present if line is not node_line]
        if parents:
            if node_line is None:
                node_line = _Line(parents[0], color, True, node_x)
            else:
                node_line.target, node_line.first = parents[0], True
            self.active.insert(node_x, node_line)
            for p in parents[1:]:
                self.active.append(_Line(p, self._free_color(ended), False, node_x))
        return node_x, color, entering

    def leaving(self) -> list[tuple[int, int]]:
        return [(line.x, line.color) for line in self.active]


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
            "incoming": [],
            "branches": sorted(repo.branches.local),
            "remote_branches": [],
            "head": None,
            "head_sha": None,
            "returned": 0,
            "lanes": 1,
            "has_more": False,
        }

    refs = _refs_by_oid(repo)
    head = repo.head.shorthand if not repo.head_is_detached else None

    tips: list[pygit2.Oid]
    if branch and not all_commits:
        try:
            target = repo.branches[branch]
        except KeyError:
            raise ValueError(f"Branch '{branch}' not found")
        tips = [target.peel(pygit2.Commit).id]
    else:
        tips = _tips(repo)

    walker = repo.walk(tips[0], SortMode.TOPOLOGICAL | SortMode.TIME)
    for oid in tips[1:]:
        walker.push(oid)

    shallow = repo.is_shallow
    layout = _Layout()
    stop_at = offset + limit if limit > 0 else 0
    nodes: list[GraphNode] = []
    incoming: list[Segment] = []
    has_more = False
    for index, c in enumerate(walker):
        sha = str(c.id)
        parents = [str(p) for p in c.parent_ids]
        drawn = [p for p in parents if p in repo] if shallow else parents
        lane, color, entering = layout.row(sha, drawn, segments=index >= offset)
        if index > 0 and index - 1 >= offset:
            nodes[-1]["segments"] = entering
        elif index == offset:
            incoming = entering
        if stop_at and index >= stop_at:
            has_more = True
            break
        if index < offset:
            continue
        msg = c.message.strip()
        nodes.append(
            {
                "sha": sha,
                "short": sha[:8],
                "lane": lane,
                "color": color,
                "parents": parents,
                "segments": [],
                "is_merge": len(parents) > 1,
                "summary": msg.splitlines()[0] if msg else "",
                "body": msg,
                "author": c.author.name,
                "email": c.author.email,
                "committer": c.committer.name,
                "committer_email": c.committer.email,
                "when": _when(c.commit_time, c.commit_time_offset),
                "author_when": _when(c.author.time, c.author.offset),
                "refs": refs.get(sha, []),
            }
        )
    if nodes and not has_more:
        nodes[-1]["segments"] = [
            {"from": x, "to": x, "color": col} for x, col in layout.leaving()
        ]

    lanes = 1
    for n in nodes:
        lanes = max(lanes, n["lane"] + 1)
        for s in n["segments"]:
            lanes = max(lanes, s["from"] + 1, s["to"] + 1)
    for s in incoming:
        lanes = max(lanes, s["from"] + 1, s["to"] + 1)

    return {
        "nodes": nodes,
        "incoming": incoming,
        "branches": sorted(repo.branches.local),
        "remote_branches": sorted(
            b for b in repo.branches.remote if not b.endswith("/HEAD")
        ),
        "head": head,
        "head_sha": str(repo.head.target),
        "returned": len(nodes),
        "lanes": lanes,
        "has_more": has_more,
    }
