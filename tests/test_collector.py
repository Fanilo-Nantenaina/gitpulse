from __future__ import annotations

from datetime import datetime, timezone

from gitpulse.core.collector import collect_activity


def _since(d="2026-01-01"):
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_collect_counts_all_commits(linear_repo):
    act = collect_activity(linear_repo, datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert act.commit_count == 5


def test_collect_respects_since_window(linear_repo):
    # only commits from 2026-01-03 onward (commits 3,4,5)
    act = collect_activity(linear_repo, datetime(2026, 1, 3, tzinfo=timezone.utc))
    assert act.commit_count == 3


def test_collect_name_override(linear_repo):
    act = collect_activity(linear_repo, datetime(2025, 1, 1, tzinfo=timezone.utc),
                           name="custom-name")
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
    # base, work, a1, a2, more work, merge = 6 commits
    assert act.commit_count >= 6
