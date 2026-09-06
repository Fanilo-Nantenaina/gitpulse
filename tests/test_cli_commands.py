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
