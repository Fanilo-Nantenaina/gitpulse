from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..core.collector import collect_activity, discover_repos
from ..core.changelog import generate_changelog
from ..core.dateparse import parse_range, parse_interval, suggestions, DateRange
from ..core import config as gp_config
from ..core import remote as gp_remote
from ..core import trends as gp_trends
from ..core import standup as gp_standup
from ..ai.summarizer import summarize
from ..ai import providers as ai_providers
from ..scheduler.runner import run_scheduler
from ..notifiers.dispatch import dispatch
from .render import (
    render_terminal,
    render_markdown,
    render_log,
    render_comparison,
    render_standup,
    progress_bar,
    status_spinner,
    console as render_console,
)

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


PROVIDER_HELP = "AI backend: auto, claude, ollama, or local (no model)."
MODEL_HELP = "Model name (provider-specific, e.g. claude-sonnet-4-6 or llama3.1)."
LANG_HELP = "Output language: code (fr, en, es...) or name. Overrides the default."


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
    files: bool = typer.Option(
        False, "--files", "-f", help="List changed files per commit"
    ),
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
        with status_spinner(
            f"Summarizing {ctx.yesterday.commit_count} commits via {label}"
        ):
            summ = summarize(ctx.yesterday, provider=provider, model=model, lang=lang)
    render_standup(ctx, summ)


@app.command()
def compare(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    period: str = typer.Option(
        "7d", "--period", "-w", help="Length of each period: 7d, 24h, 30d"
    ),
    periods: int = typer.Option(
        4, "--periods", "-n", help="How many prior periods to average"
    ),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
):
    p = parse_interval(period)
    with status_spinner(f"Comparing last {period} against prior {periods}"):
        cmp = gp_trends.compare(path, p, periods_back=periods, branch=branch)
    render_comparison(cmp)


@app.command()
def remote(
    url: str = typer.Argument(..., help="Git URL (HTTPS or SSH), any platform"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: Optional[str] = typer.Option(None, "--branch", "-b"),
    view: str = typer.Option("summary", "--view", help="summary or log"),
    files: bool = typer.Option(False, "--files", "-f", help="(log view) list files"),
    token: Optional[str] = typer.Option(
        None, "--token", help="Access token for private HTTPS repos"
    ),
    username: Optional[str] = typer.Option(
        None, "--username", help="Username for token auth"
    ),
    ssh_key: Optional[str] = typer.Option(
        None, "--ssh-key", help="Path to private SSH key"
    ),
    no_refresh: bool = typer.Option(
        False, "--no-refresh", help="Use cached clone, skip fetch"
    ),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    r = _range(when)
    tok, user, key = gp_remote.resolve_auth(token, username, ssh_key)
    name = gp_remote.repo_name_from_url(url)
    action = "Fetching" if not no_refresh else "Loading cached"
    try:
        with status_spinner(f"{action} {name}"):
            dest = gp_remote.sync_remote(url, tok, user, key, refresh=not no_refresh)
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


@app.command()
def serve(
    port: int = typer.Option(18420, "--port", help="Port to serve on"),
    host: str = typer.Option("127.0.0.1", "--host"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open the browser"),
):
    """Launch the GitPulse web interface."""
    from ..web.server import serve as run_server

    console.print(f"[cyan]GitPulse UI on http://{host}:{port}[/]  (Ctrl+C to stop)")
    run_server(host=host, port=port, open_browser=not no_open)


@app.command(name="cache-clear")
def cache_clear():
    n = gp_remote.clear_cache()
    console.print(f"[green]Cleared {n} cached remote repo(s).[/]")


@app.command()
def track(
    url: str = typer.Argument(..., help="Git URL to track for the remote dashboard"),
    label: Optional[str] = typer.Option(
        None, "--label", help="Friendly name shown in the dashboard"
    ),
):
    added, tracked = gp_config.add_tracked(url, label)
    name = label or gp_remote.repo_name_from_url(url)
    if added:
        console.print(f"[green]Tracking {name}[/] [dim]({url})[/]")
        console.print(
            f"[dim]{len(tracked)} repo(s) tracked. "
            f"View with gitpulse dashboard --remote.[/]"
        )
    else:
        console.print(f"[yellow]Already tracking {url}[/]")


@app.command()
def untrack(
    needle: str = typer.Argument(..., help="URL or label to stop tracking"),
):
    removed, tracked = gp_config.remove_tracked(needle)
    if removed:
        console.print(
            f"[green]Untracked {needle}[/] " f"[dim]({len(tracked)} remaining)[/]"
        )
    else:
        console.print(f"[yellow]Not found in tracked list: {needle}[/]")


@app.command()
def tracked():
    items = gp_config.list_tracked()
    if not items:
        console.print(
            "[yellow]No tracked remotes. Add one with "
            "[bold]gitpulse track <url>[/].[/]"
        )
        return
    table = Table(title="Tracked remotes", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("URL", style="dim")
    for i, t in enumerate(items, 1):
        name = t.get("label") or gp_remote.repo_name_from_url(t["url"])
        table.add_row(str(i), name, t["url"])
    console.print(table)
    console.print(
        f"[dim]{len(items)} tracked · "
        f"run gitpulse dashboard --remote to see activity.[/]"
    )


@app.command()
def digest(
    path: Path = typer.Argument(Path(".")),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    to: list[str] = typer.Option(
        ["desktop"], "--to", help="Channels: slack,email,telegram,desktop"
    ),
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


@app.command()
def dashboard(
    root: Path = typer.Argument(Path("."), help="Directory to scan (local mode)"),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    depth: int = typer.Option(3, "--depth"),
    remote: bool = typer.Option(
        False, "--remote", help="Use tracked remote repos instead of a local folder"
    ),
    summarize_rows: bool = typer.Option(
        False, "--summarize", help="Add an AI headline per repo (slower, may cost)"
    ),
    no_refresh: bool = typer.Option(
        False, "--no-refresh", help="(remote) use cached clones, skip fetch"
    ),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: Optional[str] = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help=LANG_HELP),
):
    r = _range(when)

    if remote:
        tracked = gp_config.list_tracked()
        if not tracked:
            console.print(
                "[yellow]No tracked remotes. Add one with "
                "[bold]gitpulse track <url>[/].[/]"
            )
            raise typer.Exit()
        targets: list[tuple[str, str, dict]] = []  # (name, kind, meta)
        tok, user, key = gp_remote.resolve_auth(None, None, None)
        with progress_bar() as prog:
            task = prog.add_task(
                "Fetching tracked remotes", total=len(tracked), detail=""
            )
            for t in tracked:
                url = t["url"]
                name = t.get("label") or gp_remote.repo_name_from_url(url)
                prog.update(task, detail=name)
                try:
                    dest = gp_remote.sync_remote(
                        url, tok, user, key, refresh=not no_refresh
                    )
                    targets.append((name, "ok", {"path": dest}))
                except Exception as e:
                    targets.append((name, "fail", {"error": str(e)}))
                prog.advance(task)
        sources = [(n, m["path"]) for n, kind, m in targets if kind == "ok"]
        prefetch_failed = sum(1 for _, kind, _ in targets if kind == "fail")
        title = f"Remote activity: {r.label}"
    else:
        with progress_bar() as prog:
            scan = prog.add_task(
                "Scanning for repositories", total=None, detail=str(root)
            )
            repos = discover_repos(root, max_depth=depth)
            prog.update(scan, total=1, completed=1, detail=f"found {len(repos)}")
        if not repos:
            console.print("[yellow]No git repositories found.[/]")
            raise typer.Exit()
        sources = [(repo.name, repo) for repo in repos]
        prefetch_failed = 0
        title = f"Activity: {r.label}"

    rows = []
    skipped = 0
    failed = prefetch_failed
    with progress_bar() as prog:
        task = prog.add_task("Analyzing repositories", total=len(sources), detail="")
        for name, src in sources:
            prog.update(task, detail=name)
            try:
                act = collect_activity(src, r.since, r.until, name=name)
                if act.commit_count == 0:
                    skipped += 1
                    prog.advance(task)
                    continue
                summ = None
                if summarize_rows:
                    summ = summarize(act, provider=provider, model=model, lang=lang)
                rows.append((act, summ))
            except Exception:
                failed += 1
            prog.advance(task)

    if not rows:
        console.print("[yellow]No activity in this window for any repository.[/]")
        raise typer.Exit()

    table = Table(title=title, show_lines=False)
    table.add_column("Repository", style="cyan")
    table.add_column("Commits", justify="right")
    table.add_column("+", justify="right", style="green")
    table.add_column("-", justify="right", style="red")
    table.add_column("Files", justify="right", style="dim")
    if summarize_rows:
        table.add_column("Headline", style="dim", max_width=46)

    rows.sort(key=lambda x: x[0].commit_count, reverse=True)
    for act, summ in rows:
        cells = [
            act.repo_name,
            str(act.commit_count),
            f"+{act.total_additions}",
            f"-{act.total_deletions}",
            str(act.files_touched),
        ]
        if summarize_rows:
            cells.append(summ.headline if summ else "")
        table.add_row(*cells)
    console.print(table)

    total_commits = sum(a.commit_count for a, _ in rows)
    footer = f"{len(rows)} active · {total_commits} commits total"
    if skipped:
        footer += f" · {skipped} idle"
    if failed:
        footer += f" · {failed} failed"
    footer += (
        f" · {len(sources) + prefetch_failed} tracked"
        if remote
        else f" · {len(sources)} scanned"
    )
    console.print(f"[dim]{footer}[/]")
    if not summarize_rows:
        console.print("[dim]Tip: add --summarize for an AI headline per repo.[/]")


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
    table.add_column("Available", justify="center")
    table.add_column("Models", style="dim")
    for name, ok, models in ai_providers.status():
        mark = "[green]yes[/]" if ok else "[red]no[/]"
        listed = ", ".join(models[:6]) if models else "-"
        if len(models) > 6:
            listed += f", +{len(models) - 6} more"
        table.add_row(name, mark, listed)
    console.print(table)
    console.print(
        "[dim]Select with --provider <name> [--model <model>]. "
        "auto picks the first available (claude, then ollama, then local).[/]"
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


def main():
    app()


if __name__ == "__main__":
    main()
