from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from gitrepo import Repo

from gitpulse.core import commitinfo, gitgraph
from gitpulse.web.server import app

client = TestClient(app, base_url="http://127.0.0.1:8420")


def _write(repo: Repo, name: str, text: str) -> None:
    (repo.path / name).write_text(text, encoding="utf-8")
    repo("add", "-A")


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    r = Repo(tmp_path / "r")
    _write(r, "a.txt", "one\ntwo\n")
    _write(r, "old.txt", "".join(f"line {i}\n" for i in range(20)))
    r.commit("root")
    return r


def test_root_commit_lists_every_file(repo: Repo) -> None:
    info = commitinfo.files(repo.path, repo("rev-parse", "HEAD"))
    assert info["base"] is None and info["parents"] == []
    assert [(f["path"], f["status"], f["additions"]) for f in info["files"]] == [
        ("a.txt", "added", 2),
        ("old.txt", "added", 20),
    ]


def test_modified_and_renamed_files(repo: Repo) -> None:
    _write(repo, "a.txt", "one\nTWO\nthree\n")
    repo("mv", "old.txt", "new.txt")
    sha = repo.commit("edit")
    info = commitinfo.files(repo.path, sha)
    by_path = {f["path"]: f for f in info["files"]}
    assert by_path["a.txt"]["status"] == "modified"
    assert (by_path["a.txt"]["additions"], by_path["a.txt"]["deletions"]) == (2, 1)
    assert by_path["new.txt"]["status"] == "renamed"
    assert by_path["new.txt"]["old_path"] == "old.txt"
    patch = commitinfo.diff(repo.path, sha, "a.txt")["patch"]
    assert "-two" in patch and "+TWO" in patch and "+three" in patch


def test_merge_is_shown_against_its_first_parent(repo: Repo) -> None:
    repo("checkout", "-q", "-b", "feat")
    _write(repo, "feat.txt", "f\n")
    repo.commit("feat")
    repo("checkout", "-q", "main")
    _write(repo, "a.txt", "main\n")
    repo.commit("main work")
    sha = repo.merge("feat")
    info = commitinfo.files(repo.path, sha)
    assert info["is_merge"] and info["base"] == repo("rev-parse", "HEAD^1")
    assert [f["path"] for f in info["files"]] == ["feat.txt"]


def test_uncommitted_changes_include_untracked_files(repo: Repo) -> None:
    (repo.path / "a.txt").write_text("changed\n", encoding="utf-8")
    (repo.path / "new.txt").write_text("x\n", encoding="utf-8")
    info = commitinfo.files(repo.path, commitinfo.UNCOMMITTED)
    assert {f["path"]: f["status"] for f in info["files"]} == {
        "a.txt": "modified",
        "new.txt": "added",
    }


def test_bad_ids_are_rejected(repo: Repo) -> None:
    with pytest.raises(ValueError):
        commitinfo.files(repo.path, "HEAD~1; rm -rf /")
    with pytest.raises(ValueError):
        commitinfo.files(repo.path, "deadbeef" * 5)
    with pytest.raises(ValueError):
        commitinfo.diff(repo.path, repo("rev-parse", "HEAD"), "missing.txt")


def test_graph_has_an_uncommitted_row_above_head(repo: Repo) -> None:
    from test_gitgraph import graph_problems

    (repo.path / "a.txt").write_text("dirty\n", encoding="utf-8")
    g = gitgraph.graph(repo.path, uncommitted=True)
    top = g["nodes"][0]
    assert top["kind"] == "uncommitted" and g["uncommitted"] == 1
    assert top["parents"] == [g["head_sha"]]
    assert graph_problems(g) == []
    assert gitgraph.graph(repo.path)["nodes"][0]["kind"] == "commit"


def test_no_uncommitted_row_when_head_is_filtered_out(repo: Repo) -> None:
    repo("branch", "other")
    repo.commit("main only")
    (repo.path / "a.txt").write_text("dirty\n", encoding="utf-8")
    g = gitgraph.graph(repo.path, branches=["other"], uncommitted=True)
    assert g["uncommitted"] == 0
    assert all(n["kind"] == "commit" for n in g["nodes"])


def test_later_pages_refuse_a_changed_history(repo: Repo) -> None:
    for i in range(5):
        repo.commit(f"c{i}")
    first = gitgraph.graph(repo.path, limit=2)
    second = gitgraph.graph(repo.path, limit=2, offset=2, version=first["version"])
    assert second["incoming"] == first["nodes"][-1]["segments"]
    repo.commit("new")
    with pytest.raises(gitgraph.GraphChanged):
        gitgraph.graph(repo.path, limit=2, offset=4, version=first["version"])
    r = client.post(
        "/api/graph",
        json={
            "path": str(repo.path),
            "limit": 2,
            "offset": 4,
            "version": first["version"],
        },
    )
    assert r.status_code == 409


def test_commit_endpoints(repo: Repo) -> None:
    _write(repo, "a.txt", "x\n")
    sha = repo.commit("edit")
    files = client.post("/api/commit/files", json={"path": str(repo.path), "sha": sha})
    assert files.status_code == 200
    assert [f["path"] for f in files.json()["files"]] == ["a.txt"]
    d = client.post(
        "/api/commit/diff", json={"path": str(repo.path), "sha": sha, "file": "a.txt"}
    )
    assert "+x" in d.json()["patch"]
    bad = client.post("/api/commit/files", json={"path": str(repo.path), "sha": "zz"})
    assert bad.status_code == 400


def test_branches_endpoint_lists_tags_and_head(repo: Repo) -> None:
    repo("tag", "v1")
    r = client.post("/api/branches", json={"path": str(repo.path)}).json()
    assert r["local"] == ["main"] and r["tags"] == ["v1"]
    assert r["head"] == "main" and r["head_sha"] == repo("rev-parse", "HEAD")


def test_scope_request_branch_semantics(repo: Repo) -> None:
    repo("checkout", "-q", "-b", "side")
    repo.commit("side work")
    repo("checkout", "-q", "main")
    body = {"path": str(repo.path), "when": "all"}

    def logged(**extra: object) -> set[str]:
        r = client.post("/api/log", json={**body, **extra})
        assert r.status_code == 200, r.json()
        return {c["summary"] for c in r.json()["activity"]["commits"]}

    assert logged(branches=[]) == {"root", "side work"}
    assert logged(branches=["HEAD"]) == {"root"}
    assert logged(branches=["side"]) == {"root", "side work"}
    assert logged() == {"root"}
