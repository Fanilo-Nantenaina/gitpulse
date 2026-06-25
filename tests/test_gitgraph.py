from __future__ import annotations

from gitpulse.core.gitgraph import graph


def test_graph_linear_single_lane(linear_repo):
    g = graph(linear_repo)
    assert g["returned"] == 5
    assert g["lanes"] == 1
    assert all(n["lane"] == 0 for n in g["nodes"])


def test_graph_branched_has_multiple_lanes(branched_repo):
    g = graph(branched_repo)
    assert g["lanes"] >= 2
    lanes_used = {n["lane"] for n in g["nodes"]}
    assert len(lanes_used) >= 2


def test_graph_head_marked(branched_repo):
    g = graph(branched_repo)
    assert g["head"] == "master"
    head_refs = [r for n in g["nodes"] for r in n["refs"] if r.get("head")]
    assert head_refs, "expected at least one ref flagged as head"


def test_graph_nodes_have_required_fields(branched_repo):
    g = graph(branched_repo)
    for n in g["nodes"]:
        assert "incoming" in n and "edges" in n
        assert "author" in n and "when" in n and "body" in n


def test_graph_continuity_no_dead_edges(branched_repo):
    g = graph(branched_repo)
    nodes = g["nodes"]
    for i, n in enumerate(nodes):
        if i < len(nodes) - 1:
            next_incoming = set(nodes[i + 1]["incoming"])
            for e in n["edges"]:
                assert e["to"] in next_incoming, (
                    f"row {i} edge to lane {e['to']} dead-ends "
                    f"(next incoming={sorted(next_incoming)})"
                )
        if i > 0:
            prev_tos = {e["to"] for e in nodes[i - 1]["edges"]}
            for lane in n["incoming"]:
                assert lane in prev_tos, (
                    f"row {i} incoming lane {lane} is unfed "
                    f"(prev edges to={sorted(prev_tos)})"
                )


def test_graph_merge_commit_flagged(branched_repo):
    g = graph(branched_repo)
    merges = [n for n in g["nodes"] if n["is_merge"]]
    assert merges, "expected at least one merge commit"
    assert any(len(n["parents"]) == 2 for n in merges)


def test_graph_empty_on_unborn(tmp_path):
    import subprocess

    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    g = graph(repo)
    assert g["returned"] == 0
    assert g["nodes"] == []
