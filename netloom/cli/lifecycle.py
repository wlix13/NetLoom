"""Lifecycle commands: up, down."""

import rich_click as click
from rich.prompt import Confirm

from netloom.models.internal import InternalTopology

from ..core.application import Application
from ._group import cli


@cli.command()
@click.option(
    "--init",
    "run_init",
    is_flag=True,
    help="Also run init (import OVA, take snapshot) before creating VMs.",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_obj
def up(obj: dict, run_init: bool, yes: bool) -> None:
    """Bring topology up: (init →) create → gen → attach → start."""

    app: Application = obj["app"]
    internal: InternalTopology = obj["internal"]

    steps = (["steps init"] if run_init else []) + ["steps create", "steps gen", "steps attach", "steps start"]
    app.console.print(f"[bold]Pipeline:[/bold] {' → '.join(steps)}")

    if not yes:
        if not Confirm.ask("[yellow]Proceed?[/yellow]", console=app.console):
            raise click.Abort()

    if run_init:
        app.console.print("[dim]── init ──[/dim]")
        app.infrastructure.init(internal, obj["workdir"])

    app.console.print("[dim]── create ──[/dim]")
    app.infrastructure.create(internal)

    app.console.print("[dim]── gen ──[/dim]")
    app.config.generate(internal)

    app.console.print("[dim]── attach ──[/dim]")
    app.config.attach(internal)

    app.console.print("[dim]── start ──[/dim]")
    app.infrastructure.start(internal)

    app.console.print("[green]✓ Topology is up.[/green]")


@cli.command()
@click.option("--all", "destroy_base", is_flag=True, help="Also destroy the base VM.")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_obj
def down(obj: dict, destroy_base: bool, yes: bool) -> None:
    """Tear topology down: stop → destroy."""

    app: Application = obj["app"]
    internal: InternalTopology = obj["internal"]

    app.console.print("[bold]Pipeline:[/bold] stop → destroy")
    if not yes:
        if not Confirm.ask("[yellow]This will destroy all topology VMs.[/yellow] Proceed?", console=app.console):
            raise click.Abort()

    app.console.print("[dim]── stop ──[/dim]")
    app.infrastructure.stop(internal)

    app.console.print("[dim]── destroy ──[/dim]")
    app.infrastructure.destroy(internal, destroy_base=destroy_base)

    app.console.print("[green]✓ Topology is down.[/green]")
