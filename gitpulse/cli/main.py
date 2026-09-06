from __future__ import annotations

from . import (
    commands_analyze,
    commands_dashboard,
    commands_remote,
    commands_service,
    commands_tools,
)
from ._shared import app

# Importing these modules is the only thing that registers their Typer
# commands on `app`. Naming them here keeps the imports referenced, so neither
# a formatting pass nor a linter can drop them without failing this list too.
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
