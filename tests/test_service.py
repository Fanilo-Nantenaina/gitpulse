from __future__ import annotations

import sys

import pytest

from gitpulse.service import controller, units


def test_status_stopped_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("GITPULSE_CONFIG_DIR", str(tmp_path))
    st = controller.status()
    assert st["running"] is False
    assert st["pid"] is None


def test_pid_and_log_paths_under_config(tmp_path, monkeypatch):
    monkeypatch.setenv("GITPULSE_CONFIG_DIR", str(tmp_path))
    assert str(tmp_path) in str(controller.pid_file())
    assert str(tmp_path) in str(controller.log_file())


def test_alive_false_for_bogus_pid():
    assert controller._alive(0) is False
    assert controller._alive(-1) is False


@pytest.mark.parametrize("plat", ["linux", "darwin", "win32"])
@pytest.mark.parametrize("kind", ["web", "watch"])
def test_unit_generation_all_platforms(plat, kind, monkeypatch):
    monkeypatch.setattr(sys, "platform", plat)
    fname, contents, hint = units.for_platform(
        kind,
        host="127.0.0.1",
        port=8420,
        path="/repo",
        every="24h",
        when="24h",
        to="desktop",
    )
    assert fname and contents and hint
    assert "gitpulse" in contents.lower()
    assert "serve" in contents if kind == "web" else "digest" in contents


def test_unsupported_platform(monkeypatch):
    monkeypatch.setattr(sys, "platform", "sunos5")
    with pytest.raises(RuntimeError):
        units.for_platform("web", host="h", port=1)


def test_systemd_web_has_restart(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    _, contents, _ = units.for_platform("web", host="127.0.0.1", port=8420)
    assert "Restart=on-failure" in contents
    assert "[Install]" in contents


def test_launchd_web_is_plist(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    fname, contents, _ = units.for_platform("web", host="127.0.0.1", port=8420)
    assert fname.endswith(".plist")
    assert "<plist" in contents and "KeepAlive" in contents


def test_windows_web_is_schtasks(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    fname, contents, _ = units.for_platform("web", host="127.0.0.1", port=8420)
    assert fname.endswith(".bat")
    assert "schtasks" in contents


def test_standup_day_window_uses_local_tz():
    from datetime import datetime, timezone, timedelta
    from gitpulse.core import standup

    tz = timezone(timedelta(hours=3))
    target = datetime(2026, 6, 18, 12, 0, tzinfo=tz)
    start, end = standup._day_window(target)
    assert start.utcoffset() == timedelta(hours=3)
    assert start.hour == 0 and end.hour == 23
    assert start.date() == target.date()


def test_procutil_run_works():
    from gitpulse.core import procutil

    r = procutil.run(["git", "--version"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "git version" in r.stdout
