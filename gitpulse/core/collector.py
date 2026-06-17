from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pygit2

from .models import Commit, FileChange, RepoActivity

# pygit2 delta status codes -> human labels
_STATUS = {
    pygit2.GIT_DELTA_ADDED: "added",
    pygit2.GIT_DELTA_DELETED: "deleted",
    pygit2.GIT_DELTA_MODIFIED: "modified",
    pygit2.GIT_DELTA_RENAMED: "renamed",
    pygit2.GIT_DELTA_COPIED: "copied",
}


def _commit_datetime(c: pygit2.Commit) -> datetime:
    """pygit2 stores commit time as epoch + tz offset (minutes)."""
    tz = timezone(timedelta(minutes=c.commit_time_offset))
    return datetime.fromtimestamp(c.commit_time, tz)


def _file_changes(repo: pygit2.Repository, commit: pygit2.Commit) -> list[FileChange]:
    """Diff a commit against its first parent (or empty tree for root commit)."""
    if commit.parents:
        parent_tree = commit.parents[0].tree
        diff = repo.diff(parent_tree, commit.tree)
    else:
        diff = commit.tree.diff_to_tree(swap=True)  # root commit vs empty

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
) -> RepoActivity:
    """Walk a repo's history and return commits within [since, until].

    `branch` defaults to the currently checked-out HEAD.
    """
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

    # Resolve the starting reference
    if branch:
        target = repo.branches.get(branch)
        if target is None:
            raise ValueError(f"Branch '{branch}' not found")
        head = target.target
    else:
        if repo.head_is_unborn:
            return RepoActivity(repo_name, str(repo_path), since, until, [])
        head = repo.head.target
        branch = repo.head.shorthand if not repo.head_is_detached else None

    commits: list[Commit] = []
    for c in repo.walk(head, pygit2.GIT_SORT_TIME):
        when = _commit_datetime(c)
        if when > until:
            continue
        if when < since:
            break  # SORT_TIME is descending, so we're done
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
                branch=branch,
            )
        )

    return RepoActivity(
        repo_name=repo_name,
        repo_path=str(repo_path),
        since=since,
        until=until,
        commits=commits,
    )


def discover_repos(root: str | os.PathLike, max_depth: int = 3) -> list[Path]:
    """Find all git repos under `root` for the multi-repo dashboard."""
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
            dirnames[:] = []  # don't descend into a repo's subdirs
    return found
