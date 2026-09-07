from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pygit2
from pygit2.enums import ObjectType, SortMode

from .models import Commit, FileChange, RepoActivity

ALL_BRANCHES = "__all__"


class AuthorCount(TypedDict):
    name: str
    email: str
    commits: int


_STATUS = {
    pygit2.GIT_DELTA_ADDED: "added",
    pygit2.GIT_DELTA_DELETED: "deleted",
    pygit2.GIT_DELTA_MODIFIED: "modified",
    pygit2.GIT_DELTA_RENAMED: "renamed",
    pygit2.GIT_DELTA_COPIED: "copied",
}


def _commit_datetime(c: pygit2.Commit) -> datetime:
    tz = timezone(timedelta(minutes=c.commit_time_offset))
    return datetime.fromtimestamp(c.commit_time, tz)


_DIFF_CACHE: OrderedDict[tuple[str, str], tuple[FileChange, ...]] = OrderedDict()
_DIFF_CACHE_MAX = 20_000


def clear_diff_cache() -> None:
    _DIFF_CACHE.clear()


def diff_cache_info() -> dict[str, int]:
    return {"entries": len(_DIFF_CACHE), "max": _DIFF_CACHE_MAX}


def _compute_file_changes(
    repo: pygit2.Repository, commit: pygit2.Commit
) -> tuple[FileChange, ...]:
    if commit.parents:
        diff = repo.diff(commit.parents[0], commit)
    else:
        diff = commit.tree.diff_to_tree(swap=True)

    changes: list[FileChange] = []
    for patch in diff:
        if patch is None:
            continue
        d = patch.delta
        changes.append(
            FileChange(
                path=d.new_file.path,
                additions=patch.line_stats[1],
                deletions=patch.line_stats[2],
                status=_STATUS.get(d.status, "modified"),
            )
        )
    return tuple(changes)


def _file_changes(repo: pygit2.Repository, commit: pygit2.Commit) -> list[FileChange]:
    key = (repo.path, str(commit.id))
    cached = _DIFF_CACHE.get(key)
    if cached is None:
        cached = _compute_file_changes(repo, commit)
        _DIFF_CACHE[key] = cached
        while len(_DIFF_CACHE) > _DIFF_CACHE_MAX:
            _DIFF_CACHE.popitem(last=False)
    else:
        _DIFF_CACHE.move_to_end(key)
    return list(cached)


def _diff_excerpt(
    repo: pygit2.Repository, commit: pygit2.Commit, max_chars: int
) -> str:
    if commit.parents:
        diff = repo.diff(commit.parents[0], commit)
    else:
        diff = commit.tree.diff_to_tree(swap=True)

    parts: list[str] = []
    total = 0
    for patch in diff:
        if patch is None:
            continue
        text = patch.text or ""
        if not text:
            continue
        room = max_chars - total
        if len(text) > room:
            if room > 200:
                parts.append(text[:room] + "\n... [diff truncated] ...")
            break
        parts.append(text)
        total += len(text)
    return "".join(parts)


def diff_excerpts(
    repo_path: str | os.PathLike[str], shas: list[str], max_chars_each: int = 1500
) -> dict[str, str]:
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        return {}
    repo = pygit2.Repository(discovered)
    out: dict[str, str] = {}
    for sha in shas:
        try:
            obj = repo.revparse_single(sha)
        except (KeyError, ValueError):
            continue
        if obj.type != ObjectType.COMMIT:
            continue
        commit = obj.peel(pygit2.Commit)
        text = _diff_excerpt(repo, commit, max_chars_each)
        if text:
            out[sha] = text
    return out


def collect_activity(
    repo_path: str | os.PathLike[str],
    since: datetime,
    until: datetime | None = None,
    branch: str | None = None,
    name: str | None = None,
    authors: list[str] | None = None,
) -> RepoActivity:
    repo_path = Path(repo_path).resolve()
    repo_name = name or repo_path.name
    discovered = pygit2.discover_repository(str(repo_path))
    if discovered is None:
        raise ValueError(f"No git repository found at {repo_path}")
    repo = pygit2.Repository(discovered)

    until = until or datetime.now(timezone.utc)
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)

    author_set = {a.lower() for a in authors} if authors else None

    all_branches = branch == ALL_BRANCHES
    if all_branches:
        if repo.head_is_unborn:
            return RepoActivity(repo_name, str(repo_path), since, until, [])
        tips: list[pygit2.Oid | str] = []
        for bname in repo.branches.local:
            try:
                tips.append(repo.branches[bname].target)
            except KeyError:
                continue
        if not tips:
            tips = [repo.head.target]
        branch_label = None
    elif branch:
        try:
            target = repo.branches[branch]
        except KeyError:
            raise ValueError(f"Branch '{branch}' not found")
        tips = [target.target]
        branch_label = branch
    else:
        if repo.head_is_unborn:
            return RepoActivity(repo_name, str(repo_path), since, until, [])
        tips = [repo.head.target]
        branch_label = repo.head.shorthand if not repo.head_is_detached else None

    walker = repo.walk(tips[0], SortMode.TIME)
    for extra in tips[1:]:
        walker.push(extra)

    commits: list[Commit] = []
    for c in walker:
        when = _commit_datetime(c)
        if when > until:
            continue
        if when < since:
            if all_branches:
                continue
            break
        if author_set is not None:
            name_l = (c.author.name or "").lower()
            email_l = (c.author.email or "").lower()
            if name_l not in author_set and email_l not in author_set:
                continue
        message = c.message.strip()
        first, _, rest = message.partition("\n")
        commits.append(
            Commit(
                sha=str(c.id),
                author_name=c.author.name,
                author_email=c.author.email,
                when=when,
                summary=first,
                body=rest.strip(),
                files=_file_changes(repo, c),
                branch=branch_label,
                is_merge=len(c.parents) > 1,
            )
        )

    return RepoActivity(
        repo_name=repo_name,
        repo_path=str(repo_path),
        since=since,
        until=until,
        commits=commits,
    )


def list_authors(
    repo_path: str | os.PathLike[str], since: datetime, until: datetime | None = None
) -> list[AuthorCount]:
    act = collect_activity(repo_path, since, until, branch=ALL_BRANCHES)
    counts: dict[str, AuthorCount] = {}
    for c in act.commits:
        key = c.author_email or c.author_name
        if key not in counts:
            counts[key] = {"name": c.author_name, "email": c.author_email, "commits": 0}
        counts[key]["commits"] += 1
    return sorted(counts.values(), key=lambda a: a["commits"], reverse=True)


def discover_repos(root: str | os.PathLike[str], max_depth: int = 3) -> list[Path]:
    root = Path(root).resolve()
    found: list[Path] = []
    root_depth = len(root.parts)
    for dirpath, dirnames, _ in os.walk(root):
        p = Path(dirpath)
        if len(p.parts) - root_depth > max_depth:
            dirnames[:] = []
            continue
        if ".git" in dirnames:
            found.append(p)
            dirnames[:] = []
    return found
