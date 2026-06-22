from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args, env_extra=None):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Tester",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "Tester",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _commit(repo: Path, message: str, date: str):
    env = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message, env_extra=env)


@pytest.fixture
def linear_repo(tmp_path):
    """A simple linear repo: 5 commits on master, one per day."""
    repo = tmp_path / "linear"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "master")
    for i in range(1, 6):
        (repo / "file.txt").write_text("\n".join(str(n) for n in range(i)))
        _commit(repo, f"commit {i}", f"2026-01-0{i}T10:00:00")
    return repo


@pytest.fixture
def branched_repo(tmp_path):
    """A repo with a real branch and a merge, for graph lane tests.

    master:  base -> work -> (merge feature) -> after
    feature: a1 -> a2  (branched from base, merged into master)
    """
    repo = tmp_path / "branched"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "master")
    (repo / "f").write_text("1")
    _commit(repo, "base", "2026-02-01T10:00:00")
    (repo / "f").write_text("1\n2")
    _commit(repo, "work", "2026-02-02T10:00:00")
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "g").write_text("a")
    _commit(repo, "feat a1", "2026-02-03T10:00:00")
    (repo / "g").write_text("a\nb")
    _commit(repo, "feat a2", "2026-02-04T10:00:00")
    _git(repo, "checkout", "-q", "master")
    (repo / "f").write_text("1\n2\n3")
    _commit(repo, "more work", "2026-02-05T10:00:00")
    _git(
        repo,
        "merge",
        "-q",
        "--no-ff",
        "feature",
        "-m",
        "merge feature",
        env_extra={
            "GIT_AUTHOR_DATE": "2026-02-06T10:00:00",
            "GIT_COMMITTER_DATE": "2026-02-06T10:00:00",
        },
    )
    return repo


@pytest.fixture
def dirty_repo(tmp_path):
    """A repo with one commit plus uncommitted changes (staged + unstaged + untracked)."""
    repo = tmp_path / "dirty"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "master")
    (repo / "app.py").write_text("def hello():\n    pass\n")
    _commit(repo, "init", "2026-03-01T10:00:00")
    (repo / "app.py").write_text("def hello():\n    return 'world'\n")
    _git(repo, "add", "app.py")
    (repo / "config.py").write_text("KEY = None\n")
    (repo / "notes.md").write_text("# notes\n")
    return repo
