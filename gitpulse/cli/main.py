from __future__ import annotations

from . import (
    commands_analyze,  # noqa: F401
    commands_dashboard,  # noqa: F401
    commands_remote,  # noqa: F401
    commands_service,  # noqa: F401
    commands_tools,  # noqa: F401
)
from ._shared import app

COMMAND_MODULES = (
    "commands_analyze",
    "commands_dashboard",
    "commands_remote",
    "commands_service",
    "commands_tools",
)


def main():
    app()


if __name__ == "__main__":
    main()
