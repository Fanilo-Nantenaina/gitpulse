
from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from gitrepo import Repo, _git

from gitpulse.core import refs
from gitpulse.core.collector import ALL_BRANCHES, collect_activity
from gitpulse.core.gitgraph import graph
from gitpulse.core.timesheet import report

EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def clone(tmp_path: Path) -> Repo:
    up = Repo(tmp_path / "up")
    up.commit("u1")
    up("checkout", "-q", "-b", "remote-only")
    up.commit("only upstream")
    up("checkout", "-q", "main")
    up.commit("u2")
    subprocess.run(
        ["git", "clone", "-q", str(up.path), str(tmp_path / "c")], check=True
    )
    c = Repo.__new__(Repo)
    c.path, c.hour = tmp_path / "c", 20
    c("checkout", "-q", "-b", "local-only")
    c.commit("only local")
    c("checkout", "-q", "-b", "gone")
    c.commit("tagged")
    c("tag", "v1")
    c("checkout", "-q", "main")
    c("branch", "-D", "gone")
    c("checkout", "-q", "--detach")
    c.commit("detached")
    return c


def test_all_branches_means_the_same_commits_in_every_view(clone: Repo) -> None:
    expected = set(
        clone(
            "log", "--format=%s", "--branches", "--remotes", "--tags", "HEAD"
        ).splitlines()
    )
    act = collect_activity(clone.path, EPOCH, branch=ALL_BRANCHES)
    assert {c.summary for c in act.commits} == expected
    assert {n["summary"] for n in graph(clone.path)["nodes"]} == expected
    assert {"only upstream", "only local", "tagged", "detached"} <= expected


@pytest.mark.parametrize(
    ("spec", "summaries"),
    [
        (None, {"detached", "u2", "u1"}),
        (["HEAD"], {"detached", "u2", "u1"}),
        (["origin/remote-only"], {"only upstream", "u1"}),
        (["v1"], {"tagged", "only local", "u2", "u1"}),
        (
            ["local-only", "origin/remote-only"],
            {"only local", "only upstream", "u2", "u1"},
        ),
    ],
)
def test_branch_selection(
    clone: Repo, spec: list[str] | None, summaries: set[str]
) -> None:
    act = collect_activity(clone.path, EPOCH, branch=spec)
    assert {c.summary for c in act.commits} == summaries
    if spec is not None:
        assert {
            n["summary"] for n in graph(clone.path, branches=spec)["nodes"]
        } == summaries


def test_unknown_branch_is_reported(clone: Repo) -> None:
    with pytest.raises(ValueError, match="nope"):
        collect_activity(clone.path, EPOCH, branch=["nope"])


def test_list_refs(clone: Repo) -> None:
    import pygit2

    r = refs.list_refs(pygit2.Repository(str(clone.path)))
    assert set(r["local"]) == {"main", "local-only"}
    assert r["remote"] == ["origin/main", "origin/remote-only"]
    assert r["tags"] == ["v1"]
    assert r["head"] is None and r["head_sha"] == clone("rev-parse", "HEAD")


def test_period_uses_the_author_date_after_a_rebase(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "r")
    repo.commit("base", hour=0)
    for day in (3, 4):
        _git(
            repo.path,
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            f"work {day}",
            date=f"2026-01-{day:02d}T09:00:00+00:00",
            committer_date="2026-02-10T18:00:00+00:00",
        )
    jan = collect_activity(
        repo.path,
        datetime(2026, 1, 2, tzinfo=timezone.utc),
        datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    assert [c.summary for c in jan.commits] == ["work 4", "work 3"]
    feb = collect_activity(
        repo.path,
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        datetime(2026, 2, 28, tzinfo=timezone.utc),
    )
    assert feb.commits == []
    assert report(jan, 120, 30).days == 2


def test_clock_skew_does_not_cut_the_walk(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "r")
    repo.commit("old", hour=0)
    _git(
        repo.path,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "in window",
        date="2026-01-05T12:00:00+00:00",
    )
    _git(
        repo.path,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "skewed",
        date="2026-01-05T09:00:00+00:00",
    )
    act = collect_activity(
        repo.path,
        datetime(2026, 1, 5, 10, tzinfo=timezone.utc),
        datetime(2026, 1, 6, tzinfo=timezone.utc),
    )
    assert [c.summary for c in act.commits] == ["in window"]
