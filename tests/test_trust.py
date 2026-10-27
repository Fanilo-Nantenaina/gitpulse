from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from gitpulse.ai import providers, summarizer
from gitpulse.ai.providers import GenResult
from gitpulse.core import history, scrub
from gitpulse.core.collector import collect_activity

MakeRepo = Callable[..., Path]

SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 12, 31, tzinfo=timezone.utc)

REPLY = json.dumps(
    {
        "headline": "Config work",
        "synthesis": "The period was about configuration.",
        "themes": [{"title": "Config", "narrative": "Added settings.", "commits": []}],
        "observations": [],
    }
)


@dataclass
class FakeProvider(providers.Provider):
    name: str = "fake"
    kind: str = "cloud"
    model: str = "fake-1"
    prompts: list[str] = field(default_factory=list[str])

    def available(self) -> bool:
        return True

    def price(self) -> tuple[float, float]:
        return (3.0, 15.0)

    def generate(self, system: str, prompt: str, max_tokens: int) -> GenResult:
        self.prompts.append(prompt)
        return GenResult(REPLY, 100, 50, 0.01, False, self.model)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    prov = FakeProvider()

    def detect(preferred: str = "auto") -> providers.Provider | None:
        return None if preferred == "local" else prov

    monkeypatch.setattr(providers, "detect", detect)
    return prov


@pytest.fixture
def leaky_repo(make_repo: MakeRepo) -> Path:
    return make_repo(
        "leaky",
        [
            (
                "feat: settings",
                "2026-03-02T10:00:00",
                {"settings.py": "DEBUG = True\n"},
            ),
            (
                "feat: wire aws",
                "2026-03-03T10:00:00",
                {
                    "settings.py": "DEBUG = True\n"
                    'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
                    'DB_PASSWORD = "Xk9pL2vQz81mN"\n'
                },
            ),
        ],
    )


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("token ghp_abcdefghijklmnopqrstuvwxyz0123456789", "github-token"),
        ("key = AKIAIOSFODNN7EXAMPLE", "aws-access-key"),
        ("sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "anthropic-key"),
        ("postgres://admin:hunter2pass@db:5432/x", "url-credentials"),
        (
            "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----",
            "private-key",
        ),
        ("https://hooks.slack.com/services/T00/B00/abcdef", "slack-webhook"),
        ('client_secret = "a1b2c3d4e5f6g7h8i9j0"', "assigned-secret"),
    ],
)
def test_scrub_catches_common_secrets(text: str, kind: str) -> None:
    res = scrub.scrub(text)
    assert res.findings[kind] == 1
    assert f"[REDACTED:{kind}]" in res.text


@pytest.mark.parametrize(
    "text",
    [
        "author = commit.author_name",
        "password = user_password",
        "password: changeme",
        'token = os.environ["TOKEN"]',
        "max_tokens = min(16000, n)",
        'tokenizer_path = "/models/tok-v2.bin"',
        '"token": "${TOKEN}"',
        "feat(auth): rotate token handling",
    ],
)
def test_scrub_leaves_ordinary_code_alone(text: str) -> None:
    res = scrub.scrub(text)
    assert res.count == 0
    assert res.text == text


def test_redaction_policy_follows_env(monkeypatch: pytest.MonkeyPatch) -> None:
    assert scrub.should_redact("cloud") and not scrub.should_redact("local")
    monkeypatch.setenv("GITPULSE_REDACT", "always")
    assert scrub.should_redact("local")
    monkeypatch.setenv("GITPULSE_REDACT", "off")
    assert not scrub.should_redact("cloud")


def test_cloud_payload_never_contains_the_secret(
    leaky_repo: Path, fake: FakeProvider
) -> None:
    activity = collect_activity(leaky_repo, SINCE, UNTIL)
    summ = summarizer.summarize(activity, provider="fake")
    assert fake.prompts, "the provider was not called"
    sent = fake.prompts[0]
    assert "AKIAIOSFODNN7EXAMPLE" not in sent
    assert "Xk9pL2vQz81mN" not in sent
    assert "[REDACTED:aws-access-key]" in sent
    assert summ.redactions >= 2
    assert "secret(s) redacted" in summ.cost_note


def test_local_provider_payload_is_not_redacted(
    leaky_repo: Path, fake: FakeProvider
) -> None:
    fake.kind = "local"
    activity = collect_activity(leaky_repo, SINCE, UNTIL)
    req = summarizer.prepare(activity, provider="fake")
    assert req.redactions == 0
    assert "AKIAIOSFODNN7EXAMPLE" in req.payload


def test_second_identical_summary_is_served_from_history(
    linear_repo: Path, fake: FakeProvider
) -> None:
    activity = collect_activity(linear_repo, SINCE, UNTIL)
    first = summarizer.summarize(activity, provider="fake")
    second = summarizer.summarize(activity, provider="fake")
    assert len(fake.prompts) == 1
    assert not first.cached and second.cached
    assert second.headline == first.headline
    assert "cached" in second.cost_note
    entries = history.entries()
    assert len(entries) == 1
    assert entries[0]["scope"] == "linear"
    assert entries[0]["commits"] == 5


def test_cache_can_be_bypassed(linear_repo: Path, fake: FakeProvider) -> None:
    activity = collect_activity(linear_repo, SINCE, UNTIL)
    summarizer.summarize(activity, provider="fake")
    summarizer.summarize(activity, provider="fake", use_cache=False)
    assert len(fake.prompts) == 2


def test_cache_can_be_disabled_by_env(
    linear_repo: Path, fake: FakeProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITPULSE_CACHE", "off")
    activity = collect_activity(linear_repo, SINCE, UNTIL)
    summarizer.summarize(activity, provider="fake")
    summarizer.summarize(activity, provider="fake")
    assert len(fake.prompts) == 2
    assert history.entries() == []


def test_a_different_model_misses_the_cache(
    linear_repo: Path, fake: FakeProvider
) -> None:
    activity = collect_activity(linear_repo, SINCE, UNTIL)
    summarizer.summarize(activity, provider="fake")
    summarizer.summarize(activity, provider="fake", model="fake-2")
    assert len(fake.prompts) == 2


def test_prepare_estimates_cost_without_calling(
    linear_repo: Path, fake: FakeProvider
) -> None:
    activity = collect_activity(linear_repo, SINCE, UNTIL)
    req = summarizer.prepare(activity, provider="fake")
    assert fake.prompts == []
    assert req.est_input_tokens > 0
    assert req.est_cost_usd > 0
    assert "Repository: linear" in req.payload


def test_history_find_by_row_and_prefix(linear_repo: Path, fake: FakeProvider) -> None:
    activity = collect_activity(linear_repo, SINCE, UNTIL)
    summarizer.summarize(activity, provider="fake")
    entry = history.entries()[0]
    assert history.find("1") == entry
    assert history.find(entry["key"][:10]) == entry
    assert history.find("zzz") is None
    assert history.clear() == 1
    assert history.entries() == []
