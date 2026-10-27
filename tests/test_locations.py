from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from gitpulse.cli import main as cli_main
from gitpulse.core import locations
from gitpulse.web import browse
from gitpulse.web.server import app

client = TestClient(app, base_url="http://127.0.0.1:8420")


def _completed(
    stdout: str = "", stderr: str = "", code: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["ssh"], code, stdout=stdout, stderr=stderr)


class _FakeSsh:
    def __init__(self, result: subprocess.CompletedProcess[str]) -> None:
        self.result = result
        self.args: list[str] = []

    def __call__(
        self, args: Sequence[str], **_: Any
    ) -> subprocess.CompletedProcess[str]:
        self.args = list(args)
        return self.result


def test_ssh_config_hosts_follow_includes_and_skip_patterns(tmp_path: Path) -> None:
    (tmp_path / "conf.d").mkdir()
    (tmp_path / "conf.d" / "work.conf").write_text(
        "Host forge\n  HostName git.example.com\n  User me\n"
    )
    cfg = tmp_path / "config"
    cfg.write_text(
        "Include conf.d/*.conf\n"
        "Host *\n  ServerAliveInterval 30\n"
        "Host vps vps-alias !nope\n  HostName=203.0.113.7\n  User deploy\n"
        "Host *.internal\n  User root\n"
        "Match host other\n  User ignored\n"
    )
    hosts = locations.ssh_hosts(cfg)
    assert [h["alias"] for h in hosts] == ["forge", "vps", "vps-alias"]
    by = {h["alias"]: h for h in hosts}
    assert by["forge"] == {
        "alias": "forge",
        "hostname": "git.example.com",
        "user": "me",
    }
    assert by["vps-alias"]["hostname"] == "203.0.113.7"
    assert by["vps"]["user"] == "deploy"


def test_missing_ssh_config_yields_no_hosts(tmp_path: Path) -> None:
    assert locations.ssh_hosts(tmp_path / "absent") == []


@pytest.mark.parametrize("host", ["vps", "me@git.example.com", "host-1.lan", "a_b"])
def test_valid_ssh_hosts(host: str) -> None:
    assert locations.valid_ssh_host(host)


@pytest.mark.parametrize(
    "host",
    ["-oProxyCommand=calc", "a b", "a;rm -rf ~", "", "me@-x", "host:22", "$(id)"],
)
def test_ssh_host_rejects_option_and_shell_injection(host: str) -> None:
    assert not locations.valid_ssh_host(host)


def test_wsl_output_decodes_utf16_and_utf8() -> None:
    utf16 = "﻿Ubuntu-26.04\r\nkali-linux\r\n".encode("utf-16-le")
    assert locations.decode_wsl_output(utf16).split() == ["Ubuntu-26.04", "kali-linux"]
    assert locations.decode_wsl_output(b"Debian\n").split() == ["Debian"]


def test_wsl_unc_paths() -> None:
    assert locations.wsl_unc("Ubuntu") == "\\\\wsl.localhost\\Ubuntu\\"
    assert (
        locations.wsl_unc("Ubuntu", "/home/me/code")
        == "\\\\wsl.localhost\\Ubuntu\\home\\me\\code"
    )


def test_wsl_distros_hide_docker_and_mark_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        locations,
        "_registry_distros",
        lambda: (["Ubuntu", "docker-desktop", "Fedora"], "Fedora"),
    )

    def fake_list(args: list[str]) -> list[str]:
        if "--running" in args:
            return ["Ubuntu", "docker-desktop", "There are no other distros."]
        return ["ignored"]

    monkeypatch.setattr(locations, "_wsl_list", fake_list)
    assert locations.wsl_distros() == [
        {"name": "Ubuntu", "default": False, "running": True},
        {"name": "Fedora", "default": True, "running": False},
    ]


def test_wsl_distros_fall_back_to_wsl_exe(monkeypatch: pytest.MonkeyPatch) -> None:

    def no_registry() -> tuple[list[str], str | None]:
        return [], None

    def fake_list(args: list[str]) -> list[str]:
        return [] if "--running" in args else ["Arch", "Alpine"]

    monkeypatch.setattr(locations, "_registry_distros", no_registry)
    monkeypatch.setattr(locations, "_wsl_list", fake_list)
    distros = locations.wsl_distros()
    assert [d["name"] for d in distros] == ["Arch", "Alpine"]
    assert distros[0]["default"] and not distros[1]["default"]


def test_windows_drives_seen_from_wsl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for letter in ("c", "d", "wsl"):
        (tmp_path / letter).mkdir()
    mounted = {str(tmp_path / "c"), str(tmp_path / "d")}

    def fake_ismount(p: str) -> bool:
        return p in mounted

    monkeypatch.setattr(locations.os.path, "ismount", fake_ismount)
    found = locations._windows_locations(str(tmp_path))
    assert [(f["label"], f["kind"]) for f in found] == [
        ("C:", "windows"),
        ("D:", "windows"),
    ]


def test_ssh_listing_parses_entries_and_builds_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSsh(_completed("/srv/code\nD docs\nR api\nR mirror.git\nD .cache\n"))
    monkeypatch.setattr(locations, "_prun", fake)
    res = locations.ssh_list_dir("vps", "~/code")
    assert "error" not in res
    assert res["path"] == "/srv/code"
    assert res["parent"] == "/srv"
    assert res.get("url") == "ssh://vps/srv/code"
    assert res.get("is_repo") is False
    assert [(e["name"], e["is_repo"]) for e in res["entries"]] == [
        ("api", True),
        ("docs", False),
        ("mirror.git", True),
    ]
    assert res["entries"][0]["url"] == "ssh://vps/srv/code/api"
    host_at = fake.args.index("vps")
    assert fake.args[host_at - 1] == "--"
    assert "BatchMode=yes" in fake.args
    assert fake.args[-1].endswith(" code")


def test_ssh_listing_reports_auth_failures_with_a_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSsh(
        _completed(stderr="me@vps: Permission denied (publickey).\n", code=255)
    )
    monkeypatch.setattr(locations, "_prun", fake)
    res = locations.ssh_list_dir("me@vps")
    assert "Permission denied" in res.get("error", "")
    assert "agent" in res.get("error", "")
    assert res["entries"] == []


def test_ssh_listing_reports_missing_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(locations, "_prun", _FakeSsh(_completed("!nodir\n", code=3)))
    res = locations.ssh_list_dir("vps", "/nope")
    assert "Not a directory" in res.get("error", "")


def test_ssh_listing_never_spawns_for_an_invalid_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeSsh(_completed("/"))
    monkeypatch.setattr(locations, "_prun", fake)
    assert "Invalid" in locations.ssh_list_dir("-oProxyCommand=x").get("error", "")
    assert fake.args == []


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX sh")
def test_remote_listing_script_runs_under_sh(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    (tmp_path / "work" / ".git").mkdir(parents=True)
    bare = tmp_path / "bare.git"
    (bare / "objects").mkdir(parents=True)
    (bare / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / "file.txt").write_text("x")
    proc = subprocess.run(
        ["sh", "-c", locations._SSH_LIST_SCRIPT, "gitpulse", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = proc.stdout.splitlines()
    assert sorted(lines[1:]) == ["D plain", "R bare.git", "R work"]


def test_browse_does_not_flag_subfolders_of_a_repo(linear_repo: Path) -> None:
    (linear_repo / "src").mkdir()
    res = browse.list_dir(str(linear_repo))
    assert res.get("is_repo") is True
    assert [(e["name"], e["is_repo"]) for e in res["entries"]] == [("src", False)]


def test_browse_flags_bare_repositories(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "--bare", str(tmp_path / "m.git")], check=True)
    res = browse.list_dir(str(tmp_path))
    assert [(e["name"], e["is_repo"]) for e in res["entries"]] == [("m.git", True)]


def test_locations_endpoint_lists_home() -> None:
    r = client.get("/api/locations")
    assert r.status_code == 200
    kinds = [loc["kind"] for loc in r.json()["locations"] if loc["kind"] != "workspace"]
    assert kinds[0] == "home"
    assert "drive" in kinds


def test_ssh_browse_endpoint_rejects_bad_hosts() -> None:
    r = client.post("/api/browse/ssh", json={"host": "-oProxyCommand=calc"})
    assert r.status_code == 400


def test_ssh_browse_endpoint_refuses_cross_site_posts() -> None:
    r = client.post(
        "/api/browse/ssh",
        json={"host": "vps"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403


def test_ssh_browse_endpoint_returns_listing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(locations, "_prun", _FakeSsh(_completed("/home/me\nR app\n")))
    r = client.post("/api/browse/ssh", json={"host": "vps"})
    assert r.status_code == 200
    assert r.json()["entries"][0]["url"] == "ssh://vps/home/me/app"


def test_locations_command_prints_every_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake: list[locations.Location] = [
        {"kind": "home", "label": "~", "path": "/home/me"},
        {
            "kind": "wsl",
            "label": "Ubuntu",
            "path": "\\\\wsl.localhost\\Ubuntu\\",
            "running": False,
            "default": True,
        },
        {
            "kind": "ssh",
            "label": "vps",
            "path": "",
            "host": "vps",
            "detail": "deploy@203.0.113.7",
        },
    ]
    monkeypatch.setattr(locations, "list_locations", lambda include_ssh=True: fake)
    res = CliRunner().invoke(cli_main.app, ["locations"], env={"COLUMNS": "200"})
    assert res.exit_code == 0, res.output
    assert "stopped (starts on open), default" in res.output
    assert "ssh://vps/<path>" in res.output
    assert "deploy@203.0.113.7" in res.output
