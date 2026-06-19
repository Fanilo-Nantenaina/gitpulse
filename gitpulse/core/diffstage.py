from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pygit2


@dataclass
class FileDelta:
    path: str
    status: str  # "added" | "modified" | "deleted" | "renamed" | "untracked"
    additions: int = 0
    deletions: int = 0


@dataclass
class WorkingChanges:
    repo_name: str
    scope: str  # "staged" | "all"
    files: list[FileDelta] = field(default_factory=list)
    diff_text: str = ""
    truncated: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(self.files)

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)


_STATUS_MAP = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "typechange",
    "?": "untracked",
}


def _run(args: list[str], cwd: str) -> str:
    proc = subprocess.run(
        ["git", "-C", cwd, *args], capture_output=True, text=True, timeout=30
    )
    return proc.stdout if proc.returncode == 0 else ""


def collect_working_changes(
    repo_path, scope: str = "all", max_diff_chars: int = 24000
) -> WorkingChanges:
    """Gather uncommitted changes (staged only, or everything) plus the diff."""
    discovered = pygit2.discover_repository(str(Path(repo_path).resolve()))
    if discovered is None:
        raise ValueError("No git repository found")
    repo = pygit2.Repository(discovered)
    workdir = repo.workdir
    if workdir is None:
        raise ValueError("Bare repository has no working tree")
    workdir = workdir.rstrip("/\\")
    name = Path(workdir).name

    staged_only = scope == "staged"
    has_head = not repo.head_is_unborn

    # numstat for per-file +/- counts.
    # - staged scope: diff --cached (index vs HEAD)
    # - all scope:    diff HEAD   (working tree vs HEAD = staged + unstaged)
    if staged_only:
        numstat_args = ["diff", "--cached", "--numstat"]
        name_args = ["diff", "--cached", "--name-status"]
        diff_args = ["diff", "--cached"]
    elif has_head:
        numstat_args = ["diff", "HEAD", "--numstat"]
        name_args = ["diff", "HEAD", "--name-status"]
        diff_args = ["diff", "HEAD"]
    else:
        # no commits yet: compare staged index against empty tree
        numstat_args = ["diff", "--cached", "--numstat"]
        name_args = ["diff", "--cached", "--name-status"]
        diff_args = ["diff", "--cached"]

    files: dict[str, FileDelta] = {}
    for line in _run(name_args, workdir).splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code = parts[0][0]
        path = parts[-1]
        files[path] = FileDelta(path=path, status=_STATUS_MAP.get(code, "modified"))

    for line in _run(numstat_args, workdir).splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add, dele, path = parts[0], parts[1], parts[-1]
        fd = files.get(path)
        if fd:
            fd.additions = int(add) if add.isdigit() else 0
            fd.deletions = int(dele) if dele.isdigit() else 0

    diff_text = _run(diff_args, workdir)

    # include untracked files when scope is "all"
    if not staged_only:
        untracked = _run(["ls-files", "--others", "--exclude-standard"], workdir)
        for path in untracked.splitlines():
            if path and path not in files:
                files[path] = FileDelta(path=path, status="untracked")
                # show a short preview of new file content in the diff
                full = Path(workdir) / path
                try:
                    if full.is_file() and full.stat().st_size < 8000:
                        body = full.read_text(encoding="utf-8", errors="replace")
                        diff_text += f"\n--- new file: {path} ---\n{body}\n"
                except OSError:
                    pass

    truncated = len(diff_text) > max_diff_chars
    if truncated:
        diff_text = diff_text[:max_diff_chars] + "\n... [diff truncated] ..."

    return WorkingChanges(
        repo_name=name,
        scope=scope,
        files=sorted(files.values(), key=lambda f: f.path),
        diff_text=diff_text,
        truncated=truncated,
    )
