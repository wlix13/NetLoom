"""Rich display helpers for topology visualization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.box import ROUNDED
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from netloom.core.enums import NodeRole
from netloom.models.internal import InternalTopology


if TYPE_CHECKING:
    from rich.console import Console

ROLE_COLOR: dict[str, str] = {
    NodeRole.ROUTER: "cyan",
    NodeRole.SWITCH: "yellow",
    NodeRole.HOST: "green",
}


def node_label(name: str, role: str, *, with_role: bool = True) -> str:
    color = ROLE_COLOR.get(role, "white")
    role_part = f" [dim]({role})[/dim]" if with_role else ""
    return f"[{color}]{name}[/{color}]{role_part}"


def render_map(internal: InternalTopology, console: Console) -> None:
    """Render a network-centric connectivity table."""

    table = Table(box=ROUNDED, show_header=True, border_style="dim", expand=False)
    table.add_column("Network", style="cyan bold", no_wrap=True, min_width=12)
    table.add_column("Participants", min_width=44)

    for network in internal.networks:
        entries = []
        for node_name, iface_name in network.participants:
            try:
                node = internal.get_node(node_name)
                iface = next((i for i in node.interfaces if i.name == iface_name), None)
                color = ROLE_COLOR.get(node.role, "white")
                ip_part = f" [dim]{iface.ip}[/dim]" if iface and iface.ip else ""
                entries.append(f"[{color}]{node_name}[/{color}]/{iface_name}{ip_part}")
            except Exception:  # noqa: BLE001
                entries.append(f"{node_name}/{iface_name}")

        if len(entries) == 2:  # noqa: PLR2004
            conn = f"{entries[0]}  ───  {entries[1]}"
        else:
            conn = "\n".join(entries)

        table.add_row(network.name, conn)

    console.print(
        Panel(
            table,
            title=f"[bold]{internal.name}[/bold] [dim]({internal.id})[/dim]",
            border_style="dim",
        )
    )


def render_graph(internal: InternalTopology, console: Console) -> None:
    """Render a BFS tree diagram of the topology using Rich Tree."""

    adjacency: dict[str, list[tuple[str, str]]] = {n.name: [] for n in internal.nodes}
    for link in internal.links:
        adjacency[link.node_a].append((link.node_b, link.network))
        adjacency[link.node_b].append((link.node_a, link.network))
    for network in internal.networks:
        if len(network.participants) > 2:  # noqa: PLR2004
            for node_a, _ in network.participants:
                for node_b, _ in network.participants:
                    if node_b != node_a:
                        adjacency[node_a].append((node_b, network.name))

    visited: set[str] = set()
    sorted_nodes = sorted(internal.nodes, key=lambda n: -len(adjacency[n.name]))

    for start in sorted_nodes:
        if start.name in visited:
            continue

        root_tree = Tree(node_label(start.name, start.role))
        visited.add(start.name)

        queue: list[tuple[str, Tree]] = [(start.name, root_tree)]
        while queue:
            cur_name, parent_branch = queue.pop(0)
            seen_neighbors: set[str] = set()
            for neighbor, net_name in adjacency[cur_name]:
                if neighbor in visited or neighbor in seen_neighbors:
                    continue
                seen_neighbors.add(neighbor)
                visited.add(neighbor)
                node = internal.get_node(neighbor)
                branch = parent_branch.add(f"{node_label(neighbor, node.role)}  [dim]via {net_name}[/dim]")
                queue.append((neighbor, branch))

        console.print(root_tree)
