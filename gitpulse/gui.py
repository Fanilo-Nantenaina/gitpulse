"""GUI entry point for GitPulse.

This is the target of the `gitpulse-gui` script (a GUI-app entry point, so on
Windows it launches without a console window). It starts the local web server
and opens the default browser — the "app" is the web UI served locally.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    host = "127.0.0.1"
    port = 8420
    # minimal arg parse so a desktop shortcut can pass --port
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass
        elif a == "--host" and i + 1 < len(argv):
            host = argv[i + 1]

    from .web.server import serve
    serve(host=host, port=port, open_browser=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
