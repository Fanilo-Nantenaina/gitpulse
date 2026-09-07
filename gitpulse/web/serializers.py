from __future__ import annotations

from pathlib import Path
from typing import Protocol, TypedDict

from fastapi import HTTPException

from ..ai.summarizer import Summary, Theme
from ..core import remote as gp_remote
from ..core.models import RepoActivity


class CommitDict(TypedDict):
    sha: str
    summary: str
    when: str
    author: str
    additions: int
    deletions: int
    files: int


class ActivityDict(TypedDict):
    repo_name: str
    since: str
    until: str
    commit_count: int
    additions: int
    deletions: int
    files_touched: int
    active_days: int
    hour_histogram: dict[int, int]
    authors: dict[str, int]
    commits: list[CommitDict]


class _SummaryDictBase(TypedDict):
    headline: str
    synthesis: str
    themes: list[Theme]
    observations: list[str]
    source: str
    cost_note: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


class SummaryDict(_SummaryDictBase, total=False):
    fallback_reason: str


class RepoSourceReq(Protocol):
    path: str | None
    url: str | None
    refresh: bool
    insecure: bool


def activity_dict(a: RepoActivity) -> ActivityDict:
    return {
        "repo_name": a.repo_name,
        "since": a.since.isoformat(),
        "until": a.until.isoformat(),
        "commit_count": a.commit_count,
        "additions": a.total_additions,
        "deletions": a.total_deletions,
        "files_touched": a.files_touched,
        "active_days": a.active_days,
        "hour_histogram": a.hour_histogram,
        "authors": a.authors,
        "commits": [
            {
                "sha": c.short_sha,
                "summary": c.summary,
                "when": c.when.isoformat(),
                "author": c.author_name,
                "additions": c.additions,
                "deletions": c.deletions,
                "files": len(c.files),
            }
            for c in a.commits
        ],
    }


def summary_dict(s: Summary) -> SummaryDict:
    d: SummaryDict = {
        "headline": s.headline,
        "synthesis": s.synthesis,
        "themes": s.themes,
        "observations": s.observations,
        "source": s.source,
        "cost_note": s.cost_note,
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens,
        "cost_usd": s.cost_usd,
    }
    if "-error" in s.source or "-parse-failed" in s.source or "-truncated" in s.source:
        d["fallback_reason"] = s.raw[:500]
    return d


def resolve_source(req: RepoSourceReq) -> tuple[str | Path, str | None]:
    if req.url:
        tok, user, key = gp_remote.resolve_auth(None, None, None)
        dest = gp_remote.sync_remote(
            req.url,
            tok,
            user,
            key,
            refresh=req.refresh,
            insecure=req.insecure,
        )
        return dest, gp_remote.repo_name_from_url(req.url)
    if not req.path:
        raise HTTPException(400, "Provide a path or url")
    return req.path, None
