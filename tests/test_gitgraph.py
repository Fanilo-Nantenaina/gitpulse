from __future__ import annotations

import random
import subprocess
from itertools import pairwise
from pathlib import Path

import pytest
from gitrepo import Repo, _git

from gitpulse.core.gitgraph import Graph, graph


def graph_problems(g: Graph) -> list[str]:
    nodes = g["nodes"]
    idx = {n["sha"]: i for i, n in enumerate(nodes)}
    probs: list[str] = []
    if len(idx) != len(nodes):
        probs.append("a commit is listed twice")
    for i, n in enumerate(nodes):
        lane, segs = n["lane"], n["segments"]
        for p in n["parents"]:
            if p in idx and idx[p] <= i:
                probs.append(f"row {i}: parent {p[:7]} is drawn above its child")
        passing = [s["from"] for s in segs if s["from"] != lane]
        if len(passing) != len(set(passing)):
            probs.append(f"row {i}: two lines share a column")
        for s in segs:
            if s["from"] != lane and s["to"] > s["from"]:
                probs.append(f"row {i}: a passing line moves right")
        if i + 1 == len(nodes):
            continue
        nxt = nodes[i + 1]
        early = [s["to"] for s in segs if s["to"] != nxt["lane"]]
        if len(early) != len(set(early)):
            probs.append(f"row {i}: two lines merge before reaching a commit")
        for s in segs:
            if s["to"] == nxt["lane"]:
                continue
            cont = [t for t in nxt["segments"] if t["from"] == s["to"]]
            if len(cont) != 1:
                probs.append(f"row {i + 1}: a line stops between commits")
            elif cont[0]["color"] != s["color"]:
                probs.append(f"row {i + 1}: a line changes colour")
        arriving = {s["to"] for s in segs}
        for t in nxt["segments"]:
            if t["from"] != nxt["lane"] and t["from"] not in arriving:
                probs.append(f"row {i + 1}: a line starts from nowhere")

    for i, n in enumerate(nodes):
        reached: list[str | None] = []
        for s in (s for s in n["segments"] if s["from"] == n["lane"]):
            r, x = i, s["to"]
            while True:
                r += 1
                if r >= len(nodes):
                    reached.append(None)
                    break
                if x == nodes[r]["lane"]:
                    reached.append(nodes[r]["sha"])
                    break
                x = next(t["to"] for t in nodes[r]["segments"] if t["from"] == x)
        want = sorted(p for p in n["parents"] if p in idx)
        got = sorted(x for x in reached if x is not None)
        if want != got:
            probs.append(f"row {i} {n['summary']!r}: lines reach {got}, parents {want}")
        dangling = len(reached) - len(got)
        if dangling and not g["has_more"] and i < len(nodes) - 1:
            probs.append(f"row {i} {n['summary']!r}: a line goes nowhere")
    return probs


def rev_list(repo: Repo, *args: str) -> list[str]:
    return repo("rev-list", *args).split()


def assert_faithful(repo: Repo, g: Graph) -> None:
    assert graph_problems(g) == []
    expected = rev_list(repo, "--branches", "--remotes", "--tags", "HEAD")
    assert sorted(n["sha"] for n in g["nodes"]) == sorted(expected)
    by_sha = {n["sha"]: n for n in g["nodes"]}
    for sha in expected:
        assert by_sha[sha]["parents"] == repo("rev-parse", f"{sha}^@").split()


def lanes_of(g: Graph, shas: list[str]) -> set[tuple[int, int]]:
    by_sha = {n["sha"]: n for n in g["nodes"]}
    return {(by_sha[s]["lane"], by_sha[s]["color"]) for s in shas}


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    return Repo(tmp_path / "r")


def test_graph_linear_single_lane(linear_repo: Path) -> None:
    g = graph(linear_repo)
    assert g["returned"] == 5
    assert g["lanes"] == 1
    assert all(n["lane"] == 0 for n in g["nodes"])
    assert graph_problems(g) == []


def test_graph_branched_has_multiple_lanes(branched_repo: Path) -> None:
    g = graph(branched_repo)
    assert g["lanes"] >= 2
    assert len({n["lane"] for n in g["nodes"]}) >= 2
    assert graph_problems(g) == []


def test_graph_head_marked(branched_repo: Path) -> None:
    g = graph(branched_repo)
    assert g["head"] == "master"
    flagged = [
        (n["sha"], r["name"]) for n in g["nodes"] for r in n["refs"] if r["head"]
    ]
    assert flagged == [(g["head_sha"], "master")]


def test_graph_merge_commit_flagged(branched_repo: Path) -> None:
    g = graph(branched_repo)
    merges = [n for n in g["nodes"] if n["is_merge"]]
    assert merges, "expected at least one merge commit"
    assert all(len(n["parents"]) == 2 for n in merges)


def test_graph_empty_on_unborn(tmp_path: Path) -> None:
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    g = graph(repo)
    assert g["returned"] == 0
    assert g["nodes"] == []
    assert g["has_more"] is False


def test_graph_pagination_limit(linear_repo: Path) -> None:
    g = graph(linear_repo, limit=2)
    assert g["returned"] == 2
    assert g["has_more"] is True
    assert g["nodes"][-1]["segments"] == [{"from": 0, "to": 0, "color": 0}]


def test_graph_pagination_exact_end_has_no_more(linear_repo: Path) -> None:
    assert graph(linear_repo, limit=5)["has_more"] is False


def test_graph_pagination_offset(linear_repo: Path) -> None:
    full = graph(linear_repo)
    sliced = graph(linear_repo, limit=2, offset=1)
    assert sliced["returned"] == 2
    assert [n["sha"] for n in sliced["nodes"]] == [n["sha"] for n in full["nodes"][1:3]]


def test_graph_branch_filter(branched_repo: Path) -> None:
    g = graph(branched_repo, branch="master", all_commits=False)
    assert g["returned"] > 0
    assert "master" in g["branches"]
    assert graph_problems(g) == []


def test_graph_unknown_branch_is_an_error(branched_repo: Path) -> None:
    with pytest.raises(ValueError):
        graph(branched_repo, branch="nope", all_commits=False)


def test_branch_lines_join_at_the_fork_commit(repo: Repo) -> None:
    base = repo.commit("base")
    repo("checkout", "-q", "-b", "side")
    repo.commit("side-1")
    repo("checkout", "-q", "--orphan", "other")
    for i in range(3):
        repo.commit(f"other-{i}")
    repo("checkout", "-q", "main")
    repo.commit("main-1")
    g = graph(repo.path)
    assert_faithful(repo, g)
    nodes = g["nodes"]
    base_row = next(i for i, n in enumerate(nodes) if n["sha"] == base)
    above = nodes[base_row - 1]["segments"]
    assert sorted(s["to"] for s in above).count(nodes[base_row]["lane"]) == 2


def test_first_parent_chain_keeps_its_lane_and_colour(repo: Repo) -> None:
    repo.commit("base")
    repo("checkout", "-q", "-b", "b")
    repo.commit("b1")
    repo("checkout", "-q", "main")
    a1 = repo.commit("a1")
    repo.merge("b", msg="merge b into main")
    repo("checkout", "-q", "b")
    repo.merge(a1, msg="merge a1 into b")
    repo("checkout", "-q", "main")
    repo.commit("a2")
    repo("checkout", "-q", "b")
    repo.commit("b2")
    repo("checkout", "-q", "main")
    repo.merge("b", msg="final")
    g = graph(repo.path)
    assert_faithful(repo, g)
    main_chain = rev_list(repo, "--first-parent", "main")
    assert lanes_of(g, main_chain) == {(0, 0)}
    b_chain = rev_list(repo, "--first-parent", "b")[:-1]
    assert len(lanes_of(g, b_chain)) == 1
    assert lanes_of(g, b_chain) != {(0, 0)}


def test_merges_of_several_active_branches(repo: Repo) -> None:
    repo.commit("base")
    for b in ("a", "b", "c"):
        repo("branch", b)
    for step in range(4):
        for b in ("a", "b", "c", "main"):
            repo("checkout", "-q", b)
            repo.commit(f"{b}{step}")
        if step == 1:
            repo("checkout", "-q", "b")
            repo.merge("main", msg="back-merge main into b")
        if step == 2:
            repo("checkout", "-q", "main")
            repo.merge("a", msg="merge a")
    repo("checkout", "-q", "main")
    repo.merge("c", msg="merge c")
    g = graph(repo.path)
    assert_faithful(repo, g)
    assert lanes_of(g, rev_list(repo, "--first-parent", "main")) == {(0, 0)}


def test_octopus_merge_draws_one_line_per_parent(repo: Repo) -> None:
    repo.commit("base")
    for b in ("p", "q", "s"):
        repo("checkout", "-q", "-b", b, "main")
        repo.commit(f"{b}1")
    repo("checkout", "-q", "main")
    repo.commit("m1")
    octo = repo.merge("p", "q", "s", msg="octopus")
    g = graph(repo.path)
    assert_faithful(repo, g)
    node = g["nodes"][0]
    assert node["sha"] == octo
    starts = [s for s in node["segments"] if s["from"] == node["lane"]]
    assert len(starts) == 4
    assert len({s["color"] for s in starts}) == 4


def test_roots_and_unrelated_histories(repo: Repo) -> None:
    repo.commit("main-root")
    repo("checkout", "-q", "--orphan", "docs")
    repo.commit("docs-root")
    repo("checkout", "-q", "--orphan", "island")
    repo.commit("island-root")
    repo("checkout", "-q", "main")
    repo.merge("docs", "--allow-unrelated-histories", msg="merge docs")
    g = graph(repo.path)
    assert_faithful(repo, g)
    roots = [n for n in g["nodes"] if not n["parents"]]
    assert len(roots) == 3
    for n in roots:
        assert [s for s in n["segments"] if s["from"] == n["lane"]] == []


def test_identical_and_skewed_dates_keep_parents_below(repo: Repo) -> None:
    repo.commit("base", hour=10)
    repo.commit("older than its parent", hour=2)
    repo("checkout", "-q", "-b", "x")
    repo.commit("x1", hour=5)
    repo.commit("x2", hour=5)
    repo("checkout", "-q", "main")
    repo.commit("m1", hour=5)
    repo.merge("x", msg="merge x", hour=1)
    assert_faithful(repo, graph(repo.path))


def test_several_refs_on_one_commit(repo: Repo) -> None:
    repo.commit("one")
    repo.commit("two")
    repo("branch", "alias")
    repo("tag", "v1")
    repo("tag", "-a", "v1-annotated", "-m", "annotated")
    g = graph(repo.path)
    refs = {(r["kind"], r["name"]) for r in g["nodes"][0]["refs"]}
    assert refs == {
        ("local", "main"),
        ("local", "alias"),
        ("tag", "v1"),
        ("tag", "v1-annotated"),
    }
    assert g["returned"] == 2


def test_commit_only_reachable_from_a_tag_is_shown(repo: Repo) -> None:
    repo.commit("base")
    repo("checkout", "-q", "-b", "gone")
    released = repo.commit("released from a deleted branch")
    repo("tag", "v0.9")
    repo("checkout", "-q", "main")
    repo("branch", "-D", "gone")
    repo.commit("main-2")
    g = graph(repo.path)
    assert_faithful(repo, g)
    node = next(n for n in g["nodes"] if n["sha"] == released)
    assert node["refs"] == [{"name": "v0.9", "kind": "tag", "head": False}]


def test_tag_on_a_tree_does_not_hide_other_tags(repo: Repo) -> None:
    repo.commit("base")
    repo("tag", "a-tree-tag", repo("rev-parse", "HEAD^{tree}"))
    repo.commit("second")
    repo("tag", "z-release")
    g = graph(repo.path)
    assert ("tag", "z-release") in {
        (r["kind"], r["name"]) for r in g["nodes"][0]["refs"]
    }


def test_detached_head_is_labelled(repo: Repo) -> None:
    repo.commit("base")
    repo.commit("two")
    repo("checkout", "-q", "--detach", "HEAD~1")
    work = repo.commit("detached work")
    g = graph(repo.path)
    assert_faithful(repo, g)
    assert g["head"] is None and g["head_sha"] == work
    node = next(n for n in g["nodes"] if n["sha"] == work)
    assert node["refs"] == [{"name": "HEAD", "kind": "head", "head": True}]
    main = next(r for n in g["nodes"] for r in n["refs"] if r["name"] == "main")
    assert main["head"] is False


def test_local_and_remote_branches(tmp_path: Path) -> None:
    up = Repo(tmp_path / "up")
    up.commit("u1")
    up("checkout", "-q", "-b", "dev")
    up.commit("u-dev")
    up("checkout", "-q", "main")
    up.commit("u2")
    subprocess.run(
        ["git", "clone", "-q", str(up.path), str(tmp_path / "clone")], check=True
    )
    clone = Repo.__new__(Repo)
    clone.path, clone.hour = tmp_path / "clone", 10
    clone.commit("local ahead")
    g = graph(clone.path)
    assert_faithful(clone, g)
    assert g["remote_branches"] == ["origin/dev", "origin/main"]
    kinds = {(r["kind"], r["name"]) for n in g["nodes"] for r in n["refs"]}
    assert {
        ("local", "main"),
        ("remote", "origin/main"),
        ("remote", "origin/dev"),
    } <= kinds
    assert graph(clone.path, branch="origin/dev", all_commits=False)["returned"] == 2


def test_shallow_clone_boundary(tmp_path: Path) -> None:
    up = Repo(tmp_path / "up")
    for i in range(4):
        up.commit(f"c{i}")
    subprocess.run(
        ["git", "clone", "-q", "--depth", "2", up.path.as_uri(), str(tmp_path / "s")],
        check=True,
    )
    g = graph(tmp_path / "s")
    assert g["returned"] == 2
    assert graph_problems(g) == []
    assert g["nodes"][-1]["segments"] == []


def _dense(repo: Repo, n: int, seed: int) -> None:
    rnd = random.Random(seed)
    repo.commit("root")
    branches = ["main"]
    for i in range(n):
        x = rnd.random()
        if x < 0.12 and len(branches) < 8:
            branches.append(f"b{i}")
            repo("branch", branches[-1], rnd.choice(branches[:-1]))
        elif x < 0.25 and len(branches) > 1:
            dst = rnd.choice(branches)
            src = rnd.choice([b for b in branches if b != dst])
            repo("checkout", "-q", dst)
            repo.merge(src, msg=f"merge {src} into {dst}")
            if src != "main" and rnd.random() < 0.5:
                repo("branch", "-D", src)
                branches.remove(src)
        else:
            b = rnd.choice(branches)
            repo("checkout", "-q", b)
            repo.commit(f"{b}-{i}")
    repo("checkout", "-q", "main")


@pytest.mark.parametrize("seed", [3, 7])
def test_dense_history_is_faithful(repo: Repo, seed: int) -> None:
    _dense(repo, 120, seed)
    g = graph(repo.path)
    assert_faithful(repo, g)
    top = g["nodes"][0]["sha"]
    assert lanes_of(g, rev_list(repo, "--first-parent", top)) == {(0, 0)}


def test_pages_concatenate_to_the_full_graph(repo: Repo) -> None:
    _dense(repo, 60, 11)
    full = graph(repo.path)
    pages: list[Graph] = []
    offset = 0
    while True:
        page = graph(repo.path, limit=17, offset=offset)
        pages.append(page)
        offset += page["returned"]
        if not page["has_more"]:
            break
    assert [n for p in pages for n in p["nodes"]] == full["nodes"]
    for prev, page in pairwise(pages):
        assert page["incoming"] == prev["nodes"][-1]["segments"]


def test_author_and_commit_dates_are_both_reported(repo: Repo) -> None:
    repo.commit("x", hour=3)
    _git(repo.path, "commit", "-q", "--amend", "--allow-empty", "--no-edit")
    n = graph(repo.path)["nodes"][0]
    assert n["author_when"].startswith("2026-01-01T03:00")
    assert n["when"] != n["author_when"]
