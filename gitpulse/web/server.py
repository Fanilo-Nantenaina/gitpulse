from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import analysis, commit, providers as providers_routes, repos

app = FastAPI(title="GitPulse")
_STATIC = Path(__file__).parent / "static"

# Domain routers — each owns a cohesive slice of the API surface.
app.include_router(providers_routes.router)
app.include_router(repos.router)
app.include_router(analysis.router)
app.include_router(commit.router)


@app.get("/")
def index():
    return FileResponse(_STATIC / "index.html")


if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def serve(host: str = "127.0.0.1", port: int = 8420, open_browser: bool = True):
    import uvicorn
    if open_browser:
        import threading
        import webbrowser
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
