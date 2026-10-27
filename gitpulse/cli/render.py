from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.status import Status
from rich.table import Table
from rich.text import Text

from ..ai.summarizer import PreparedRequest, Summary, summary_from_json
from ..core.doctor import Check
from ..core.history import HistoryEntry
from ..core.models import RepoActivity
from ..core.risks import Risk
from ..core.standup import StandupContext
from ..core.timesheet import TimeReport, format_hours
from ..core.trends import Comparison
from ..core.workspace import RepoFailure

console = Console()

_MAX_FAILURES_SHOWN = 5


def render_failures(failures: list[RepoFailure]) -> None:
    for f in failures[:_MAX_FAILURES_SHOWN]:
        console.print(
            Text(f"  ! skipped {f['name']}: {f['error']}", style="dim yellow")
        )
    extra = len(failures) - _MAX_FAILURES_SHOWN
    if extra > 0:
        console.print(Text(f"  ! {extra} more repo(s) skipped", style="dim yellow"))


def render_repos(activity: RepoActivity) -> None:
    if not activity.is_workspace:
        return
    counts = activity.commits_per_repo
    head = Text("  repos  ", style="dim")
    head.append(f"{len(counts)} scanned", style="dim")
    head.append(" · ", style="dim")
    head.append(f"{len(activity.active_repos)} active", style="dim")
    console.print(head)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Repository")
    table.add_column("Commits", justify="right")
    for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower())):
        style = "cyan" if n else "dim"
        table.add_row(Text(name, style=style), Text(str(n), style=style))
    console.print(Padding(table, (0, 0, 0, 2)))


def render_comparison(cmp: Comparison) -> None:
    days = cmp.period_len.days or round(cmp.period_len.total_seconds() / 86400, 1)
    header = Text()
    header.append(f"  {cmp.repo_name}  ", style="bold")
    header.append(
        f"current {days}-day period vs avg of prior {cmp.periods_back}", style="dim"
    )
    console.print()
    console.print(header)
    console.print()

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Metric", style="cyan")
    table.add_column("Now", justify="right")
    table.add_column("Avg", justify="right", style="dim")
    table.add_column("Change", justify="right")
    table.add_column("", justify="left")

    for m in cmp.metrics:
        arrow = {"up": "▲", "down": "▼", "flat": "="}[m.direction]
        good_up = m.name in ("Commits", "Files touched", "Active days", "Lines added")
        if m.direction == "flat":
            color = "dim"
        elif (m.direction == "up") == good_up:
            color = "green"
        else:
            color = "yellow"
        if m.pct is None:
            change = "new" if m.current else "-"
        else:
            change = f"{m.pct:+.0f}%"
        avg_str = f"{m.baseline:.1f}".rstrip("0").rstrip(".")
        table.add_row(
            m.name,
            str(int(m.current)),
            avg_str,
            f"[{color}]{change}[/]",
            f"[{color}]{arrow}[/]",
        )
    console.print(table)
    if cmp.current.is_workspace:
        console.print()
        render_repos(cmp.current)
    console.print()


def _render_workspace_today(ctx: StandupContext) -> None:
    for state in ctx.repos:
        bits: list[str] = []
        if state.current_branch:
            bits.append(f"on {state.current_branch}")
        if state.uncommitted:
            n = len(state.uncommitted)
            bits.append(f"{n} uncommitted file{'s' if n != 1 else ''}")
        others = [b for b in state.recent_branches if b != state.current_branch]
        if others:
            bits.append("also " + ", ".join(others[:3]))
        line = Text("• ", style="green")
        line.append(state.name + ": ")
        line.append(" · ".join(bits) if bits else "clean", style="dim")
        console.print(Padding(line, (0, 2, 0, 4)), width=_width())


def render_standup(ctx: StandupContext, summary: Summary) -> None:
    w = _width()
    console.print()
    console.print(
        Panel(
            Text(f"Standup — {ctx.repo_name}", style="bold cyan"),
            border_style="cyan",
            width=w,
            padding=(0, 1),
        )
    )

    console.print(Text("  Yesterday", style="bold"))
    if ctx.yesterday.commit_count == 0:
        console.print(Padding(Text("No commits.", style="dim"), (0, 0, 0, 4)))
    else:
        recap = summary.synthesis or summary.headline
        console.print(Padding(Text(recap), (0, 2, 0, 4)), width=w)
        for theme in summary.themes:
            line = Text("• ", style="blue")
            line.append(theme.get("title", ""), style="bold")
            console.print(Padding(line, (0, 0, 0, 4)))
            console.print(
                Padding(Text(theme.get("narrative", ""), style="dim"), (0, 2, 0, 6)),
                width=w,
            )
    if ctx.yesterday.is_workspace:
        console.print()
        render_repos(ctx.yesterday)
    console.print()

    console.print(Text("  Today", style="bold"))
    if ctx.repos:
        _render_workspace_today(ctx)
        console.print()
        console.print(Text(f"  {summary.cost_note}", style="dim"))
        console.print()
        return

    plan: list[tuple[str, str]] = []
    if ctx.current_branch:
        plan.append(("Continue on branch", ctx.current_branch))
    if ctx.uncommitted:
        files = ", ".join(ctx.uncommitted[:5])
        more = f" (+{len(ctx.uncommitted) - 5})" if len(ctx.uncommitted) > 5 else ""
        plan.append(("Uncommitted work in progress", files + more))
    others = [b for b in ctx.recent_branches if b != ctx.current_branch]
    if others:
        plan.append(("Other recently active branches", ", ".join(others[:4])))
    if not plan:
        console.print(
            Padding(Text("No work in progress detected.", style="dim"), (0, 0, 0, 4))
        )
    else:
        for label, detail in plan:
            line = Text("• ", style="green")
            line.append(label + ": ", style="default")
            line.append(detail, style="dim")
            console.print(Padding(line, (0, 2, 0, 4)), width=w)
    console.print()
    console.print(Text(f"  {summary.cost_note}", style="dim"))
    console.print()


@contextmanager
def progress_bar(description: str = "Working") -> Generator[Progress, None, None]:
    prog = Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[detail]}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
    with prog:
        yield prog


@contextmanager
def status_spinner(message: str) -> Generator[Status, None, None]:
    with console.status(f"[bold]{message}", spinner="dots") as st:
        yield st


_BLOCKS = " ▁▂▃▄▅▆▇█"


def _spark(values: list[int]) -> str:
    if not values or max(values) == 0:
        return _BLOCKS[0] * len(values)
    hi = max(values)
    return "".join(_BLOCKS[min(8, round(v / hi * 8))] for v in values)


_MAX_WIDTH = 100


def _width() -> int:
    return min(_MAX_WIDTH, console.size.width)


def _render_header(activity: RepoActivity, summary: Summary) -> None:
    w = _width()
    console.print()
    header = Panel(
        Text(summary.headline, style="bold cyan"),
        title=f"{activity.repo_name}",
        title_align="left",
        subtitle=f"{activity.since:%Y-%m-%d} → {activity.until:%Y-%m-%d}",
        subtitle_align="right",
        border_style="cyan",
        width=w,
        padding=(0, 1),
    )
    console.print(header)


def render_terminal(
    activity: RepoActivity, summary: Summary, risks: list[Risk] | None = None
) -> None:
    _render_header(activity, summary)

    stats = Text()
    stats.append(f"  {activity.commit_count} commits", style="bold")
    stats.append("   ")
    stats.append(f"+{activity.total_additions}", style="green")
    stats.append(" / ")
    stats.append(f"-{activity.total_deletions}", style="red")
    stats.append(" lines", style="dim")
    console.print(stats)

    hist = activity.hour_histogram
    spark = _spark([hist[h] for h in range(24)])
    heat = Text("  hours  ", style="dim")
    heat.append(spark, style="yellow")
    heat.append("  00h→23h", style="dim")
    console.print(heat)
    console.print()

    if activity.is_workspace:
        render_repos(activity)
        console.print()

    render_summary_body(summary, risks)


def render_summary_body(summary: Summary, risks: list[Risk] | None = None) -> None:
    w = _width()
    if summary.synthesis:
        console.print(Text("  Overview", style="bold"))
        console.print(Padding(Text(summary.synthesis), (0, 2, 0, 4)), width=w)
        console.print()

    for i, theme in enumerate(summary.themes, 1):
        title = Text()
        title.append(f"  {i}. ", style="bold blue")
        title.append(theme.get("title", "Untitled"), style="bold blue")
        console.print(title)

        body = Text(theme.get("narrative", ""), style="default")
        console.print(Padding(body, (0, 2, 0, 5)), width=w)

        shas = theme.get("commits", [])
        if shas:
            sha_line = Text("     ", style="dim")
            sha_line.append(" ".join(shas[:10]), style="dim")
            if len(shas) > 10:
                sha_line.append(f"  (+{len(shas) - 10} more)", style="dim")
            console.print(sha_line)
        console.print()

    if summary.observations:
        console.print(Text("  ⚠ Observations", style="bold yellow"))
        for o in summary.observations:
            bullet = Text("• ", style="yellow")
            bullet.append(o, style="default")
            console.print(Padding(bullet, (0, 2, 0, 3)), width=w)
        console.print()

    if risks:
        render_risks(risks, limit=5)
        console.print()

    console.print(Text(f"  {summary.cost_note}", style="dim"))
    if summary.source == "local(truncated)":
        console.print(
            Text(
                "  ⚠ Claude's reply was cut off; max_tokens was raised — retry. "
                "Showed local summary instead.",
                style="dim red",
            )
        )
    console.print()


def render_log(activity: RepoActivity, show_files: bool = False) -> None:
    w = _width()
    if activity.commit_count == 0:
        if activity.is_workspace:
            render_repos(activity)
        console.print(Text("  No commits in this window.", style="dim"))
        return

    header = Text()
    header.append(f"  {activity.repo_name}  ", style="bold")
    header.append(
        f"{activity.since:%Y-%m-%d} .. {activity.until:%Y-%m-%d}  ", style="dim"
    )
    header.append(f"{activity.commit_count} commits", style="dim")
    console.print(header)
    console.print()

    if activity.is_workspace:
        render_repos(activity)
        console.print()

    for c in activity.commits:
        line = Text("commit ", style="default")
        line.append(c.sha, style="yellow")
        if c.repo:
            line.append(f"  [{c.repo}]", style="magenta")
        if c.branch:
            line.append(f"  ({c.branch})", style="cyan")
        console.print(line)

        meta = Text("Author: ", style="default")
        meta.append(f"{c.author_name} <{c.author_email}>", style="default")
        console.print(meta)

        date_line = Text("Date:   ", style="default")
        date_line.append(f"{c.when:%a %b %d %H:%M:%S %Y %z}", style="default")
        console.print(date_line)
        console.print()

        subject = Text("    ")
        subject.append(c.summary, style="bold")
        console.print(subject, width=w)
        if c.body:
            console.print()
            for para in c.body.split("\n"):
                console.print(Padding(Text(para), (0, 0, 0, 4)), width=w)

        stat = Text("    ")
        stat.append(f"+{c.additions}", style="green")
        stat.append(" / ", style="dim")
        stat.append(f"-{c.deletions}", style="red")
        stat.append(
            f"  {len(c.files)} file{'s' if len(c.files) != 1 else ''}", style="dim"
        )
        console.print(stat)

        if show_files:
            for f in c.files:
                fl = Text("      ")
                fl.append(f"{f.status[:3]:>3} ", style="dim")
                fl.append(f.path, style="default")
                fl.append(f"  +{f.additions}/-{f.deletions}", style="dim")
                console.print(fl, width=w)
        console.print()


def render_markdown(
    activity: RepoActivity, summary: Summary, risks: list[Risk] | None = None
) -> str:
    lines = [
        f"# {activity.repo_name} — {activity.since:%Y-%m-%d} → {activity.until:%Y-%m-%d}",
        "",
        f"**{summary.headline}**",
        "",
        f"`{activity.commit_count} commits` · "
        f"`+{activity.total_additions}` / `-{activity.total_deletions}` lines",
        "",
    ]
    if summary.synthesis:
        lines.append(summary.synthesis)
        lines.append("")
    for theme in summary.themes:
        lines.append(f"## {theme['title']}")
        lines.append(theme.get("narrative", ""))
        if theme.get("commits"):
            lines.append("")
            lines.append("> " + " ".join(f"`{s}`" for s in theme["commits"]))
        lines.append("")
    if summary.observations:
        lines.append("## Observations")
        for o in summary.observations:
            lines.append(f"- ⚠ {o}")
        lines.append("")
    serious = [r for r in risks or [] if r["severity"] != "low"]
    if serious:
        lines.append("## Risk flags")
        for r in serious:
            lines.append(f"- **{r['severity']}** · {r['title']}: {r['detail']}")
        lines.append("")
    return "\n".join(lines)


_SEVERITY_STYLE = {"high": "bold red", "medium": "yellow", "low": "dim"}


def render_risks(risks: list[Risk], limit: int | None = None) -> None:
    w = _width()
    if not risks:
        console.print(Text("  ✓ No risk flags in this window.", style="green"))
        return
    console.print(Text(f"  Risk flags ({len(risks)})", style="bold"))
    for r in risks[:limit] if limit else risks:
        line = Text("  ")
        line.append(
            f"{r['severity'].upper():<6} ", style=_SEVERITY_STYLE[r["severity"]]
        )
        line.append(r["title"], style="bold")
        console.print(line)
        console.print(Padding(Text(r["detail"]), (0, 2, 0, 9)), width=w)
    if limit and len(risks) > limit:
        console.print(
            Text(f"  … {len(risks) - limit} more: gitpulse risks", style="dim")
        )


def render_dry_run(activity: RepoActivity, req: PreparedRequest) -> None:
    prov = req.provider
    console.print(Text("  System prompt", style="bold"))
    console.print(Padding(Text(req.system, style="dim"), (0, 2, 0, 4)))
    console.print(
        Text("  Payload (exactly what the model would receive)", style="bold")
    )
    console.print(Padding(Text(req.payload), (0, 2, 0, 4)))
    target = f"{prov.name}:{prov.model}" if prov else "local fallback (no model)"
    cost = f"~${req.est_cost_usd:.4f} max" if req.est_cost_usd else "free"
    console.print(
        Text(
            f"  {activity.commit_count} commits -> {target} · "
            f"~{req.est_input_tokens} input tok · up to {req.max_tokens} output tok · "
            f"{cost}",
            style="cyan",
        )
    )
    if req.redacted:
        kinds = ", ".join(f"{k}×{n}" for k, n in sorted(req.redacted.items()))
        console.print(Text(f"  Redacted before sending: {kinds}", style="yellow"))
    console.print(Text("  Dry run: nothing was sent.", style="dim"))


def render_time_report(report: TimeReport) -> None:
    console.print()
    head = Text(f"  {report.scope}  ", style="bold")
    head.append(f"{report.since:%Y-%m-%d} .. {report.until:%Y-%m-%d}", style="dim")
    console.print(head)
    if not report.rows:
        console.print(Text("  No commits in this window.", style="dim"))
        return
    total = Text("  ")
    total.append(format_hours(report.total_minutes), style="bold cyan")
    total.append(
        f" estimated over {report.days} day(s) and {len(report.sessions)} session(s)",
        style="dim",
    )
    console.print(total)
    console.print()

    per_repo = report.by("repo")
    if len(per_repo) > 1:
        t = Table(title="By repository", show_lines=False)
        t.add_column("Repository", style="cyan")
        t.add_column("Time", justify="right")
        t.add_column("Commits", justify="right", style="dim")
        for name, minutes, commits in per_repo:
            t.add_row(name, format_hours(minutes), str(commits))
        console.print(t)

    t = Table(title="By day", show_lines=False)
    t.add_column("Day", style="cyan")
    t.add_column("Author")
    if len(per_repo) > 1:
        t.add_column("Repository", style="dim")
    t.add_column("Time", justify="right")
    t.add_column("Commits", justify="right", style="dim")
    for r in report.rows:
        cells = [r["day"], r["author"]]
        if len(per_repo) > 1:
            cells.append(r["repo"] or "-")
        cells += [format_hours(r["minutes"]), str(r["commits"])]
        t.add_row(*cells)
    console.print(t)
    console.print(
        Text(
            f"  Estimate from commit times: a session ends after "
            f"{report.gap_minutes} min without a commit, and each session gets "
            f"+{report.warmup_minutes} min for the work before its first commit.",
            style="dim",
        )
    )


def render_history(entries: list[HistoryEntry]) -> None:
    if not entries:
        console.print("[yellow]No saved digests yet. Run gitpulse summary.[/]")
        return
    t = Table(title="Saved digests", show_lines=False)
    t.add_column("#", justify="right", style="dim")
    t.add_column("Created", style="dim")
    t.add_column("Scope", style="cyan")
    t.add_column("Window")
    t.add_column("Commits", justify="right")
    t.add_column("Headline", max_width=48)
    for i, e in enumerate(entries, 1):
        t.add_row(
            str(i),
            e["created"][:16].replace("T", " "),
            e["scope"],
            f"{e['since'][:10]} -> {e['until'][:10]}",
            str(e["commits"]),
            e["headline"],
        )
    console.print(t)
    console.print("[dim]Show one: gitpulse history show <#|key>[/]")


def render_history_entry(entry: HistoryEntry) -> None:
    summ = summary_from_json(entry["summary"])
    if summ is None:
        console.print("[red]This entry is unreadable.[/]")
        return
    summ.cached = True
    activity = RepoActivity(
        repo_name=entry["scope"],
        repo_path="",
        since=_parse_iso(entry["since"]),
        until=_parse_iso(entry["until"]),
    )
    console.print(
        Text(
            f"  Saved {entry['created'][:16].replace('T', ' ')} · {entry['commits']} commits",
            style="dim",
        )
    )
    _render_header(activity, summ)
    render_summary_body(summ)


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


_CHECK_STYLE = {"ok": ("✓", "green"), "warn": ("!", "yellow"), "fail": ("✗", "red")}


def render_checks(checks: list[Check]) -> None:
    t = Table(title="GitPulse doctor", show_lines=False)
    t.add_column("", justify="center")
    t.add_column("Check", style="bold")
    t.add_column("Detail", overflow="fold")
    t.add_column("Fix", style="dim", overflow="fold")
    for c in checks:
        mark, colour = _CHECK_STYLE[c["status"]]
        t.add_row(f"[{colour}]{mark}[/]", c["name"], c["detail"], c["hint"])
    console.print(t)
    fails = sum(1 for c in checks if c["status"] == "fail")
    warns = sum(1 for c in checks if c["status"] == "warn")
    colour = "red" if fails else "yellow" if warns else "green"
    console.print(
        f"[{colour}]{fails} failing · {warns} warning(s) · {len(checks)} checks[/]"
    )
