from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..core.models import RepoActivity
from ..ai.summarizer import Summary

console = Console()

_BLOCKS = " ▁▂▃▄▅▆▇█"


def _spark(values: list[int]) -> str:
    if not values or max(values) == 0:
        return _BLOCKS[0] * len(values)
    hi = max(values)
    return "".join(_BLOCKS[min(8, round(v / hi * 8))] for v in values)


def render_terminal(activity: RepoActivity, summary: Summary) -> None:
    console.print()
    console.print(
        Panel(
            Text(summary.headline, style="bold cyan"),
            title=f"{activity.repo_name}",
            subtitle=f"{activity.since:%Y-%m-%d} → {activity.until:%Y-%m-%d}",
            border_style="cyan",
        )
    )

    stats = Table.grid(padding=(0, 3))
    stats.add_row(
        Text(f"{activity.commit_count}", style="bold"),
        "commits",
        Text(f"+{activity.total_additions}", style="green"),
        "added",
        Text(f"-{activity.total_deletions}", style="red"),
        "deleted",
    )
    console.print(stats)

    # Productivity heatmap (24h sparkline)
    hist = activity.hour_histogram
    spark = _spark([hist[h] for h in range(24)])
    console.print(
        Text("  hours  ", style="dim")
        + Text(spark, style="yellow")
        + Text("  (00h→23h)", style="dim")
    )
    console.print()

    for theme in summary.themes:
        body = Text(theme.get("narrative", ""))
        shas = " ".join(theme.get("commits", []))
        console.print(
            Panel(
                body,
                title=f"[bold]{theme['title']}[/bold]",
                subtitle=f"[dim]{shas}[/dim]",
                border_style="blue",
                padding=(0, 1),
            )
        )

    if summary.observations:
        obs = Table(show_header=False, box=None, padding=(0, 1))
        for o in summary.observations:
            obs.add_row("⚠", o)
        console.print(Panel(obs, title="Observations", border_style="yellow"))
    console.print()


def render_markdown(activity: RepoActivity, summary: Summary) -> str:
    """Markdown digest for email / Slack / changelog use."""
    lines = [
        f"# 📊 {activity.repo_name} — {activity.since:%Y-%m-%d} → {activity.until:%Y-%m-%d}",
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
