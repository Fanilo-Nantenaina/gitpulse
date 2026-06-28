from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from ._shared import (app, console, _range,
                      WHEN_HELP, PROVIDER_HELP, MODEL_HELP, LANG_HELP)
from ..core.collector import collect_activity
from ..core import config as gp_config
from ..core import remote as gp_remote
from ..ai.summarizer import summarize
from .render import render_terminal, render_log, status_spinner


@app.command()
def remote(
    url: str = typer.Argument(..., help="Git URL (HTTPS or SSH), any platform"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    view: str = typer.Option("summary", "--view", help="summary or log"),
    files: bool = typer.Option(False, "--files", "-f", help="(log view) list files"),
    token: Optional[str] = typer.Option(None, "--token", help="Access token for private HTTPS repos"),
    username: Optional[str] = typer.Option(None, "--username", help="Username for token auth"),
    ssh_key: Optional[str] = typer.Option(None, "--ssh-key", help="Path to private SSH key"),
    no_refresh: bool = typer.Option(False, "--no-refresh", help="Use cached clone, skip fetch"),
    insecure: bool = typer.Option(False, "--insecure", help="Disable SSL cert verification (use at your own risk)"),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    r = _range(when)
    tok, user, key = gp_remote.resolve_auth(token, username, ssh_key)
    name = gp_remote.repo_name_from_url(url)
    action = "Fetching" if not no_refresh else "Loading cached"
    if insecure:
        console.print("[yellow]⚠ SSL verification disabled — use only on trusted networks.[/]")
    try:
        with status_spinner(f"{action} {name}"):
            dest = gp_remote.sync_remote(url, tok, user, key, refresh=not no_refresh, insecure=insecure)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)

    activity = collect_activity(dest, r.since, r.until, branch=branch, name=name)
    if view == "log":
        render_log(activity, show_files=files)
        return
    if activity.commit_count == 0:
        render_terminal(activity, summarize(activity, provider="local", lang=lang))
        return
    label = "local" if provider == "local" else provider
    with status_spinner(f"Summarizing {activity.commit_count} commits via {label}"):
        summ = summarize(activity, provider=provider, model=model, lang=lang)
    render_terminal(activity, summ)


@app.command(name="cache-clear")
def cache_clear():
    n = gp_remote.clear_cache()
    console.print(f"[green]Cleared {n} cached remote repo(s).[/]")


@app.command()
def track(
    url: str = typer.Argument(..., help="Git URL to track for the remote dashboard"),
    label: Optional[str] = typer.Option(None, "--label", help="Friendly name shown in the dashboard"),
):
    added, tracked = gp_config.add_tracked(url, label)
    name = label or gp_remote.repo_name_from_url(url)
    if added:
        console.print(f"[green]Tracking {name}[/] [dim]({url})[/]")
        console.print(f"[dim]{len(tracked)} repo(s) tracked. "
                      f"View with gitpulse dashboard --remote.[/]")
    else:
        console.print(f"[yellow]Already tracking {url}[/]")


@app.command()
def untrack(
    needle: str = typer.Argument(..., help="URL or label to stop tracking"),
):
    removed, tracked = gp_config.remove_tracked(needle)
    if removed:
        console.print(f"[green]Untracked {needle}[/] "
                      f"[dim]({len(tracked)} remaining)[/]")
    else:
        console.print(f"[yellow]Not found in tracked list: {needle}[/]")


@app.command()
def tracked():
    items = gp_config.list_tracked()
    if not items:
        console.print("[yellow]No tracked remotes. Add one with "
                      "[bold]gitpulse track <url>[/].[/]")
        return
    table = Table(title="Tracked remotes", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="dim")
    for i, t in enumerate(items, 1):
        name = t.get("label") or gp_remote.repo_name_from_url(t["url"])
        table.add_row(str(i), name, t["url"])
    console.print(table)
    console.print(f"[dim]{len(items)} tracked · "
                  f"run gitpulse dashboard --remote to see activity.[/]")
