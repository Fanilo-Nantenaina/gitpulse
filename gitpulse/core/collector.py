from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pygit2

from .models import Commit, FileChange, RepoActivity

ALL_BRANCHES = "__all__"

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


def _file_changes(repo: pygit2.Repository, commit: pygit2.Commit) -> list[FileChange]:
    if commit.parents:
        parent_tree = commit.parents[0].tree
        diff = repo.diff(parent_tree, commit.tree)
    else:
        diff = commit.tree.diff_to_tree(swap=True)

    changes: list[FileChange] = []
    for patch in diff:
        d = patch.delta
        changes.append(
            FileChange(
                path=d.new_file.path,
                additions=patch.line_stats[1],
                deletions=patch.line_stats[2],
                status=_STATUS.get(d.status, "modified"),
            )
        )
    return changes


def collect_activity(
    repo_path: str | os.PathLike,
    since: datetime,
    until: Optional[datetime] = None,
    branch: Optional[str] = None,
    name: Optional[str] = None,
    authors: Optional[list[str]] = None,
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
        tips = []
        for bname in repo.branches.local:
            b = repo.branches.get(bname)
            if b is not None:
                tips.append(b.target)
        if not tips:
            tips = [repo.head.target]
        branch_label = None
    elif branch:
        target = repo.branches.get(branch)
        if target is None:
            raise ValueError(f"Branch '{branch}' not found")
        tips = [target.target]
        branch_label = branch
    else:
        if repo.head_is_unborn:
            return RepoActivity(repo_name, str(repo_path), since, until, [])
        tips = [repo.head.target]
        branch_label = repo.head.shorthand if not repo.head_is_detached else None

    walker = repo.walk(tips[0], pygit2.GIT_SORT_TIME)
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
    repo_path: str | os.PathLike, since: datetime, until: Optional[datetime] = None
) -> list[dict]:
    act = collect_activity(repo_path, since, until, branch=ALL_BRANCHES)
    counts: dict[str, dict] = {}
    for c in act.commits:
        key = c.author_email or c.author_name
        if key not in counts:
            counts[key] = {"name": c.author_name, "email": c.author_email, "commits": 0}
        counts[key]["commits"] += 1
    return sorted(counts.values(), key=lambda a: a["commits"], reverse=True)


def discover_repos(root: str | os.PathLike, max_depth: int = 3) -> list[Path]:
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
