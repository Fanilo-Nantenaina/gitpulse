from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

import pygit2

from . import config
from . import remote as gp_remote
from .models import RepoRef

DEFAULT_DEPTH = 3

_SCP_URL_RE = re.compile(r"^[\w.-]+@[\w.-]+:(?!\\)")
_URL_SCHEMES = ("http://", "https://", "ssh://", "git://", "file://")


class RepoFailure(TypedDict):
    name: str
    path: str
    error: str


@dataclass
class RepoSet:
    name: str
    root: str
    refs: list[RepoRef] = field(default_factory=list[RepoRef])
    single: bool = False
    failures: list[RepoFailure] = field(default_factory=list[RepoFailure])


def is_url(spec: str) -> bool:
    return spec.startswith(_URL_SCHEMES) or bool(_SCP_URL_RE.match(spec))


def is_named(spec: str) -> bool:
    return spec.startswith("@") and len(spec) > 1


def display_name(spec: str | os.PathLike[str]) -> str:
    text = str(spec)
    if is_named(text):
        return text
    if is_url(text):
        return gp_remote.repo_name_from_url(text)
    return Path(text).resolve().name or text


def is_repo(path: str | os.PathLike[str]) -> bool:
    text = str(path)
    if is_named(text) or is_url(text):
        return False
    return pygit2.discover_repository(str(Path(text).resolve())) is not None


def discover(
    root: str | os.PathLike[str], max_depth: int = DEFAULT_DEPTH
) -> list[RepoRef]:
    root_path = Path(root).resolve()
    found: list[RepoRef] = []
    root_depth = len(root_path.parts)
    for dirpath, dirnames, _ in os.walk(root_path):
        p = Path(dirpath)
        if len(p.parts) - root_depth > max_depth:
            dirnames[:] = []
            continue
        if ".git" in dirnames or (p / ".git").exists():
            found.append(RepoRef(name=p.name, path=str(p)))
            dirnames[:] = []
    return sorted(found, key=lambda r: r.name.lower())


def sync_url(url: str, refresh: bool = True, insecure: bool = False) -> Path:
    tok, user, key = gp_remote.resolve_auth(None, None, None)
    return gp_remote.sync_remote(
        url, tok, user, key, refresh=refresh, insecure=insecure
    )


def expand(
    spec: str | os.PathLike[str],
    max_depth: int = DEFAULT_DEPTH,
    refresh: bool = True,
    insecure: bool = False,
) -> RepoSet:
    text = str(spec)
    if is_named(text):
        return _expand_named(text[1:], max_depth, refresh, insecure)
    if is_url(text):
        name = gp_remote.repo_name_from_url(text)
        dest = sync_url(text, refresh, insecure)
        return RepoSet(name, str(dest), [RepoRef(name, str(dest))], single=True)
    root = Path(text).resolve()
    if is_repo(root):
        return RepoSet(root.name, str(root), [RepoRef(root.name, str(root))], True)
    refs = discover(root, max_depth)
    if not refs:
        raise ValueError(f"No git repositories found under {root}")
    return RepoSet(root.name, str(root), refs)


def _expand_named(name: str, max_depth: int, refresh: bool, insecure: bool) -> RepoSet:
    members = config.get_workspace(name)
    if members is None:
        known = ", ".join(f"@{n}" for n in config.list_workspaces()) or "none yet"
        raise ValueError(
            f"Unknown workspace @{name}. Known: {known}. "
            f"Create it with: gitpulse workspace add {name} <path-or-url>..."
        )
    result = RepoSet(f"@{name}", f"@{name}")
    taken: set[str] = set()
    for member in members:
        try:
            part = expand(member, max_depth, refresh, insecure)
        except (ValueError, RuntimeError, OSError, pygit2.GitError) as e:
            result.failures.append(
                {
                    "name": display_name(member),
                    "path": member,
                    "error": str(e).splitlines()[0],
                }
            )
            continue
        result.failures.extend(part.failures)
        for ref in part.refs:
            label = ref.name
            n = 2
            while label in taken:
                label = f"{ref.name}-{n}"
                n += 1
            taken.add(label)
            result.refs.append(RepoRef(label, ref.path))
    if not result.refs:
        detail = "; ".join(f"{f['path']}: {f['error']}" for f in result.failures)
        raise ValueError(f"Workspace @{name} has no reachable repository. {detail}")
    return result
