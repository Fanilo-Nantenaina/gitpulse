from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from gitpulse.ai import providers
from gitpulse.core.trends import compare


def test_status_lists_all_providers() -> None:
    names = {s["name"] for s in providers.status()}
    assert {"claude", "openai", "gemini", "ollama"}.issubset(names)


def test_status_entries_have_shape() -> None:
    for s in providers.status():
        assert set(s) >= {"name", "kind", "available", "detail", "models"}
        assert s["kind"] in ("cloud", "local")


def test_cloud_providers_are_cloud() -> None:
    for name in ("claude", "openai", "gemini"):
        assert providers.get_provider(name).kind == "cloud"


def test_ollama_is_local() -> None:
    assert providers.get_provider("ollama").kind == "local"


def test_detect_local_returns_none() -> None:
    assert providers.detect("local") is None


def test_unknown_provider_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        providers.get_provider("nope")


def test_compare_returns_metrics(branched_repo: Path) -> None:
    cmp = compare(
        branched_repo,
        timedelta(days=7),
        periods_back=2,
        now=datetime(2026, 2, 7, tzinfo=timezone.utc),
    )
    assert cmp.metrics
    names = {m.name for m in cmp.metrics}
    assert "Commits" in names
    for m in cmp.metrics:
        assert m.direction in ("up", "down", "flat")
