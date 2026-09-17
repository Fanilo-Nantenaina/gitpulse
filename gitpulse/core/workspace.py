from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict

import pygit2

from .collector import ALL_BRANCHES, collect_activity
from .models import Commit, RepoActivity, RepoRef

DEFAULT_DEPTH = 3

AuthorScope = Literal["window", "all"]


class WorkspaceAuthor(TypedDict):
    name: str
    email: str
    commits: int
    repos: list[str]


class RepoFailure(TypedDict):
    name: str
    path: str
    error: str


def is_repo(path: str | os.PathLike[str]) -> bool:
    return pygit2.discover_repository(str(Path(path).resolve())) is not None


def discover(
    root: str | os.PathLike[str], max_depth: int = DEFAULT_DEPTH
) -> list[RepoRef]:
    root_path = Path(root).resolve()
    found: list[RepoRef] = []
    root_depth = len(root_path.parts)
    for dirpath, dirnames, _ in os.walk(root_path):
        p = Path(dirpath)
        if len(p.parts) - root_depth > max_depth:
            dirnames[:] = []
            continue
        if ".git" in dirnames or (p / ".git").exists():
            found.append(RepoRef(name=p.name, path=str(p)))
            dirnames[:] = []
    return sorted(found, key=lambda r: r.name.lower())


def is_workspace(path: str | os.PathLike[str], max_depth: int = DEFAULT_DEPTH) -> bool:
    return not is_repo(path) and bool(discover(path, max_depth))


def _tag(commits: list[Commit], ref: RepoRef) -> list[Commit]:
    for c in commits:
        c.repo = ref.name
        c.repo_path = ref.path
    return commits


def collect_workspace(
    root: str | os.PathLike[str],
    since: datetime,
    until: datetime | None = None,
    branch: str | None = None,
    name: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScope = "window",
    max_depth: int = DEFAULT_DEPTH,
) -> tuple[RepoActivity, list[RepoFailure]]:
    root_path = Path(root).resolve()
    refs = discover(root_path, max_depth)
    if not refs:
        raise ValueError(f"No git repositories found under {root_path}")

    until = until or datetime.now(timezone.utc)
    keep, failures = _repos_for_authors(refs, authors, author_scope, until)

    commits: list[Commit] = []
    contributed: set[str] = set()
    for ref in keep:
        try:
            act = collect_activity(
                ref.path,
                since,
                until,
                branch=branch,
                name=ref.name,
                authors=authors,
            )
        except (ValueError, pygit2.GitError) as e:
            failures.append({"name": ref.name, "path": ref.path, "error": str(e)})
            continue
        if act.commits:
            contributed.add(ref.name)
        commits.extend(_tag(act.commits, ref))

    if authors and author_scope == "window":
        keep = [r for r in keep if r.name in contributed]

    commits.sort(key=lambda c: c.when, reverse=True)
    activity = RepoActivity(
        repo_name=name or root_path.name,
        repo_path=str(root_path),
        since=since,
        until=until,
        commits=commits,
        repos=keep,
    )
    return activity, failures


def _repos_for_authors(
    refs: list[RepoRef],
    authors: list[str] | None,
    scope: AuthorScope,
    until: datetime,
) -> tuple[list[RepoRef], list[RepoFailure]]:
    if not authors or scope == "window":
        return refs, []
    epoch = datetime.fromtimestamp(0, timezone.utc)
    keep: list[RepoRef] = []
    failures: list[RepoFailure] = []
    for ref in refs:
        try:
            ever = collect_activity(
                ref.path,
                epoch,
                until,
                branch=ALL_BRANCHES,
                name=ref.name,
                authors=authors,
            )
        except (ValueError, pygit2.GitError) as e:
            failures.append({"name": ref.name, "path": ref.path, "error": str(e)})
            continue
        if ever.commits:
            keep.append(ref)
    return keep, failures


def collect(
    source: str | os.PathLike[str],
    since: datetime,
    until: datetime | None = None,
    branch: str | None = None,
    name: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScope = "window",
    max_depth: int = DEFAULT_DEPTH,
) -> tuple[RepoActivity, list[RepoFailure]]:
    if is_repo(source):
        activity = collect_activity(
            source, since, until, branch=branch, name=name, authors=authors
        )
        return activity, []
    return collect_workspace(
        source,
        since,
        until,
        branch=branch,
        name=name,
        authors=authors,
        author_scope=author_scope,
        max_depth=max_depth,
    )


def list_workspace_authors(
    root: str | os.PathLike[str],
    since: datetime,
    until: datetime | None = None,
    max_depth: int = DEFAULT_DEPTH,
) -> list[WorkspaceAuthor]:
    refs = discover(root, max_depth)
    if not refs:
        raise ValueError(f"No git repositories found under {Path(root).resolve()}")
    until = until or datetime.now(timezone.utc)
    by_key: dict[str, WorkspaceAuthor] = {}
    for ref in refs:
        try:
            act = collect_activity(
                ref.path, since, until, branch=ALL_BRANCHES, name=ref.name
            )
        except (ValueError, pygit2.GitError):
            continue
        for c in act.commits:
            key = (c.author_email or c.author_name).lower()
            entry = by_key.get(key)
            if entry is None:
                entry = WorkspaceAuthor(
                    name=c.author_name,
                    email=c.author_email,
                    commits=0,
                    repos=[],
                )
                by_key[key] = entry
            entry["commits"] += 1
            if ref.name not in entry["repos"]:
                entry["repos"].append(ref.name)
    return sorted(by_key.values(), key=lambda a: a["commits"], reverse=True)
