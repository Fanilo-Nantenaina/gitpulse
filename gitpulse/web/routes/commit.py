from __future__ import annotations

from typing import TypedDict

from fastapi import APIRouter, HTTPException

from ...ai.commitmsg import generate_commit_message
from ...core.diffstage import collect_working_changes
from ..schemas import CommitMsgReq

router = APIRouter(prefix="/api")


class ChangedFileDict(TypedDict):
    path: str
    status: str
    additions: int
    deletions: int


@router.post("/changes-count")
def api_changes_count(body: dict[str, object]):
    path = body.get("path")
    if not isinstance(path, str) or not path:
        return {"count": 0, "staged": 0}
    try:
        all_changes = collect_working_changes(path, scope="all", include_diff=False)
        staged = collect_working_changes(path, scope="staged", include_diff=False)
        return {
            "count": len(all_changes.files),
            "staged": len(staged.files),
            "additions": all_changes.total_additions,
            "deletions": all_changes.total_deletions,
        }
    except (ValueError, RuntimeError):
        return {"count": 0, "staged": 0}


@router.post("/commit-message")
def api_commit_message(req: CommitMsgReq):
    try:
        changes = collect_working_changes(req.path, scope=req.scope)
        files: list[ChangedFileDict] = [
            {
                "path": f.path,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
            }
            for f in changes.files
        ]
        if not changes.has_changes:
            return {"has_changes": False, "scope": req.scope, "files": files}
        msg = generate_commit_message(
            changes,
            provider=req.provider,
            model=req.model,
            lang=req.lang,
            force_type=req.force_type,
        )
        return {
            "has_changes": True,
            "scope": req.scope,
            "files": files,
            "additions": changes.total_additions,
            "deletions": changes.total_deletions,
            "truncated": changes.truncated,
            "subject": msg.subject,
            "bullets": msg.bullets,
            "full_text": msg.full_text,
            "source": msg.source,
            "cost_usd": msg.cost_usd,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
