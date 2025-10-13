from pathlib import Path

import click

from .models.common import load_topology
from .models.converters import to_internal
from .providers.factory import make_provider


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
    default=".asvk-labs",
    show_default=True,
    type=click.Path(file_okay=False),
    help="Working directory for generated configs and artifacts.",
)
@click.option(
    "--provider",
    default="virtualbox",
    show_default=True,
    type=click.Choice(["virtualbox"]),
    help="Infrastructure provider.",
)
@click.option(
    "--basefolder",
    default=None,
    type=click.Path(file_okay=False),
    help="Provider VM base folder.",
)
@click.option(
    "--ova",
    "ova_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="[VirtualBox] Path to base OVA (used on first init).",
)
@click.option(
    "--base-vm",
    "base_vm_name",
    default="Labs-Base",
    show_default=True,
    help="[VirtualBox] Name for the imported base VM.",
)
@click.option(
    "--snapshot",
    "snapshot_name",
    default="golden",
    show_default=True,
    help="[VirtualBox] Snapshot used for linked clones.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    topo_path: str,
    workdir: str,
    provider: str,
    basefolder: str | None,
    ova_path: str | None,
    base_vm_name: str,
    snapshot_name: str,
):
    """NetLoom topology orchestrator."""

    top = load_topology(topo_path)
    internal = to_internal(top, workdir=workdir)
    prov = make_provider(
        provider,
        basefolder=basefolder,
        ova_path=ova_path,
        base_vm_name=base_vm_name,
        snapshot_name=snapshot_name,
    )
    Path(workdir).mkdir(parents=True, exist_ok=True)
    ctx.obj = {
        "top": top,
        "internal": internal,
        "prov": prov,
        "workdir": workdir,
    }


@cli.command()
@click.pass_obj
def init(obj):
    """Import base OVA and take a snapshot."""

    obj["prov"].init(obj["internal"], obj["workdir"])
    click.echo("Initialized base VM and workdir.")


@cli.command()
@click.pass_obj
def create(obj):
    """Create clones and attach empty config-drives."""

    obj["prov"].create(obj["internal"], obj["workdir"])
    click.echo("Created linked clones and config-drives.")


@cli.command("gen")
@click.option(
    "--templates",
    "template_name",
    default="networkd",
    show_default=True,
    help="Template set name (plugin), e.g. 'networkd'.",
)
@click.pass_obj
def generate(obj, template_name: str):
    """Generate configs."""

    obj["prov"].generate_configs(obj["internal"], obj["workdir"], template_name=template_name)
    click.echo(f"Generated configs using template set: {template_name}")


@cli.command()
@click.pass_obj
def attach(obj):
    """Copy generated configs into each node's config-drive."""

    obj["prov"].attach_raw_config_disks(obj["internal"], obj["workdir"])
    click.echo("Config-drives populated.")


@cli.command()
@click.pass_obj
def start(obj):
    """Start all topology VMs."""

    obj["prov"].start(obj["internal"])
    click.echo("VMs started.")


@cli.command()
@click.pass_obj
def shutdown(obj):
    """Gracefully shutdown all topology VMs."""

    obj["prov"].shutdown(obj["internal"])
    click.echo("Shutdown signals sent.")


@cli.command()
@click.pass_obj
def save(obj):
    """Pull changed files from config-drive back to workdir/saved/<node>/."""

    obj["prov"].save_changed_configs(obj["internal"], obj["workdir"])
    click.echo("Saved config-drive contents to host.")


@cli.command()
@click.pass_obj
def restore(obj):
    """Restore last saved configs into workdir/configs/<node>/."""

    obj["prov"].restore_saved_configs(obj["internal"], obj["workdir"])
    click.echo("Restored saved configs into staging.")
