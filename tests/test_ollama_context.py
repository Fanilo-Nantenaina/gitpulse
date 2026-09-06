from __future__ import annotations

from datetime import datetime, timezone

from gitpulse.ai import providers
from gitpulse.ai.summarizer import _build_payload
from gitpulse.core.collector import collect_activity


def _provider(ctx_limit: int) -> providers.OllamaProvider:
    p = providers.OllamaProvider(model="test-model")
    p.model_context_limit = lambda model: ctx_limit
    return p


def test_num_ctx_grows_with_the_prompt():
    p = _provider(200_000)
    small = p._num_ctx("test-model", "sys", "x" * 1_000, 500)
    medium = p._num_ctx("test-model", "sys", "x" * 60_000, 500)
    assert medium > small
    assert medium >= 20_000


def test_num_ctx_never_below_floor():
    p = _provider(200_000)
    assert p._num_ctx("test-model", "", "hi", 10) == providers.OLLAMA_MIN_CTX


def test_num_ctx_capped_by_model_limit():
    p = _provider(8192)
    assert p._num_ctx("test-model", "sys", "x" * 400_000, 500) == 8192


def test_num_ctx_capped_by_global_max():
    p = _provider(1_000_000)
    assert p._num_ctx("test-model", "sys", "x" * 4_000_000, 500) == providers.OLLAMA_MAX_CTX


def test_payload_includes_diff_excerpts(linear_repo):
    activity = collect_activity(
        linear_repo, datetime(2020, 1, 1, tzinfo=timezone.utc), None
    )
    payload = _build_payload(activity)
    assert "Diff excerpts" in payload
    assert "diff --git" in payload


def test_payload_skips_merge_commit_diffs(branched_repo):
    activity = collect_activity(
        branched_repo,
        datetime(2020, 1, 1, tzinfo=timezone.utc),
        None,
        branch="master",
    )
    merges = [c for c in activity.commits if c.is_merge]
    assert merges, "fixture should contain a merge commit"
    payload = _build_payload(activity)
    for c in merges:
        assert f"--- [{c.short_sha}]" not in payload
