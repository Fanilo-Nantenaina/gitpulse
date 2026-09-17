from __future__ import annotations

from pathlib import Path

import typer

from ..ai.summarizer import summarize
from ..core import standup as gp_standup
from ..core import trends as gp_trends
from ..core import workspace
from ..core.collector import collect_activity
from ..core.dateparse import parse_interval
from ..notifiers.dispatch import dispatch
from ._shared import (
    AUTHOR_HELP,
    AUTHOR_SCOPE_HELP,
    DEPTH_HELP,
    LANG_HELP,
    MODEL_HELP,
    PATH_HELP,
    PROVIDER_HELP,
    WHEN_HELP,
    AuthorScopeOption,
    app,
    collect_scope,
    console,
    resolve_range,
)
from .render import (
    render_comparison,
    render_failures,
    render_log,
    render_markdown,
    render_standup,
    render_terminal,
    status_spinner,
)


@app.command()
def summary(
    path: Path = typer.Argument(Path("."), help=PATH_HELP),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: str | None = typer.Option(None, "--branch", "-b"),
    author: list[str] = typer.Option([], "--author", "-a", help=AUTHOR_HELP),
    author_scope: AuthorScopeOption = typer.Option(
        AuthorScopeOption.WINDOW, "--author-scope", help=AUTHOR_SCOPE_HELP
    ),
    depth: int = typer.Option(workspace.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: str | None = typer.Option(None, "--lang", "-l", help=LANG_HELP),
) -> None:
    r = resolve_range(when)
    with status_spinner(f"Reading commits from {path.name}"):
        activity, failures = collect_scope(
            path,
            r.since,
            r.until,
            branch=branch,
            authors=author,
            author_scope=author_scope,
            depth=depth,
        )
    render_failures(failures)
    if activity.commit_count == 0:
        render_terminal(activity, summarize(activity, provider="local", lang=lang))
        return
    label = "local" if provider == "local" else provider
    with status_spinner(f"Summarizing {activity.commit_count} commits via {label}"):
        summ = summarize(activity, provider=provider, model=model, lang=lang)
    render_terminal(activity, summ)


@app.command()
def log(
    path: Path = typer.Argument(Path("."), help=PATH_HELP),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    branch: str | None = typer.Option(None, "--branch", "-b"),
    files: bool = typer.Option(
        False, "--files", "-f", help="List changed files per commit"
    ),
    author: list[str] = typer.Option([], "--author", "-a", help=AUTHOR_HELP),
    author_scope: AuthorScopeOption = typer.Option(
        AuthorScopeOption.WINDOW, "--author-scope", help=AUTHOR_SCOPE_HELP
    ),
    depth: int = typer.Option(workspace.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
) -> None:
    r = resolve_range(when)
    activity, failures = collect_scope(
        path,
        r.since,
        r.until,
        branch=branch,
        authors=author,
        author_scope=author_scope,
        depth=depth,
    )
    render_failures(failures)
    render_log(activity, show_files=files)


@app.command()
def standup(
    path: Path = typer.Argument(Path("."), help=PATH_HELP),
    depth: int = typer.Option(workspace.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: str | None = typer.Option(None, "--lang", "-l", help=LANG_HELP),
) -> None:
    with status_spinner("Gathering yesterday's work"):
        try:
            ctx = gp_standup.gather(path, max_depth=depth)
        except ValueError as e:
            console.print(f"[red]{e}[/]")
            raise typer.Exit(1)
    if ctx.yesterday.commit_count == 0:
        summ = summarize(ctx.yesterday, provider="local", lang=lang)
    else:
        label = "local" if provider == "local" else provider
        with status_spinner(
            f"Summarizing {ctx.yesterday.commit_count} commits via {label}"
        ):
            summ = summarize(ctx.yesterday, provider=provider, model=model, lang=lang)
    render_standup(ctx, summ)


@app.command(name="commit-msg")
def commit_msg(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    staged: bool = typer.Option(
        False, "--staged", help="Only staged changes (default: all)"
    ),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: str | None = typer.Option(None, "--lang", "-l", help=LANG_HELP),
) -> None:
    from ..ai.commitmsg import generate_commit_message
    from ..core.diffstage import collect_working_changes

    scope = "staged" if staged else "all"
    changes = collect_working_changes(path, scope=scope)
    if not changes.has_changes:
        console.print("[yellow]No uncommitted changes to describe.[/]")
        raise typer.Exit()
    label = "local" if provider == "local" else provider
    with status_spinner(f"Describing {len(changes.files)} changed file(s) via {label}"):
        msg = generate_commit_message(
            changes, provider=provider, model=model, lang=lang
        )
    console.print(f"\n[bold cyan]{msg.subject}[/]\n")
    for b in msg.bullets:
        console.print(f"  [dim]•[/] {b}")
    console.print(
        f"\n[dim]{msg.source} · {len(changes.files)} files "
        f"(+{changes.total_additions}/-{changes.total_deletions})"
        f"{f' · cost ~${msg.cost_usd:.4f}' if msg.cost_usd else ''}[/]"
    )


@app.command()
def compare(
    path: Path = typer.Argument(Path("."), help=PATH_HELP),
    period: str = typer.Option(
        "7d", "--period", "-w", help="Length of each period: 7d, 24h, 30d"
    ),
    periods: int = typer.Option(
        4, "--periods", "-n", help="How many prior periods to average"
    ),
    branch: str | None = typer.Option(None, "--branch", "-b"),
    author: list[str] = typer.Option([], "--author", "-a", help=AUTHOR_HELP),
    author_scope: AuthorScopeOption = typer.Option(
        AuthorScopeOption.WINDOW, "--author-scope", help=AUTHOR_SCOPE_HELP
    ),
    depth: int = typer.Option(workspace.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
) -> None:
    p = parse_interval(period)
    with status_spinner(f"Comparing last {period} against prior {periods}"):
        try:
            cmp = gp_trends.compare(
                path,
                p,
                periods_back=periods,
                branch=branch,
                authors=author or None,
                author_scope=author_scope.scope,
                max_depth=depth,
            )
        except ValueError as e:
            console.print(f"[red]{e}[/]")
            raise typer.Exit(1)
    render_comparison(cmp)


@app.command()
def digest(
    path: Path = typer.Argument(Path(".")),
    when: str = typer.Option("7d", "--when", "-w", help=WHEN_HELP),
    to: list[str] = typer.Option(
        ["desktop"], "--to", help="Channels: slack,email,telegram,desktop"
    ),
    provider: str = typer.Option("auto", "--provider", "-p", help=PROVIDER_HELP),
    model: str | None = typer.Option(None, "--model", "-m", help=MODEL_HELP),
    lang: str | None = typer.Option(None, "--lang", "-l", help=LANG_HELP),
) -> None:
    r = resolve_range(when)
    with status_spinner(f"Reading commits from {path.name}"):
        activity = collect_activity(path, r.since, r.until)
    label = "local" if provider == "local" else provider
    with status_spinner(f"Summarizing {activity.commit_count} commits via {label}"):
        summ = summarize(activity, provider=provider, model=model, lang=lang)
    md = render_markdown(activity, summ)
    with status_spinner(f"Sending to {', '.join(to)}"):
        results = dispatch(to, md)
    colour = {"ok": "green", "skipped": "yellow", "failed": "red"}
    for r in results.values():
        detail = f" [dim]({r.reason})[/]" if r.reason else ""
        console.print(f"[{colour[r.status]}]{r.status}[/] {r.channel}{detail}")
    if not any(results.values()):
        console.print("[yellow]Nothing was delivered - printing the digest below.[/]")
        console.print(md)
