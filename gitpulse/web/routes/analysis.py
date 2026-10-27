from __future__ import annotations

from typing import TypedDict

from fastapi import APIRouter, HTTPException

from ...ai.summarizer import summarize
from ...core import commitinfo as gp_commitinfo
from ...core import config as gp_config
from ...core import gitgraph
from ...core import remote as gp_remote
from ...core import risks as gp_risks
from ...core import standup as gp_standup
from ...core import timesheet as gp_timesheet
from ...core import trends as gp_trends
from ...core import workspace as gp_workspace
from ...core.collector import collect_activity
from ...core.dateparse import parse_interval, parse_range
from ...core.gitcreds import redact
from ..schemas import (
    CommitDiffReq,
    CommitReq,
    CompareReq,
    DashboardReq,
    GraphReq,
    LogReq,
    SummaryReq,
    TimesheetReq,
)
from ..serializers import activity_dict, resolve_source, summary_dict

router = APIRouter(prefix="/api")


class DashboardRow(TypedDict):
    name: str
    commits: int
    additions: int
    deletions: int
    files: int
    headline: str | None


class DashboardFailure(TypedDict):
    name: str
    url: str
    reason: str
    error: str


@router.get("/range")
def api_range(when: str = "7d"):
    try:
        r = parse_range(when)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "since": r.since.isoformat(),
        "until": r.until.isoformat(),
        "label": r.label,
    }


@router.post("/summary")
def api_summary(req: SummaryReq):
    from ...core.stats import compute_stats

    try:
        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity, failed = gp_workspace.collect(
            src,
            r.since,
            r.until,
            branch=req.branch_spec(),
            name=name,
            authors=req.authors,
            author_scope=req.author_scope,
            max_depth=req.depth,
        )
        found = gp_risks.detect(activity) if req.risks else []
        summ = summarize(
            activity,
            provider=req.provider,
            model=req.model,
            lang=req.lang,
            risks=found,
            use_cache=req.use_cache,
        )
        return {
            "activity": activity_dict(activity),
            "summary": summary_dict(summ),
            "stats": compute_stats(activity),
            "risks": found,
            "range_label": r.label,
            "failed_repos": failed,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/log")
def api_log(req: LogReq):
    try:
        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity, failed = gp_workspace.collect(
            src,
            r.since,
            r.until,
            branch=req.branch_spec(),
            name=name,
            authors=req.authors,
            author_scope=req.author_scope,
            max_depth=req.depth,
        )
        return {
            "activity": activity_dict(activity),
            "range_label": r.label,
            "failed_repos": failed,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/risks")
def api_risks(req: LogReq):
    try:
        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity, failed = gp_workspace.collect(
            src,
            r.since,
            r.until,
            branch=req.branch_spec(),
            name=name,
            authors=req.authors,
            max_depth=req.depth,
        )
        return {
            "risks": gp_risks.detect(activity),
            "commit_count": activity.commit_count,
            "range_label": r.label,
            "failed_repos": failed,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/timesheet")
def api_timesheet(req: TimesheetReq):
    try:
        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity, failed = gp_workspace.collect(
            src,
            r.since,
            r.until,
            branch=req.branch_spec(),
            name=name,
            authors=req.authors,
            max_depth=req.depth,
        )
        report = gp_timesheet.report(activity, req.gap, req.warmup)
        return {
            "scope": report.scope,
            "range_label": r.label,
            "total_minutes": report.total_minutes,
            "days": report.days,
            "sessions": len(report.sessions),
            "gap": report.gap_minutes,
            "warmup": report.warmup_minutes,
            "rows": report.rows,
            "by_repo": [
                {"name": n, "minutes": m, "commits": c} for n, m, c in report.by("repo")
            ],
            "by_author": [
                {"name": n, "minutes": m, "commits": c}
                for n, m, c in report.by("author")
            ],
            "csv": report.to_csv(),
            "failed_repos": failed,
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/authors")
def api_authors(req: SummaryReq):
    try:
        from ...core.collector import list_authors

        r = parse_range(req.when)
        src, _ = resolve_source(req)
        if gp_workspace.is_repo(src):
            return {"authors": list_authors(src, r.since, r.until), "workspace": False}
        authors = gp_workspace.list_workspace_authors(
            src, r.since, r.until, max_depth=req.depth
        )
        return {"authors": authors, "workspace": True}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/stats")
def api_stats(req: SummaryReq):
    try:
        from ...core.stats import compute_stats

        r = parse_range(req.when)
        src, name = resolve_source(req)
        activity, _ = gp_workspace.collect(
            src,
            r.since,
            r.until,
            branch=req.branch_spec(),
            name=name,
            authors=req.authors,
            author_scope=req.author_scope,
            max_depth=req.depth,
        )
        return {"stats": compute_stats(activity), "range_label": r.label}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/compare")
def api_compare(req: CompareReq):
    try:
        src, name = resolve_source(req)
        p = parse_interval(req.period)
        cmp = gp_trends.compare(
            src,
            p,
            periods_back=req.periods,
            branch=req.branch_spec(),
            name=name,
            authors=req.authors,
            author_scope=req.author_scope,
        )
        return {
            "repo_name": cmp.repo_name,
            "is_workspace": cmp.current.is_workspace,
            "repos": [r.name for r in cmp.current.repos],
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
        ctx = gp_standup.gather(src, name=name, max_depth=req.depth)
        prov = "local" if ctx.yesterday.commit_count == 0 else req.provider
        summ = summarize(ctx.yesterday, provider=prov, model=req.model, lang=req.lang)
        return {
            "repo_name": ctx.repo_name,
            "current_branch": ctx.current_branch,
            "uncommitted": ctx.uncommitted,
            "has_uncommitted": bool(ctx.uncommitted)
            or any(s.uncommitted for s in ctx.repos),
            "is_local": bool(req.path),
            "recent_branches": ctx.recent_branches,
            "is_workspace": ctx.yesterday.is_workspace,
            "repos": [
                {
                    "name": s.name,
                    "current_branch": s.current_branch,
                    "uncommitted": s.uncommitted,
                    "recent_branches": s.recent_branches,
                }
                for s in ctx.repos
            ],
            "yesterday": activity_dict(ctx.yesterday),
            "summary": summary_dict(summ),
        }
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/graph")
def api_graph(req: GraphReq) -> gitgraph.Graph:
    try:
        src, _ = resolve_source(req)
        branches = (
            req.branches
            if req.branches is not None
            else ([req.branch] if req.branch else None)
        )
        return gitgraph.graph(
            src,
            limit=req.limit,
            offset=req.offset,
            branches=branches,
            uncommitted=req.uncommitted,
            version=req.version,
        )
    except gitgraph.GraphChanged as e:
        raise HTTPException(409, str(e))
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/commit/files")
def api_commit_files(req: CommitReq) -> gp_commitinfo.CommitFiles:
    try:
        src, _ = resolve_source(req)
        return gp_commitinfo.files(src, req.sha)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/commit/diff")
def api_commit_diff(req: CommitDiffReq) -> gp_commitinfo.FileDiff:
    try:
        src, _ = resolve_source(req)
        return gp_commitinfo.diff(src, req.sha, req.file)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


@router.post("/dashboard")
def api_dashboard(req: DashboardReq):
    rows: list[DashboardRow] = []
    failed: list[DashboardFailure] = []
    tracked = gp_config.list_tracked()
    if not tracked:
        return {"rows": rows, "error": "No tracked remotes"}
    r = parse_range(req.when)
    tok, user, key = gp_remote.resolve_auth(None, None, None)
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
                insecure=req.insecure,
            )
            act = collect_activity(dest, r.since, r.until, name=name)
            row: DashboardRow = {
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
            safe = redact(str(e), tok)
            failed.append(
                {
                    "name": name,
                    "url": gp_remote.strip_userinfo(url),
                    "reason": _classify_remote_error(safe),
                    "error": safe,
                }
            )
    rows.sort(key=lambda x: x["commits"], reverse=True)
    return {"rows": rows, "failed": failed, "range_label": r.label}


def _classify_remote_error(msg: str) -> str:
    m = msg.lower()
    if any(
        k in m
        for k in (
            "authentication",
            "auth",
            "403",
            "denied",
            "permission",
            "credential",
            "401",
        )
    ):
        return "auth"
    if any(
        k in m
        for k in (
            "not found",
            "404",
            "repository not found",
            "does not exist",
            "could not read",
        )
    ):
        return "not_found"
    if any(
        k in m
        for k in (
            "could not resolve",
            "timed out",
            "timeout",
            "network",
            "connection",
            "unable to access",
            "ssl",
            "certificate",
        )
    ):
        return "network"
    return "other"
