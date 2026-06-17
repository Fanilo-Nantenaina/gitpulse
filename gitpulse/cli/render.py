from __future__ import annotations

from rich.console import Console
from rich.padding import Padding
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

    # --- Observations --------------------------------------------------------
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
                "  Claude's reply was cut off; max_tokens was raised — retry. "
                "Showed local summary instead.",
                style="dim red",
            )
        )
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
