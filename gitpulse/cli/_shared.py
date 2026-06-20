"""Shared CLI primitives: the Typer app, console, help strings, and helpers.

Command modules import `app` from here and register their commands onto it, so
the command namespace stays flat (`gitpulse summary`, not `gitpulse x summary`)
while the definitions live in small per-domain files.
"""
from __future__ import annotations

import typer
from rich.console import Console

from ..core.dateparse import parse_range, DateRange

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
