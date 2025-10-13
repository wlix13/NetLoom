"""NetLoom CLI."""

import sys
from pathlib import Path

import click
import rich_click

from .core.application import Application
from .core.paramtypes import DirectoryType, OvaFileType, TemplateSetType, TopologyFileType


# Configure rich-click
rich_click.rich_click.USE_RICH_MARKUP = True
rich_click.rich_click.SHOW_ARGUMENTS = True
rich_click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
rich_click.rich_click.USE_MARKDOWN = False
rich_click.rich_click.STYLE_ERRORS_SUGGESTION = "dim italic"
rich_click.rich_click.MAX_WIDTH = 100


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--topology",
    "topo_path",
    type=TopologyFileType(),
    help="Path to topology YAML.",
)
@click.option(
    "--workdir",
    default=".labs_configs",
    show_default=True,
    type=DirectoryType(must_exist=False),
    help="Working directory for generated configs and artifacts.",
)
@click.option(
    "--basefolder",
    default=None,
    type=DirectoryType(must_exist=False),
    help="VirtualBox VM base folder.",
)
@click.option(
    "--ova",
    "ova_path",
    default=None,
    type=OvaFileType(),
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
    topo_path: str | None,
    workdir: str,
    basefolder: str | None,
    ova_path: str | None,
    base_vm_name: str,
    snapshot_name: str,
):
    """NetLoom topology orchestrator."""

    if ctx.invoked_subcommand == "install-completion":
        ctx.obj = {"app": Application.current()}
        return

    if not topo_path:
        raise click.BadParameter("--topology is required.", param_hint="--topology")

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
    type=TemplateSetType(),
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
@click.option(
    "--all",
    "destroy_base",
    is_flag=True,
    help="Also destroy the base VM and its snapshot. Use with caution!",
)
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


@cli.command("install-completion")
@click.option(
    "--install",
    "install_shell",
    type=click.Choice(["bash", "zsh", "fish", "powershell"], case_sensitive=False),
    help="Install completion script for the specified shell.",
)
@click.pass_obj
def install_completion(obj: dict | None, install_shell: str | None):
    """Generate or install shell completion scripts for netloom."""

    app = Application.current()

    if install_shell:
        shell = install_shell.lower()

        home = Path.home()
        if shell == "bash":
            config_file = home / ".bashrc"
            completion_line = 'eval "$(_NETLOOM_COMPLETE=bash_source netloom)"'
        elif shell == "zsh":
            config_file = home / ".zshrc"
            completion_line = 'eval "$(_NETLOOM_COMPLETE=zsh_source netloom)"'
        elif shell == "fish":
            config_dir = home / ".config" / "fish"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.fish"
            completion_line = "eval (env _NETLOOM_COMPLETE=fish_source netloom)"
        elif shell == "powershell":
            raise NotImplementedError("PowerShell completion is not supported yet.")

        try:
            if config_file.exists():
                with open(config_file, encoding="utf-8") as f:
                    content = f.read()
                    if "_NETLOOM_COMPLETE" in content:
                        app.console.print(f"[yellow]Completion already installed in {config_file}[/yellow]")
                        return

            with open(config_file, "a", encoding="utf-8") as f:
                f.write(f"\n# NetLoom completion\n{completion_line}\n")

            app.console.print(f"[green]✓ Completion script installed for {shell}[/green]")
            app.console.print(f"[dim]Added to: {config_file}[/dim]")
        except Exception as e:
            app.console.print(f"[red]Error installing completion: {e}[/red]")
            app.console.print("\n[yellow]Manual installation:[/yellow]")
            app.console.print(f"  Add this line to {config_file}:")
            app.console.print(f"  {completion_line}")
            sys.exit(1)
    else:
        app.console.print("[bold]Shell Completion Setup[/bold]\n")
        app.console.print("To enable tab completion, add one of the following to your shell config:\n")
        app.console.print("[cyan]Bash (~/.bashrc):[/cyan]")
        app.console.print('  eval "$(_NETLOOM_COMPLETE=bash_source netloom)"')
        app.console.print("\n[cyan]Zsh (~/.zshrc):[/cyan]")
        app.console.print('  eval "$(_NETLOOM_COMPLETE=zsh_source netloom)"')
        app.console.print("\n[cyan]Fish (~/.config/fish/config.fish):[/cyan]")
        app.console.print("  eval (env _NETLOOM_COMPLETE=fish_source netloom)")
        app.console.print("\n[yellow]Or use --install option to automatically install:[/yellow]")
        app.console.print("  netloom install-completion --install zsh")
