"""Terminal rendering of summaries using Rich."""

from __future__ import annotations

from contextlib import contextmanager

from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    MofNCompleteColumn,
    TaskProgressColumn,
)
from rich.table import Table
from rich.text import Text

from ..core.models import RepoActivity
from ..ai.summarizer import Summary

console = Console()


@contextmanager
def progress_bar(description: str = "Working"):
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
def status_spinner(message: str):
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


def render_terminal(activity: RepoActivity, summary: Summary) -> None:
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

    console.print(Text(f"  {summary.cost_note}", style="dim"))
    if summary.source == "local(truncated)":
        console.print(
            Text(
                "Claude's reply was cut off; max_tokens was raised — retry. "
                "Showed local summary instead.",
                style="dim red",
            )
        )
    console.print()


def render_log(activity: RepoActivity, show_files: bool = False) -> None:
    w = _width()
    if activity.commit_count == 0:
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

    for c in activity.commits:
        line = Text("commit ", style="default")
        line.append(c.sha, style="yellow")
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


def render_markdown(activity: RepoActivity, summary: Summary) -> str:
    """Markdown digest for email / Slack / changelog use."""
    lines = [
        f"# {activity.repo_name} — {activity.since:%Y-%m-%d} → {activity.until:%Y-%m-%d}",
        "",
        f"**{summary.headline}**",
        "",
        f"`{activity.commit_count} commits` · "
        f"`+{activity.total_additions}` / `-{activity.total_deletions}` lines",
        "",
    ]
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
            lines.append(f"- {o}")
        lines.append("")
    return "\n".join(lines)
