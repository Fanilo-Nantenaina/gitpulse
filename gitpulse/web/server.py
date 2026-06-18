from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..core.collector import collect_activity
from ..core.dateparse import parse_range, parse_interval
from ..core import config as gp_config
from ..core import remote as gp_remote
from ..core import trends as gp_trends
from ..core import standup as gp_standup
from ..core import gitgraph
from ..ai.summarizer import summarize
from ..ai import providers as ai_providers

app = FastAPI(title="GitPulse")
_STATIC = Path(__file__).parent / "static"


def _activity_dict(a) -> dict:
    return {
        "repo_name": a.repo_name,
        "since": a.since.isoformat(),
        "until": a.until.isoformat(),
        "commit_count": a.commit_count,
        "additions": a.total_additions,
        "deletions": a.total_deletions,
        "files_touched": a.files_touched,
        "active_days": a.active_days,
        "hour_histogram": a.hour_histogram,
        "authors": a.authors,
        "commits": [
            {
                "sha": c.short_sha,
                "summary": c.summary,
                "when": c.when.isoformat(),
                "author": c.author_name,
                "additions": c.additions,
                "deletions": c.deletions,
                "files": len(c.files),
            }
            for c in a.commits
        ],
    }


def _summary_dict(s) -> dict:
    return {
        "headline": s.headline,
        "synthesis": s.synthesis,
        "themes": s.themes,
        "observations": s.observations,
        "source": s.source,
        "cost_note": s.cost_note,
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens,
        "cost_usd": s.cost_usd,
    }


def _resolve_source(req) -> tuple[object, Optional[str]]:
    """Return (path-or-cache-dir, display_name). Handles local or remote URLs."""
    if req.url:
        tok, user, key = gp_remote.resolve_auth(None, None, None)
        dest = gp_remote.sync_remote(req.url, tok, user, key, refresh=req.refresh)
        return dest, gp_remote.repo_name_from_url(req.url)
    if not req.path:
        raise HTTPException(400, "Provide a path or url")
    return req.path, None


# ---- request models ----
class SummaryReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    when: str = "7d"
    branch: Optional[str] = None
    provider: str = "auto"
    model: Optional[str] = None
    lang: Optional[str] = None
    refresh: bool = True


class LogReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    when: str = "7d"
    branch: Optional[str] = None
    refresh: bool = True


class CompareReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    period: str = "7d"
    periods: int = 4
    branch: Optional[str] = None
    refresh: bool = True


class GraphReq(BaseModel):
    path: Optional[str] = None
    url: Optional[str] = None
    limit: int = 120
    branch: Optional[str] = None
    refresh: bool = True


class TrackReq(BaseModel):
    url: str
    label: Optional[str] = None


class DashboardReq(BaseModel):
    when: str = "7d"
    summarize: bool = False
    provider: str = "auto"
    model: Optional[str] = None
    lang: Optional[str] = None
    refresh: bool = True


# ---- endpoints ----
@app.get("/api/providers")
def api_providers():
    return [
        {"name": n, "available": ok, "models": m} for n, ok, m in ai_providers.status()
    ]


@app.get("/api/config")
def api_get_config():
    cfg = gp_config.load_config()
    return {
        "lang": gp_config.resolve_lang(),
        "languages": gp_config.LANGUAGES,
        "tracked": cfg.get("tracked", []),
    }


@app.post("/api/config/lang")
def api_set_lang(body: dict):
    code = gp_config.normalize_lang(body.get("lang"))
    if not code:
        raise HTTPException(400, "Unknown language")
    cfg = gp_config.load_config()
    cfg["lang"] = code
    gp_config.save_config(cfg)
    return {"lang": code}


@app.get("/api/browse")
def api_browse(path: Optional[str] = None):
    from . import browse

    return browse.list_dir(path)


@app.get("/api/drives")
def api_drives():
    from . import browse

    return {"drives": browse.drives()}


@app.post("/api/summary")
def api_summary(req: SummaryReq):
    try:
        r = parse_range(req.when)
        src, name = _resolve_source(req)
        activity = collect_activity(src, r.since, r.until, branch=req.branch, name=name)
        summ = summarize(
            activity, provider=req.provider, model=req.model, lang=req.lang
        )
        return {
            "activity": _activity_dict(activity),
            "summary": _summary_dict(summ),
            "range_label": r.label,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/log")
def api_log(req: LogReq):
    try:
        r = parse_range(req.when)
        src, name = _resolve_source(req)
        activity = collect_activity(src, r.since, r.until, branch=req.branch, name=name)
        return {"activity": _activity_dict(activity), "range_label": r.label}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/compare")
def api_compare(req: CompareReq):
    try:
        src, name = _resolve_source(req)
        p = parse_interval(req.period)
        cmp = gp_trends.compare(
            src, p, periods_back=req.periods, branch=req.branch, name=name
        )
        return {
            "repo_name": cmp.repo_name,
            "period_days": cmp.period_len.days,
            "periods_back": cmp.periods_back,
            "metrics": [
                {
                    "name": m.name,
                    "current": m.current,
                    "baseline": m.baseline,
                    "pct": m.pct,
                    "direction": m.direction,
                }
                for m in cmp.metrics
            ],
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/standup")
def api_standup(req: SummaryReq):
    try:
        src, name = _resolve_source(req)
        ctx = gp_standup.gather(src, name=name)
        prov = "local" if ctx.yesterday.commit_count == 0 else req.provider
        summ = summarize(ctx.yesterday, provider=prov, model=req.model, lang=req.lang)
        return {
            "repo_name": ctx.repo_name,
            "current_branch": ctx.current_branch,
            "uncommitted": ctx.uncommitted,
            "recent_branches": ctx.recent_branches,
            "yesterday": _activity_dict(ctx.yesterday),
            "summary": _summary_dict(summ),
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@app.post("/api/graph")
def api_graph(req: GraphReq):
    try:
        src, _ = _resolve_source(req)
        return gitgraph.graph(src, limit=req.limit, branch=req.branch)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/tracked")
def api_tracked():
    return gp_config.list_tracked()


@app.post("/api/tracked")
def api_track(body: TrackReq):
    added, tracked = gp_config.add_tracked(body.url, body.label)
    return {"added": added, "tracked": tracked}


@app.delete("/api/tracked")
def api_untrack(needle: str):
    removed, tracked = gp_config.remove_tracked(needle)
    return {"removed": removed, "tracked": tracked}


@app.post("/api/dashboard")
def api_dashboard(req: DashboardReq):
    tracked = gp_config.list_tracked()
    if not tracked:
        return {"rows": [], "error": "No tracked remotes"}
    r = parse_range(req.when)
    tok, user, key = gp_remote.resolve_auth(None, None, None)
    rows = []
    failed = []
    for t in tracked:
        url = t["url"]
        name = t.get("label") or gp_remote.repo_name_from_url(url)
        try:
            dest = gp_remote.sync_remote(url, tok, user, key, refresh=req.refresh)
            act = collect_activity(dest, r.since, r.until, name=name)
            row = {
                "name": name,
                "commits": act.commit_count,
                "additions": act.total_additions,
                "deletions": act.total_deletions,
                "files": act.files_touched,
                "headline": None,
            }
            if req.summarize and act.commit_count:
                summ = summarize(
                    act, provider=req.provider, model=req.model, lang=req.lang
                )
                row["headline"] = summ.headline
            rows.append(row)
        except Exception as e:
            failed.append({"name": name, "error": str(e)})
    rows.sort(key=lambda x: x["commits"], reverse=True)
    return {"rows": rows, "failed": failed, "range_label": r.label}


@app.get("/")
def index():
    return FileResponse(_STATIC / "index.html")


if _STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def serve(host: str = "127.0.0.1", port: int = 8420, open_browser: bool = True):
    import uvicorn

    if open_browser:
        import threading, webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
