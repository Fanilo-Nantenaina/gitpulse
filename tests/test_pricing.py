from __future__ import annotations

import pytest

from gitpulse.ai import providers as P

CLAUDE_RATES = [
    ("claude-fable-5-1", 10.0, 50.0),
    ("claude-opus-5", 5.0, 25.0),
    ("claude-opus-4-8", 5.0, 25.0),
    ("claude-sonnet-5", 2.0, 10.0),
    ("claude-sonnet-4-6", 3.0, 15.0),
    ("claude-haiku-4-5", 1.0, 5.0),
]


@pytest.mark.parametrize("model,pin,pout", CLAUDE_RATES)
def test_claude_rates(model, pin, pout):
    assert P.ClaudeProvider(model=model)._price() == (pin, pout)


def test_claude_default_model_is_current():
    assert P.ClaudeProvider().model == P.DEFAULT_CLAUDE_MODEL == "claude-opus-5"


def test_every_offered_claude_model_is_priced():
    prov = P.ClaudeProvider()
    for model in prov.list_models():
        assert P.ClaudeProvider(model=model)._price() in {
            (pin, pout) for _, pin, pout in CLAUDE_RATES
        }


def test_unknown_model_falls_back_to_default_price():
    fallback = P.ClaudeProvider(model="claude-something-unreleased")._price()
    assert fallback == P.ClaudeProvider(model=P.DEFAULT_CLAUDE_MODEL)._price()


@pytest.mark.parametrize(
    "provider_cls,model,expected",
    [
        (P.OpenAIProvider, "gpt-4o-mini", (0.15, 0.6)),
        (P.OpenAIProvider, "gpt-4o", (2.5, 10.0)),
        (P.OpenAIProvider, "gpt-4.1-mini", (0.4, 1.6)),
        (P.OpenAIProvider, "gpt-4.1", (2.0, 8.0)),
        (P.GeminiProvider, "gemini-2.5-flash", (0.3, 2.5)),
        (P.GeminiProvider, "gemini-2.5-pro", (1.25, 10.0)),
    ],
)
def test_exact_match_wins_over_shorter_prefix(provider_cls, model, expected):
    assert provider_cls(model=model)._price() == expected


def test_defaults_are_present_in_their_price_tables():
    assert P.DEFAULT_CLAUDE_MODEL in P._CLAUDE_PRICES
    assert P.DEFAULT_OPENAI_MODEL in P._OPENAI_PRICES
    assert P.DEFAULT_GEMINI_MODEL in P._GEMINI_PRICES


def test_dated_model_id_prices_from_its_base_id():
    assert P.ClaudeProvider(model="claude-haiku-4-5-20251001")._price() == (1.0, 5.0)
