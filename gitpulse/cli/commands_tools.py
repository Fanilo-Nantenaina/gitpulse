from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from ._shared import app, console, PROVIDER_HELP, MODEL_HELP, LANG_HELP
from ..core.collector import collect_activity
from ..core.changelog import generate_changelog
from ..core.dateparse import parse_range, parse_interval, suggestions
from ..core import config as gp_config
from ..ai.summarizer import summarize
from ..ai import providers as ai_providers
from ..scheduler.runner import run_scheduler
from ..notifiers.dispatch import dispatch
from .render import render_markdown


@app.command()
def serve(
    port: int = typer.Option(8420, "--port", help="Port to serve on"),
    host: str = typer.Option("127.0.0.1", "--host"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open the browser"),
):
    from ..web.server import serve as run_server

    console.print(f"[cyan]GitPulse UI on http://{host}:{port}[/]  (Ctrl+C to stop)")
    run_server(host=host, port=port, open_browser=not no_open)


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
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    parse_interval(every)

    def job():
        r = parse_range(when)
        activity = collect_activity(path, r.since, r.until)
        summ = summarize(activity, provider=provider, model=model, lang=lang)
        md = render_markdown(activity, summ)
        dispatch(to, md)
        from datetime import datetime

        console.print(
            f"[dim]{datetime.now():%H:%M}[/] digest sent ({activity.commit_count} commits)"
        )

    console.print(f"[cyan]Watching {path} every {every}...[/]")
    run_scheduler(job, every)


@app.command()
def config(
    lang: Optional[str] = typer.Option(
        None, "--lang", "-l", help="Set the default output language (code or name)."
    ),
    show: bool = typer.Option(False, "--show", help="Show current settings."),
):
    cfg = gp_config.load_config()
    if lang is not None:
        code = gp_config.normalize_lang(lang)
        if code is None:
            console.print(f"[red]Unknown language: {lang!r}[/]")
            console.print(
                "Supported: "
                + ", ".join(f"{c} ({n})" for c, n in gp_config.LANGUAGES.items())
            )
            raise typer.Exit(1)
        cfg["lang"] = code
        path = gp_config.save_config(cfg)
        console.print(
            f"[green]Default language set to {gp_config.lang_name(code)} ({code}).[/]"
        )
        console.print(f"[dim]Saved to {path}[/]")
        return

    active = gp_config.resolve_lang()
    table = Table(title="Configuration", show_lines=False)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="bold")
    table.add_column("Source", style="dim")
    if gp_config.normalize_lang(os.environ.get("GITPULSE_LANG")):
        src = "env GITPULSE_LANG"
    elif gp_config.normalize_lang(cfg.get("lang")):
        src = "config file"
    else:
        src = "default"
    table.add_row("language", f"{gp_config.lang_name(active)} ({active})", src)
    console.print(table)
    console.print("[dim]Supported: " + ", ".join(gp_config.LANGUAGES) + "[/]")
    console.print(
        "[dim]Set default: gitpulse config --lang fr · "
        "override once: any command with --lang fr[/]"
    )


@app.command()
def providers():
    table = Table(title="AI providers", show_lines=False)
    table.add_column("Provider", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")
    table.add_column("Models", style="dim")
    for s in ai_providers.status():
        mark = "[green]yes[/]" if s["available"] else "[red]no[/]"
        models = s["models"]
        listed = ", ".join(models[:5]) if models else "-"
        if len(models) > 5:
            listed += f", +{len(models) - 5} more"
        table.add_row(s["name"], s["kind"], mark, s["detail"], listed)
    console.print(table)
    console.print(
        "[dim]Select with --provider <name> [--model <model>]. "
        "auto picks the first available local model, then cloud.[/]"
    )


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
