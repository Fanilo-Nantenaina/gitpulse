from __future__ import annotations

import json
import os
from pathlib import Path

LANGUAGES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "mg": "Malagasy",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
}

DEFAULT_LANG = "en"


def _config_path() -> Path:
    base = os.environ.get("GITPULSE_CONFIG_DIR")
    if base:
        return Path(base) / "config.json"
    return Path.home() / ".gitpulse" / "config.json"


def load_config() -> dict:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict) -> Path:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def normalize_lang(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in LANGUAGES:
        return v
    for code, name in LANGUAGES.items():
        if name.lower() == v:
            return code
    return None


def resolve_lang(cli_value: str | None = None) -> str:
    candidate = normalize_lang(cli_value)
    if candidate:
        return candidate
    candidate = normalize_lang(os.environ.get("GITPULSE_LANG"))
    if candidate:
        return candidate
    candidate = normalize_lang(load_config().get("lang"))
    if candidate:
        return candidate
    return DEFAULT_LANG


def lang_name(code: str) -> str:
    return LANGUAGES.get(code, code)
