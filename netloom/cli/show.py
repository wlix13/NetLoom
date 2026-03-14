"""Show command for topology information display."""

import rich_click as click
from rich.box import ROUNDED
from rich.table import Table

from netloom.models.internal import InternalTopology
from netloom.utils.display import ROLE_COLOR, render_graph, render_map

from ..core.application import Application
from ._group import cli
from ._paramtypes import NodeNameType


@cli.command("show")
@click.option("--node", "-n", "node_name", default=None, type=NodeNameType(), help="Show only this node.")
@click.option("--routing", "-r", is_flag=True, help="Show routing config (static, OSPF, RIP).")
@click.option("--services", "-s", is_flag=True, help="Show services config.")
@click.option("--bridges", "-b", is_flag=True, help="Show bridge config.")
@click.option("--vlans", "-v", is_flag=True, help="Show VLAN config.")
@click.option("--tunnels", "-t", is_flag=True, help="Show tunnel config.")
@click.option("--sysctl", "-y", is_flag=True, help="Show sysctl settings.")
@click.option("--all", "-a", "show_all", is_flag=True, help="Show all sections.")
@click.option("--map", "-m", "show_map", is_flag=True, help="Show network connectivity map.")
@click.option("--graph", "-g", "show_graph", is_flag=True, help="Draw topology as a tree diagram.")
@click.pass_obj
def show_topology(
    obj: dict,
    node_name: str | None,
    routing: bool,
    services: bool,
    bridges: bool,
    vlans: bool,
    tunnels: bool,
    sysctl: bool,
    show_all: bool,
    show_map: bool,
    show_graph: bool,
) -> None:
    """Display topology information.

    \b
    Examples:
      netloom --topology lab.yaml show           # node summary
      netloom --topology lab.yaml show --map     # network connectivity table
      netloom --topology lab.yaml show --graph   # tree diagram
      netloom --topology lab.yaml show -n R1 -r  # routing info for R1
    """

    app: Application = obj["app"]
    internal: InternalTopology = obj["internal"]

    if show_map and show_graph:
        raise click.BadParameter("Choose only one of --map or --graph.", param_hint="--map/--graph")

    if (show_map or show_graph) and any([show_all, routing, services, bridges, vlans, tunnels, sysctl]):
        raise click.BadParameter("Topology summary cannot be shown with --map or --graph.", param_hint="--map/--graph")

    if show_map:
        render_map(internal, app.console)
        return

    if show_graph:
        render_graph(internal, app.console)
        return

    nodes = [internal.get_node(node_name)] if node_name else internal.nodes

    app.console.print(f"[bold]Topology:[/bold] {internal.name} [dim]({internal.id})[/dim]")
    if internal.description:
        app.console.print(f"[dim]{internal.description}[/dim]")
    app.console.print()

    table = Table(box=ROUNDED, show_header=True, border_style="dim", expand=False)
    table.add_column("Node", no_wrap=True)
    table.add_column("Interfaces", min_width=28)
    table.add_column("Details", min_width=32)

    for node in nodes:
        role_color = ROLE_COLOR.get(node.role, "white")
        node_cell = f"[{role_color}]{node.name}[/{role_color}]\n[dim]{node.role}[/dim]"

        iface_lines = []
        for iface in node.interfaces:
            peer = f" [dim]→ {iface.peer_node}[/dim]" if iface.peer_node else ""
            ip = f" [green]{iface.ip}[/green]" if iface.ip else ""
            mac = f"\n  [dim]{iface.mac_address}[/dim]" if iface.mac_address else ""
            iface_lines.append(f"{iface.name}{ip}{peer}{mac}")
        iface_cell = "\n".join(iface_lines) if iface_lines else "[dim]—[/dim]"

        detail_parts: list[str] = []

        if (routing or show_all) and node.routing:
            r = node.routing
            if r.engine:
                router_id_part = f" (id: {r.router_id})" if r.router_id else ""
                detail_parts.append(f"[blue]routing[/blue]: {r.engine}{router_id_part}")
            for route in r.static_routes:
                detail_parts.append(f"  static: {route.destination} via {route.gateway}")
            if r.ospf_enabled:
                for area in r.ospf_areas:
                    ifaces_str = ", ".join(area.interfaces) if area.interfaces else "—"
                    detail_parts.append(f"  OSPF area {area.id}: {ifaces_str}")
            if r.rip and r.rip.enabled:
                ifaces_str = ", ".join(r.rip.interfaces) if r.rip.interfaces else "—"
                detail_parts.append(f"  RIP v{r.rip.version}: {ifaces_str}")

        if (vlans or show_all) and node.vlans:
            for vlan in node.vlans:
                ip_str = f" {vlan.ip}" if vlan.ip else ""
                detail_parts.append(f"[magenta]vlan[/magenta] {vlan.name} (id={vlan.id}){ip_str}")

        if (tunnels or show_all) and node.tunnels:
            for tunnel in node.tunnels:
                ip_str = f" {tunnel.ip}" if tunnel.ip else ""
                detail_parts.append(f"[cyan]tunnel[/cyan] {tunnel.name} ({tunnel.type}){ip_str}")

        if (bridges or show_all) and node.bridges:
            for br in node.bridges:
                stp = "[green]STP[/green]" if br.stp else "[dim]no STP[/dim]"
                detail_parts.append(f"[yellow]bridge[/yellow] {br.name} {stp}")

        if (services or show_all) and node.services:
            if node.services.http_server_port:
                detail_parts.append(f"[green]http[/green]: :{node.services.http_server_port}")
            if node.services.wireguard:
                wg = node.services.wireguard
                detail_parts.append(f"[green]wireguard[/green]: {wg.address} :{wg.listen_port}")
            if node.services.firewall:
                fw = node.services.firewall
                detail_parts.append(f"[green]firewall[/green] ({fw.impl}): {len(fw.rules)} rule(s)")

        if (sysctl or show_all) and node.sysctl:
            if node.sysctl.ip_forwarding:
                detail_parts.append("[dim]ip_forwarding: on[/dim]")
            for k, v in node.sysctl.custom.items():
                detail_parts.append(f"[dim]{k}={v}[/dim]")

        detail_cell = "\n".join(detail_parts) if detail_parts else "[dim]—[/dim]"
        table.add_row(node_cell, iface_cell, detail_cell)

    app.console.print(table)

    if not node_name:
        app.console.print()
        app.console.print(
            f"[dim]Nodes: {len(internal.nodes)}  •  "
            f"Networks: {len(internal.networks)}  •  "
            f"Links: {len(internal.links)}[/dim]"
        )
        app.console.print("[dim]Use --map or --graph for a topology diagram.[/dim]")
