from __future__ import annotations

import typer
from rich.table import Table

from ..core import config as gp_config
from ..core import sources
from ._shared import DEPTH_HELP, app, console

workspace_app = typer.Typer(
    help=(
        "Named workspaces: a saved set of folders, repos and git URLs from any "
        "location (Windows, WSL, SSH, forges), used as @name by every command."
    ),
    no_args_is_help=True,
)
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("add")
def workspace_add(
    name: str = typer.Argument(..., help="Workspace name (used as @name)"),
    members: list[str] = typer.Argument(
        ..., help="Repos, parent folders or git URLs to add"
    ),
) -> None:
    try:
        current = gp_config.add_to_workspace(name, members)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    label = name.removeprefix("@")
    console.print(f"[green]@{label}[/] now has {len(current)} member(s).")
    console.print(f"[dim]Try: gitpulse summary @{label}[/]")


@workspace_app.command("remove")
def workspace_remove(
    name: str = typer.Argument(..., help="Workspace name"),
    members: list[str] = typer.Argument(
        None, help="Members to drop; omit to delete the whole workspace"
    ),
) -> None:
    label = name.removeprefix("@")
    if gp_config.remove_from_workspace(label, members or None):
        what = f"{len(members)} member(s) from" if members else "workspace"
        console.print(f"[green]Removed {what} @{label}.[/]")
    else:
        console.print(f"[yellow]Nothing to remove for @{label}.[/]")


@workspace_app.command("list")
def workspace_list() -> None:
    items = gp_config.list_workspaces()
    if not items:
        console.print(
            "[yellow]No workspaces yet. Create one with "
            "[bold]gitpulse workspace add <name> <path-or-url>...[/][/]"
        )
        return
    table = Table(title="Workspaces", show_lines=False)
    table.add_column("Name", style="cyan")
    table.add_column("Members", justify="right")
    table.add_column("Paths and URLs", style="dim", overflow="fold")
    for name, members in items.items():
        table.add_row(f"@{name}", str(len(members)), "\n".join(members))
    console.print(table)


@workspace_app.command("show")
def workspace_show(
    name: str = typer.Argument(..., help="Workspace name"),
    depth: int = typer.Option(sources.DEFAULT_DEPTH, "--depth", help=DEPTH_HELP),
    no_refresh: bool = typer.Option(
        False, "--no-refresh", help="Use cached clones for URL members"
    ),
) -> None:
    label = name.removeprefix("@")
    try:
        repo_set = sources.expand(f"@{label}", depth, refresh=not no_refresh)
    except (ValueError, RuntimeError) as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    table = Table(title=f"@{label}: {len(repo_set.refs)} repositories")
    table.add_column("Repository", style="cyan")
    table.add_column("Location", style="dim", overflow="fold")
    for ref in repo_set.refs:
        table.add_row(ref.name, ref.path)
    for f in repo_set.failures:
        table.add_row(f"[red]{f['name']}[/]", f"[red]{f['error']}[/]")
    console.print(table)
