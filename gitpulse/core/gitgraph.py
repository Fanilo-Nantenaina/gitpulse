from __future__ import annotations

import hashlib
import os
import sys
import threading
from collections import OrderedDict
from collections.abc import Iterator, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pygit2
from pygit2.enums import SortMode

from . import refs as gp_refs


class RefLabel(TypedDict):
    name: str
    kind: str
    head: bool


Segment = TypedDict("Segment", {"from": int, "to": int, "color": int})


class GraphNode(TypedDict):
    sha: str
    short: str
    kind: str
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
    tags: list[str]
    head: str | None
    head_sha: str | None
    uncommitted: int
    version: str
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


UNCOMMITTED = "uncommitted"


class GraphChanged(ValueError):
    pass


def _fingerprint(repo: pygit2.Repository) -> str:
    h = hashlib.sha1()
    h.update(str(repo.head.target).encode() if not repo.head_is_unborn else b"-")
    for name in sorted(repo.references):
        try:
            target = repo.references[name].target
        except Exception:
            continue
        h.update(f"{name}={target};".encode())
    return h.hexdigest()[:16]


def _uncommitted_count(repo: pygit2.Repository) -> int:
    if repo.is_bare or repo.head_is_unborn:
        return 0
    try:
        return sum(
            1
            for flags in repo.status().values()
            if not flags & pygit2.enums.FileStatus.IGNORED
        )
    except pygit2.GitError:
        return 0


def _node(c: pygit2.Commit, refs: dict[str, list[RefLabel]]) -> GraphNode:
    sha = str(c.id)
    msg = c.message.strip()
    parents = [str(p) for p in c.parent_ids]
    return {
        "sha": sha,
        "short": sha[:8],
        "kind": "commit",
        "lane": 0,
        "color": 0,
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


class _Session:

    def __init__(
        self,
        repo: pygit2.Repository,
        tips: list[pygit2.Oid],
        uncommitted: int,
        version: str,
    ) -> None:
        self.lock = threading.Lock()
        self.version = version
        self.uncommitted = uncommitted
        self.refs = _refs_by_oid(repo)
        self.nodes: list[GraphNode] = []
        self.final = 0
        self.done = False
        self._layout = _Layout()
        self._rows = self._walk(repo, tips)

    def _walk(
        self, repo: pygit2.Repository, tips: list[pygit2.Oid]
    ) -> Iterator[GraphNode]:
        if self.uncommitted:
            now = datetime.now().astimezone().isoformat()
            row = _node(repo.head.peel(pygit2.Commit), {})
            row["sha"] = UNCOMMITTED
            row["short"] = ""
            row["kind"] = UNCOMMITTED
            row["parents"] = [str(repo.head.target)]
            row["is_merge"] = False
            row["summary"] = f"Uncommitted changes ({self.uncommitted})"
            row["body"] = ""
            for field in ("author", "email", "committer", "committer_email"):
                row[field] = ""
            row["when"] = row["author_when"] = now
            yield row
        walker = repo.walk(tips[0], SortMode.TOPOLOGICAL | SortMode.TIME)
        for oid in tips[1:]:
            walker.push(oid)
        for c in walker:
            yield _node(c, self.refs)

    def ensure(self, rows: int, repo: pygit2.Repository) -> None:
        shallow = repo.is_shallow
        while self.final < rows and not self.done:
            node = next(self._rows, None)
            if node is None:
                if self.nodes:
                    self.nodes[-1]["segments"] = [
                        {"from": x, "to": x, "color": col}
                        for x, col in self._layout.leaving()
                    ]
                self.final = len(self.nodes)
                self.done = True
                break
            drawn = (
                [p for p in node["parents"] if p in repo]
                if shallow
                else node["parents"]
            )
            node["lane"], node["color"], entering = self._layout.row(node["sha"], drawn)
            if self.nodes:
                self.nodes[-1]["segments"] = entering
                self.final = len(self.nodes)
            self.nodes.append(node)


_SESSIONS: OrderedDict[tuple[str, tuple[str, ...], bool], _Session] = OrderedDict()
_SESSIONS_LOCK = threading.Lock()
_SESSIONS_MAX = 4


def clear_sessions() -> None:
    with _SESSIONS_LOCK:
        _SESSIONS.clear()


def graph(
    repo_path: str | os.PathLike[str],
    limit: int = 0,
    offset: int = 0,
    branches: Sequence[str] | None = None,
    uncommitted: bool = False,
    version: str | None = None,
) -> Graph:
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        raise ValueError("No git repository found")
    repo = pygit2.Repository(discovered)
    ref_list = gp_refs.list_refs(repo)
    base: Graph = {
        "nodes": [],
        "incoming": [],
        "branches": sorted(ref_list["local"]),
        "remote_branches": ref_list["remote"],
        "tags": ref_list["tags"],
        "head": ref_list["head"],
        "head_sha": ref_list["head_sha"],
        "uncommitted": 0,
        "version": "",
        "returned": 0,
        "lanes": 1,
        "has_more": False,
    }
    if repo.head_is_unborn:
        return base

    names = tuple(branches or ())
    tips = gp_refs.tips_for(repo, list(names) if names else gp_refs.ALL_BRANCHES)
    current = _fingerprint(repo)
    if version is not None and version != current:
        raise GraphChanged("The repository changed: reload the graph.")
    key = (discovered, names, uncommitted)
    with _SESSIONS_LOCK:
        session = _SESSIONS.get(key)
        if session is None or offset == 0 or session.version != current:
            count = 0
            if uncommitted and _head_is_shown(repo, tips):
                count = _uncommitted_count(repo)
            session = _Session(repo, tips, count, current)
            _SESSIONS[key] = session
        _SESSIONS.move_to_end(key)
        while len(_SESSIONS) > _SESSIONS_MAX:
            _SESSIONS.popitem(last=False)

    with session.lock:
        session.ensure(offset + limit + 1 if limit > 0 else sys.maxsize, repo)
        end = offset + limit if limit > 0 else session.final
        nodes = session.nodes[offset : min(end, session.final)]
        incoming = (
            session.nodes[offset - 1]["segments"] if 0 < offset <= session.final else []
        )
        has_more = session.final > end or not session.done

    lanes = 1
    for n in nodes:
        lanes = max(lanes, n["lane"] + 1)
        for s in n["segments"]:
            lanes = max(lanes, s["from"] + 1, s["to"] + 1)
    for s in incoming:
        lanes = max(lanes, s["from"] + 1, s["to"] + 1)
    base.update(
        {
            "nodes": nodes,
            "incoming": incoming,
            "uncommitted": session.uncommitted,
            "version": current,
            "returned": len(nodes),
            "lanes": lanes,
            "has_more": has_more and bool(nodes),
        }
    )
    return base


def _head_is_shown(repo: pygit2.Repository, tips: list[pygit2.Oid]) -> bool:
    head = repo.head.target
    return any(t == head or repo.descendant_of(t, head) for t in tips)
