"""CLI group definition and global options."""

from __future__ import annotations

from pathlib import Path

import rich_click as click

from netloom.models.common import load_topology
from netloom.models.converters import convert_topology

from ..core.application import Application
from ..core.paramtypes import DirectoryType, FaultsFileType, TopologyFileType
from ..hypervisors import available_hypervisors, get_hypervisor_class


click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "dim italic"
click.rich_click.MAX_WIDTH = 100
click.rich_click.COMMAND_GROUPS = {
    "netloom": [
        {"name": "Lab Lifecycle", "commands": ["up", "down"]},
        {"name": "Step-by-step", "commands": ["steps"]},
        {"name": "Config Management", "commands": ["save", "restore", "list-templates"]},
        {"name": "Broken Labs", "commands": ["faults"]},
        {"name": "Runtime", "commands": ["status", "connect"]},
        {"name": "Info", "commands": ["show", "install-completion"]},
    ],
    "netloom faults": [
        {"name": "Commands", "commands": ["catalog", "generate", "reveal"]},
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
    "--faults",
    "faults_path",
    default=None,
    type=FaultsFileType(),
    help="Apply a fault-injection spec: deploy the lab deliberately broken. [yellow]Instructor option.[/yellow]",
)
@click.option(
    "--debug",
    is_flag=True,
    default=False,
    help="Enable debug output (writes _node.json per node).",
)
@click.pass_context
def cli(  # noqa: PLR0913
    ctx: click.Context,
    topo_path: str | None,
    workdir: str,
    hypervisor: str,
    faults_path: str | None,
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

    if faults_path:
        report = app.faults.apply_spec(internal, faults_path)
        app.console.print(
            f"[yellow]⚠ Broken-lab mode: {len(report.faults)} fault(s) injected "
            f"(answer key: {app.faults.answer_key_path}).[/yellow]"
        )

    ctx.obj = {
        "app": app,
        "internal": internal,
        "workdir": app.workdir,
    }


# Inject every registered driver's (prefixed) CLI options so they appear in
# --help and are passed as **driver_kwargs to the callback above.  The
# selected driver picks out its own parameters via strip_own_prefix().
for _driver_name in available_hypervisors():
    for _opt in get_hypervisor_class(_driver_name).cli_options():
        cli.params.append(_opt)

# Register components and wire their CLI commands onto the group.
# This happens at import time so commands are visible to Click before any
# invocation occurs.  app.hypervisor is set later in the cli() callback.
from netloom.components.config import ConfigComponent  # noqa: E402
from netloom.components.faults import FaultsComponent  # noqa: E402
from netloom.components.infrastructure import InfrastructureComponent  # noqa: E402


_app = Application.current()
_app.register(InfrastructureComponent)
_app.register(ConfigComponent)
_app.register(FaultsComponent)
for _component in _app.components.values():
    _component.expose_cli(cli)
