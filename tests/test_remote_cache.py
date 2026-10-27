from __future__ import annotations

from pathlib import Path

import pytest
from gitrepo import Repo, _git

from gitpulse.core import remote as R
from gitpulse.core.collector import ALL_BRANCHES, collect_activity
from gitpulse.core.gitgraph import graph


def _refs(repo: Path) -> dict[str, str]:
    out = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    return dict(line.split() for line in out.splitlines())


def _mirrored(upstream: Repo) -> dict[str, str]:
    return {
        name: sha
        for name, sha in _refs(upstream.path).items()
        if name.startswith(("refs/heads/", "refs/tags/"))
    }


@pytest.fixture
def upstream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Repo:
    monkeypatch.setenv("GITPULSE_CACHE_DIR", str(tmp_path / "cache"))
    up = Repo(tmp_path / "up")
    up.commit("u1")
    up("branch", "dev")
    up("branch", "doomed")
    up("tag", "v1")
    return up


@pytest.mark.parametrize("clone", ["pygit2", "cli"])
def test_cache_mirrors_branches_after_clone_and_refresh(
    upstream: Repo, clone: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if clone == "cli":

        def no_libgit2_clone(*a: object, **k: object) -> bool:
            return False

        monkeypatch.setattr(R, "_clone_pygit2", no_libgit2_clone)
    url = upstream.path.as_uri()
    dest = R.sync_remote(url)
    assert _refs(dest) == _mirrored(upstream)

    upstream("checkout", "-q", "dev")
    upstream.commit("dev-2")
    upstream("checkout", "-q", "main")
    upstream.commit("u2")
    upstream("branch", "-D", "doomed")
    upstream("tag", "-d", "v1")
    upstream("tag", "v2")
    dest = R.sync_remote(url, refresh=True)
    assert _refs(dest) == _mirrored(upstream)

    g = graph(dest)
    labels = {(r["kind"], r["name"]) for n in g["nodes"] for r in n["refs"]}
    assert labels == {("local", "main"), ("local", "dev"), ("tag", "v2")}
    assert g["remote_branches"] == []


def test_all_branches_right_after_a_libgit2_clone(upstream: Repo) -> None:
    from datetime import datetime, timezone

    upstream("checkout", "-q", "dev")
    upstream.commit("only on dev")
    upstream("checkout", "-q", "main")
    dest = R.sync_remote(upstream.path.as_uri())
    act = collect_activity(
        dest, datetime(2000, 1, 1, tzinfo=timezone.utc), branch=ALL_BRANCHES
    )
    assert "only on dev" in {c.summary for c in act.commits}


def test_default_branch_renamed_upstream(upstream: Repo) -> None:
    url = upstream.path.as_uri()
    R.sync_remote(url)
    upstream("branch", "-m", "main", "trunk")
    upstream("symbolic-ref", "HEAD", "refs/heads/trunk")
    dest = R.sync_remote(url, refresh=True)
    g = graph(dest)
    assert g["returned"] == 1
    assert g["head"] in {"dev", "doomed", "trunk"}
