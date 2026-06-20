from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _exe() -> str:
    try:
        found = shutil.which("gitpulse")
    except Exception:
        found = None
    if found:
        return found
    return f"{sys.executable} -m gitpulse.cli.main"


def systemd_web(host: str, port: int) -> tuple[str, str, str]:
    unit = f"""[Unit]
Description=GitPulse web UI
After=network.target

[Service]
Type=simple
ExecStart={_exe()} serve --host {host} --port {port} --no-open
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
    service = f"""[Unit]
Description=GitPulse periodic digest

[Service]
Type=oneshot
ExecStart={_exe()} digest {path} --when {when} {' '.join(f'--to {c}' for c in to.split(','))}
"""
    timer = f"""[Unit]
Description=GitPulse digest timer

[Timer]
OnBootSec=5min
OnUnitActiveSec={every}
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


def launchd_web(host: str, port: int) -> tuple[str, str, str]:
    exe = _exe().split()
    args = "".join(
        f"\n    <string>{a}</string>"
        for a in [*exe, "serve", "--host", host, "--port", str(port), "--no-open"]
    )
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
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
    exe = _exe().split()
    parts = [*exe, "digest", path, "--when", when]
    for c in to.split(","):
        parts += ["--to", c]
    args = "".join(f"\n    <string>{a}</string>" for a in parts)
    secs = {"m": 60, "h": 3600, "d": 86400}.get(every[-1], 3600) * int(every[:-1] or 1)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.gitpulse.digest</string>
  <key>ProgramArguments</key><array>{args}
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
    cmd = f"{_exe()} serve --host {host} --port {port} --no-open"
    script = f"""@echo off
REM GitPulse web UI — register as a logon task that runs in the background.
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
    unit = every[-1]
    n = every[:-1] or "1"
    sc = {"m": "MINUTE", "h": "HOURLY", "d": "DAILY"}.get(unit, "HOURLY")
    chans = " ".join(f"--to {c}" for c in to.split(","))
    cmd = f"{_exe()} digest {path} --when {when} {chans}"
    script = f"""@echo off
REM GitPulse periodic digest.
schtasks /Create /TN "GitPulse Digest" /SC {sc} /MO {n} ^
  /TR "{cmd}" /F
echo Task "GitPulse Digest" created (every {n} {sc.lower()}).
"""
    hint = (
        "Save as install-gitpulse-digest.bat and run it.\n"
        'Remove later with:  schtasks /Delete /TN "GitPulse Digest" /F'
    )
    return "install-gitpulse-digest.bat", script, hint


def for_platform(kind: str, **kw) -> tuple[str, str, str]:
    """kind = 'web' or 'watch'. Returns (filename, contents, install_hint)."""
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
