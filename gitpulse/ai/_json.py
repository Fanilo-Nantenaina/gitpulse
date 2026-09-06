"""Typed narrowing helpers for untrusted JSON.

`json.loads` hands back `Any`, and the payloads this package reads come from
HTTP APIs and from language models — neither is guaranteed to match the shape
we asked for. Parsed payloads are therefore declared as `JsonValue` and read
through the coercions below, so the surrounding code stays honestly typed
without pretending a remote response has a known schema.
"""

from __future__ import annotations

from typing import TypeAlias

JsonScalar: TypeAlias = "str | int | float | bool | None"
JsonValue: TypeAlias = "JsonScalar | list[JsonValue] | dict[str, JsonValue]"


def as_object(value: JsonValue) -> dict[str, JsonValue]:
    """Return `value` when it is a JSON object, otherwise an empty one."""
    return value if isinstance(value, dict) else {}


def as_array(value: JsonValue) -> list[JsonValue]:
    """Return `value` when it is a JSON array, otherwise an empty one."""
    return value if isinstance(value, list) else []


def as_str(value: JsonValue, default: str = "") -> str:
    """Return `value` when it is a JSON string, otherwise `default`."""
    return value if isinstance(value, str) else default


def as_int(value: JsonValue, default: int = 0) -> int:
    """Return `value` as an int when it is a JSON number, otherwise `default`."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)
