from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes import analysis, commit, providers as providers_routes, repos

app = FastAPI(title="GitPulse")
_STATIC = Path(__file__).parent / "static"

app.include_router(providers_routes.router)
app.include_router(repos.router)
app.include_router(analysis.router)
app.include_router(commit.router)


def _asset_version() -> str:
    try:
        from importlib.metadata import version

        ver = version("gitpulse")
    except Exception:
        ver = "dev"
    h = hashlib.sha1()
    for sub in ("css", "js"):
        d = _STATIC / sub
        if not d.exists():
            continue
        for f in sorted(d.glob("*")):
            try:
                h.update(f.read_bytes())
            except OSError:
                pass
    return f"{ver}.{h.hexdigest()[:8]}"


_VERSION = _asset_version()


@app.get("/")
def index():
    html = (_STATIC / "index.html").read_text(encoding="utf-8")
    html = re.sub(
        r'(/static/[^"\']+\.(?:js|css))', lambda m: f"{m.group(1)}?v={_VERSION}", html
    )
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def serve(host: str = "127.0.0.1", port: int = 8420, open_browser: bool = True):
    import uvicorn

    if open_browser:
        import threading
        import time
        import urllib.request
        import webbrowser

        def _open_when_ready():
            url = f"http://{host}:{port}"
            for _ in range(40):
                try:
                    urllib.request.urlopen(url, timeout=0.5)
                    break
                except Exception:
                    time.sleep(0.25)
            webbrowser.open(url)

        threading.Thread(target=_open_when_ready, daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
