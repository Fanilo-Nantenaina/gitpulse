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
                {"name": bname, "kind": "local", "head": bname == head})
        except Exception:
            continue
    for bname in repo.branches.remote:
        try:
            out.setdefault(str(repo.branches[bname].target), []).append(
                {"name": bname, "kind": "remote", "head": False})
        except Exception:
            continue
    try:
        for ref_name in repo.references:
            if ref_name.startswith("refs/tags/"):
                target = repo.references[ref_name].peel(pygit2.Commit).id
                out.setdefault(str(target), []).append(
                    {"name": ref_name.split("refs/tags/")[-1], "kind": "tag", "head": False})
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
            seen.add(s); oids.append(commit.id)
    if not repo.head_is_unborn:
        add_commit(repo.head.target)
    for coll in (repo.branches.local, repo.branches.remote):
        for bname in coll:
            # skip symbolic refs like origin/HEAD that don't point at a commit directly
            if bname.endswith("/HEAD"):
                continue
            try:
                add_commit(repo.branches[bname].target)
            except Exception:
                continue
    return oids


def graph(repo_path, limit: int = 0, offset: int = 0,
          branch: str | None = None, all_commits: bool = True) -> dict:
    """Build the full commit graph across ALL branches, newest first.

    The graph is always all-branches: no per-branch filtering, no pagination.
    `limit`/`offset`/`branch`/`all_commits` are accepted for API compatibility
    but the graph view loads the entire DAG and the frontend renders it
    progressively as the user scrolls.
    """
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        raise ValueError("No git repository found")
    repo = pygit2.Repository(discovered)
    if repo.head_is_unborn:
        return {"nodes": [], "branches": [], "remote_branches": [],
                "head": None, "returned": 0, "lanes": 1, "has_more": False}

    refs = _refs_by_oid(repo)
    head = repo.head.shorthand if not repo.head_is_detached else None

    flags = pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_TOPOLOGICAL
    walker = repo.walk(repo.head.target, flags)
    for oid in _tips(repo):
        try:
            walker.push(oid)
        except Exception:
            continue

    # ---- Lane algorithm with strict pass-through continuity ----
    # `lanes[i]` = the sha that lane i is waiting to draw next, or None (free).
    # CONTRACT (per the continuity requirement): every lane active when entering
    # a row appears in `incoming`, and every such lane emits exactly one edge to
    # its position in the next row's state — so a transiting branch is always
    # both an incoming line and a {from:L,to:L} edge. No segment can dead-end.
    lanes: list[str | None] = []
    nodes = []

    def first_free(state):
        for i, v in enumerate(state):
            if v is None:
                return i
        state.append(None)
        return len(state) - 1

    for c in walker:
        sha = str(c.id)
        parents = [str(p) for p in c.parent_ids]

        # snapshot the state entering this row
        before = list(lanes)

        # the commit's lane = leftmost lane already waiting for it, else a new one
        waiting = [i for i, v in enumerate(before) if v == sha]
        if waiting:
            my_lane = waiting[0]
        else:
            my_lane = first_free(lanes)
            before = list(lanes)            # include the freshly opened lane
            lanes[my_lane] = sha
            before[my_lane] = sha

        # build the AFTER state by routing parents
        after = list(before)
        # lanes that were waiting for this sha all converge into the commit:
        # the chosen lane continues to the first parent; the rest are freed.
        for i in waiting:
            after[i] = None
        if my_lane < len(after):
            after[my_lane] = None

        first_parent_lane = my_lane
        if parents:
            p0 = parents[0]
            # if the first parent is ALREADY carried by another lane, the commit's
            # own lane merges into that lane (don't create a parallel duplicate).
            existing0 = next((i for i, v in enumerate(after) if v == p0), None)
            if existing0 is not None:
                first_parent_lane = existing0          # own lane ends, flows left
            else:
                after[my_lane] = p0                    # own lane continues
                first_parent_lane = my_lane

        merge_targets = []
        for p in parents[1:]:
            tgt = next((i for i, v in enumerate(after) if v == p), None)
            if tgt is None:
                tgt = first_free(after)
            after[tgt] = p
            merge_targets.append(tgt)

        # commit the new state
        lanes = list(after)

        # incoming = every lane active when entering the row
        incoming = [i for i, v in enumerate(before) if v is not None]

        # edges: every incoming lane maps to where it continues (or the commit).
        edges = []
        for i, v in enumerate(before):
            if v is None:
                continue
            if i == my_lane:
                if parents:
                    edges.append({"from": my_lane, "to": first_parent_lane, "kind": "commit"})
            elif v == sha:
                edges.append({"from": i, "to": my_lane, "kind": "converge"})
            else:
                to = next((j for j, w in enumerate(after) if w == v), None)
                if to is not None:
                    edges.append({"from": i, "to": to, "kind": "pass"})
        for tgt, p in zip(merge_targets, parents[1:]):
            edges.append({"from": my_lane, "to": tgt, "kind": "merge"})

        msg = c.message.strip()
        nodes.append({
            "sha": sha, "short": sha[:8],
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
                c.commit_time, timezone(timedelta(minutes=c.commit_time_offset))).isoformat(),
            "refs": refs.get(sha, []),
            "width": len([v for v in lanes if v is not None]) or 1,
        })

    # Authoritative continuity: a row's incoming lanes are EXACTLY the
    # destination lanes of the previous row's edges. A brand-new branch tip
    # (a commit whose lane has nothing above it) is flagged via `tip` so the
    # renderer draws only the lower half of its lane, not a phantom top half.
    for i, n in enumerate(nodes):
        if i == 0:
            n["incoming"] = []
        else:
            n["incoming"] = sorted(set(e["to"] for e in nodes[i - 1]["edges"]))
        n["tip"] = n["lane"] not in n["incoming"]

    # widest point across the whole graph
    max_w = 1
    for n in nodes:
        used = set(n["incoming"]) | {e["from"] for e in n["edges"]} | {e["to"] for e in n["edges"]} | {n["lane"]}
        max_w = max(max_w, (max(used) + 1) if used else 1)

    return {
        "nodes": nodes,
        "branches": sorted(repo.branches.local),
        "remote_branches": sorted(repo.branches.remote),
        "head": head,
        "returned": len(nodes),
        "lanes": max_w,
        "has_more": False,
    }
