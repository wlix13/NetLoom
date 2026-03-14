"""CLI group definition and global options."""

from pathlib import Path

import rich_click as click

from netloom.models.common import load_topology
from netloom.models.converters import convert_topology

from ..core.application import Application
from ..core.vbox import VBoxSettings
from ._paramtypes import DirectoryType, OvaFileType, TopologyFileType


click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.USE_MARKDOWN = False
click.rich_click.STYLE_ERRORS_SUGGESTION = "dim italic"
click.rich_click.MAX_WIDTH = 100
click.rich_click.COMMAND_GROUPS = {
    "netloom": [
        {"name": "Lab Lifecycle", "commands": ["up", "down"]},
        {"name": "Step-by-step", "commands": ["steps"]},
        {"name": "Config Management", "commands": ["save", "restore", "list-templates"]},
        {"name": "Info", "commands": ["show", "install-completion"]},
    ],
    "netloom steps": [
        {"name": "Commands", "commands": ["init", "create", "gen", "attach", "start", "stop", "destroy"]},
    ],
}


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
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug output (writes _node.json per node).",
)
@click.pass_context
def cli(
    ctx: click.Context,
    topo_path: str | None,
    workdir: Path,
    basefolder: str | None,
    ova_path: str | None,
    base_vm_name: str,
    snapshot_name: str,
    debug: bool,
) -> None:
    """NetLoom topology orchestrator."""

    if ctx.invoked_subcommand == "install-completion":
        ctx.obj = {"app": Application.current()}
        return

    if not topo_path:
        raise click.BadParameter("--topology is required.", param_hint="--topology")

    app = Application.current()
    app.workdir = Path(workdir)
    app.debug = debug

    vbox_settings = VBoxSettings(base_vm_name=base_vm_name, snapshot_name=snapshot_name)
    if basefolder:
        vbox_settings.basefolder = Path(basefolder)
    if ova_path:
        vbox_settings.ova_path = Path(ova_path)
    app.vbox_settings = vbox_settings

    internal = convert_topology(load_topology(topo_path), workdir=workdir)
    app.workdir.mkdir(parents=True, exist_ok=True)

    ctx.obj = {
        "app": app,
        "internal": internal,
        "workdir": app.workdir,
    }
