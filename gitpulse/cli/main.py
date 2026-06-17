from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..core.collector import collect_activity, discover_repos
from ..core.changelog import generate_changelog
from ..core.dateparse import parse_range, parse_interval, suggestions, DateRange
from ..ai.summarizer import summarize
from ..scheduler.runner import run_scheduler
from ..notifiers.dispatch import dispatch
from .render import render_terminal, render_markdown, render_log

app = typer.Typer(
    help="GitPulse - AI-powered git activity digests.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()

WHEN_HELP = (
    "Time window. Accepts: intervals (7d, 24h, 30m), a date (2026-06-15), "
    "a range (2026-06-10..2026-06-14 or yesterday..today), relative terms "
    "(today, yesterday, avant-hier), weekdays (thursday, 'jeudi dernier'), "
    "or this-week / last-week."
)


def _range(when: str) -> DateRange:
    try:
        return parse_range(when)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        console.print("Run [bold]gitpulse dates[/] to see accepted formats.")
        raise typer.Exit(1)


@app.command()
def summary(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
):
    r = _range(when)
    activity = collect_activity(path, r.since, r.until, branch=branch)
    summ = summarize(activity)
    render_terminal(activity, summ)


@app.command()
def log(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    files: bool = typer.Option(
        False, "--files", "-f", help="List changed files per commit"
    ),
):
    r = _range(when)
    activity = collect_activity(path, r.since, r.until, branch=branch)
    render_log(activity, show_files=files)


@app.command()
def digest(
    path: Path = typer.Argument(Path(".")),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    to: list[str] = typer.Option(
        ["desktop"], "--to", help="Channels: slack,email,telegram,desktop"
    ),
):
    r = _range(when)
    activity = collect_activity(path, r.since, r.until)
    summ = summarize(activity)
    md = render_markdown(activity, summ)
    results = dispatch(to, md)
    for ch, ok in results.items():
        console.print(f"[{'green' if ok else 'red'}]{'ok' if ok else 'fail'}[/] {ch}")
    if not any(results.values()):
        console.print(md)


@app.command()
def dashboard(
    root: Path = typer.Argument(Path("."), help="Directory to scan for repos"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    depth: int = typer.Option(3, "--depth"),
):
    r = _range(when)
    repos = discover_repos(root, max_depth=depth)
    if not repos:
        console.print("[yellow]No git repositories found.[/]")
        raise typer.Exit()

    table = Table(title=f"Activity: {r.label}", show_lines=False)
    table.add_column("Repository", style="cyan")
    table.add_column("Commits", justify="right")
    table.add_column("+", justify="right", style="green")
    table.add_column("-", justify="right", style="red")
    table.add_column("Headline", style="dim", max_width=50)

    rows = []
    for repo in repos:
        act = collect_activity(repo, r.since, r.until)
        if act.commit_count == 0:
            continue
        summ = summarize(act)
        rows.append((act, summ))
    rows.sort(key=lambda x: x[0].commit_count, reverse=True)
    for act, summ in rows:
        table.add_row(
            act.repo_name,
            str(act.commit_count),
            f"+{act.total_additions}",
            f"-{act.total_deletions}",
            summ.headline,
        )
    console.print(table)


@app.command()
def changelog(
    path: Path = typer.Argument(Path(".")),
    from_ref: Optional[str] = typer.Option(None, "--from"),
    to_ref: str = typer.Option("HEAD", "--to"),
):
    console.print(generate_changelog(str(path), from_ref, to_ref))


@app.command()
def watch(
    path: Path = typer.Argument(Path(".")),
    every: str = typer.Option("24h", "--every", "-e", help="Cadence: 24h, 7d, 30m"),
    when: str = typer.Option("24h", "--when", "-w", help="Window each digest covers"),
    to: list[str] = typer.Option(["desktop"], "--to"),
):
    parse_interval(every)

    def job():
        r = parse_range(when)
        activity = collect_activity(path, r.since, r.until)
        summ = summarize(activity)
        md = render_markdown(activity, summ)
        dispatch(to, md)
        from datetime import datetime

        console.print(
            f"[dim]{datetime.now():%H:%M}[/] digest sent ({activity.commit_count} commits)"
        )

    console.print(f"[cyan]Watching {path} every {every}...[/]")
    run_scheduler(job, every)


@app.command()
def dates():
    table = Table(title="Accepted --when formats", show_lines=False)
    table.add_column("Type", style="cyan")
    table.add_column("Example", style="bold")
    table.add_column("Resolves to", style="dim")

    table.add_row("interval", "7d / 24h / 30m", "rolling window from now")
    table.add_row("single date", "2026-06-15", "that whole day")
    table.add_row("range", "2026-06-10..2026-06-14", "inclusive span")
    table.add_row("open range", "2026-06-12..", "from date to now")
    table.add_row("relative", "today / yesterday / avant-hier", "that whole day")
    table.add_row("weekday", "thursday / 'jeudi dernier'", "most recent that weekday")
    table.add_row("week", "this-week / last-week", "Mon-Sun span")
    console.print(table)

    sug = Table(title="This week", show_lines=False)
    sug.add_column("Term", style="cyan")
    sug.add_column("Date", style="bold")
    for label, hint in suggestions():
        sug.add_row(label, hint)
    console.print(sug)


def main():
    app()


if __name__ == "__main__":
    main()
