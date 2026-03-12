"""Step-by-step infrastructure commands grouped under 'steps'."""

import rich_click as click
from rich.prompt import Confirm

from netloom.models.internal import InternalTopology

from ..core.application import Application
from ..core.enums import RoutingEngine, TemplateSet
from ._group import cli
from ._paramtypes import NodeNameType


@cli.group("steps", invoke_without_command=True)
@click.pass_context
def steps(ctx: click.Context) -> None:
    """Step-by-step infrastructure and config management.

    \b
    Typical order: init → create → gen → attach → start
    """

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@steps.command("init")
@click.pass_obj
def init(obj: dict) -> None:
    """Import base OVA and take a snapshot."""

    app: Application = obj["app"]
    app.infrastructure.init(obj["internal"], obj["workdir"])
    app.console.print("[green]✓ Initialized base VM and workdir.[/green]")


@steps.command("create")
@click.pass_obj
def create(obj: dict) -> None:
    """Create clones and attach empty config-drives."""

    app: Application = obj["app"]
    app.infrastructure.create(obj["internal"])
    app.console.print("[green]✓ Created linked clones and config-drives.[/green]")


@steps.command("gen")
@click.option(
    "--node",
    "-n",
    "node_name",
    default=None,
    type=NodeNameType(),
    help="Generate config only for this node.",
)
@click.pass_obj
def generate(obj: dict, node_name: str | None) -> None:
    """Generate configs for all nodes (or a single node with --node).

    The primary template set (networkd) is always rendered.
    Additional sets are auto-detected from each node's config:

    \b
    - bird     when routing.engine is 'bird'
    - nftables when services.firewall is configured
    - wireguard when services.wireguard is configured
    """

    app: Application = obj["app"]
    internal: InternalTopology = obj["internal"]

    if node_name:
        target = internal.get_node(node_name)
        single = InternalTopology(
            id=internal.id,
            name=internal.name,
            description=internal.description,
            vbox=internal.vbox,
            nodes=[target],
            networks=internal.networks,
            links=internal.links,
        )
        app.config.generate(single)
        app.console.print(f"[green]✓ Config generated for node '{node_name}'.[/green]")
        return

    app.config.generate(internal)

    rendered: set[TemplateSet] = {TemplateSet.NETWORKD}
    for node in internal.nodes:
        if node.routing and node.routing.engine == RoutingEngine.BIRD and node.routing.configured:
            rendered.add(TemplateSet.BIRD)
        if node.services and node.services.firewall:
            rendered.add(TemplateSet.NFTABLES)
        if node.services and node.services.wireguard:
            rendered.add(TemplateSet.WIREGUARD)

    app.console.print(f"[green]✓ Templates rendered: {', '.join(sorted(rendered))}[/green]")


@steps.command("attach")
@click.pass_obj
def attach(obj: dict) -> None:
    """Copy generated configs into each node's config-drive."""

    app: Application = obj["app"]
    app.config.attach(obj["internal"])
    app.console.print("[green]✓ Config-drives populated.[/green]")


@steps.command("start")
@click.pass_obj
def start(obj: dict) -> None:
    """Start all topology VMs."""

    app: Application = obj["app"]
    app.infrastructure.start(obj["internal"])
    app.console.print("[green]✓ VMs started.[/green]")


@steps.command("stop")
@click.pass_obj
def stop(obj: dict) -> None:
    """Send stop signals to all topology VMs."""

    app: Application = obj["app"]
    app.infrastructure.stop(obj["internal"])
    app.console.print("[green]✓ Stop signals sent.[/green]")


@steps.command("destroy")
@click.option(
    "--all",
    "destroy_base",
    is_flag=True,
    help="Also destroy the base VM and its snapshot.",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_obj
def destroy(obj: dict, destroy_base: bool, yes: bool) -> None:
    """Stop and remove all topology VMs."""

    app: Application = obj["app"]
    if not yes:
        if not Confirm.ask("[yellow]This will destroy all topology VMs.[/yellow] Proceed", console=app.console):
            raise click.Abort()

    app.infrastructure.destroy(obj["internal"], destroy_base=destroy_base)
    app.console.print("[green]✓ All VMs destroyed.[/green]")
