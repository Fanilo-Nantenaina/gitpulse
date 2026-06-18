from __future__ import annotations

import os
from pathlib import Path

import pygit2


def list_dir(path: str | None) -> dict:
    if not path:
        target = Path.home()
    else:
        target = Path(path).expanduser()
    target = target.resolve()

    if not target.exists() or not target.is_dir():
        return {
            "error": f"Not a directory: {target}",
            "path": str(target),
            "parent": str(target.parent),
            "entries": [],
        }

    entries = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith("."):
                continue
            if not child.is_dir():
                continue
            entries.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "is_repo": _is_repo(child),
                }
            )
    except PermissionError:
        return {
            "error": "Permission denied",
            "path": str(target),
            "parent": str(target.parent),
            "entries": [],
        }

    return {
        "path": str(target),
        "parent": str(target.parent) if target.parent != target else None,
        "is_repo": _is_repo(target),
        "entries": entries,
    }


def _is_repo(p: Path) -> bool:
    try:
        return pygit2.discover_repository(str(p)) is not None
    except Exception:
        return False


def drives() -> list[str]:
    if os.name != "nt":
        return ["/"]
    found = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        d = f"{letter}:\\"
        if Path(d).exists():
            found.append(d)
    return found
