from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ._shared import app, console
from ..service import controller, units


service_app = typer.Typer(
    help="Run the GitPulse web UI as a background service.", no_args_is_help=True
)
app.add_typer(service_app, name="service")


@service_app.command("start")
def service_start(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8420, "--port"),
):
    """Start the web UI in the background (detached)."""
    res = controller.start(host=host, port=port)
    if res.get("already"):
        console.print(f"[yellow]Already running[/] (pid {res['pid']}) — {res['url']}")
    elif res.get("started"):
        console.print(f"[green]Started[/] (pid {res['pid']}) — {res['url']}")
        console.print("[dim]Stop with: gitpulse service stop[/]")
    else:
        console.print(f"[red]Failed to start:[/] {res.get('error')}")
        console.print(f"[dim]Log: {res.get('log')}[/]")
        raise typer.Exit(1)


@service_app.command("stop")
def service_stop():
    """Stop the background web UI."""
    res = controller.stop()
    if res.get("stopped"):
        console.print(f"[green]Stopped[/] (pid {res['pid']})")
    else:
        console.print(f"[yellow]Not running.[/]")


@service_app.command("status")
def service_status():
    """Show whether the background web UI is running."""
    st = controller.status()
    if st["running"]:
        console.print(f"[green]running[/] — pid {st['pid']}")
    else:
        console.print("[dim]stopped[/]")
    console.print(f"[dim]Log: {st['log']}[/]")


@service_app.command("restart")
def service_restart(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8420, "--port"),
):
    """Restart the background web UI."""
    controller.stop()
    service_start(host=host, port=port)


@service_app.command("install")
def service_install(
    kind: str = typer.Argument(
        "web", help="'web' (keep UI running) or 'watch' (periodic digest)"
    ),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8420, "--port"),
    path: Path = typer.Option(Path("."), "--path", help="(watch) repo to digest"),
    every: str = typer.Option("24h", "--every", help="(watch) cadence"),
    when: str = typer.Option("24h", "--when", help="(watch) window each digest covers"),
    to: str = typer.Option("desktop", "--to", help="(watch) channels, comma-separated"),
    write: Optional[Path] = typer.Option(
        None, "--write", help="Write the unit file to this path"
    ),
):
    """Generate an OS-native boot service (systemd / launchd / Task Scheduler)."""
    if kind not in ("web", "watch"):
        console.print("[red]kind must be 'web' or 'watch'[/]")
        raise typer.Exit(1)
    fname, contents, hint = units.for_platform(
        kind, host=host, port=port, path=str(path), every=every, when=when, to=to
    )

    if write:
        target = write if write.is_dir() is False else write / fname
        target.write_text(contents, encoding="utf-8")
        console.print(f"[green]Wrote {target}[/]")
    else:
        console.print(f"[bold cyan]# {fname}[/]")
        console.print(contents)
    console.print("[bold]Install:[/]")
    console.print(hint)


@app.command()
def shutdown(
    port: int = typer.Option(8420, "--port", help="Port to also free if held"),
):
    res = controller.shutdown_all(port=port)
    if res["count"] == 0 and not res["failed"]:
        console.print("[dim]No running GitPulse processes found.[/]")
    else:
        if res["killed"]:
            console.print(
                f"[green]Stopped {res['count']} process(es):[/] "
                + ", ".join(str(p) for p in res["killed"])
            )
        if res["failed"]:
            console.print(
                f"[yellow]Could not stop:[/] "
                + ", ".join(str(p) for p in res["failed"])
                + " — close this terminal and retry, or stop them in Task Manager."
            )
    console.print("[dim]You can now run: pipx uninstall gitpulse[/]")


@app.command()
def gui(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8420, "--port"),
):
    from ..gui import main as gui_main

    gui_main(["--host", host, "--port", str(port)])
