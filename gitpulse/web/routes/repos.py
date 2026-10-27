from __future__ import annotations

import os
from typing import TypedDict

from fastapi import APIRouter, HTTPException

from ...core import config as gp_config
from ...core import refs as gp_refs
from ...core import remote as gp_remote
from ...core import workspace as gp_workspace
from ...core.gitcreds import git_config_env, redact
from ..schemas import BranchesReq, LangReq, SshBrowseReq, TrackReq, WorkspaceReq
from ..serializers import resolve_source

router = APIRouter(prefix="/api")


class _BranchesBase(TypedDict):
    local: list[str]
    remote: list[str]
    tags: list[str]
    remote_url: str | None
    head: str | None
    head_sha: str | None


class BranchesResult(_BranchesBase, total=False):
    error: str
    is_workspace: bool


@router.get("/config")
def api_get_config():
    return {
        "lang": gp_config.resolve_lang(),
        "languages": gp_config.LANGUAGES,
        "tracked": gp_config.list_tracked(),
    }


@router.post("/config/lang")
def api_set_lang(body: LangReq):
    code = gp_config.normalize_lang(body.lang)
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


@router.get("/locations")
def api_locations():
    from ...core import locations

    return {"locations": locations.list_locations()}


@router.post("/browse/ssh")
def api_browse_ssh(body: SshBrowseReq):
    from ...core import locations

    if not locations.valid_ssh_host(body.host):
        raise HTTPException(400, "Invalid SSH host")
    return locations.ssh_list_dir(body.host, body.path)


def _put_refs(result: BranchesResult, refs: gp_refs.RefList) -> None:
    result["local"] = refs["local"]
    result["remote"] = refs["remote"]
    result["tags"] = refs["tags"]
    result["head"] = refs["head"]
    result["head_sha"] = refs["head_sha"]


@router.post("/branches")
def api_branches(req: BranchesReq) -> BranchesResult:
    result: BranchesResult = {
        "local": [],
        "remote": [],
        "tags": [],
        "remote_url": None,
        "head": None,
        "head_sha": None,
    }
    tok: str | None = None
    try:
        if req.force and (req.url or (req.path or "").startswith("@")):
            resolve_source(req)
        if req.path:
            import pygit2

            disc = pygit2.discover_repository(req.path)
            if not disc:
                if gp_workspace.is_workspace(req.path):
                    result["is_workspace"] = True
                    return result
                raise HTTPException(400, "Not a git repository")
            repo = pygit2.Repository(disc)
            _put_refs(result, gp_refs.list_refs(repo))
            try:
                result["remote_url"] = repo.remotes["origin"].url
            except Exception:
                pass
            return result
        if req.url:
            cached = gp_remote.cached_path(req.url)
            if cached is not None:
                import pygit2

                _put_refs(result, gp_refs.list_refs(pygit2.Repository(str(cached))))
                result["remote_url"] = gp_remote.strip_userinfo(req.url)
                return result
            tok, user, _ = gp_remote.resolve_auth(None, None, None)
            ls_url = gp_remote.strip_userinfo(req.url)
            env = git_config_env(tok, user, req.insecure, for_url=ls_url)
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
                        result["local"].append(line.split("refs/heads/")[-1])
            result["remote_url"] = ls_url
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


@router.get("/workspaces")
def api_workspaces():
    return {
        "workspaces": [
            {"name": name, "members": members}
            for name, members in gp_config.list_workspaces().items()
        ]
    }


@router.post("/workspaces")
def api_workspace_add(body: WorkspaceReq):
    try:
        members = gp_config.add_to_workspace(body.name, body.members)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"name": body.name.removeprefix("@"), "members": members}


@router.delete("/workspaces")
def api_workspace_remove(name: str, member: str | None = None):
    removed = gp_config.remove_from_workspace(name, [member] if member else None)
    return {"removed": removed}


@router.get("/history")
def api_history(limit: int = 30):
    from ...core import history

    return {
        "entries": [
            {k: v for k, v in e.items() if k != "summary"}
            for e in history.entries(limit)
        ]
    }


@router.get("/doctor")
def api_doctor():
    from ...ai import providers
    from ...core import doctor

    return {"checks": doctor.run_all() + providers.health()}
