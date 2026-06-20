from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException

from ...core import config as gp_config
from ...core import remote as gp_remote
from ..schemas import TrackReq

router = APIRouter(prefix="/api")


@router.get("/config")
def api_get_config():
    cfg = gp_config.load_config()
    return {
        "lang": gp_config.resolve_lang(),
        "languages": gp_config.LANGUAGES,
        "tracked": cfg.get("tracked", []),
    }


@router.post("/config/lang")
def api_set_lang(body: dict):
    code = gp_config.normalize_lang(body.get("lang"))
    if not code:
        raise HTTPException(400, "Unknown language")
    cfg = gp_config.load_config()
    cfg["lang"] = code
    gp_config.save_config(cfg)
    return {"lang": code}


@router.get("/browse")
def api_browse(path: Optional[str] = None):
    from .. import browse

    return browse.list_dir(path)


@router.get("/drives")
def api_drives():
    from .. import browse

    return {"drives": browse.drives()}


@router.post("/branches")
def api_branches(body: dict):
    """List local branches; optionally include remote branches via ls-remote."""
    import subprocess

    path = body.get("path")
    url = body.get("url")
    include_remote = body.get("include_remote", False)
    result = {"local": [], "remote": [], "remote_url": None, "head": None}
    try:
        if path:
            import pygit2

            disc = pygit2.discover_repository(path)
            if not disc:
                raise HTTPException(400, "Not a git repository")
            repo = pygit2.Repository(disc)
            result["local"] = sorted(repo.branches.local)
            if not repo.head_is_unborn and not repo.head_is_detached:
                result["head"] = repo.head.shorthand
            try:
                result["remote_url"] = repo.remotes["origin"].url
            except Exception:
                pass
            if include_remote and result["remote_url"]:
                url = result["remote_url"]
        if include_remote and url:
            tok, user, key = gp_remote.resolve_auth(None, None, None)
            ls_url = url
            if tok and url.startswith("http"):
                ls_url = gp_remote._inject_token(url, tok, user)
            ssl_opts = ["-c", "http.sslVerify=false"] if body.get("insecure") else []
            from ...core.procutil import run as _prun

            proc = _prun(
                ["git", *ssl_opts, "ls-remote", "--heads", ls_url],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            if proc.returncode == 0:
                for line in proc.stdout.strip().splitlines():
                    if "refs/heads/" in line:
                        result["remote"].append(line.split("refs/heads/")[-1])
    except HTTPException:
        raise
    except Exception as e:
        result["error"] = str(e)
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
