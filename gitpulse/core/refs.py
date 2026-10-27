
from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

import pygit2

ALL_BRANCHES = "__all__"
HEAD = "HEAD"

BranchSpec = str | Sequence[str] | None


class RefList(TypedDict):
    local: list[str]
    remote: list[str]
    tags: list[str]
    head: str | None
    head_sha: str | None


def _commit_id(repo: pygit2.Repository, target: pygit2.Oid | str) -> pygit2.Oid | None:
    try:
        return repo[target].peel(pygit2.Commit).id
    except Exception:
        return None


def _ref_commit(repo: pygit2.Repository, name: str) -> pygit2.Commit | None:
    try:
        return repo.references[name].peel(pygit2.Commit)
    except Exception:
        return None


def all_tips(repo: pygit2.Repository) -> list[pygit2.Oid]:
    oids: list[pygit2.Oid] = []
    seen: set[pygit2.Oid] = set()

    def add(oid: pygit2.Oid | None) -> None:
        if oid is not None and oid not in seen:
            seen.add(oid)
            oids.append(oid)

    if not repo.head_is_unborn:
        add(_commit_id(repo, repo.head.target))
    for name in repo.references:
        if not name.startswith(("refs/heads/", "refs/remotes/", "refs/tags/")):
            continue
        try:
            if repo.references[name].type == pygit2.enums.ReferenceType.SYMBOLIC:
                continue
        except Exception:
            continue
        commit = _ref_commit(repo, name)
        add(commit.id if commit is not None else None)
    return oids


def resolve(repo: pygit2.Repository, name: str) -> pygit2.Oid:
    if name == HEAD:
        if repo.head_is_unborn:
            raise ValueError("HEAD has no commit yet")
        oid = _commit_id(repo, repo.head.target)
        if oid is not None:
            return oid
    for full in (f"refs/heads/{name}", f"refs/remotes/{name}", f"refs/tags/{name}"):
        if full in repo.references:
            commit = _ref_commit(repo, full)
            if commit is not None:
                return commit.id
    raise ValueError(f"Branch '{name}' not found")


def tips_for(repo: pygit2.Repository, spec: BranchSpec) -> list[pygit2.Oid]:
    if spec is None:
        return [] if repo.head_is_unborn else [resolve(repo, HEAD)]
    names = [spec] if isinstance(spec, str) else list(spec)
    if not names or ALL_BRANCHES in names:
        return all_tips(repo)
    tips: list[pygit2.Oid] = []
    for n in names:
        oid = resolve(repo, n)
        if oid not in tips:
            tips.append(oid)
    return tips


def label_for(repo: pygit2.Repository, spec: BranchSpec) -> str | None:
    if spec is None:
        if repo.head_is_unborn or repo.head_is_detached:
            return None
        return repo.head.shorthand
    names = [spec] if isinstance(spec, str) else list(spec)
    if len(names) == 1 and names[0] not in (ALL_BRANCHES, HEAD):
        return names[0]
    return None


def list_refs(repo: pygit2.Repository) -> RefList:
    def recency(name: str) -> int:
        commit = _ref_commit(repo, name)
        return commit.commit_time if commit is not None else 0

    heads = [n for n in repo.references if n.startswith("refs/heads/")]
    remotes = [
        n
        for n in repo.references
        if n.startswith("refs/remotes/") and not n.endswith("/HEAD")
    ]
    tags = [n for n in repo.references if n.startswith("refs/tags/")]
    head = None
    if not repo.head_is_unborn and not repo.head_is_detached:
        head = repo.head.shorthand
    head_sha = None if repo.head_is_unborn else str(repo.head.target)
    return {
        "local": [
            n[len("refs/heads/") :] for n in sorted(heads, key=recency, reverse=True)
        ],
        "remote": sorted(n[len("refs/remotes/") :] for n in remotes),
        "tags": sorted(
            (n[len("refs/tags/") :] for n in tags),
            key=lambda t: recency(f"refs/tags/{t}"),
            reverse=True,
        ),
        "head": head,
        "head_sha": head_sha,
    }
