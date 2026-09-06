from __future__ import annotations

from . import (
    commands_analyze,
    commands_dashboard,
    commands_remote,
    commands_service,
    commands_tools,
)
from ._shared import app

COMMAND_MODULES: tuple[str, ...] = tuple(
    module.__name__.rsplit(".", 1)[-1]
    for module in (
        commands_analyze,
        commands_dashboard,
        commands_remote,
        commands_service,
        commands_tools,
    )
)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
