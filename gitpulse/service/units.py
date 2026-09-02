
from __future__ import annotations

import re
import shutil
import sys
from xml.sax.saxutils import escape as xml_escape
from xml.sax.saxutils import quoteattr as xml_quoteattr  # noqa: F401  (API parity)

_WHEN_RE = re.compile(r"^[\w.:-]+(?:\.\.[\w.:-]+)?$")
_EVERY_RE = re.compile(r"^(\d+)([mhd])$")
_CHANNEL_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_HOST_RE = re.compile(r"^[A-Za-z0-9._:\[\]-]+$")


class UnitValueError(ValueError):
    pass




def _check_no_control_chars(value: str, label: str) -> str:
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise UnitValueError(f"{label} must not contain control characters or newlines")
    return value


def validate_when(when: str) -> str:
    when = _check_no_control_chars(str(when), "--when")
    if not _WHEN_RE.match(when):
        raise UnitValueError(
            f"invalid --when value {when!r}: expected something like 7d, 24h, "
            "2026-06-15, yesterday, or a..b range"
        )
    return when


def validate_every(every: str) -> tuple[int, str]:
    m = _EVERY_RE.match(_check_no_control_chars(str(every), "--every").strip())
    if not m:
        raise UnitValueError(
            f"invalid --every value {every!r}: expected <number><m|h|d>, e.g. 30m"
        )
    count = int(m.group(1))
    if count < 1:
        raise UnitValueError("--every must be at least 1")
    return count, m.group(2)


def validate_channels(to: str) -> list[str]:
    channels = [c.strip() for c in str(to).split(",") if c.strip()]
    if not channels:
        raise UnitValueError("--to must name at least one channel")
    for c in channels:
        if not _CHANNEL_RE.match(c):
            raise UnitValueError(f"invalid channel name {c!r}")
    return channels


def validate_host(host: str) -> str:
    host = _check_no_control_chars(str(host), "--host").strip()
    if not _HOST_RE.match(host):
        raise UnitValueError(f"invalid host {host!r}")
    return host


def validate_port(port: int) -> int:
    port = int(port)
    if not 1 <= port <= 65535:
        raise UnitValueError(f"port out of range: {port}")
    return port


def validate_path(path: str) -> str:
    return _check_no_control_chars(str(path), "repository path")




def _exe_argv() -> list[str]:
    try:
        found = shutil.which("gitpulse")
    except (OSError, AttributeError):
        found = None
    if found:
        return [found]
    return [sys.executable, "-m", "gitpulse.cli.main"]


def _exe() -> str:
    return " ".join(_exe_argv())




def _systemd_quote(arg: str) -> str:
    _check_no_control_chars(arg, "unit argument")
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{escaped}"'


def _systemd_exec(*args: str) -> str:
    return " ".join(_systemd_quote(a) for a in args)


def _plist_args(*args: str) -> str:
    return "".join(
        f"\n    <string>{xml_escape(_check_no_control_chars(a, 'unit argument'))}"
        f"</string>"
        for a in args
    )


def _bat_command(*args: str) -> str:
    out = []
    for a in args:
        _check_no_control_chars(a, "unit argument")
        if '"' in a:
            raise UnitValueError(
                f"value {a!r} contains a double quote, which cannot be "
                "represented in a Windows scheduled-task command"
            )
        a = a.replace("%", "%%")
        out.append(f"\\?{a}\\?" if " " in a else a)
    return " ".join(o.replace("\\?", '\\"') for o in out)




def systemd_web(host: str, port: int) -> tuple[str, str, str]:
    host, port = validate_host(host), validate_port(port)
    exec_start = _systemd_exec(
        *_exe_argv(), "serve", "--host", host, "--port", str(port), "--no-open"
    )
    unit = f"""[Unit]
Description=GitPulse web UI
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure

[Install]
WantedBy=default.target
"""
    hint = (
        "Save to ~/.config/systemd/user/gitpulse-web.service, then:\n"
        "  systemctl --user daemon-reload\n"
        "  systemctl --user enable --now gitpulse-web.service\n"
        "  loginctl enable-linger $USER   # keep running after logout"
    )
    return "gitpulse-web.service", unit, hint


def systemd_watch(path: str, every: str, when: str, to: str) -> tuple[str, str, str]:
    path, when = validate_path(path), validate_when(when)
    count, unit_letter = validate_every(every)
    argv = [*_exe_argv(), "digest", path, "--when", when]
    for channel in validate_channels(to):
        argv += ["--to", channel]
    service = f"""[Unit]
Description=GitPulse periodic digest

[Service]
Type=oneshot
ExecStart={_systemd_exec(*argv)}
"""
    timer = f"""[Unit]
Description=GitPulse digest timer

[Timer]
OnBootSec=5min
OnUnitActiveSec={count}{unit_letter}
Persistent=true

[Install]
WantedBy=timers.target
"""
    hint = (
        "Save the .service and .timer to ~/.config/systemd/user/, then:\n"
        "  systemctl --user daemon-reload\n"
        "  systemctl --user enable --now gitpulse-digest.timer"
    )
    return "gitpulse-digest", service + "\n---TIMER---\n" + timer, hint



_PLIST_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>"""


def launchd_web(host: str, port: int) -> tuple[str, str, str]:
    host, port = validate_host(host), validate_port(port)
    args = _plist_args(
        *_exe_argv(), "serve", "--host", host, "--port", str(port), "--no-open"
    )
    plist = f"""{_PLIST_HEAD}
  <key>Label</key><string>com.gitpulse.web</string>
  <key>ProgramArguments</key><array>{args}
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
"""
    hint = (
        "Save to ~/Library/LaunchAgents/com.gitpulse.web.plist, then:\n"
        "  launchctl load ~/Library/LaunchAgents/com.gitpulse.web.plist\n"
        "  launchctl start com.gitpulse.web"
    )
    return "com.gitpulse.web.plist", plist, hint


def launchd_watch(path: str, every: str, when: str, to: str) -> tuple[str, str, str]:
    path, when = validate_path(path), validate_when(when)
    count, unit_letter = validate_every(every)
    argv = [*_exe_argv(), "digest", path, "--when", when]
    for channel in validate_channels(to):
        argv += ["--to", channel]
    secs = count * {"m": 60, "h": 3600, "d": 86400}[unit_letter]
    plist = f"""{_PLIST_HEAD}
  <key>Label</key><string>com.gitpulse.digest</string>
  <key>ProgramArguments</key><array>{_plist_args(*argv)}
  </array>
  <key>StartInterval</key><integer>{secs}</integer>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
"""
    hint = (
        "Save to ~/Library/LaunchAgents/com.gitpulse.digest.plist, then:\n"
        "  launchctl load ~/Library/LaunchAgents/com.gitpulse.digest.plist"
    )
    return "com.gitpulse.digest.plist", plist, hint




def windows_web(host: str, port: int) -> tuple[str, str, str]:
    host, port = validate_host(host), validate_port(port)
    cmd = _bat_command(
        *_exe_argv(), "serve", "--host", host, "--port", str(port), "--no-open"
    )
    script = f"""@echo off
REM GitPulse web UI - register as a logon task that runs in the background.
schtasks /Create /TN "GitPulse Web" /SC ONLOGON /RL LIMITED ^
  /TR "{cmd}" /F
echo Task "GitPulse Web" created. It starts the UI at logon.
echo Start it now with:  schtasks /Run /TN "GitPulse Web"
"""
    hint = (
        "Save as install-gitpulse-web.bat and run it (double-click).\n"
        'Remove later with:  schtasks /Delete /TN "GitPulse Web" /F'
    )
    return "install-gitpulse-web.bat", script, hint


def windows_watch(path: str, every: str, when: str, to: str) -> tuple[str, str, str]:
    path, when = validate_path(path), validate_when(when)
    count, unit_letter = validate_every(every)
    sc = {"m": "MINUTE", "h": "HOURLY", "d": "DAILY"}[unit_letter]
    argv = [*_exe_argv(), "digest", path, "--when", when]
    for channel in validate_channels(to):
        argv += ["--to", channel]
    cmd = _bat_command(*argv)
    script = f"""@echo off
REM GitPulse periodic digest.
schtasks /Create /TN "GitPulse Digest" /SC {sc} /MO {count} ^
  /TR "{cmd}" /F
echo Task "GitPulse Digest" created (every {count} {sc.lower()}).
"""
    hint = (
        "Save as install-gitpulse-digest.bat and run it.\n"
        'Remove later with:  schtasks /Delete /TN "GitPulse Digest" /F'
    )
    return "install-gitpulse-digest.bat", script, hint


def for_platform(kind: str, **kw) -> tuple[str, str, str]:
    plat = sys.platform
    if plat.startswith("linux"):
        return (
            systemd_web(kw["host"], kw["port"])
            if kind == "web"
            else systemd_watch(kw["path"], kw["every"], kw["when"], kw["to"])
        )
    if plat == "darwin":
        return (
            launchd_web(kw["host"], kw["port"])
            if kind == "web"
            else launchd_watch(kw["path"], kw["every"], kw["when"], kw["to"])
        )
    if plat.startswith("win"):
        return (
            windows_web(kw["host"], kw["port"])
            if kind == "web"
            else windows_watch(kw["path"], kw["every"], kw["when"], kw["to"])
        )
    raise RuntimeError(f"Unsupported platform: {plat}")
