from __future__ import annotations

from . import (
    commands_dashboard,  # noqa: F401  dashboard
    commands_service,  # noqa: F401  service start/stop/status/install, gui
    )
from ._shared import app


def main():
    app()


if __name__ == "__main__":
    main()
