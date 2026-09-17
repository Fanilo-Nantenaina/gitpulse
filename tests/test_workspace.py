from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gitpulse.core import workspace
from gitpulse.core.models import RepoActivity

WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 12, 31, tzinfo=timezone.utc)


def _git(repo: Path, *args: str, author: str | None = None, date: str = "") -> None:
    env_name, env_mail = (author or "Alice <alice@example.com>").split(" <")
    env = {
        "GIT_AUTHOR_NAME": env_name,
        "GIT_AUTHOR_EMAIL": env_mail.rstrip(">"),
        "GIT_COMMITTER_NAME": env_name,
        "GIT_COMMITTER_EMAIL": env_mail.rstrip(">"),
    }
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    import os

    full = dict(os.environ)
    full.update(env)
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=full,
        check=False,
    )


def _make_repo(parent: Path, name: str) -> Path:
    repo = parent / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "master")
    return repo


def _commit(repo: Path, message: str, author: str, date: str, content: str) -> None:
    (repo / "README.md").write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message, author=author, date=date)


@pytest.fixture
def parent(tmp_path: Path) -> Path:
    root = tmp_path / "work"

    alpha = _make_repo(root, "alpha")
    _commit(
        alpha,
        "feat: alpha one",
        "Alice <alice@example.com>",
        "2026-06-01T10:00:00",
        "a1",
    )
    _commit(
        alpha,
        "feat: alpha two",
        "Alice <alice@example.com>",
        "2026-06-02T10:00:00",
        "a2",
    )

    beta = _make_repo(root, "beta")
    _commit(beta, "fix: beta one", "Bob <bob@example.com>", "2026-06-03T10:00:00", "b1")

    gamma = _make_repo(root, "gamma")
    _commit(
        gamma,
        "chore: gamma old",
        "Alice <alice@example.com>",
        "2020-01-01T10:00:00",
        "g1",
    )

    (root / "not-a-repo").mkdir()
    return root


def _collect(
    root: Path,
    authors: list[str] | None = None,
    author_scope: workspace.AuthorScope = "window",
) -> RepoActivity:
    activity, _ = workspace.collect(
        root,
        WINDOW_START,
        WINDOW_END,
        authors=authors,
        author_scope=author_scope,
    )
    return activity


def test_discovery_finds_each_repo_and_skips_plain_folders(parent: Path) -> None:
    names = [r.name for r in workspace.discover(parent)]
    assert names == ["alpha", "beta", "gamma"]


def test_is_workspace_distinguishes_parent_from_repo(parent: Path) -> None:
    assert workspace.is_workspace(parent) is True
    assert workspace.is_workspace(parent / "alpha") is False
    assert workspace.is_repo(parent / "alpha") is True


def test_collect_merges_commits_and_tags_each_with_its_repo(parent: Path) -> None:
    activity = _collect(parent)
    assert activity.is_workspace is True
    assert activity.commit_count == 3
    assert {c.repo for c in activity.commits} == {"alpha", "beta"}
    assert activity.commits_per_repo == {"alpha": 2, "beta": 1, "gamma": 0}
    assert activity.active_repos == ["alpha", "beta"]
    assert activity.commits == sorted(
        activity.commits, key=lambda c: c.when, reverse=True
    )


def test_collect_on_a_plain_repo_still_works(parent: Path) -> None:
    activity = _collect(parent / "alpha")
    assert activity.is_workspace is False
    assert activity.commit_count == 2
    assert all(c.repo == "" for c in activity.commits)


def test_identical_paths_across_repos_are_not_conflated(parent: Path) -> None:
    activity = _collect(parent)
    assert activity.files_touched == 2
    assert set(activity.hotspots) == {"alpha/README.md", "beta/README.md"}


def test_authors_are_aggregated_across_repos(parent: Path) -> None:
    authors = workspace.list_workspace_authors(parent, WINDOW_START, WINDOW_END)
    by_name = {a["name"]: a for a in authors}
    assert set(by_name) == {"Alice", "Bob"}
    assert by_name["Alice"]["commits"] == 2
    assert by_name["Alice"]["repos"] == ["alpha"]
    assert by_name["Bob"]["repos"] == ["beta"]


def test_author_filter_window_scope_keeps_only_repos_active_in_window(
    parent: Path,
) -> None:
    activity = _collect(parent, authors=["alice@example.com"], author_scope="window")
    assert [r.name for r in activity.repos] == ["alpha"]
    assert activity.commit_count == 2


def test_author_filter_all_scope_keeps_repos_they_ever_touched(parent: Path) -> None:
    activity = _collect(parent, authors=["alice@example.com"], author_scope="all")
    assert [r.name for r in activity.repos] == ["alpha", "gamma"]
    assert activity.commits_per_repo == {"alpha": 2, "gamma": 0}
    assert activity.commit_count == 2


@pytest.mark.parametrize("scope", ["window", "all"])
def test_author_filter_excludes_other_peoples_repos(
    parent: Path, scope: workspace.AuthorScope
) -> None:
    activity = _collect(parent, authors=["alice@example.com"], author_scope=scope)
    assert "beta" not in [r.name for r in activity.repos]


def test_empty_parent_folder_is_reported_clearly(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="No git repositories"):
        workspace.collect_workspace(tmp_path / "empty", WINDOW_START, WINDOW_END)


def test_listing_authors_of_a_repoless_folder_is_reported_clearly(
    tmp_path: Path,
) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError, match="No git repositories"):
        workspace.list_workspace_authors(tmp_path / "empty", WINDOW_START, WINDOW_END)


def _wreck(repo: Path) -> None:
    (repo / ".git").rename(repo / ".git-moved-aside")
    (repo / ".git").write_text("gitdir: nowhere\n", encoding="utf-8")


@pytest.mark.parametrize("scope", ["window", "all"])
def test_unreadable_repos_are_reported_not_dropped(
    parent: Path, scope: workspace.AuthorScope
) -> None:
    _wreck(parent / "beta")
    _, failures = workspace.collect(
        parent,
        WINDOW_START,
        WINDOW_END,
        authors=["alice@example.com"],
        author_scope=scope,
    )
    assert [f["name"] for f in failures] == ["beta"]
    assert failures[0]["error"]
