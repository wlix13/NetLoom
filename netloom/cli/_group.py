"""CLI group definition and global options."""

from __future__ import annotations

from pathlib import Path

import rich_click as click

from netloom.models.common import load_topology
from netloom.models.converters import convert_topology

from ..core.application import Application
from ..hypervisors import available_hypervisors, get_hypervisor_class
from ._paramtypes import DirectoryType, TopologyFileType


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
        {"name": "Runtime", "commands": ["status", "connect"]},
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
    "--hypervisor",
    default="vbox",
    show_default=True,
    help=f"Hypervisor driver. Available: {', '.join(available_hypervisors())}.",
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
    workdir: str,
    hypervisor: str,
    debug: bool,
    **driver_kwargs: object,
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

    driver_cls = get_hypervisor_class(hypervisor)
    app.hypervisor = driver_cls.from_cli_params(console=app.console, **driver_kwargs)

    internal = convert_topology(load_topology(topo_path), workdir=workdir)
    app.workdir.mkdir(parents=True, exist_ok=True)

    ctx.obj = {
        "app": app,
        "internal": internal,
        "workdir": app.workdir,
    }


# Inject the default driver's (vbox) CLI options so they appear in --help
# and are passed as **driver_kwargs to the callback above.
_default_driver_cls = get_hypervisor_class("vbox")
for _opt in _default_driver_cls.cli_options():
    cli.params.append(_opt)

# Register components and wire their CLI commands onto the group.
# This happens at import time so commands are visible to Click before any
# invocation occurs.  app.hypervisor is set later in the cli() callback.
from netloom.components.config import ConfigComponent  # noqa: E402
from netloom.components.infrastructure import InfrastructureComponent  # noqa: E402


_app = Application.current()
_app.register(InfrastructureComponent)
_app.register(ConfigComponent)
for _component in _app.components.values():
    _component.expose_cli(cli)
