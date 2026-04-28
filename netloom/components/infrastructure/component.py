"""Infrastructure component: lifecycle wrapper + CLI for VM orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import rich_click as click
from rich.box import ROUNDED
from rich.prompt import Confirm
from rich.table import Table

from netloom.core.component import BaseComponent
from netloom.core.enums import VMState
from netloom.models.internal import InternalTopology

from .controller import InfrastructureController, NodeStatus


if TYPE_CHECKING:
    from netloom.core.application import Application  # noqa: F401


_STATE_STYLE: dict[str, str] = {
    VMState.RUNNING: "green",
    VMState.POWEROFF: "dim",
    VMState.SAVED: "yellow",
    VMState.ABORTED: "red",
}


class InfrastructureComponent(BaseComponent["Application", InfrastructureController]):
    """Owns the VM lifecycle controller and wires its CLI commands."""

    name: ClassVar[str] = "infrastructure"
    controller_class: ClassVar[type] = InfrastructureController

    def expose_cli(self, base: click.Group) -> None:  # noqa: PLR0915
        # ── steps group ──────────────────────────────────────────────────────

        @base.group("steps", invoke_without_command=True)
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
            app = obj["app"]
            app.infrastructure.init(obj["internal"], obj["workdir"])
            app.console.print("[green]✓ Initialized base VM and workdir.[/green]")

        @steps.command("create")
        @click.pass_obj
        def create(obj: dict) -> None:
            """Create clones and attach empty config-drives."""
            app = obj["app"]
            app.infrastructure.create(obj["internal"])
            app.console.print("[green]✓ Created linked clones and config-drives.[/green]")

        @steps.command("gen")
        @click.option("--node", "-n", "node_name", default=None, help="Generate config only for this node.")
        @click.pass_obj
        def generate(obj: dict, node_name: str | None) -> None:
            """Generate configs for all nodes (or a single node with --node).

            \b
            Template sets are auto-detected from each node's config:
              - networkd   always
              - bird       when routing.engine is 'bird'
              - nftables   when services.firewall is configured
              - wireguard  when services.wireguard is configured
            """
            app = obj["app"]
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
            rendered = app.config.rendered_sets(internal)
            app.console.print(f"[green]✓ Templates rendered: {', '.join(sorted(rendered))}[/green]")

        @steps.command("attach")
        @click.pass_obj
        def attach(obj: dict) -> None:
            """Copy generated configs into each node's config-drive."""
            app = obj["app"]
            app.config.attach(obj["internal"])
            app.console.print("[green]✓ Config-drives populated.[/green]")

        @steps.command("start")
        @click.pass_obj
        def start(obj: dict) -> None:
            """Start all topology VMs."""
            app = obj["app"]
            app.infrastructure.start(obj["internal"])
            app.console.print("[green]✓ VMs started.[/green]")

        @steps.command("stop")
        @click.pass_obj
        def stop(obj: dict) -> None:
            """Send stop signals to all topology VMs."""
            app = obj["app"]
            app.infrastructure.stop(obj["internal"])
            app.console.print("[green]✓ Stop signals sent.[/green]")

        @steps.command("destroy")
        @click.option("--all", "destroy_base", is_flag=True, help="Also destroy the base VM and its snapshot.")
        @click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
        @click.pass_obj
        def destroy(obj: dict, destroy_base: bool, yes: bool) -> None:
            """Stop and remove all topology VMs."""
            app = obj["app"]
            if not yes:
                if not Confirm.ask("[yellow]This will destroy all topology VMs.[/yellow] Proceed", console=app.console):
                    raise click.Abort()
            app.infrastructure.destroy(obj["internal"], destroy_base=destroy_base)
            app.console.print("[green]✓ All VMs destroyed.[/green]")

        # ── up / down ─────────────────────────────────────────────────────────

        @base.command()
        @click.option("--init", "run_init", is_flag=True, help="Also run init before creating VMs.")
        @click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
        @click.pass_obj
        def up(obj: dict, run_init: bool, yes: bool) -> None:
            """Bring topology up: (init →) create → gen → attach → start."""
            app = obj["app"]
            internal: InternalTopology = obj["internal"]

            pipeline = (["steps init"] if run_init else []) + [
                "steps create",
                "steps gen",
                "steps attach",
                "steps start",
            ]
            app.console.print(f"[bold]Pipeline:[/bold] {' → '.join(pipeline)}")

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

        @base.command()
        @click.option("--all", "destroy_base", is_flag=True, help="Also destroy the base VM.")
        @click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
        @click.pass_obj
        def down(obj: dict, destroy_base: bool, yes: bool) -> None:
            """Tear topology down: stop → destroy."""
            app = obj["app"]
            internal: InternalTopology = obj["internal"]

            app.console.print("[bold]Pipeline:[/bold] stop → destroy")
            if not yes:
                msg = "[yellow]This will destroy all topology VMs.[/yellow] Proceed?"
                if not Confirm.ask(msg, console=app.console):
                    raise click.Abort()

            app.console.print("[dim]── stop ──[/dim]")
            app.infrastructure.stop(internal)
            app.console.print("[dim]── destroy ──[/dim]")
            app.infrastructure.destroy(internal, destroy_base=destroy_base)
            app.console.print("[green]✓ Topology is down.[/green]")

        # ── runtime: status / connect ─────────────────────────────────────────

        @base.command()
        @click.option("--node", "-n", "node_name", default=None, help="Show only this node.")
        @click.pass_obj
        def status(obj: dict, node_name: str | None) -> None:
            """Show live VM state and UART connection port for each node."""
            app = obj["app"]
            internal: InternalTopology = obj["internal"]
            rows: list[NodeStatus] = app.infrastructure.status(internal, node_name)

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

                conn_cell = f"[cyan]{row.connection.uri}[/cyan]" if row.connection else "[dim]—[/dim]"
                table.add_row(row.name, state_cell, conn_cell)

            app.console.print(table)
            if not node_name:
                app.console.print()
                parts = [f"Running: {running}", f"Stopped: {stopped}"]
                if other:
                    parts.append(f"Other: {other}")
                parts.append(f"Not created: {missing}")
                app.console.print(f"[dim]{'  •  '.join(parts)}[/dim]")

        @base.command()
        @click.argument("node")
        @click.pass_obj
        def connect(obj: dict, node: str) -> None:
            """Open an interactive console to NODE."""
            app = obj["app"]
            infra = app.infrastructure

            state = infra.get_vm_state(node)
            if state is None:
                app.console.print(f"[red]VM '{node}' not created.[/red] Run 'netloom up' first.")
                raise SystemExit(1)
            if state != VMState.RUNNING:
                app.console.print(f"[red]VM '{node}' is {state}.[/red] Start it with 'netloom steps start'.")
                raise SystemExit(1)

            info = infra.get_connection_info(node)
            if info is None:
                app.console.print(f"[red]No console connection available for '{node}'.[/red]")
                raise SystemExit(1)

            if info.protocol == "tcp-serial":
                from netloom.connect import run_bridge

                code = run_bridge(info.host, info.port, app.console)
                if code != 0:
                    raise SystemExit(code)
            else:
                app.console.print(f"[cyan]Connect to:[/cyan] {info.uri}")
