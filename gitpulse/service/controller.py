from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TypedDict

from ..core import config as gp_config

# Detach the child from this console so it survives the terminal that spawned
# it. These constants only exist on Windows; POSIX gets start_new_session.
if sys.platform == "win32":
    _DETACHED_FLAGS = (
        subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NO_WINDOW
    )
    _NEW_SESSION = False
else:
    _DETACHED_FLAGS = 0
    _NEW_SESSION = True


class ServiceStatus(TypedDict):
    running: bool
    pid: int | None
    log: str


class StartResult(TypedDict):
    started: bool
    already: bool
    pid: int | None
    url: str | None
    error: str | None
    log: str


class StopResult(TypedDict):
    stopped: bool
    pid: int | None
    reason: str


class ShutdownResult(TypedDict):
    killed: list[int]
    failed: list[int]
    port: int
    count: int


def _runtime_dir() -> Path:
    d = gp_config.config_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def pid_file() -> Path:
    return _runtime_dir() / "server.pid"


def log_file() -> Path:
    return _runtime_dir() / "server.log"


def _read_pid() -> int | None:
    p = pid_file()
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except (ValueError, OSError):
        return None


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            from ..core.procutil import run as _prun

            out = _prun(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
            )
            return str(pid) in out.stdout
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def status() -> ServiceStatus:
    pid = _read_pid()
    if pid and _alive(pid):
        return {"running": True, "pid": pid, "log": str(log_file())}
    return {"running": False, "pid": None, "log": str(log_file())}


def start(host: str = "127.0.0.1", port: int = 8420) -> StartResult:
    url = f"http://{host}:{port}"
    log_path = str(log_file())
    st = status()
    if st["running"]:
        return {
            "started": False,
            "already": True,
            "pid": st["pid"],
            "url": url,
            "error": None,
            "log": log_path,
        }

    log = open(log_file(), "ab")  # noqa: SIM115
    cmd = [
        sys.executable,
        "-m",
        "gitpulse.cli.main",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
        "--no-open",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        creationflags=_DETACHED_FLAGS,
        start_new_session=_NEW_SESSION,
    )
    pid_file().write_text(str(proc.pid))

    time.sleep(1.2)
    if not _alive(proc.pid):
        return {
            "started": False,
            "already": False,
            "pid": None,
            "url": None,
            "error": "server exited immediately; see log",
            "log": log_path,
        }
    return {
        "started": True,
        "already": False,
        "pid": proc.pid,
        "url": url,
        "error": None,
        "log": log_path,
    }


def stop() -> StopResult:
    pid = _read_pid()
    if not pid or not _alive(pid):
        pid_file().unlink(missing_ok=True)
        return {"stopped": False, "pid": None, "reason": "not running"}
    try:
        if os.name == "nt":
            from ..core.procutil import run as _prun

            _prun(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            for _ in range(10):
                time.sleep(0.3)
                if not _alive(pid):
                    break
            else:
                os.kill(pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    pid_file().unlink(missing_ok=True)
    return {"stopped": True, "pid": pid, "reason": ""}


def _is_gitpulse_server(name: str, cmdline: list[str]) -> bool:
    name = (name or "").lower()
    if name in ("gitpulse", "gitpulse.exe", "gitpulse-gui", "gitpulse-gui.exe"):
        return True
    args = [a.lower() for a in (cmdline or [])]
    if not args:
        return False
    joined = " ".join(args)
    runs_python = any("python" in a for a in args[:1]) or "python" in (
        args[0] if args else ""
    )
    invokes_gitpulse = (
        "gitpulse.cli.main" in joined
        or "-m gitpulse" in joined
        or any(
            a.endswith("gitpulse")
            or a.endswith("gitpulse.exe")
            or a.endswith("gitpulse-gui")
            for a in args
        )
    )
    is_serve = "serve" in args or "gitpulse-gui" in joined
    exe_is_script = args and (
        args[0].endswith("gitpulse")
        or args[0].endswith("gitpulse.exe")
        or args[0].endswith("gitpulse-gui")
        or args[0].endswith("gitpulse-gui.exe")
    )
    if exe_is_script:
        return True
    return runs_python and invokes_gitpulse and is_serve


def _find_gitpulse_pids() -> list[int]:
    me = os.getpid()
    parent = os.getppid()
    pids: set[int] = set()
    try:
        import psutil

        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            info = p.info
            pid: int = info["pid"]
            if pid in (me, parent):
                continue
            if _is_gitpulse_server(info.get("name") or "", info.get("cmdline") or []):
                pids.add(pid)
        return list(pids)
    except Exception:
        pass

    if os.name == "nt":
        from ..core.procutil import run as _prun

        out = _prun(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True)
        for line in (out.stdout or "").splitlines():
            parts = [c.strip('"') for c in line.split('","')]
            if len(parts) >= 2 and parts[0].lower() in (
                "gitpulse.exe",
                "gitpulse-gui.exe",
            ):
                try:
                    pid = int(parts[1])
                    if pid not in (me, parent):
                        pids.add(pid)
                except ValueError:
                    pass
    else:
        from ..core.procutil import run as _prun

        out = _prun(["pgrep", "-af", "gitpulse"], capture_output=True, text=True)
        for line in (out.stdout or "").splitlines():
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            if pid in (me, parent):
                continue
            if _is_gitpulse_server("", parts[1].split()):
                pids.add(pid)
    return list(pids)


def _pids_on_port(port: int) -> list[int]:
    me = os.getpid()
    found: set[int] = set()
    try:
        import psutil

        for c in psutil.net_connections(kind="inet"):
            if c.laddr and c.laddr.port == port and c.pid and c.pid != me:
                found.add(c.pid)
        return list(found)
    except Exception:
        pass
    if os.name == "nt":
        from ..core.procutil import run as _prun

        out = _prun(["netstat", "-ano"], capture_output=True, text=True)
        for line in (out.stdout or "").splitlines():
            if f":{port} " in line or line.strip().endswith(f":{port}"):
                parts = line.split()
                if parts:
                    try:
                        pid = int(parts[-1])
                        if pid != me:
                            found.add(pid)
                    except ValueError:
                        pass
    return list(found)


def _kill(pid: int) -> bool:
    try:
        if os.name == "nt":
            from ..core.procutil import run as _prun

            _prun(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)
        return True
    except (OSError, ProcessLookupError):
        return False


def shutdown_all(port: int = 8420) -> ShutdownResult:
    targets = set(_find_gitpulse_pids()) | set(_pids_on_port(port))
    targets.discard(os.getpid())
    killed: list[int] = []
    failed: list[int] = []
    for pid in targets:
        (killed if _kill(pid) else failed).append(pid)
    pid_file().unlink(missing_ok=True)
    return {
        "killed": sorted(killed),
        "failed": sorted(failed),
        "port": port,
        "count": len(killed),
    }
