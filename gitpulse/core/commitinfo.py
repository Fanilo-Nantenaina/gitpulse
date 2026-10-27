
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pygit2
from pygit2.enums import DeltaStatus, DiffOption

UNCOMMITTED = "uncommitted"
MAX_PATCH_CHARS = 200_000

_STATUS = {
    DeltaStatus.ADDED: "added",
    DeltaStatus.DELETED: "deleted",
    DeltaStatus.MODIFIED: "modified",
    DeltaStatus.RENAMED: "renamed",
    DeltaStatus.COPIED: "copied",
    DeltaStatus.TYPECHANGE: "typechange",
    DeltaStatus.UNTRACKED: "added",
}


class ChangedFile(TypedDict):
    path: str
    old_path: str | None
    status: str
    additions: int
    deletions: int
    binary: bool


class CommitFiles(TypedDict):
    sha: str
    message: str
    author: str
    email: str
    committer: str
    committer_email: str
    author_when: str
    when: str
    parents: list[str]
    base: str | None
    is_merge: bool
    files: list[ChangedFile]
    additions: int
    deletions: int


class FileDiff(TypedDict):
    sha: str
    path: str
    patch: str
    binary: bool
    truncated: bool


def _open(repo_path: str | os.PathLike[str]) -> pygit2.Repository:
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        raise ValueError("No git repository found")
    return pygit2.Repository(discovered)


def _commit(repo: pygit2.Repository, sha: str) -> pygit2.Commit:
    if not re.fullmatch(r"[0-9a-fA-F]{4,64}", sha):
        raise ValueError(f"Not a commit id: {sha!r}")
    try:
        return repo.revparse_single(sha).peel(pygit2.Commit)
    except (KeyError, ValueError, pygit2.GitError):
        raise ValueError(f"Commit {sha[:12]} not found")


def _diff(
    repo: pygit2.Repository, sha: str
) -> tuple[pygit2.Diff, list[str], str | None]:
    if sha == UNCOMMITTED:
        if repo.is_bare or repo.head_is_unborn:
            raise ValueError("No working tree to compare")
        head = repo.head.peel(pygit2.Commit)
        flags = (
            DiffOption.INCLUDE_UNTRACKED
            | DiffOption.RECURSE_UNTRACKED_DIRS
            | DiffOption.SHOW_UNTRACKED_CONTENT
        )
        diff = head.tree.diff_to_workdir(flags=flags)
        return diff, [str(head.id)], str(head.id)
    commit = _commit(repo, sha)
    parents = [str(p) for p in commit.parent_ids]
    if commit.parents:
        diff = repo.diff(commit.parents[0], commit)
        base: str | None = parents[0]
    else:
        diff = commit.tree.diff_to_tree(swap=True)
        base = None
    diff.find_similar()
    return diff, parents, base


def _when(t: int, offset: int) -> str:
    return datetime.fromtimestamp(t, timezone(timedelta(minutes=offset))).isoformat()


def files(repo_path: str | os.PathLike[str], sha: str) -> CommitFiles:
    repo = _open(repo_path)
    diff, parents, base = _diff(repo, sha)
    if sha == UNCOMMITTED:
        now = datetime.now().astimezone().isoformat()
        message, author, email, committer, committer_email = "", "", "", "", ""
        author_when = when = now
    else:
        c = _commit(repo, sha)
        message = c.message.strip()
        author, email = c.author.name, c.author.email
        committer, committer_email = c.committer.name, c.committer.email
        author_when = _when(c.author.time, c.author.offset)
        when = _when(c.commit_time, c.commit_time_offset)
    out: list[ChangedFile] = []
    for patch in diff:
        if patch is None:
            continue
        d = patch.delta
        _, adds, dels = patch.line_stats
        out.append(
            {
                "path": d.new_file.path,
                "old_path": d.old_file.path
                if d.old_file.path != d.new_file.path
                else None,
                "status": _STATUS.get(d.status, "modified"),
                "additions": adds,
                "deletions": dels,
                "binary": bool(d.is_binary),
            }
        )
    out.sort(key=lambda f: f["path"].lower())
    return {
        "sha": sha if sha == UNCOMMITTED else str(_commit(repo, sha).id),
        "message": message,
        "author": author,
        "email": email,
        "committer": committer,
        "committer_email": committer_email,
        "author_when": author_when,
        "when": when,
        "parents": parents,
        "base": base,
        "is_merge": len(parents) > 1,
        "files": out,
        "additions": sum(f["additions"] for f in out),
        "deletions": sum(f["deletions"] for f in out),
    }


def diff(repo_path: str | os.PathLike[str], sha: str, path: str) -> FileDiff:
    repo = _open(repo_path)
    d, _, _ = _diff(repo, sha)
    for patch in d:
        if patch is None:
            continue
        if path not in (patch.delta.new_file.path, patch.delta.old_file.path):
            continue
        text = "" if patch.delta.is_binary else (patch.text or "")
        return {
            "sha": sha,
            "path": path,
            "patch": text[:MAX_PATCH_CHARS],
            "binary": bool(patch.delta.is_binary),
            "truncated": len(text) > MAX_PATCH_CHARS,
        }
    raise ValueError(f"{path} is not changed by {sha[:12]}")
