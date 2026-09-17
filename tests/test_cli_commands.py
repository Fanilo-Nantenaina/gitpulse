from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gitpulse.cli import main as cli_main

EXPECTED_COMMANDS = {
    "cache-clear",
    "changelog",
    "commit-msg",
    "compare",
    "config",
    "dashboard",
    "dates",
    "digest",
    "gui",
    "log",
    "providers",
    "remote",
    "serve",
    "shutdown",
    "standup",
    "summary",
    "track",
    "tracked",
    "untrack",
    "watch",
}
EXPECTED_GROUPS = {"service"}

CLI_DIR = Path(cli_main.__file__).parent


def _registered_commands() -> set[str]:
    names: set[str] = set()
    for cmd in cli_main.app.registered_commands:
        if cmd.name:
            names.add(cmd.name)
            continue
        callback = cmd.callback
        assert callback is not None, "command has no name and no callback"
        names.add(callback.__name__.replace("_", "-"))
    return names


def test_every_documented_command_is_registered() -> None:
    assert _registered_commands() >= EXPECTED_COMMANDS


def test_no_unexpected_commands_appear() -> None:
    assert _registered_commands() <= EXPECTED_COMMANDS


def test_expected_groups_are_registered() -> None:
    assert {g.name for g in cli_main.app.registered_groups} == EXPECTED_GROUPS


def _modules_declaring_commands() -> set[str]:
    found: set[str] = set()
    for path in sorted(CLI_DIR.glob("commands_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute):
                continue
            value = node.value
            is_app = isinstance(value, ast.Name) and value.id == "app"
            if is_app and node.attr in ("command", "add_typer"):
                found.add(path.stem)
    return found


def test_main_imports_every_command_module() -> None:
    declaring = _modules_declaring_commands()
    assert declaring, "no command modules found - the glob or layout changed"
    missing = declaring - set(cli_main.COMMAND_MODULES)
    assert not missing, f"cli/main.py does not import: {sorted(missing)}"


@pytest.mark.parametrize("module", sorted(_modules_declaring_commands()))
def test_declared_module_list_is_accurate(module: str) -> None:
    assert module in cli_main.COMMAND_MODULES


import os
import subprocess
from datetime import datetime, timezone

from typer.testing import CliRunner

from gitpulse.ai.summarizer import Summary
from gitpulse.cli.render import render_standup
from gitpulse.core.models import RepoActivity, RepoRef
from gitpulse.core.standup import RepoState, StandupContext

runner = CliRunner()
WINDOW = ["-w", "2026-06-01..2026-06-30"]


def _git(repo: Path, *args: str, author: str = "Alice", date: str = "") -> None:
    mail = f"{author.lower()}@example.com"
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": mail,
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": mail,
        }
    )
    if date:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _repo_with(parent: Path, name: str, commits: list[tuple[str, str, str]]) -> Path:
    repo = parent / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "branch", "-M", "master")
    for i, (message, author, date) in enumerate(commits):
        (repo / "README.md").write_text(f"{name}{i}", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", message, author=author, date=date)
    return repo


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    _repo_with(
        root,
        "alpha",
        [
            ("feat: one", "Alice", "2026-06-01T10:00:00"),
            ("feat: two", "Alice", "2026-06-02T10:00:00"),
        ],
    )
    _repo_with(root, "beta", [("fix: one", "Bob", "2026-06-03T10:00:00")])
    _repo_with(root, "gamma", [("chore: old", "Alice", "2020-01-01T10:00:00")])
    (root / "plain").mkdir()
    return root


def _row(output: str, name: str) -> str:
    for line in output.splitlines():
        if line.strip().startswith(name):
            return line.strip()
    raise AssertionError(f"no line for {name} in:\n{output}")


def test_summary_accepts_a_parent_folder_and_breaks_down_per_repo(
    workspace_root: Path,
) -> None:
    res = runner.invoke(
        cli_main.app, ["summary", str(workspace_root), *WINDOW, "-p", "local"]
    )
    assert res.exit_code == 0, res.output
    assert "3 scanned" in res.output
    assert "2 active" in res.output
    assert _row(res.output, "alpha").endswith("2")
    assert _row(res.output, "beta").endswith("1")
    assert _row(res.output, "gamma").endswith("0")


def test_summary_of_a_single_repo_keeps_its_plain_output(
    workspace_root: Path,
) -> None:
    res = runner.invoke(
        cli_main.app, ["summary", str(workspace_root / "alpha"), *WINDOW, "-p", "local"]
    )
    assert res.exit_code == 0, res.output
    assert "scanned" not in res.output
    assert "2 commits" in res.output


def test_log_tags_each_commit_with_its_repo(workspace_root: Path) -> None:
    res = runner.invoke(cli_main.app, ["log", str(workspace_root), *WINDOW])
    assert res.exit_code == 0, res.output
    assert "[alpha]" in res.output
    assert "[beta]" in res.output


def test_log_of_a_single_repo_has_no_repo_tag(workspace_root: Path) -> None:
    res = runner.invoke(cli_main.app, ["log", str(workspace_root / "alpha"), *WINDOW])
    assert res.exit_code == 0, res.output
    assert "[alpha]" not in res.output
    assert "scanned" not in res.output


def test_author_filter_narrows_the_workspace(workspace_root: Path) -> None:
    res = runner.invoke(
        cli_main.app,
        ["log", str(workspace_root), *WINDOW, "-a", "alice@example.com"],
    )
    assert res.exit_code == 0, res.output
    assert "[alpha]" in res.output
    assert "[beta]" not in res.output


def test_author_scope_all_keeps_repos_they_ever_touched(
    workspace_root: Path,
) -> None:
    args = [
        "summary",
        str(workspace_root),
        *WINDOW,
        "-p",
        "local",
        "-a",
        "alice@example.com",
    ]
    window = runner.invoke(cli_main.app, [*args, "--author-scope", "window"])
    every = runner.invoke(cli_main.app, [*args, "--author-scope", "all"])
    assert window.exit_code == 0 and every.exit_code == 0
    assert "gamma" not in window.output
    assert _row(every.output, "gamma").endswith("0")


def test_depth_limits_how_far_repos_are_looked_for(tmp_path: Path) -> None:
    root = tmp_path / "deep"
    _repo_with(
        root / "nested", "buried", [("feat: one", "Alice", "2026-06-01T10:00:00")]
    )
    shallow = runner.invoke(cli_main.app, ["log", str(root), *WINDOW, "--depth", "1"])
    deeper = runner.invoke(cli_main.app, ["log", str(root), *WINDOW, "--depth", "2"])
    assert shallow.exit_code == 1
    assert "No git repositories found" in shallow.output
    assert deeper.exit_code == 0, deeper.output
    assert "[buried]" in deeper.output


def test_unreadable_repos_are_reported_not_dropped(workspace_root: Path) -> None:
    (workspace_root / "wrecked" / ".git").mkdir(parents=True)
    res = runner.invoke(cli_main.app, ["log", str(workspace_root), *WINDOW])
    assert res.exit_code == 0, res.output
    assert "skipped wrecked" in res.output
    assert "[alpha]" in res.output


def test_standup_lists_the_state_of_every_repo(
    capsys: pytest.CaptureFixture[str],
) -> None:
    now = datetime(2026, 6, 10, tzinfo=timezone.utc)
    activity = RepoActivity(
        repo_name="work",
        repo_path="work",
        since=now,
        until=now,
        repos=[RepoRef(name="alpha", path="alpha"), RepoRef(name="beta", path="beta")],
    )
    ctx = StandupContext(
        repo_name="work",
        yesterday=activity,
        current_branch=None,
        repos=[
            RepoState(name="alpha", current_branch="master", uncommitted=["a.py"]),
            RepoState(name="beta", current_branch="feature"),
        ],
    )
    render_standup(ctx, Summary(headline="h", themes=[], observations=[]))
    out = capsys.readouterr().out
    assert "alpha: on master · 1 uncommitted file" in out
    assert "beta: on feature" in out
