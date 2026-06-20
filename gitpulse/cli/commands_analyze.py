from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ._shared import (app, console, _range,
                      WHEN_HELP, PROVIDER_HELP, MODEL_HELP, LANG_HELP)
from ..core.collector import collect_activity
from ..core.dateparse import parse_interval
from ..core import trends as gp_trends
from ..core import standup as gp_standup
from ..ai.summarizer import summarize
from ..notifiers.dispatch import dispatch
from .render import (render_terminal, render_markdown, render_log,
                     render_comparison, render_standup, status_spinner)


@app.command()
def summary(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    r = _range(when)
    with status_spinner(f"Reading commits from {path.name}"):
        activity = collect_activity(path, r.since, r.until, branch=branch)
    if activity.commit_count == 0:
        render_terminal(activity, summarize(activity, provider="local", lang=lang))
        return
    label = "local" if provider == "local" else provider
    with status_spinner(f"Summarizing {activity.commit_count} commits via {label}"):
        summ = summarize(activity, provider=provider, model=model, lang=lang)
    render_terminal(activity, summ)


@app.command()
def log(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    files: bool = typer.Option(False, "--files", "-f", help="List changed files per commit"),
):
    r = _range(when)
    activity = collect_activity(path, r.since, r.until, branch=branch)
    render_log(activity, show_files=files)


@app.command()
def standup(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    with status_spinner("Gathering yesterday's work"):
        ctx = gp_standup.gather(path)
    if ctx.yesterday.commit_count == 0:
        summ = summarize(ctx.yesterday, provider="local", lang=lang)
    else:
        label = "local" if provider == "local" else provider
        with status_spinner(f"Summarizing {ctx.yesterday.commit_count} commits via {label}"):
            summ = summarize(ctx.yesterday, provider=provider, model=model, lang=lang)
    render_standup(ctx, summ)


@app.command(name="commit-msg")
def commit_msg(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    staged: bool = typer.Option(False, "--staged", help="Only staged changes (default: all)"),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    """Generate a commit message from uncommitted changes."""
    from ..core.diffstage import collect_working_changes
    from ..ai.commitmsg import generate_commit_message
    scope = "staged" if staged else "all"
    changes = collect_working_changes(path, scope=scope)
    if not changes.has_changes:
        console.print("[yellow]No uncommitted changes to describe.[/]")
        raise typer.Exit()
    label = "local" if provider == "local" else provider
    with status_spinner(f"Describing {len(changes.files)} changed file(s) via {label}"):
        msg = generate_commit_message(changes, provider=provider, model=model, lang=lang)
    console.print(f"\n[bold cyan]{msg.subject}[/]\n")
    for b in msg.bullets:
        console.print(f"  [dim]•[/] {b}")
    console.print(f"\n[dim]{msg.source} · {len(changes.files)} files "
                  f"(+{changes.total_additions}/-{changes.total_deletions})"
                  f"{' · cost ~$%.4f' % msg.cost_usd if msg.cost_usd else ''}[/]")


@app.command()
def compare(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    period: str = typer.Option("7d", "--period", "-w", help="Length of each period: 7d, 24h, 30d"),
    periods: int = typer.Option(4, "--periods", "-n", help="How many prior periods to average"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
):
    p = parse_interval(period)
    with status_spinner(f"Comparing last {period} against prior {periods}"):
        cmp = gp_trends.compare(path, p, periods_back=periods, branch=branch)
    render_comparison(cmp)


@app.command()
def digest(
    path: Path = typer.Argument(Path(".")),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    to: list[str] = typer.Option(["desktop"], "--to", help="Channels: slack,email,telegram,desktop"),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    r = _range(when)
    with status_spinner(f"Reading commits from {path.name}"):
        activity = collect_activity(path, r.since, r.until)
    label = "local" if provider == "local" else provider
    with status_spinner(f"Summarizing {activity.commit_count} commits via {label}"):
        summ = summarize(activity, provider=provider, model=model, lang=lang)
    md = render_markdown(activity, summ)
    with status_spinner(f"Sending to {', '.join(to)}"):
        results = dispatch(to, md)
    for ch, ok in results.items():
        console.print(f"[{'green' if ok else 'red'}]{'ok' if ok else 'fail'}[/] {ch}")
    if not any(results.values()):
        console.print(md)
