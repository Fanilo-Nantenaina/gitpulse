from __future__ import annotations

import glob
import os
import posixpath
import re
import shlex
import string
import subprocess
import sys
from pathlib import Path
from typing import Literal, TypedDict

from . import config
from .procutil import run as _prun

LocationKind = Literal["workspace", "home", "drive", "wsl", "windows", "ssh"]

WSL_UNC_ROOT = "\\\\wsl.localhost"
_HIDDEN_DISTROS = ("docker-desktop",)
_LXSS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Lxss"
_HOST_RE = re.compile(r"(?!-)[\w.-]+(?:@(?!-)[\w.-]+)?", re.ASCII)
_SSH_OPTION_RE = re.compile(r"(\w+)\s*(?:=\s*|\s+)(.+)")

_SSH_LIST_SCRIPT = (
    'cd -- "${1:-$HOME}" 2>/dev/null || { echo "!nodir"; exit 3; }; '
    "pwd; "
    'if [ -e .git ] || { [ -f HEAD ] && [ -d objects ]; }; then echo "!repo"; fi; '
    'for d in */; do [ -d "$d" ] || continue; d="${d%/}"; '
    'if [ -e "$d/.git" ] || { [ -f "$d/HEAD" ] && [ -d "$d/objects" ]; }; '
    'then echo "R $d"; else echo "D $d"; fi; done'
)


class _LocationBase(TypedDict):
    kind: LocationKind
    label: str
    path: str


class Location(_LocationBase, total=False):
    detail: str
    running: bool
    default: bool
    host: str


class WslDistro(TypedDict):
    name: str
    default: bool
    running: bool


class SshHost(TypedDict):
    alias: str
    hostname: str
    user: str


class SshEntry(TypedDict):
    name: str
    path: str
    is_repo: bool
    url: str


class _SshBrowseBase(TypedDict):
    host: str
    path: str
    parent: str | None
    entries: list[SshEntry]


class SshBrowseResult(_SshBrowseBase, total=False):
    is_repo: bool
    url: str
    error: str


def list_locations(include_ssh: bool = True) -> list[Location]:
    found: list[Location] = [
        {
            "kind": "workspace",
            "label": f"@{name}",
            "path": f"@{name}",
            "detail": f"{len(members)} member(s)",
        }
        for name, members in config.list_workspaces().items()
    ]
    found.append({"kind": "home", "label": "~", "path": str(Path.home())})
    found.extend({"kind": "drive", "label": d, "path": d} for d in drives())
    if sys.platform == "win32":
        found.extend(_wsl_locations())
    elif is_wsl():
        found.extend(_windows_locations())
    if include_ssh:
        for h in ssh_hosts():
            loc: Location = {
                "kind": "ssh",
                "label": h["alias"],
                "path": "",
                "host": h["alias"],
            }
            target = h["hostname"] or h["alias"]
            loc["detail"] = f"{h['user']}@{target}" if h["user"] else target
            found.append(loc)
    return found


def drives() -> list[str]:
    if os.name != "nt":
        return ["/"]
    return [f"{c}:\\" for c in string.ascii_uppercase if Path(f"{c}:\\").exists()]


def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return False


def wsl_unc(distro: str, path: str = "/") -> str:
    tail = path.strip("/").replace("/", "\\")
    return f"{WSL_UNC_ROOT}\\{distro}\\{tail}"


def wsl_distros() -> list[WslDistro]:
    names, default = _registry_distros()
    if not names:
        names = _wsl_list(["-l", "-q"])
        default = names[0] if names else None
    running: set[str] = set()
    if names:
        running = set(_wsl_list(["-l", "--running", "-q"])) & set(names)
    return [
        {"name": n, "default": n == default, "running": n in running}
        for n in names
        if not n.lower().startswith(_HIDDEN_DISTROS)
    ]


def _registry_distros() -> tuple[list[str], str | None]:
    if sys.platform != "win32":
        return [], None
    import winreg

    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _LXSS_KEY)
    except OSError:
        return [], None
    names: list[str] = []
    default_name: str | None = None
    with root:
        try:
            default_id = str(winreg.QueryValueEx(root, "DefaultDistribution")[0])
        except OSError:
            default_id = ""
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with winreg.OpenKey(root, sub) as key:
                    name = str(winreg.QueryValueEx(key, "DistributionName")[0])
            except OSError:
                continue
            names.append(name)
            if sub == default_id:
                default_name = name
    return names, default_name


def _wsl_list(args: list[str]) -> list[str]:
    try:
        proc = _prun(["wsl.exe", *args], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [
        ln.strip() for ln in decode_wsl_output(proc.stdout).splitlines() if ln.strip()
    ]


def decode_wsl_output(raw: bytes) -> str:
    if b"\x00" in raw:
        text = raw.decode("utf-16-le", errors="ignore")
    else:
        text = raw.decode("utf-8", errors="ignore")
    return text.replace("﻿", "")


def _wsl_locations() -> list[Location]:
    found: list[Location] = []
    for d in wsl_distros():
        home = _wsl_home(d["name"]) if d["running"] else None
        found.append(
            {
                "kind": "wsl",
                "label": d["name"],
                "path": home or wsl_unc(d["name"]),
                "running": d["running"],
                "default": d["default"],
            }
        )
    return found


def _wsl_home(distro: str) -> str | None:
    home = Path(wsl_unc(distro, "/home"))
    try:
        users = [p for p in home.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError:
        return None
    if len(users) == 1:
        return str(users[0])
    return str(home) if users else None


def _windows_locations(mnt: str = "/mnt") -> list[Location]:
    found: list[Location] = []
    for letter in string.ascii_lowercase:
        p = os.path.join(mnt, letter)
        if os.path.ismount(p):
            found.append({"kind": "windows", "label": f"{letter.upper()}:", "path": p})
    return found


def ssh_hosts(config: Path | None = None) -> list[SshHost]:
    hosts: dict[str, SshHost] = {}
    _parse_ssh_config(config or Path.home() / ".ssh" / "config", hosts, 0)
    return list(hosts.values())


def _parse_ssh_config(path: Path, hosts: dict[str, SshHost], depth: int) -> None:
    if depth > 4:
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    current: list[SshHost] = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _SSH_OPTION_RE.match(line)
        if not m:
            continue
        key, value = m.group(1).lower(), m.group(2).strip()
        if key == "include":
            for pattern in shlex.split(value):
                target = Path(pattern).expanduser()
                if not target.is_absolute():
                    target = path.parent / target
                for inc in sorted(glob.glob(str(target))):
                    _parse_ssh_config(Path(inc), hosts, depth + 1)
        elif key == "host":
            current = []
            for alias in value.split():
                if any(c in alias for c in "*?!"):
                    continue
                current.append(
                    hosts.setdefault(
                        alias, {"alias": alias, "hostname": "", "user": ""}
                    )
                )
        elif key == "match":
            current = []
        elif key in ("hostname", "user"):
            for entry in current:
                if not entry[key]:
                    entry[key] = value


def valid_ssh_host(host: str) -> bool:
    return bool(_HOST_RE.fullmatch(host))


def ssh_url(host: str, path: str) -> str:
    return f"ssh://{host}/{path.lstrip('/')}"


def _ssh_path_arg(path: str | None) -> str:
    if not path or path == "~":
        return ""
    if path.startswith("~/"):
        return path[2:]
    return path


def ssh_list_dir(
    host: str, path: str | None = None, timeout: float = 20
) -> SshBrowseResult:
    asked = path or "~"
    result: SshBrowseResult = {
        "host": host,
        "path": asked,
        "parent": None,
        "entries": [],
    }
    if not valid_ssh_host(host):
        result["error"] = f"Invalid SSH host: {host!r}"
        return result
    remote = (
        f"sh -c {shlex.quote(_SSH_LIST_SCRIPT)} gitpulse "
        f"{shlex.quote(_ssh_path_arg(path))}"
    )
    try:
        proc = _prun(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "--",
                host,
                remote,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        result["error"] = "No ssh client found on PATH."
        return result
    except subprocess.TimeoutExpired:
        result["error"] = f"ssh {host} timed out after {timeout:.0f}s."
        return result

    lines = proc.stdout.splitlines()
    if proc.returncode != 0 or not lines or not lines[0].startswith("/"):
        result["error"] = _ssh_error(host, asked, proc.stdout, proc.stderr)
        return result

    cwd = lines[0]
    result["path"] = cwd
    result["parent"] = posixpath.dirname(cwd) if cwd != "/" else None
    result["is_repo"] = "!repo" in lines[1:2]
    result["url"] = ssh_url(host, cwd)
    for line in lines[1:]:
        tag, _, name = line.partition(" ")
        if tag not in ("R", "D") or not name or name.startswith("."):
            continue
        child = posixpath.join(cwd, name)
        result["entries"].append(
            {
                "name": name,
                "path": child,
                "is_repo": tag == "R",
                "url": ssh_url(host, child),
            }
        )
    result["entries"].sort(key=lambda e: e["name"].lower())
    return result


def _ssh_error(host: str, asked: str, stdout: str, stderr: str) -> str:
    if "!nodir" in stdout:
        return f"Not a directory on {host}: {asked}"
    detail = next((ln for ln in reversed(stderr.splitlines()) if ln.strip()), "")
    low = detail.lower()
    if "host key verification failed" in low:
        hint = f"Connect once with `ssh {host}` in a terminal to accept its host key."
    elif "permission denied" in low:
        hint = "GitPulse needs key or agent auth (no password prompts)."
    else:
        hint = "Check that `ssh " + host + "` works from a terminal."
    return f"ssh {host} failed: {detail.rstrip('.') or 'no output'}. {hint}"
