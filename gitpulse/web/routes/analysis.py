from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...core.collector import collect_activity
from ...core.dateparse import parse_range, parse_interval
from ...core import remote as gp_remote
from ...core import trends as gp_trends
from ...core import standup as gp_standup
from ...core import config as gp_config
from ...core import gitgraph
from ...ai.summarizer import summarize
from ..schemas import SummaryReq, LogReq, CompareReq, GraphReq, DashboardReq
from ..serializers import activity_dict, summary_dict, resolve_source

router = APIRouter(prefix="/api")


@router.post("/summary")
def api_summary(req: SummaryReq):
    try:
        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity = collect_activity(
            src, r.since, r.until, branch=req.branch, name=name, authors=req.authors
        )
        summ = summarize(
            activity, provider=req.provider, model=req.model, lang=req.lang
        )
        return {
            "activity": activity_dict(activity),
            "summary": summary_dict(summ),
            "range_label": r.label,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/log")
def api_log(req: LogReq):
    try:
        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity = collect_activity(
            src, r.since, r.until, branch=req.branch, name=name, authors=req.authors
        )
        return {"activity": activity_dict(activity), "range_label": r.label}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/authors")
def api_authors(req: SummaryReq):
    try:
        from ...core.collector import list_authors

        r = parse_range(req.when)
        src, name = resolve_source(req)
        return {"authors": list_authors(src, r.since, r.until)}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/compare")
def api_compare(req: CompareReq):
    try:
        src, name = resolve_source(req)
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


@router.post("/standup")
def api_standup(req: SummaryReq):
    try:
        src, name = resolve_source(req)
        ctx = gp_standup.gather(src, name=name)
        prov = "local" if ctx.yesterday.commit_count == 0 else req.provider
        summ = summarize(ctx.yesterday, provider=prov, model=req.model, lang=req.lang)
        return {
            "repo_name": ctx.repo_name,
            "current_branch": ctx.current_branch,
            "uncommitted": ctx.uncommitted,
            "has_uncommitted": bool(ctx.uncommitted),
            "is_local": bool(req.path),
            "recent_branches": ctx.recent_branches,
            "yesterday": activity_dict(ctx.yesterday),
            "summary": summary_dict(summ),
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/graph")
def api_graph(req: GraphReq):
    try:
        src, _ = resolve_source(req)
        return gitgraph.graph(src)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/dashboard")
def api_dashboard(req: DashboardReq):
    tracked = gp_config.list_tracked()
    if not tracked:
        return {"rows": [], "error": "No tracked remotes"}
    r = parse_range(req.when)
    tok, user, key = gp_remote.resolve_auth(None, None, None)
    rows, failed = [], []
    for t in tracked:
        url = t["url"]
        name = t.get("label") or gp_remote.repo_name_from_url(url)
        try:
            dest = gp_remote.sync_remote(
                url,
                tok,
                user,
                key,
                refresh=req.refresh,
                insecure=getattr(req, "insecure", False),
            )
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
