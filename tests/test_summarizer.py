from __future__ import annotations

import json

import pytest

from gitpulse.ai.summarizer import Summary


def test_from_json_parses_well_formed_response() -> None:
    payload = json.dumps(
        {
            "headline": "Busy week on the parser",
            "synthesis": "Work focused on dateparse.py.",
            "themes": [{"title": "feat", "narrative": "...", "commits": ["abc1234"]}],
            "observations": ["README.md changed 3x."],
        }
    )
    summ = Summary.from_json(payload)
    assert summ.headline == "Busy week on the parser"
    assert summ.themes[0]["title"] == "feat"
    assert summ.observations == ["README.md changed 3x."]


def test_from_json_rejects_schema_deviation() -> None:
    payload = json.dumps(
        {
            "query": "gitpulse",
            "type": "project",
            "description": "A code review tool.",
        }
    )
    with pytest.raises(ValueError):
        Summary.from_json(payload)


def test_from_json_rejects_empty_fields() -> None:
    payload = json.dumps(
        {"headline": "", "synthesis": "", "themes": [], "observations": []}
    )
    with pytest.raises(ValueError):
        Summary.from_json(payload)


def test_from_json_normalizes_themes_given_as_plain_strings() -> None:
    payload = json.dumps(
        {
            "headline": "Busy week",
            "synthesis": "Lots of work happened.",
            "themes": ["Web UI Enhancements", "Backend fixes"],
            "observations": [],
        }
    )
    summ = Summary.from_json(payload)
    assert summ.themes == [
        {"title": "Web UI Enhancements", "narrative": "", "commits": []},
        {"title": "Backend fixes", "narrative": "", "commits": []},
    ]


def test_from_json_rejects_themes_with_invalid_entries() -> None:
    payload = json.dumps(
        {
            "headline": "Busy week",
            "synthesis": "Lots of work happened.",
            "themes": [1, 2, 3],
            "observations": [],
        }
    )
    with pytest.raises(ValueError):
        Summary.from_json(payload)


def test_from_json_tolerates_missing_observations() -> None:
    payload = json.dumps(
        {
            "headline": "Quiet day",
            "synthesis": "One small fix landed.",
            "themes": [{"title": "fix", "narrative": "...", "commits": []}],
        }
    )
    summ = Summary.from_json(payload)
    assert summ.observations == []
