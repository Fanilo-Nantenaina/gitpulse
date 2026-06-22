from __future__ import annotations

from datetime import datetime, timezone

from gitpulse.core.collector import collect_activity


def _since(d="2026-01-01"):
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_collect_counts_all_commits(linear_repo):
    act = collect_activity(linear_repo, datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert act.commit_count == 5


def test_collect_respects_since_window(linear_repo):
    act = collect_activity(linear_repo, datetime(2026, 1, 3, tzinfo=timezone.utc))
    assert act.commit_count == 3


def test_collect_name_override(linear_repo):
    act = collect_activity(
        linear_repo, datetime(2025, 1, 1, tzinfo=timezone.utc), name="custom-name"
    )
    assert act.repo_name == "custom-name"


def test_collect_tracks_additions(linear_repo):
    act = collect_activity(linear_repo, datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert act.total_additions > 0
    assert act.files_touched >= 1


def test_collect_author_present(linear_repo):
    act = collect_activity(linear_repo, datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert "Tester" in act.authors


def test_collect_branched_repo_has_merge(branched_repo):
    act = collect_activity(branched_repo, datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert act.commit_count >= 6


from datetime import datetime, timezone
from gitpulse.core.collector import collect_activity, list_authors, ALL_BRANCHES

_SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)
_UNTIL = datetime(2026, 12, 31, tzinfo=timezone.utc)


def test_all_branches_includes_unmerged_feature(branched_repo):
    on_master = collect_activity(branched_repo, _SINCE, _UNTIL)
    all_b = collect_activity(branched_repo, _SINCE, _UNTIL, branch=ALL_BRANCHES)
    assert all_b.commit_count >= on_master.commit_count
    shas = [c.sha for c in all_b.commits]
    assert len(shas) == len(set(shas))


def test_all_branches_with_truly_unmerged_branch(tmp_path):
    import subprocess

    d = tmp_path / "r"
    d.mkdir()

    def g(*a, **k):
        env = dict(__import__("os").environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": "A",
                "GIT_AUTHOR_EMAIL": "a@x.com",
                "GIT_COMMITTER_NAME": "A",
                "GIT_COMMITTER_EMAIL": "a@x.com",
            }
        )
        env.update(k.get("env", {}))
        subprocess.run(["git", "-C", str(d), *a], env=env, capture_output=True)

    g("init", "-q")
    g("branch", "-M", "main")
    (d / "x").write_text("1")
    g("add", "-A")
    g(
        "commit",
        "-m",
        "on main",
        env={
            "GIT_AUTHOR_DATE": "2026-03-01T10:00:00",
            "GIT_COMMITTER_DATE": "2026-03-01T10:00:00",
        },
    )
    g("checkout", "-q", "-b", "wip")
    (d / "y").write_text("2")
    g("add", "-A")
    g(
        "commit",
        "-m",
        "on wip unmerged",
        env={
            "GIT_AUTHOR_DATE": "2026-03-02T10:00:00",
            "GIT_COMMITTER_DATE": "2026-03-02T10:00:00",
        },
    )
    g("checkout", "-q", "main")
    main_only = collect_activity(d, _SINCE, _UNTIL)
    all_b = collect_activity(d, _SINCE, _UNTIL, branch=ALL_BRANCHES)
    assert main_only.commit_count == 1
    assert all_b.commit_count == 2


def test_author_filter(tmp_path):
    import subprocess, os

    d = tmp_path / "r2"
    d.mkdir()

    def g(*a, name="A", email="a@x.com", date=None):
        env = dict(os.environ)
        env.update(
            {
                "GIT_AUTHOR_NAME": name,
                "GIT_AUTHOR_EMAIL": email,
                "GIT_COMMITTER_NAME": name,
                "GIT_COMMITTER_EMAIL": email,
            }
        )
        if date:
            env.update({"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
        subprocess.run(["git", "-C", str(d), *a], env=env, capture_output=True)

    g("init", "-q")
    g("branch", "-M", "main")
    (d / "a").write_text("1")
    g("add", "-A")
    g(
        "commit",
        "-m",
        "alice",
        name="Alice",
        email="alice@x.com",
        date="2026-04-01T10:00:00",
    )
    (d / "b").write_text("2")
    g("add", "-A")
    g("commit", "-m", "bob", name="Bob", email="bob@x.com", date="2026-04-02T10:00:00")
    only_bob = collect_activity(d, _SINCE, _UNTIL, authors=["bob@x.com"])
    assert only_bob.commit_count == 1
    assert only_bob.commits[0].author_name == "Bob"
    authors = list_authors(d, _SINCE, _UNTIL)
    names = {a["name"] for a in authors}
    assert names == {"Alice", "Bob"}
