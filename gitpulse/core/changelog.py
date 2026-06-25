from __future__ import annotations

import re
from datetime import datetime, timezone

import pygit2

_CONV = re.compile(
    r"^(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s*(?P<desc>.+)"
)

_SECTION = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "test": "Tests",
    "build": "Build",
    "ci": "CI",
    "chore": "Chores",
}


def generate_changelog(
    repo_path: str, from_ref: str | None, to_ref: str = "HEAD"
) -> str:
    repo = pygit2.Repository(pygit2.discover_repository(repo_path))
    to_oid = repo.revparse_single(to_ref).id
    from_oid = repo.revparse_single(from_ref).id if from_ref else None

    sections: dict[str, list[str]] = {}
    breaking: list[str] = []

    for c in repo.walk(to_oid, pygit2.GIT_SORT_TIME):
        if from_oid and c.id == from_oid:
            break
        first = c.message.strip().splitlines()[0]
        m = _CONV.match(first)
        if not m:
            continue
        typ, scope, bang, desc = (
            m.group("type"),
            m.group("scope"),
            m.group("bang"),
            m.group("desc"),
        )
        entry = f"- {f'**{scope}:** ' if scope else ''}{desc} (`{str(c.id)[:7]}`)"
        if bang or "BREAKING CHANGE" in c.message:
            breaking.append(entry)
        sections.setdefault(typ, []).append(entry)

    out = [f"## {to_ref}", f"_{datetime.now(timezone.utc):%Y-%m-%d}_", ""]
    if breaking:
        out.append("### ⚠ BREAKING CHANGES")
        out.extend(breaking)
        out.append("")
    for typ, title in _SECTION.items():
        if typ in sections:
            out.append(f"### {title}")
            out.extend(sections[typ])
            out.append("")
    return "\n".join(out)
