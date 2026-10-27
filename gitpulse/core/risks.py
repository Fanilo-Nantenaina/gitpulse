from __future__ import annotations

import re
from collections import Counter
from pathlib import PurePosixPath
from typing import Literal, TypedDict

from . import collector, scrub
from .models import Commit, FileChange, RepoActivity, qualified_path

Severity = Literal["high", "medium", "low"]

SEVERITY_ORDER: dict[Severity, int] = {"high": 0, "medium": 1, "low": 2}

CODE_EXTENSIONS = frozenset(
    [
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".kts",
        ".cs",
        ".cpp",
        ".cc",
        ".c",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".swift",
        ".scala",
        ".vue",
        ".svelte",
        ".dart",
        ".lua",
        ".ex",
        ".exs",
        ".sql",
        ".sh",
        ".ps1",
    ]
)
_LOCKFILES = frozenset(
    [
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "uv.lock",
        "Cargo.lock",
        "Gemfile.lock",
        "composer.lock",
        "go.sum",
        "Pipfile.lock",
    ]
)
_TEST_PATH = re.compile(
    r"(?:^|/)(?:tests?|specs?|__tests__|testing)/|(?:^|/)test_[^/]+$"
    r"|_test\.[a-z]+$|\.(?:test|spec)\.[a-z]+$|Tests?\.[a-z]+$"
)
_UNCLEAR = re.compile(r"^(?:wip|tmp|temp|fixup!|squash!|update|changes|\.+|-+)\b", re.I)
_FIX = re.compile(r"^(?:fix|hotfix|bugfix)\b", re.I)

LARGE_UNTESTED_CHURN = 400
HUGE_COMMIT_FILES = 40
HUGE_COMMIT_CHURN = 2000
HOTSPOT_MIN = 5
SECRET_SCAN_COMMITS = 60
SECRET_SCAN_CHARS = 60_000


class Risk(TypedDict):
    kind: str
    severity: Severity
    title: str
    detail: str
    commits: list[str]
    repo: str


def is_test_path(path: str) -> bool:
    return bool(_TEST_PATH.search(path.replace("\\", "/")))


def is_code_path(path: str) -> bool:
    p = PurePosixPath(path.replace("\\", "/"))
    return p.suffix.lower() in CODE_EXTENSIONS and not is_test_path(path)


def _reviewable(files: list[FileChange]) -> list[FileChange]:
    return [f for f in files if PurePosixPath(f.path).name not in _LOCKFILES]


def _risk(
    kind: str,
    severity: Severity,
    title: str,
    detail: str,
    commits: list[Commit],
) -> Risk:
    repos = sorted({c.repo for c in commits if c.repo})
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "detail": detail,
        "commits": [c.short_sha for c in commits[:12]],
        "repo": ", ".join(repos),
    }


def detect(
    activity: RepoActivity,
    scan_secrets: bool = True,
    max_scan: int = SECRET_SCAN_COMMITS,
) -> list[Risk]:
    commits = [c for c in activity.commits if not c.is_merge]
    found: list[Risk] = []
    if scan_secrets:
        found.extend(_secrets(activity, commits[:max_scan]))
    found.extend(_large_untested(commits))
    found.extend(_huge(commits))
    found.extend(_reverts(commits))
    found.extend(_fix_chains(commits))
    found.extend(_hotspots(activity, commits))
    found.extend(_off_hours(commits))
    found.extend(_unclear(commits))
    found.sort(key=lambda r: SEVERITY_ORDER[r["severity"]])
    return found


def _secrets(activity: RepoActivity, commits: list[Commit]) -> list[Risk]:
    by_repo: dict[str, list[Commit]] = {}
    for c in commits:
        if c.churn:
            by_repo.setdefault(c.repo_path or activity.repo_path, []).append(c)
    out: list[Risk] = []
    for repo_path, group in by_repo.items():
        try:
            diffs = collector.diff_excerpts(
                repo_path, [c.sha for c in group], max_chars_each=SECRET_SCAN_CHARS
            )
        except Exception:
            continue
        for c in group:
            text = diffs.get(c.sha)
            if not text:
                continue
            for path, kinds in _added_secrets(text).items():
                where = f"{c.repo}/{path}" if c.repo else path
                out.append(
                    _risk(
                        "committed_secret",
                        "high",
                        "Possible secret committed",
                        f"{', '.join(sorted(kinds))} added in {where} "
                        f"({c.short_sha}: {c.summary}). Rotate it and purge history "
                        "if it is real.",
                        [c],
                    )
                )
    return out


def _added_secrets(diff_text: str) -> dict[str, Counter[str]]:
    added: dict[str, list[str]] = {}
    current = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ "):
            current = line[4:].removeprefix("b/").strip()
            continue
        if line.startswith("+") and current and current != "/dev/null":
            added.setdefault(current, []).append(line[1:])
    out: dict[str, Counter[str]] = {}
    for path, lines in added.items():
        kinds = scrub.scan("\n".join(lines))
        if kinds:
            out[path] = kinds
    return out


def _large_untested(commits: list[Commit]) -> list[Risk]:
    out: list[Risk] = []
    for c in commits:
        files = _reviewable(c.files)
        code = [f for f in files if is_code_path(f.path)]
        churn = sum(f.churn for f in code)
        if churn < LARGE_UNTESTED_CHURN or any(is_test_path(f.path) for f in files):
            continue
        out.append(
            _risk(
                "large_untested",
                "medium",
                "Large change without tests",
                f"{c.short_sha} changes {churn} lines across {len(code)} code "
                f"file(s) with no test file touched: {c.summary}",
                [c],
            )
        )
    return out[:5]


def _huge(commits: list[Commit]) -> list[Risk]:
    out: list[Risk] = []
    for c in commits:
        files = _reviewable(c.files)
        churn = sum(f.churn for f in files)
        if len(files) < HUGE_COMMIT_FILES and churn < HUGE_COMMIT_CHURN:
            continue
        out.append(
            _risk(
                "huge_commit",
                "low",
                "Hard-to-review commit",
                f"{c.short_sha} touches {len(files)} files (+{c.additions}/"
                f"-{c.deletions}): {c.summary}",
                [c],
            )
        )
    return out[:5]


def _reverts(commits: list[Commit]) -> list[Risk]:
    reverts = [c for c in commits if c.summary.lower().startswith("revert")]
    if not reverts:
        return []
    listed = "; ".join(f"{c.short_sha} {c.summary}" for c in reverts[:5])
    return [
        _risk(
            "revert",
            "medium",
            "Reverted work",
            f"{len(reverts)} revert commit(s): {listed}",
            reverts,
        )
    ]


def _fix_chains(commits: list[Commit]) -> list[Risk]:
    per_file: dict[str, list[Commit]] = {}
    for c in commits:
        if not _FIX.match(c.summary):
            continue
        for f in c.files:
            per_file.setdefault(qualified_path(c, f), []).append(c)
    chains = sorted(
        ((p, cs) for p, cs in per_file.items() if len(cs) >= 3),
        key=lambda kv: len(kv[1]),
        reverse=True,
    )
    return [
        _risk(
            "fix_chain",
            "medium",
            "Repeated fixes in one file",
            f"{path} was fixed {len(cs)} times in this window, which suggests the "
            "underlying problem is not settled.",
            cs,
        )
        for path, cs in chains[:3]
    ]


def _hotspots(activity: RepoActivity, commits: list[Commit]) -> list[Risk]:
    n = len(commits)
    if n < HOTSPOT_MIN or activity.files_touched < HOTSPOT_MIN:
        return []
    out: list[Risk] = []
    for path, count in list(activity.hotspots.items())[:3]:
        if count < HOTSPOT_MIN or count / n < 0.25:
            continue
        touching = [
            c for c in commits if any(qualified_path(c, f) == path for f in c.files)
        ]
        out.append(
            _risk(
                "churn_hotspot",
                "low",
                "Churn hotspot",
                f"{path} changed in {count} of {n} commits.",
                touching,
            )
        )
    return out


def _off_hours(commits: list[Commit]) -> list[Risk]:
    late = [c for c in commits if c.hour >= 22 or c.hour < 6]
    if len(commits) < 5 or len(late) / len(commits) < 0.3:
        return []
    share = round(100 * len(late) / len(commits))
    return [
        _risk(
            "off_hours",
            "low",
            "Lots of off-hours work",
            f"{len(late)} of {len(commits)} commits ({share}%) landed between 22h "
            "and 6h.",
            late,
        )
    ]


def _unclear(commits: list[Commit]) -> list[Risk]:
    vague = [c for c in commits if _UNCLEAR.match(c.summary.strip())]
    if len(vague) < 3:
        return []
    sample = ", ".join(f"'{c.summary[:30]}'" for c in vague[:4])
    return [
        _risk(
            "unclear_history",
            "low",
            "Unclear commit messages",
            f"{len(vague)} commits with messages like {sample}; squash or reword "
            "them before merging.",
            vague,
        )
    ]
