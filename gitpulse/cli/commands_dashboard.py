from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from ._shared import (
    app,
    console,
    _range,
    WHEN_HELP,
    PROVIDER_HELP,
    MODEL_HELP,
    LANG_HELP,
)
from ..core.collector import collect_activity, discover_repos
from ..core import config as gp_config
from ..core import remote as gp_remote
from ..ai.summarizer import summarize
from .render import progress_bar


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
