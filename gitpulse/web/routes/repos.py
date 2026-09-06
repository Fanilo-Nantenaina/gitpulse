from __future__ import annotations

import os
from typing import TypedDict

from fastapi import APIRouter, HTTPException

from ...core import config as gp_config
from ...core import remote as gp_remote
from ...core.gitcreds import git_config_env, redact
from ..schemas import TrackReq

router = APIRouter(prefix="/api")


class _BranchesBase(TypedDict):
    local: list[str]
    remote: list[str]
    remote_url: str | None
    head: str | None


class BranchesResult(_BranchesBase, total=False):
    # Only set when branch discovery failed; the other keys stay at their
    # empty defaults in that case.
    error: str


@router.get("/config")
def api_get_config():
    return {
        "lang": gp_config.resolve_lang(),
        "languages": gp_config.LANGUAGES,
        "tracked": gp_config.list_tracked(),
    }


@router.post("/config/lang")
def api_set_lang(body: dict[str, object]):
    lang = body.get("lang")
    code = gp_config.normalize_lang(lang if isinstance(lang, str) else None)
    if not code:
        raise HTTPException(400, "Unknown language")
    cfg = gp_config.load_config()
    cfg["lang"] = code
    gp_config.save_config(cfg)
    return {"lang": code}


@router.get("/browse")
def api_browse(path: str | None = None):
    from .. import browse

    return browse.list_dir(path)


@router.get("/drives")
def api_drives():
    from .. import browse

    return {"drives": browse.drives()}


@router.post("/branches")
def api_branches(body: dict[str, object]):

    path = body.get("path")
    raw_url = body.get("url")
    url = raw_url if isinstance(raw_url, str) else None
    include_remote = bool(body.get("include_remote", False))
    result: BranchesResult = {
        "local": [],
        "remote": [],
        "remote_url": None,
        "head": None,
    }
    tok: str | None = None
    try:
        if isinstance(path, str) and path:
            import pygit2

            disc = pygit2.discover_repository(path)
            if not disc:
                raise HTTPException(400, "Not a git repository")
            repo = pygit2.Repository(disc)

            def _branch_time(bn: str) -> int:
                try:
                    return repo.branches.get(bn).peel(pygit2.Commit).commit_time
                except Exception:
                    return 0

            result["local"] = sorted(
                repo.branches.local, key=_branch_time, reverse=True
            )
            if not repo.head_is_unborn and not repo.head_is_detached:
                result["head"] = repo.head.shorthand
            try:
                result["remote_url"] = repo.remotes["origin"].url
            except Exception:
                pass
            remote_url = result["remote_url"]
            if include_remote and remote_url:
                url = remote_url
        if include_remote and url:
            tok, user, _ = gp_remote.resolve_auth(None, None, None)
            ls_url = gp_remote.strip_userinfo(url)
            env = git_config_env(tok, user, bool(body.get("insecure")), for_url=ls_url)
            from ...core.procutil import run as _prun

            proc = _prun(
                ["git", "ls-remote", "--heads", ls_url],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, **env},
            )
            if proc.returncode == 0:
                for line in proc.stdout.strip().splitlines():
                    if "refs/heads/" in line:
                        result["remote"].append(line.split("refs/heads/")[-1])
    except HTTPException:
        raise
    except Exception as e:
        result["error"] = redact(str(e), tok)
    return result


@router.get("/tracked")
def api_tracked():
    return gp_config.list_tracked()


@router.post("/tracked")
def api_track(body: TrackReq):
    added, tracked = gp_config.add_tracked(body.url, body.label)
    return {"added": added, "tracked": tracked}


@router.delete("/tracked")
def api_untrack(needle: str):
    removed, tracked = gp_config.remove_tracked(needle)
    return {"removed": removed, "tracked": tracked}
