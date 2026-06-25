from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from ..core import remote as gp_remote


def activity_dict(a) -> dict:
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


def summary_dict(s) -> dict:
    return {
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


def resolve_source(req) -> tuple[object, Optional[str]]:
    if getattr(req, "url", None):
        tok, user, key = gp_remote.resolve_auth(None, None, None)
        dest = gp_remote.sync_remote(
            req.url,
            tok,
            user,
            key,
            refresh=getattr(req, "refresh", True),
            insecure=getattr(req, "insecure", False),
        )
        return dest, gp_remote.repo_name_from_url(req.url)
    if not getattr(req, "path", None):
        raise HTTPException(400, "Provide a path or url")
    return req.path, None
