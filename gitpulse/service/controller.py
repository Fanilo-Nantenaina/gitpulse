"""Cross-platform background control for the GitPulse web server.

Uses a PID file under the config dir so `start` / `stop` / `status` work the
same on Windows, Linux, and macOS without a system service manager. For a true
boot-time service, see `units.py` (systemd / launchd / Windows Task Scheduler).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from ..core import config as gp_config


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
        os.kill(pid, 0)  # signal 0 = existence check
        return True
    except (OSError, ProcessLookupError):
        return False


def status() -> dict:
    pid = _read_pid()
    if pid and _alive(pid):
        return {"running": True, "pid": pid, "log": str(log_file())}
    return {"running": False, "pid": None, "log": str(log_file())}


def start(host: str = "127.0.0.1", port: int = 8420) -> dict:
    """Launch `gitpulse serve` detached, writing a PID file. Idempotent."""
    st = status()
    if st["running"]:
        return {
            "started": False,
            "already": True,
            "pid": st["pid"],
            "url": f"http://{host}:{port}",
        }

    log = open(log_file(), "ab")
    # Re-invoke our own CLI so the child is a normal `serve` process.
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

    kwargs: dict = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        # detach into its own process group AND suppress any console window
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True  # detach via setsid

    proc = subprocess.Popen(cmd, **kwargs)
    pid_file().write_text(str(proc.pid))

    # confirm it stayed up briefly
    time.sleep(1.2)
    if not _alive(proc.pid):
        return {
            "started": False,
            "error": "server exited immediately; see log",
            "log": str(log_file()),
        }
    return {"started": True, "pid": proc.pid, "url": f"http://{host}:{port}"}


def stop() -> dict:
    pid = _read_pid()
    if not pid or not _alive(pid):
        pid_file().unlink(missing_ok=True)
        return {"stopped": False, "reason": "not running"}
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
    return {"stopped": True, "pid": pid}
