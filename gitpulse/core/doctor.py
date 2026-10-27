from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from typing import Literal, TypedDict

import pygit2

from . import config, history, locations, remote
from .procutil import run as _prun

Status = Literal["ok", "warn", "fail"]


class Check(TypedDict):
    name: str
    status: Status
    detail: str
    hint: str


def _check(name: str, status: Status, detail: str, hint: str = "") -> Check:
    return {"name": name, "status": status, "detail": detail, "hint": hint}


def _cmd(
    args: list[str], timeout: float = 8
) -> subprocess.CompletedProcess[str] | None:
    try:
        return _prun(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def check_python() -> Check:
    v = sys.version_info
    status: Status = "ok" if v >= (3, 10) else "fail"
    return _check(
        "python",
        status,
        f"{platform.python_implementation()} {v.major}.{v.minor}.{v.micro}",
        "" if status == "ok" else "GitPulse needs Python 3.10 or newer.",
    )


def check_pygit2() -> Check:
    try:
        version = importlib.metadata.version("pygit2")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return _check("pygit2", "ok", f"{version} (libgit2 {pygit2.LIBGIT2_VERSION})")


def check_git() -> Check:
    proc = _cmd(["git", "--version"])
    if proc is None or proc.returncode != 0:
        return _check(
            "git CLI",
            "warn",
            "not found",
            "Install git: remote fetches, commit messages and SSH fall back to it.",
        )
    return _check("git CLI", "ok", proc.stdout.strip())


def check_ssh() -> Check:
    if shutil.which("ssh") is None:
        return _check(
            "ssh",
            "warn",
            "no ssh client on PATH",
            "Needed for SSH remotes and browsing SSH hosts.",
        )
    agent = _cmd(["ssh-add", "-l"])
    hosts = len(locations.ssh_hosts())
    if agent is None or agent.returncode == 2:
        return _check(
            "ssh",
            "warn",
            f"client found, no agent reachable · {hosts} host(s) in ~/.ssh/config",
            "Start ssh-agent and ssh-add your key, or set GITPULSE_SSH_KEY.",
        )
    keys = 0 if agent.returncode == 1 else len(agent.stdout.strip().splitlines())
    status: Status = "ok" if keys else "warn"
    return _check(
        "ssh",
        status,
        f"agent has {keys} key(s) · {hosts} host(s) in ~/.ssh/config",
        "" if keys else "Run ssh-add so batch-mode SSH can authenticate.",
    )


def check_wsl() -> Check | None:
    if sys.platform == "win32":
        distros = locations.wsl_distros()
        running = sum(1 for d in distros if d["running"])
        if not distros:
            return _check("WSL", "warn", "no distro found", "wsl --install, if needed.")
        return _check("WSL", "ok", f"{len(distros)} distro(s), {running} running")
    if locations.is_wsl():
        drives = len(locations.list_locations(include_ssh=False)) - 2
        return _check(
            "WSL",
            "ok",
            f"inside {os.environ.get('WSL_DISTRO_NAME', 'WSL')}, "
            f"{max(drives, 0)} Windows drive(s) mounted",
        )
    return None


def check_config_dir() -> Check:
    d = config.config_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=d, prefix=".probe-"):
            pass
    except OSError as e:
        return _check("config dir", "fail", f"{d}: {e}", "Set GITPULSE_CONFIG_DIR.")
    ws = len(config.list_workspaces())
    tracked = len(config.list_tracked())
    return _check(
        "config dir", "ok", f"{d} · {ws} workspace(s) · {tracked} tracked remote(s)"
    )


def check_caches() -> Check:
    rd = remote.cache_dir()
    clones = sum(1 for _ in rd.iterdir()) if rd.exists() else 0
    digests = len(history.entries())
    state = "on" if history.enabled() else "off (GITPULSE_CACHE)"
    return _check(
        "caches",
        "ok",
        f"{clones} remote clone(s) · {digests} cached digest(s) · cache {state}",
    )


def check_web() -> Check:
    missing = [m for m in ("fastapi", "uvicorn") if importlib.util.find_spec(m) is None]
    if missing:
        return _check(
            "web UI",
            "warn",
            f"missing {', '.join(missing)}",
            'pip install "gitpulse[web]" to use gitpulse serve / gui.',
        )
    return _check("web UI", "ok", "fastapi + uvicorn installed")


def run_all() -> list[Check]:
    steps: list[Callable[[], Check | None]] = [
        check_python,
        check_pygit2,
        check_git,
        check_ssh,
        check_wsl,
        check_config_dir,
        check_caches,
        check_web,
    ]
    out: list[Check] = []
    for step in steps:
        try:
            result = step()
        except Exception as e:
            result = _check(step.__name__.removeprefix("check_"), "fail", str(e))
        if result is not None:
            out.append(result)
    return out


def make_check(name: str, status: Status, detail: str, hint: str = "") -> Check:
    return _check(name, status, detail, hint)
