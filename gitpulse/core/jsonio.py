from __future__ import annotations

from typing import TypeAlias

JsonScalar: TypeAlias = "str | int | float | bool | None"
JsonValue: TypeAlias = "JsonScalar | list[JsonValue] | dict[str, JsonValue]"


def as_object(value: JsonValue) -> dict[str, JsonValue]:
    return value if isinstance(value, dict) else {}


def as_array(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def as_str(value: JsonValue, default: str = "") -> str:
    return value if isinstance(value, str) else default


def as_int(value: JsonValue, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)
