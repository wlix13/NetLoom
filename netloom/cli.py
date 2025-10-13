"""NetLoom CLI."""

from pathlib import Path

import click

from .core.application import Application


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--topology",
    "topo_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to topology YAML.",
)
@click.option(
    "--workdir",
    default=".labs_configs",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Working directory for generated configs and artifacts.",
)
@click.option(
    "--basefolder",
    default=None,
    type=click.Path(file_okay=False),
    help="VirtualBox VM base folder.",
)
@click.option(
    "--ova",
    "ova_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to base OVA (used on first init).",
)
@click.option(
    "--base-vm",
    "base_vm_name",
    default="Labs-Base",
    show_default=True,
    help="Name for the imported base VM.",
)
@click.option(
    "--snapshot",
    "snapshot_name",
    default="golden",
    show_default=True,
    help="Snapshot used for linked clones.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    topo_path: str,
    workdir: str,
    basefolder: str | None,
    ova_path: str | None,
    base_vm_name: str,
    snapshot_name: str,
):
    """NetLoom topology orchestrator."""

    app = Application.current()
    app.workdir = Path(workdir)

    app.infrastructure.configure(
        basefolder=basefolder,
        ova_path=ova_path,
        base_vm_name=base_vm_name,
        snapshot_name=snapshot_name,
    )

    topology = app.topology.load(topo_path)
    internal = app.topology.convert(topology, workdir=workdir)

    Path(workdir).mkdir(parents=True, exist_ok=True)

    ctx.obj = {
        "app": app,
        "topology": topology,
        "internal": internal,
        "workdir": workdir,
    }


@cli.command()
@click.pass_obj
def init(obj):
    """Import base OVA and take a snapshot."""

    app: Application = obj["app"]
    app.infrastructure.init(obj["internal"], obj["workdir"])
    app.console.print("[green]Initialized base VM and workdir.[/green]")


@cli.command()
@click.pass_obj
def create(obj):
    """Create clones and attach empty config-drives."""

    app: Application = obj["app"]
    app.infrastructure.create(obj["internal"])
    app.console.print("[green]Created linked clones and config-drives.[/green]")


@cli.command("gen")
@click.option(
    "--templates",
    "template_name",
    default="networkd",
    show_default=True,
    help="Template set name, e.g. 'networkd'.",
)
@click.pass_obj
def generate(obj, template_name: str):
    """Generate configs for all nodes."""

    app: Application = obj["app"]
    app.config.generate(obj["internal"], template_set=template_name)
    app.console.print(f"[green]Generated configs using template set: {template_name}[/green]")


@cli.command()
@click.pass_obj
def attach(obj):
    """Copy generated configs into each node's config-drive."""

    app: Application = obj["app"]
    app.config.attach(obj["internal"])
    app.console.print("[green]Config-drives populated.[/green]")


@cli.command()
@click.pass_obj
def start(obj):
    """Start all topology VMs."""

    app: Application = obj["app"]
    app.infrastructure.start(obj["internal"])
    app.console.print("[green]VMs started.[/green]")


@cli.command()
@click.pass_obj
def stop(obj):
    """Send stop signals to all topology VMs."""

    app: Application = obj["app"]
    app.infrastructure.stop(obj["internal"])
    app.console.print("[green]Stop signals sent.[/green]")


@cli.command()
@click.option("--all", "destroy_base", is_flag=True, help="Also destroy the base (golden) VM.")
@click.pass_obj
def destroy(obj, destroy_base: bool):
    """Stop and remove all topology VMs."""

    app: Application = obj["app"]
    app.infrastructure.destroy(obj["internal"], destroy_base=destroy_base)
    app.console.print("[green]All VMs destroyed.[/green]")


@cli.command()
@click.pass_obj
def save(obj):
    """Pull changed files from config-drive back to workdir/saved/<node>/."""

    app: Application = obj["app"]
    app.config.save(obj["internal"])
    app.console.print("[green]Saved config-drive contents to host.[/green]")


@cli.command()
@click.pass_obj
def restore(obj):
    """Restore last saved configs into workdir/configs/<node>/."""

    app: Application = obj["app"]
    app.config.restore(obj["internal"])
    app.console.print("[green]Restored saved configs into staging.[/green]")


@cli.command("list-templates")
@click.pass_obj
def list_templates(obj):
    """List available template sets."""

    app: Application = obj["app"]
    templates = app.config.list_template_sets()
    if templates:
        app.console.print("[bold]Available template sets:[/bold]")
        for tpl in templates:
            app.console.print(f"  - {tpl}")
    else:
        app.console.print("[yellow]No template sets found.[/yellow]")


@cli.command("show")
@click.pass_obj
def show_topology(obj):
    """Display topology information."""

    app: Application = obj["app"]
    internal = obj["internal"]

    app.console.print(f"[bold]Topology:[/bold] {internal.name} ({internal.id})")
    if internal.description:
        app.console.print(f"[dim]{internal.description}[/dim]")
    app.console.print()

    app.console.print(f"[bold]Nodes:[/bold] {len(internal.nodes)}")
    for node in internal.nodes:
        role_color = {"router": "cyan", "switch": "yellow", "host": "green"}.get(node.role, "white")
        app.console.print(f"  [{role_color}]{node.name}[/{role_color}] ({node.role})")
        for iface in node.interfaces:
            peer = f" -> {iface.peer_node}" if iface.peer_node else ""
            ip = f" [{iface.ip}]" if iface.ip else ""
            app.console.print(f"    {iface.name}{ip}{peer}")

    app.console.print()
    app.console.print(f"[bold]Links:[/bold] {len(internal.links)}")
    for link in internal.links:
        app.console.print(f"  {link.node_a}/{link.interface_a} <-> {link.node_b}/{link.interface_b}")
