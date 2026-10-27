from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from .config import config_dir
from .jsonio import JsonValue, as_array, as_object, as_str

PROMPT_VERSION = "2"


class HistoryEntry(TypedDict):
    key: str
    created: str
    scope: str
    since: str
    until: str
    commits: int
    source: str
    headline: str
    summary: dict[str, JsonValue]


def history_dir() -> Path:
    base = os.environ.get("GITPULSE_HISTORY_DIR")
    return Path(base) if base else config_dir() / "history"


def enabled() -> bool:
    return os.environ.get("GITPULSE_CACHE", "1").strip().lower() not in (
        "0",
        "off",
        "false",
        "no",
    )


def cache_key(*parts: str) -> str:
    h = hashlib.sha256(PROMPT_VERSION.encode())
    for part in parts:
        h.update(b"\x00")
        h.update(part.encode("utf-8", errors="replace"))
    return h.hexdigest()


def _path(key: str) -> Path:
    return history_dir() / f"{key}.json"


def _coerce(raw: JsonValue, key: str) -> HistoryEntry | None:
    obj = as_object(raw)
    summary = as_object(obj.get("summary"))
    if not summary or not as_str(summary.get("headline")):
        return None
    commits = obj.get("commits")
    return {
        "key": key,
        "created": as_str(obj.get("created")),
        "scope": as_str(obj.get("scope")),
        "since": as_str(obj.get("since")),
        "until": as_str(obj.get("until")),
        "commits": commits if isinstance(commits, int) else 0,
        "source": as_str(obj.get("source")),
        "headline": as_str(summary.get("headline")),
        "summary": summary,
    }


def load(key: str) -> HistoryEntry | None:
    try:
        raw: JsonValue = json.loads(_path(key).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _coerce(raw, key)


def store(
    key: str,
    *,
    scope: str,
    since: datetime,
    until: datetime,
    commits: int,
    source: str,
    summary: dict[str, JsonValue],
) -> Path | None:
    payload: dict[str, JsonValue] = {
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": scope,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "commits": commits,
        "source": source,
        "summary": summary,
    }
    target = _path(key)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, target)
    except OSError:
        return None
    return target


def entries(limit: int | None = None) -> list[HistoryEntry]:
    d = history_dir()
    if not d.exists():
        return []
    found: list[HistoryEntry] = []
    for f in d.glob("*.json"):
        entry = load(f.stem)
        if entry is not None:
            found.append(entry)
    found.sort(key=lambda e: e["created"], reverse=True)
    return found[:limit] if limit else found


def find(ref: str) -> HistoryEntry | None:
    items = entries()
    if ref.isdigit() and 0 < int(ref) <= len(items):
        return items[int(ref) - 1]
    matches = [e for e in items if e["key"].startswith(ref)]
    return matches[0] if len(matches) == 1 else None


def clear() -> int:
    d = history_dir()
    if not d.exists():
        return 0
    n = sum(1 for _ in d.glob("*.json"))
    shutil.rmtree(d, ignore_errors=True)
    return n


def themes_of(entry: HistoryEntry) -> list[dict[str, JsonValue]]:
    return [as_object(t) for t in as_array(entry["summary"].get("themes"))]
