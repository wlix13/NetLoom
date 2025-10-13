"""Network controller for interface, bridge, and routing logic."""

import re
from typing import TYPE_CHECKING

from ..core.controller import BaseController
from ..models.internal import (
    InternalBridge,
    InternalInterface,
    InternalLink,
    InternalOSPFArea,
    InternalRouting,
    InternalStaticRoute,
    ifname_to_vbox_adapter_index,
)


if TYPE_CHECKING:
    from ..core.application import Application
    from ..models.config import Node


class NetworkController(BaseController["Application"]):
    """Controller for network-related operations.

    Handles interface assignment, bridge configuration, routing, and VirtualBox network name generation.
    """

    def __init__(self, app: "Application") -> None:
        super().__init__(app)
        self._interface_counters: dict[str, int] = {}

    def reset_counters(self) -> None:
        """Reset interface counters for a new topology conversion."""

        self._interface_counters = {}

    def next_interface_name(self, node_name: str) -> str:
        """Get the next available interface name for a node."""

        idx = self._interface_counters.get(node_name, 0)
        self._interface_counters[node_name] = idx + 1
        return f"eth{idx}"

    def generate_vbox_network_name(self, topo_id: str, node_a: str, node_b: str) -> str:
        """Generate VirtualBox internal network name for a link."""

        sorted_names = sorted([node_a, node_b])
        return f"{topo_id}_{sorted_names[0]}_{sorted_names[1]}"

    def create_interface(
        self,
        name: str,
        peer_node: str,
        vbox_network_name: str,
    ) -> InternalInterface:
        """Create an internal interface representation."""

        return InternalInterface(
            name=name,
            vbox_nic_index=ifname_to_vbox_adapter_index(name),
            peer_node=peer_node,
            vbox_network_name=vbox_network_name,
        )

    def create_link(
        self,
        node_a: str,
        node_b: str,
        interface_a: str,
        interface_b: str,
        vbox_network_name: str,
    ) -> InternalLink:
        """Create an internal link representation."""

        return InternalLink(
            node_a=node_a,
            node_b=node_b,
            interface_a=interface_a,
            interface_b=interface_b,
            vbox_network_name=vbox_network_name,
        )

    def convert_bridge(
        self,
        node: "Node",
        interfaces: list[InternalInterface],
    ) -> InternalBridge | None:
        """Convert bridge config and associate interfaces."""

        if not node.bridge:
            return None

        bridge = node.bridge
        interface_names = [iface.name for iface in interfaces]

        return InternalBridge(
            name=bridge.name,
            stp=bridge.stp,
            interfaces=interface_names,
            configured=bridge.configured,
        )

    def convert_routing(self, node: "Node") -> InternalRouting | None:
        """Convert routing config to internal format."""

        if not node.routing:
            return None

        routing = node.routing

        # parse static routes
        static_routes: list[InternalStaticRoute] = []
        if routing.static:
            for route_str in routing.static:
                parsed = self._parse_static_route(route_str)
                if parsed:
                    static_routes.append(parsed)

        # convert OSPF areas
        ospf_areas: list[InternalOSPFArea] = []
        ospf_enabled = False
        if routing.ospf:
            ospf_enabled = routing.ospf.enabled
            if routing.ospf.areas:
                for area in routing.ospf.areas:
                    ospf_areas.append(
                        InternalOSPFArea(
                            id=area.id,
                            interfaces=area.interfaces or [],
                        )
                    )
        # NOTE: New routing engine support will be added later.

        return InternalRouting(
            engine=routing.engine,
            router_id=routing.router_id,
            static_routes=static_routes,
            ospf_enabled=ospf_enabled,
            ospf_areas=ospf_areas,
            configured=routing.configured,
        )

    def _parse_static_route(self, route_str: str) -> InternalStaticRoute | None:
        """Parse a static route string like '10.0.0.0/8 via 192.168.1.1'."""

        match = re.match(r"^(\S+)\s+via\s+(\S+)$", route_str.strip())
        if match:
            return InternalStaticRoute(destination=match.group(1), gateway=match.group(2))
        return None

    def apply_interface_configs(
        self,
        node: "Node",
        interfaces: list[InternalInterface],
    ) -> None:
        """Apply interface configurations from node config to internal interfaces."""

        if node.interfaces:
            for idx, iface_config in enumerate(node.interfaces):
                if idx < len(interfaces):
                    interfaces[idx].ip = iface_config.ip
                    interfaces[idx].gateway = iface_config.gateway
                    interfaces[idx].configured = iface_config.configured
