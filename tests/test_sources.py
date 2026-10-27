from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from gitpulse.cli import main as cli_main
from gitpulse.core import config, sources, standup, workspace
from gitpulse.web.server import app

MakeRepo = Callable[..., Path]
SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 12, 31, tzinfo=timezone.utc)
runner = CliRunner()
client = TestClient(app, base_url="http://127.0.0.1:8420")


@pytest.fixture
def two_places(tmp_path: Path, make_repo: MakeRepo) -> tuple[Path, Path]:
    win = tmp_path / "windows"
    wsl = tmp_path / "wsl"
    make_repo("api", [("feat: api", "2026-05-04T10:00:00", {"a.py": "1"})], parent=win)
    make_repo("web", [("feat: web", "2026-05-05T10:00:00", {"w.js": "1"})], parent=win)
    other = make_repo(
        "api", [("fix: other api", "2026-05-06T10:00:00", {"b.py": "1"})], parent=wsl
    )
    return win, other


@pytest.mark.parametrize(
    ("spec", "url"),
    [
        ("https://github.com/o/r.git", True),
        ("git@github.com:o/r.git", True),
        ("ssh://vps/srv/git/a.git", True),
        ("C:\\Users\\me\\code", False),
        ("\\\\wsl.localhost\\Ubuntu\\home\\me", False),
        ("/home/me/code", False),
        ("@client", False),
    ],
)
def test_url_detection(spec: str, url: bool) -> None:
    assert sources.is_url(spec) is url


def test_named_workspace_merges_members_from_several_places(
    two_places: tuple[Path, Path],
) -> None:
    win, other = two_places
    config.add_to_workspace("client", [str(win), str(other)])
    repo_set = sources.expand("@client")
    assert repo_set.name == "@client"
    assert sorted(r.name for r in repo_set.refs) == ["api", "api-2", "web"]
    activity, failures = workspace.collect("@client", SINCE, UNTIL)
    assert failures == []
    assert activity.is_workspace
    assert activity.repo_name == "@client"
    assert activity.commit_count == 3
    assert set(activity.commits_per_repo) == {"api", "api-2", "web"}


def test_unreachable_members_are_reported_not_fatal(
    two_places: tuple[Path, Path], tmp_path: Path
) -> None:
    win, _ = two_places
    config.add_to_workspace("mixed", [str(win), str(tmp_path / "gone")])
    activity, failures = workspace.collect("@mixed", SINCE, UNTIL)
    assert activity.commit_count == 2
    assert len(failures) == 1
    assert "gone" in failures[0]["path"]


def test_unknown_workspace_explains_how_to_create_it() -> None:
    with pytest.raises(ValueError, match="gitpulse workspace add"):
        sources.expand("@nope")


def test_workspace_names_and_nesting_are_validated() -> None:
    with pytest.raises(ValueError, match="Invalid workspace name"):
        config.add_to_workspace("bad name", ["/x"])
    with pytest.raises(ValueError, match="cannot contain another workspace"):
        config.add_to_workspace("ok", ["@other"])


def test_remove_member_then_workspace() -> None:
    config.add_to_workspace("w", ["/a", "/b"])
    assert config.remove_from_workspace("w", ["/a"])
    assert config.get_workspace("w") == ["/b"]
    assert config.remove_from_workspace("@w")
    assert config.get_workspace("w") is None
    assert not config.remove_from_workspace("w")


def test_standup_accepts_a_named_workspace(two_places: tuple[Path, Path]) -> None:
    win, other = two_places
    config.add_to_workspace("client", [str(win), str(other)])
    ctx = standup.gather("@client")
    assert ctx.repo_name == "@client"
    assert {s.name for s in ctx.repos} == {"api", "api-2", "web"}


def test_cli_workspace_lifecycle(two_places: tuple[Path, Path]) -> None:
    win, other = two_places
    res = runner.invoke(
        cli_main.app, ["workspace", "add", "client", str(win), str(other)]
    )
    assert res.exit_code == 0, res.output
    assert "2 member(s)" in res.output
    res = runner.invoke(cli_main.app, ["workspace", "list"], env={"COLUMNS": "200"})
    assert "@client" in res.output
    res = runner.invoke(
        cli_main.app, ["workspace", "show", "client"], env={"COLUMNS": "200"}
    )
    assert res.exit_code == 0, res.output
    assert "3 repositories" in res.output
    res = runner.invoke(
        cli_main.app,
        ["log", "@client", "-w", "2026-05-01..2026-05-31"],
        env={"COLUMNS": "200"},
    )
    assert res.exit_code == 0, res.output
    assert "[api-2]" in res.output
    res = runner.invoke(cli_main.app, ["workspace", "remove", "client"])
    assert "Removed" in res.output


def test_cli_reports_unknown_workspace_cleanly() -> None:
    res = runner.invoke(cli_main.app, ["summary", "@nope", "-p", "local"])
    assert res.exit_code == 1
    assert "Unknown workspace @nope" in res.output


def test_api_workspaces_and_locations(two_places: tuple[Path, Path]) -> None:
    win, _ = two_places
    r = client.post("/api/workspaces", json={"name": "client", "members": [str(win)]})
    assert r.status_code == 200
    assert r.json()["members"] == [str(win)]
    assert client.get("/api/workspaces").json()["workspaces"][0]["name"] == "client"
    locs = client.get("/api/locations").json()["locations"]
    assert locs[0] == {
        "kind": "workspace",
        "label": "@client",
        "path": "@client",
        "detail": "1 member(s)",
    }
    r = client.post(
        "/api/log", json={"path": "@client", "when": "2026-05-01..2026-05-31"}
    )
    assert r.status_code == 200
    assert r.json()["activity"]["is_workspace"] is True
    assert (
        client.post(
            "/api/workspaces", json={"name": "x y", "members": ["/a"]}
        ).status_code
        == 400
    )
    assert client.delete("/api/workspaces", params={"name": "client"}).json() == {
        "removed": True
    }
