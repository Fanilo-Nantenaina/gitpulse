from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gitpulse.ai import summarizer
from gitpulse.core import standup, trends, workspace
from gitpulse.core.stats import compute_stats

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
WINDOW_START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _git(repo: Path, *args: str, author: str = "Alice", date: str = "") -> None:
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": f"{author.lower()}@example.com",
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": f"{author.lower()}@example.com",
        }
    )
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    for name, author, days in (("alpha", "Alice", 3), ("beta", "Bob", 2)):
        repo = root / name
        repo.mkdir(parents=True)
        _git(repo, "init", "-q")
        _git(repo, "branch", "-M", "master")
        for i in range(days):
            (repo / "src.py").write_text(f"value = {i}\n" * (i + 1), encoding="utf-8")
            when = (NOW - timedelta(days=i + 1)).strftime("%Y-%m-%dT%H:%M:%S")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-m", f"feat: {name} {i}", author=author, date=when)
    return root


def test_payload_frames_the_workspace_and_tags_each_commit(
    workspace_root: Path,
) -> None:
    activity, _ = workspace.collect(workspace_root, WINDOW_START, NOW)
    payload = summarizer._build_payload(activity)

    assert "NOT one project" in payload
    assert "alpha (3)" in payload and "beta (2)" in payload
    commit_lines = [ln for ln in payload.splitlines() if ln.startswith("- [")]
    assert commit_lines
    assert all(("(alpha)" in ln or "(beta)" in ln) for ln in commit_lines)


def test_single_repo_payload_is_unchanged(workspace_root: Path) -> None:
    activity, _ = workspace.collect(workspace_root / "alpha", WINDOW_START, NOW)
    payload = summarizer._build_payload(activity)

    assert payload.startswith("Repository: alpha")
    assert "Workspace:" not in payload
    assert "NOT one project" not in payload
    assert "(alpha)" not in payload


def test_local_fallback_groups_by_repo_in_a_workspace(workspace_root: Path) -> None:
    activity, _ = workspace.collect(workspace_root, WINDOW_START, NOW)
    summ = summarizer._local_fallback(activity, "en")

    assert {t["title"] for t in summ.themes} == {"alpha", "beta"}
    assert "repo(s)" in summ.headline


def test_stats_break_down_per_repo(workspace_root: Path) -> None:
    activity, _ = workspace.collect(workspace_root, WINDOW_START, NOW)
    stats = compute_stats(activity)

    rows = {r["name"]: r for r in stats["repos"]}
    assert rows["alpha"]["commits"] == 3
    assert rows["beta"]["commits"] == 2
    assert rows["alpha"]["authors"] == 1
    assert {f["path"] for f in stats["top_files"]} == {"alpha/src.py", "beta/src.py"}


def test_stats_have_no_repo_rows_for_a_single_repo(workspace_root: Path) -> None:
    activity, _ = workspace.collect(workspace_root / "alpha", WINDOW_START, NOW)
    assert compute_stats(activity)["repos"] == []


def test_compare_works_across_a_workspace(workspace_root: Path) -> None:
    cmp = trends.compare(workspace_root, timedelta(days=7), periods_back=2, now=NOW)

    assert cmp.current.is_workspace is True
    assert {r.name for r in cmp.current.repos} == {"alpha", "beta"}
    assert {m.name: m.current for m in cmp.metrics}["Commits"] == 5


def test_standup_reports_state_for_every_repo(workspace_root: Path) -> None:
    ctx = standup.gather(workspace_root, now=NOW)

    assert ctx.yesterday.is_workspace is True
    assert {s.name for s in ctx.repos} == {"alpha", "beta"}
    assert all(s.current_branch == "master" for s in ctx.repos)
    assert ctx.current_branch is None
    assert ctx.uncommitted == []


def test_standup_on_a_single_repo_keeps_the_flat_shape(workspace_root: Path) -> None:
    ctx = standup.gather(workspace_root / "alpha", now=NOW)

    assert ctx.yesterday.is_workspace is False
    assert ctx.repos == []
    assert ctx.current_branch == "master"
