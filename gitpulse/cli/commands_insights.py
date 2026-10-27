from __future__ import annotations

from enum import Enum

import typer

from ..ai import providers as ai_providers
from ..core import doctor as gp_doctor
from ..core import history as gp_history
from ..core import risks as gp_risks
from ..core import timesheet as gp_timesheet
from ..core import workspace
from ..core.collector import ALL_BRANCHES
from ._shared import (
    AUTHOR_HELP,
    DEPTH_HELP,
    PATH_HELP,
    WHEN_HELP,
    app,
    collect_scope,
    console,
    resolve_range,
    source_label,
)
from .render import (
    render_checks,
    render_failures,
    render_history,
    render_history_entry,
    render_risks,
    render_time_report,
    status_spinner,
)


class TimeFormat(str, Enum):
    TABLE = "table"
    CSV = "csv"
    MARKDOWN = "md"


@app.command()
def risks(
    source: str = typer.Argument(".", help=PATH_HELP),
    when: str = typer.Option("30d", "--when", "-w", help=WHEN_HELP),
    branch: str | None = typer.Option(None, "--branch", "-b"),
    author: list[str] = typer.Option([], "--author", "-a", help=AUTHOR_HELP),
    depth: int = typer.Option(workspace.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
    no_secrets: bool = typer.Option(
        False, "--no-secrets", help="Skip scanning diffs for committed secrets."
    ),
    fail_on: str | None = typer.Option(
        None,
        "--fail-on",
        help="Exit with code 2 when a flag of this severity or worse exists "
        "(high, medium, low). Handy in CI or a pre-push hook.",
    ),
) -> None:
    r = resolve_range(when)
    with status_spinner(f"Reading commits from {source_label(source)}"):
        activity, failures = collect_scope(
            source, r.since, r.until, branch=branch, authors=author, depth=depth
        )
    render_failures(failures)
    with status_spinner(f"Checking {activity.commit_count} commits"):
        found = gp_risks.detect(activity, scan_secrets=not no_secrets)
    console.print(
        f"[bold]{activity.repo_name}[/] [dim]{r.label} · "
        f"{activity.commit_count} commits[/]"
    )
    render_risks(found)
    if fail_on:
        limit = {"high": 0, "medium": 1, "low": 2}.get(fail_on.lower())
        if limit is None:
            console.print(
                f"[red]--fail-on must be high, medium or low, not {fail_on!r}[/]"
            )
            raise typer.Exit(1)
        if any(gp_risks.SEVERITY_ORDER[x["severity"]] <= limit for x in found):
            raise typer.Exit(2)


@app.command()
def timesheet(
    source: str = typer.Argument(".", help=PATH_HELP),
    when: str = typer.Option("this-week", "--when", "-w", help=WHEN_HELP),
    author: list[str] = typer.Option([], "--author", "-a", help=AUTHOR_HELP),
    depth: int = typer.Option(workspace.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
    gap: int = typer.Option(
        gp_timesheet.DEFAULT_GAP_MINUTES,
        "--gap",
        help="Minutes without a commit that end a work session.",
    ),
    warmup: int = typer.Option(
        gp_timesheet.DEFAULT_WARMUP_MINUTES,
        "--warmup",
        help="Minutes credited before the first commit of each session.",
    ),
    fmt: TimeFormat = typer.Option(TimeFormat.TABLE, "--format", "-f"),
) -> None:
    r = resolve_range(when)
    with status_spinner(f"Reading commits from {source_label(source)}"):
        activity, failures = collect_scope(
            source,
            r.since,
            r.until,
            branch=ALL_BRANCHES,
            authors=author,
            depth=depth,
        )
    report = gp_timesheet.report(activity, gap, warmup)
    if fmt is TimeFormat.CSV:
        typer.echo(report.to_csv(), nl=False)
        return
    if fmt is TimeFormat.MARKDOWN:
        typer.echo(report.to_markdown(), nl=False)
        return
    render_failures(failures)
    render_time_report(report)


@app.command()
def doctor() -> None:
    with status_spinner("Checking your setup"):
        checks = gp_doctor.run_all() + ai_providers.health()
    render_checks(checks)
    if any(c["status"] == "fail" for c in checks):
        raise typer.Exit(1)


history_app = typer.Typer(
    help="Digests GitPulse has already written: list, reopen, or clear them.",
    no_args_is_help=True,
)
app.add_typer(history_app, name="history")


@history_app.command("list")
def history_list(
    limit: int = typer.Option(20, "--limit", "-n", help="How many to show"),
) -> None:
    render_history(gp_history.entries(limit))


@history_app.command("show")
def history_show(
    ref: str = typer.Argument(
        ..., help="Row number from 'history list', or a key prefix"
    ),
) -> None:
    entry = gp_history.find(ref)
    if entry is None:
        console.print(f"[red]No single saved digest matches {ref!r}.[/]")
        raise typer.Exit(1)
    render_history_entry(entry)


@history_app.command("clear")
def history_clear() -> None:
    n = gp_history.clear()
    console.print(f"[green]Deleted {n} saved digest(s).[/]")
