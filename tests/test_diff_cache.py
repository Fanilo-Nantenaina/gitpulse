from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from gitpulse.core import collector
from gitpulse.core.collector import collect_activity
from gitpulse.core.models import RepoActivity
from gitpulse.web.server import app

SINCE = datetime(2000, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clean_cache() -> Iterator[None]:
    collector.clear_diff_cache()
    yield
    collector.clear_diff_cache()


def test_cache_is_populated_by_a_collection(linear_repo: Path) -> None:
    assert collector.diff_cache_info()["entries"] == 0
    act = collect_activity(linear_repo, SINCE)
    assert collector.diff_cache_info()["entries"] == act.commit_count > 0


def test_second_collection_computes_no_diffs(linear_repo: Path) -> None:
    collect_activity(linear_repo, SINCE)
    with mock.patch.object(
        collector, "_compute_file_changes", side_effect=AssertionError("recomputed")
    ):
        act = collect_activity(linear_repo, SINCE)
    assert act.commit_count > 0
    assert act.total_additions > 0


def test_cached_and_uncached_results_are_identical(linear_repo: Path) -> None:
    def snapshot(
        a: RepoActivity,
    ) -> list[tuple[str, list[tuple[str, int, int, str]]]]:
        return [
            (c.sha, [(f.path, f.additions, f.deletions, f.status) for f in c.files])
            for c in a.commits
        ]

    cold = snapshot(collect_activity(linear_repo, SINCE))
    warm = snapshot(collect_activity(linear_repo, SINCE))
    assert cold == warm


def test_caller_cannot_corrupt_a_cache_entry(linear_repo: Path) -> None:
    first = collect_activity(linear_repo, SINCE)
    n_before = len(first.commits[0].files)
    first.commits[0].files.clear()
    second = collect_activity(linear_repo, SINCE)
    assert len(second.commits[0].files) == n_before


def test_cache_is_keyed_per_repository(linear_repo: Path, branched_repo: Path) -> None:
    collect_activity(linear_repo, SINCE)
    a = collector.diff_cache_info()["entries"]
    collect_activity(branched_repo, SINCE)
    assert collector.diff_cache_info()["entries"] > a


def test_cache_is_bounded(linear_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collector, "_DIFF_CACHE_MAX", 2)
    collect_activity(linear_repo, SINCE)
    assert collector.diff_cache_info()["entries"] <= 2


def test_clear_diff_cache_empties_it(linear_repo: Path) -> None:
    collect_activity(linear_repo, SINCE)
    collector.clear_diff_cache()
    assert collector.diff_cache_info()["entries"] == 0


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1:8420")


def test_summary_response_carries_stats(client: TestClient, linear_repo: Path) -> None:
    r = client.post(
        "/api/summary",
        json={"path": str(linear_repo), "when": "all", "provider": "local"},
    )
    assert r.status_code == 200, r.text
    stats = r.json()["stats"]
    assert set(stats) >= {"totals", "daily", "authors", "by_hour", "top_files"}


def test_inline_stats_match_the_dedicated_endpoint(
    client: TestClient, linear_repo: Path
) -> None:
    body = {"path": str(linear_repo), "when": "all", "provider": "local"}
    inline = client.post("/api/summary", json=body).json()["stats"]
    separate = client.post("/api/stats", json=body).json()["stats"]
    assert inline == separate


def test_summary_collects_the_window_only_once(
    client: TestClient, linear_repo: Path
) -> None:
    body = {"path": str(linear_repo), "when": "all", "provider": "local"}
    with mock.patch(
        "gitpulse.core.workspace.collect_activity",
        side_effect=collect_activity,
    ) as spy:
        assert client.post("/api/summary", json=body).status_code == 200
    assert spy.call_count == 1
