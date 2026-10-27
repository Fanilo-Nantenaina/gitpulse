from __future__ import annotations

import io
import sys

from . import (
    commands_analyze,
    commands_dashboard,
    commands_insights,
    commands_remote,
    commands_service,
    commands_tools,
    commands_workspace,
)
from ._shared import app

COMMAND_MODULES: tuple[str, ...] = tuple(
    module.__name__.rsplit(".", 1)[-1]
    for module in (
        commands_analyze,
        commands_dashboard,
        commands_insights,
        commands_remote,
        commands_service,
        commands_tools,
        commands_workspace,
    )
)


def _tolerate_legacy_consoles() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main() -> None:
    _tolerate_legacy_consoles()
    app()


if __name__ == "__main__":
    main()
