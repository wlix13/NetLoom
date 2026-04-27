"""Runtime commands: status, connect."""

import rich_click as click
from rich.box import ROUNDED
from rich.table import Table

from ..connect import run_bridge
from ..core.application import Application
from ..core.enums import VMState
from ..models.internal import InternalTopology
from ._group import cli
from ._paramtypes import NodeNameType


_STATE_STYLE: dict[str, str] = {
    VMState.RUNNING: "green",
    VMState.POWEROFF: "dim",
    VMState.SAVED: "yellow",
    VMState.ABORTED: "red",
}


@cli.command()
@click.option("--node", "-n", "node_name", default=None, type=NodeNameType(), help="Show only this node.")
@click.pass_obj
def status(obj: dict, node_name: str | None) -> None:
    """Show live VM state and UART connection port for each node."""

    app: Application = obj["app"]
    internal: InternalTopology = obj["internal"]

    rows = app.infrastructure.status(internal, node_name)

    table = Table(box=ROUNDED, show_header=True, border_style="dim", expand=False)
    table.add_column("Node", no_wrap=True)
    table.add_column("State")
    table.add_column("Connection")

    running = stopped = other = missing = 0
    for row in rows:
        if row.state is None:
            state_cell = "[dim red]not created[/dim red]"
            missing += 1
        else:
            style = _STATE_STYLE.get(row.state, "white")
            state_cell = f"[{style}]{row.state}[/{style}]"
            if row.state == VMState.RUNNING:
                running += 1
            elif row.state == VMState.POWEROFF:
                stopped += 1
            else:
                other += 1

        conn_cell = f"[cyan]tcp://127.0.0.1:{row.port}[/cyan]" if row.port else "[dim]—[/dim]"
        table.add_row(row.name, state_cell, conn_cell)

    app.console.print(table)
    if not node_name:
        app.console.print()
        parts = [f"Running: {running}", f"Stopped: {stopped}"]
        if other:
            parts.append(f"Other: {other}")
        parts.append(f"Not created: {missing}")
        app.console.print(f"[dim]{'  •  '.join(parts)}[/dim]")


@cli.command()
@click.argument("node", type=NodeNameType())
@click.pass_obj
def connect(obj: dict, node: str) -> None:
    """Open an interactive serial console to NODE over its UART TCP port."""

    app: Application = obj["app"]
    infra = app.infrastructure

    state = infra.get_vm_state(node)
    if state is None:
        app.console.print(f"[red]VM '{node}' not created.[/red] Run 'netloom up' first.")
        raise SystemExit(1)

    if state != VMState.RUNNING:
        app.console.print(f"[red]VM '{node}' is {state}.[/red] Start it with 'netloom steps start'.")
        raise SystemExit(1)

    endpoint = infra.get_connection_endpoint(node)
    if endpoint is None:
        app.console.print(f"[red]UART1 on '{node}' is not in tcpserver mode; cannot connect.[/red]")
        raise SystemExit(1)

    host, port = endpoint
    code = run_bridge(host, port, app.console)
    if code != 0:
        raise SystemExit(code)
