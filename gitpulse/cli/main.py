from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..core.collector import collect_activity, discover_repos
from ..core.changelog import generate_changelog
from ..ai.summarizer import summarize
from ..scheduler.runner import parse_interval, run_scheduler
from ..notifiers.dispatch import dispatch
from .render import render_terminal, render_markdown

app = typer.Typer(
    help="GitPulse — AI-powered git activity digests.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


def _since(window: str) -> datetime:
    return datetime.now(timezone.utc) - parse_interval(window)


@app.command()
def summary(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    since: str = typer.Option("7d", "--since", "-s", help="Window e.g. 7d, 24h"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
):
    """Print a semantic summary of recent activity to the terminal."""
    activity = collect_activity(path, _since(since), branch=branch)
    summ = summarize(activity)
    render_terminal(activity, summ)


@app.command()
def digest(
    path: Path = typer.Argument(Path(".")),
    since: str = typer.Option("7d", "--since", "-s"),
    to: list[str] = typer.Option(
        ["desktop"], "--to", help="Channels: slack,email,telegram,desktop"
    ),
):
    """Generate a digest and dispatch it to notification channels."""
    activity = collect_activity(path, _since(since))
    summ = summarize(activity)
    md = render_markdown(activity, summ)
    results = dispatch(to, md)
    for ch, ok in results.items():
        console.print(f"[{'green' if ok else 'red'}]{'✓' if ok else '✗'}[/] {ch}")
    if not any(results.values()):
        console.print(md)


@app.command()
def dashboard(
    root: Path = typer.Argument(Path("."), help="Directory to scan for repos"),
    since: str = typer.Option("7d", "--since", "-s"),
    depth: int = typer.Option(3, "--depth"),
):
    """Aggregated activity across all repos under a directory."""
    repos = discover_repos(root, max_depth=depth)
    if not repos:
        console.print("[yellow]No git repositories found.[/]")
        raise typer.Exit()

    table = Table(title=f"Activity since {since}", show_lines=False)
    table.add_column("Repository", style="cyan")
    table.add_column("Commits", justify="right")
    table.add_column("+", justify="right", style="green")
    table.add_column("-", justify="right", style="red")
    table.add_column("Headline", style="dim", max_width=50)

    rows = []
    for repo in repos:
        act = collect_activity(repo, _since(since))
        if act.commit_count == 0:
            continue
        summ = summarize(act)
        rows.append((act, summ))
    rows.sort(key=lambda r: r[0].commit_count, reverse=True)
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
    """Generate Conventional-Commits release notes between two refs."""
    console.print(generate_changelog(str(path), from_ref, to_ref))


@app.command()
def watch(
    path: Path = typer.Argument(Path(".")),
    every: str = typer.Option("24h", "--every", "-e"),
    since: str = typer.Option("24h", "--since", "-s"),
    to: list[str] = typer.Option(["desktop"], "--to"),
):
    """Run digests on a recurring schedule (blocks)."""

    def job():
        activity = collect_activity(path, _since(since))
        summ = summarize(activity)
        md = render_markdown(activity, summ)
        dispatch(to, md)
        console.print(
            f"[dim]{datetime.now():%H:%M}[/] digest sent ({activity.commit_count} commits)"
        )

    console.print(f"[cyan]Watching {path} every {every}...[/]")
    run_scheduler(job, every)


def main():
    app()


if __name__ == "__main__":
    main()
