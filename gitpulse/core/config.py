from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import TypedDict

from .jsonio import JsonValue, as_array, as_object, as_str


class _TrackedBase(TypedDict):
    url: str


class TrackedRepo(_TrackedBase, total=False):
    label: str


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
    return config_dir() / "config.json"


def config_dir() -> Path:
    base = os.environ.get("GITPULSE_CONFIG_DIR")
    return Path(base) if base else Path.home() / ".gitpulse"


def load_config() -> dict[str, JsonValue]:
    p = _config_path()
    if not p.exists():
        return {}
    try:
        return as_object(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(cfg: dict[str, JsonValue]) -> Path:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    _restrict(p.parent, stat.S_IRWXU)
    payload = json.dumps(cfg, indent=2, ensure_ascii=False)

    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=".config-")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        _restrict(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, p)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _restrict(p, stat.S_IRUSR | stat.S_IWUSR)
    return p


def _restrict(path: Path, mode: int) -> None:
    if os.name == "nt":
        return
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def _read_tracked(cfg: dict[str, JsonValue]) -> list[TrackedRepo]:
    out: list[TrackedRepo] = []
    for entry in as_array(cfg.get("tracked")):
        obj = as_object(entry)
        url = as_str(obj.get("url"))
        if not url:
            continue
        label = as_str(obj.get("label"))
        out.append({"url": url, "label": label} if label else {"url": url})
    return out


def _write_tracked(cfg: dict[str, JsonValue], tracked: list[TrackedRepo]) -> None:
    payload: list[JsonValue] = []
    for t in tracked:
        entry: dict[str, JsonValue] = {"url": t["url"]}
        label = t.get("label")
        if label:
            entry["label"] = label
        payload.append(entry)
    cfg["tracked"] = payload


def list_tracked() -> list[TrackedRepo]:
    return _read_tracked(load_config())


_KEY_FIELDS = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _read_keys(cfg: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return {
        name: value
        for name, value in as_object(cfg.get("keys")).items()
        if isinstance(value, str)
    }


def get_api_key(provider: str) -> str | None:
    env_name = _KEY_FIELDS.get(provider)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    return as_str(_read_keys(load_config()).get(provider)) or None


def set_api_key(provider: str, key: str) -> None:
    cfg = load_config()
    keys = _read_keys(cfg)
    if key:
        keys[provider] = key
    else:
        keys.pop(provider, None)
    cfg["keys"] = keys
    save_config(cfg)


def has_stored_key(provider: str) -> bool:
    return bool(as_str(_read_keys(load_config()).get(provider)))


def add_tracked(url: str, label: str | None = None) -> tuple[bool, list[TrackedRepo]]:
    cfg = load_config()
    tracked = _read_tracked(cfg)
    if any(t["url"] == url for t in tracked):
        return False, tracked
    tracked.append({"url": url, "label": label} if label else {"url": url})
    _write_tracked(cfg, tracked)
    save_config(cfg)
    return True, tracked


def remove_tracked(needle: str) -> tuple[bool, list[TrackedRepo]]:
    cfg = load_config()
    tracked = _read_tracked(cfg)
    kept = [t for t in tracked if t["url"] != needle and t.get("label") != needle]
    changed = len(kept) != len(tracked)
    if changed:
        _write_tracked(cfg, kept)
        save_config(cfg)
    return changed, kept


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
    candidate = normalize_lang(as_str(load_config().get("lang")))
    if candidate:
        return candidate
    return DEFAULT_LANG


def lang_name(code: str) -> str:
    return LANGUAGES.get(code, code)


_WORKSPACE_NAME_RE = re.compile(r"[A-Za-z0-9][\w.-]{0,63}")


def valid_workspace_name(name: str) -> bool:
    return _WORKSPACE_NAME_RE.fullmatch(name) is not None


def _read_workspaces(cfg: dict[str, JsonValue]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, members in as_object(cfg.get("workspaces")).items():
        if not valid_workspace_name(name):
            continue
        out[name] = [m for m in (as_str(x) for x in as_array(members)) if m]
    return out


def _write_workspaces(cfg: dict[str, JsonValue], ws: dict[str, list[str]]) -> None:
    cfg["workspaces"] = {name: list[JsonValue](members) for name, members in ws.items()}


def list_workspaces() -> dict[str, list[str]]:
    return _read_workspaces(load_config())


def get_workspace(name: str) -> list[str] | None:
    return _read_workspaces(load_config()).get(name.removeprefix("@"))


def add_to_workspace(name: str, members: list[str]) -> list[str]:
    name = name.removeprefix("@")
    if not valid_workspace_name(name):
        raise ValueError(
            f"Invalid workspace name {name!r}: use letters, digits, '.', '_' or '-'."
        )
    bad = [m for m in members if m.startswith("@")]
    if bad:
        raise ValueError(f"A workspace cannot contain another workspace: {bad[0]}")
    cfg = load_config()
    ws = _read_workspaces(cfg)
    current = ws.setdefault(name, [])
    for m in members:
        if m not in current:
            current.append(m)
    _write_workspaces(cfg, ws)
    save_config(cfg)
    return current


def remove_from_workspace(name: str, members: list[str] | None = None) -> bool:
    name = name.removeprefix("@")
    cfg = load_config()
    ws = _read_workspaces(cfg)
    if name not in ws:
        return False
    if members:
        kept = [m for m in ws[name] if m not in members]
        if len(kept) == len(ws[name]):
            return False
        ws[name] = kept
    else:
        del ws[name]
    _write_workspaces(cfg, ws)
    save_config(cfg)
    return True
