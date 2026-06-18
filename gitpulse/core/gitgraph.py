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
            # skip symbolic refs like origin/HEAD that don't point at a commit directly
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

    # ---- Git Graph-style lane algorithm ----
    # `lanes` is the list of branch lines currently flowing downward; each entry
    # is the sha that lane is waiting to reach next (its next expected commit),
    # or None for a free slot. A lane is only ever created to carry a real
    # parent link, so there are no "whisker" edges that start and go nowhere.
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

        # Every lane waiting for THIS commit converges here. The leftmost such
        # lane becomes the commit's lane; the others are freed (they merge in).
        waiting = [i for i, v in enumerate(lanes) if v == sha]
        if waiting:
            my_lane = waiting[0]
        else:
            my_lane = first_free()
            lanes[my_lane] = sha

        # lanes entering this row from above (everything currently active)
        incoming = [i for i, v in enumerate(lanes) if v is not None]

        # edges leaving this row downward, computed against the lane state AFTER
        # we route parents. Each edge is {from, to, kind}.
        edges = []

        # Lanes that were waiting for this sha but aren't the chosen lane: they
        # terminate into the commit (converging branches). Free them now.
        for i in waiting:
            if i != my_lane:
                lanes[i] = None

        if parents:
            # first parent continues straight down the commit's own lane
            lanes[my_lane] = parents[0]
        else:
            lanes[my_lane] = None  # root commit: lane ends

        # extra parents (merge): reuse a lane already waiting for that parent,
        # else open ONE new lane for it — this is a real edge with a real target
        for p in parents[1:]:
            tgt = next((i for i, v in enumerate(lanes) if v == p), None)
            if tgt is None:
                tgt = first_free()
                lanes[tgt] = p
            edges.append({"from": my_lane, "to": tgt, "kind": "merge"})

        # the commit's own lane edge (if it continues)
        if parents:
            edges.append({"from": my_lane, "to": my_lane, "kind": "commit"})

        # every other still-active lane flows straight down to itself
        for i, v in enumerate(lanes):
            if v is not None and i != my_lane and not any(e["to"] == i for e in edges):
                # only if it was already active above (not a brand-new merge lane handled above)
                if i in incoming:
                    edges.append({"from": i, "to": i, "kind": "pass"})

        merge_targets = [e["to"] for e in edges if e["kind"] == "merge"]

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

    max_w = max((n["width"] for n in nodes), default=1)
    max_w = max(max_w, max((n["lane"] for n in nodes), default=0) + 1)

    # Post-pass: a row's incoming lanes are exactly the destination lanes of the
    # previous row's edges. This guarantees every top-half connects to a real
    # bottom-half above it — no floating/dead-ending segments.
    for i, n in enumerate(nodes):
        if i == 0:
            n["incoming"] = [n["lane"]]
        else:
            n["incoming"] = sorted(set(e["to"] for e in nodes[i - 1]["edges"]))
        # ensure the commit's own lane is always shown entering
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
