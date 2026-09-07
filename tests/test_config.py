from __future__ import annotations

import json
from pathlib import Path

import pytest

from gitpulse.core import config

MALFORMED: list[tuple[str, object]] = [
    ("wrong scalar types", {"lang": 42, "keys": "not-an-object", "tracked": "oops"}),
    ("null values", {"lang": None, "keys": None, "tracked": None}),
    ("nested wrong types", {"keys": {"claude": 1}, "tracked": [1, "x", None]}),
    ("tracked entries missing url", {"tracked": [{"label": "no url"}, {}]}),
    ("top level array", [1, 2, 3]),
    ("top level string", "nonsense"),
]


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GITPULSE_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("GITPULSE_LANG", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


def _write(config_dir: Path, payload: object) -> None:
    (config_dir / "config.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.parametrize("label,payload", MALFORMED, ids=[m[0] for m in MALFORMED])
def test_readers_degrade_to_defaults(
    label: str, payload: object, config_dir: Path
) -> None:
    _write(config_dir, payload)
    assert config.resolve_lang() == config.DEFAULT_LANG
    assert config.list_tracked() == []
    assert config.get_api_key("claude") is None
    assert config.has_stored_key("claude") is False


def test_unparseable_file_degrades_to_defaults(config_dir: Path) -> None:
    (config_dir / "config.json").write_text("{not json", encoding="utf-8")
    assert config.load_config() == {}
    assert config.resolve_lang() == config.DEFAULT_LANG


def test_list_tracked_always_returns_well_formed_entries(config_dir: Path) -> None:
    _write(
        config_dir,
        {"tracked": [{"url": "https://x/a.git", "label": 7}, {"url": ""}, "junk"]},
    )
    tracked = config.list_tracked()
    assert tracked == [{"url": "https://x/a.git"}]


def test_round_trip_survives_a_malformed_starting_file(config_dir: Path) -> None:
    _write(config_dir, {"keys": "not-an-object", "tracked": "oops"})
    config.set_api_key("claude", "sk-test")
    added, tracked = config.add_tracked("https://x/a.git", label="a")
    assert added is True
    assert config.get_api_key("claude") == "sk-test"
    assert tracked == [{"url": "https://x/a.git", "label": "a"}]
    assert config.list_tracked() == [{"url": "https://x/a.git", "label": "a"}]


def test_written_config_is_valid_json_objects(config_dir: Path) -> None:
    config.add_tracked("https://x/a.git", label="a")
    config.set_api_key("claude", "sk-test")
    raw = json.loads((config_dir / "config.json").read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    assert raw["tracked"] == [{"url": "https://x/a.git", "label": "a"}]
    assert raw["keys"] == {"claude": "sk-test"}


def test_remove_tracked_on_malformed_file_is_a_noop(config_dir: Path) -> None:
    _write(config_dir, {"tracked": "oops"})
    changed, kept = config.remove_tracked("anything")
    assert changed is False
    assert kept == []
