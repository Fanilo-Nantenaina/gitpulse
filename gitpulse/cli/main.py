from __future__ import annotations

from ._shared import app

# Importing each module registers its @app.command() functions onto `app`.
from . import (
    commands_analyze,
)  # noqa: F401  summary, log, standup, commit-msg, compare, digest
from . import (
    commands_remote,
)  # noqa: F401  remote, track, untrack, tracked, cache-clear
from . import commands_dashboard  # noqa: F401  dashboard
from . import (
    commands_tools,
)  # noqa: F401  serve, changelog, watch, config, providers, dates


def main():
    app()


if __name__ == "__main__":
    main()
