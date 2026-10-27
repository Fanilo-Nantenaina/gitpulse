from __future__ import annotations

from datetime import datetime
from enum import Enum

import typer
from rich.console import Console

from ..core import workspace
from ..core.dateparse import DateRange, parse_range
from ..core.models import RepoActivity
from ..core.workspace import AuthorScope, RepoFailure

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
MODEL_HELP = "Model name (provider-specific, e.g. claude-opus-5 or llama3.1)."
LANG_HELP = "Output language: code (fr, en, es...) or name. Overrides the default."
PATH_HELP = (
    "What to analyze: a repository, a parent folder of repositories, a git URL "
    "(https://, git@, ssh://), or a named workspace (@name)."
)
DEPTH_HELP = "How deep to look for repositories under a parent folder."
AUTHOR_HELP = "Only commits by this author (name or email, repeatable)."
AUTHOR_SCOPE_HELP = (
    "With --author: 'window' keeps the repos they committed in during the "
    "window, 'all' keeps every repo they ever touched."
)


class AuthorScopeOption(str, Enum):
    WINDOW = "window"
    ALL = "all"

    @property
    def scope(self) -> AuthorScope:
        return "all" if self is AuthorScopeOption.ALL else "window"


def resolve_range(when: str) -> DateRange:
    try:
        return parse_range(when)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        console.print("Run [bold]gitpulse dates[/] to see accepted formats.")
        raise typer.Exit(1)


def collect_scope(
    source: str,
    since: datetime,
    until: datetime | None = None,
    branch: str | None = None,
    authors: list[str] | None = None,
    author_scope: AuthorScopeOption = AuthorScopeOption.WINDOW,
    depth: int = workspace.DEFAULT_DEPTH,
) -> tuple[RepoActivity, list[RepoFailure]]:
    try:
        return workspace.collect(
            source,
            since,
            until,
            branch=branch,
            authors=authors or None,
            author_scope=author_scope.scope,
            max_depth=depth,
        )
    except (ValueError, RuntimeError) as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)


def source_label(source: str) -> str:
    from ..core.sources import display_name

    return display_name(source)
