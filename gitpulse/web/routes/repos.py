from __future__ import annotations

import os
from typing import TypedDict

from fastapi import APIRouter, HTTPException

from ...core import config as gp_config
from ...core import remote as gp_remote
from ...core import workspace as gp_workspace
from ...core.gitcreds import git_config_env, redact
from ..schemas import SshBrowseReq, TrackReq, WorkspaceReq

router = APIRouter(prefix="/api")


class _BranchesBase(TypedDict):
    local: list[str]
    remote: list[str]
    remote_url: str | None
    head: str | None


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
                if gp_workspace.is_workspace(path):
                    result["is_workspace"] = True
                    return result
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
            if include_remote:
                result["remote"] = sorted(
                    b for b in repo.branches.remote if not b.endswith("/HEAD")
                )
            return result
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
