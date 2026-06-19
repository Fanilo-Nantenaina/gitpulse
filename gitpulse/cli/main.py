"""GitPulse CLI entry point.

Commands are defined in per-domain modules (commands_analyze, commands_remote,
commands_dashboard, commands_tools). Importing them registers their commands
onto the shared Typer `app`, keeping the command namespace flat while the
definitions stay in small, focused files.
"""
from __future__ import annotations

from ._shared import app

# Importing each module registers its @app.command() functions onto `app`.
from . import commands_analyze    # noqa: F401  summary, log, standup, commit-msg, compare, digest
from . import commands_remote     # noqa: F401  remote, track, untrack, tracked, cache-clear
from . import commands_dashboard  # noqa: F401  dashboard
from . import commands_tools      # noqa: F401  serve, changelog, watch, config, providers, dates
from . import commands_service    # noqa: F401  service start/stop/status/install, gui


def main():
    app()


if __name__ == "__main__":
    main()
