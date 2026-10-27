from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal, TypedDict

import pygit2

from .collector import ALL_BRANCHES, BranchSpec, collect_activity
from .models import Commit, RepoActivity, RepoRef
from .sources import DEFAULT_DEPTH, RepoFailure, RepoSet, discover, expand, is_repo

__all__ = [
    "DEFAULT_DEPTH",
    "AuthorScope",
    "RepoFailure",
    "WorkspaceAuthor",
    "collect",
    "collect_refs",
    "collect_workspace",
    "discover",
    "is_repo",
    "is_workspace",
    "list_workspace_authors",
]

AuthorScope = Literal["window", "all"]


class WorkspaceAuthor(TypedDict):
    name: str
    email: str
    commits: int
    repos: list[str]


def is_workspace(path: str | os.PathLike[str], max_depth: int = DEFAULT_DEPTH) -> bool:
    text = str(path)
    if text.startswith("@"):
        return True
    if "://" in text:
        return False
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
    branch: BranchSpec = None,
    name: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScope = "window",
    max_depth: int = DEFAULT_DEPTH,
) -> tuple[RepoActivity, list[RepoFailure]]:
    repo_set = expand(root, max_depth)
    return collect_refs(
        repo_set,
        since,
        until,
        branch=branch,
        name=name,
        authors=authors,
        author_scope=author_scope,
    )


def collect_refs(
    repo_set: RepoSet,
    since: datetime,
    until: datetime | None = None,
    branch: BranchSpec = None,
    name: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScope = "window",
) -> tuple[RepoActivity, list[RepoFailure]]:
    refs = repo_set.refs
    until = until or datetime.now(timezone.utc)
    keep, failures = _repos_for_authors(refs, authors, author_scope, until)
    failures = [*repo_set.failures, *failures]

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
        repo_name=name or repo_set.name,
        repo_path=repo_set.root,
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
    branch: BranchSpec = None,
    name: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScope = "window",
    max_depth: int = DEFAULT_DEPTH,
    refresh: bool = True,
    insecure: bool = False,
) -> tuple[RepoActivity, list[RepoFailure]]:
    text = str(source)
    if not text.startswith("@") and "://" not in text and is_repo(source):
        activity = collect_activity(
            source, since, until, branch=branch, name=name, authors=authors
        )
        return activity, []
    repo_set = expand(source, max_depth, refresh=refresh, insecure=insecure)
    if repo_set.single:
        ref = repo_set.refs[0]
        activity = collect_activity(
            ref.path,
            since,
            until,
            branch=branch,
            name=name or ref.name,
            authors=authors,
        )
        return activity, []
    return collect_refs(
        repo_set,
        since,
        until,
        branch=branch,
        name=name,
        authors=authors,
        author_scope=author_scope,
    )


def list_workspace_authors(
    root: str | os.PathLike[str],
    since: datetime,
    until: datetime | None = None,
    max_depth: int = DEFAULT_DEPTH,
) -> list[WorkspaceAuthor]:
    refs = expand(root, max_depth).refs
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
