"""Converters from user-facing config models to internal representations."""

from __future__ import annotations

import re

from .config import (
    Node,
    Topology,
)
from .internal import (
    InternalBridge,
    InternalFirewall,
    InternalFirewallRule,
    InternalInterface,
    InternalLink,
    InternalNode,
    InternalOSPFArea,
    InternalRouting,
    InternalServices,
    InternalStaticRoute,
    InternalSysctl,
    InternalTopology,
    InternalVBoxSettings,
    InternalWireguard,
    InternalWireguardPeer,
    ifname_to_vbox_adapter_index,
)


def _parse_static_route(route_str: str) -> InternalStaticRoute | None:
    """Parse a static route string like '10.0.0.0/8 via 192.168.1.1'."""

    # Pattern: destination via gateway
    match = re.match(r"^(\S+)\s+via\s+(\S+)$", route_str.strip())
    if match:
        return InternalStaticRoute(destination=match.group(1), gateway=match.group(2))
    return None


def _generate_vbox_network_name(topo_id: str, node_a: str, node_b: str) -> str:
    """Generate VirtualBox internal network name for a link."""

    sorted_names = sorted([node_a, node_b])
    return f"{topo_id}_{sorted_names[0]}_{sorted_names[1]}"


class TopologyConverter:
    """Converts a Topology config to InternalTopology."""

    def __init__(self, topology: Topology, workdir: str | None = None):
        self.topology = topology
        self.workdir = workdir
        self._interface_counters: dict[str, int] = {}
        """Allocator for interface index per node (starts at 1 for eth1)."""

    def _next_interface_name(self, node_name: str) -> str:
        """Get the next available interface name for a node."""

        idx = self._interface_counters.get(node_name, 1)
        self._interface_counters[node_name] = idx + 1
        return f"eth{idx}"

    def _convert_vbox_settings(self) -> InternalVBoxSettings:
        """Convert VBox settings from defaults."""

        defaults = self.topology.defaults
        if defaults and defaults.vbox:
            vbox = defaults.vbox
            return InternalVBoxSettings(
                paravirt_provider=vbox.paravirt_provider,
                chipset=vbox.chipset,
                ioapic=vbox.ioapic,
                hpet=vbox.hpet,
            )
        return InternalVBoxSettings()

    def _convert_sysctl(self, node: Node) -> InternalSysctl:
        """Build sysctl config from defaults and node-specific settings."""

        defaults = self.topology.defaults

        ip_forwarding = defaults.ip_forwarding if defaults else False
        custom: dict[str, object] = {}

        # Global sysctl
        if defaults and defaults.sysctl:
            custom.update(defaults.sysctl)

        # Node-specific sysctl (overrides globals)
        if node.sysctl:
            custom.update(node.sysctl)

        # Don't make users broke router by default :)
        if node.role == "router":
            ip_forwarding = True

        return InternalSysctl(ip_forwarding=ip_forwarding, custom=custom)

    def _convert_routing(self, node: Node) -> InternalRouting | None:
        """Convert routing config to internal format."""

        if not node.routing:
            return None

        routing = node.routing

        # Parse static routes
        static_routes: list[InternalStaticRoute] = []
        if routing.static:
            for route_str in routing.static:
                parsed = _parse_static_route(route_str)
                if parsed:
                    static_routes.append(parsed)

        # Convert OSPF areas
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

    def _convert_services(self, node: Node) -> InternalServices | None:
        """Convert services config to internal format."""

        if not node.services:
            return None

        services = node.services

        # WireGuard
        wireguard = None
        if services.wireguard and services.wireguard.private_key:
            wg = services.wireguard
            peers: list[InternalWireguardPeer] = []
            if wg.peers:
                for peer in wg.peers:
                    if peer.public_key and peer.allowed_ips:
                        peers.append(
                            InternalWireguardPeer(
                                public_key=peer.public_key,
                                allowed_ips=peer.allowed_ips,
                                endpoint=peer.endpoint,
                            )
                        )
            if wg.listen_port and wg.address:
                wireguard = InternalWireguard(
                    private_key=wg.private_key,
                    listen_port=wg.listen_port,
                    address=wg.address,
                    peers=peers,
                )

        # Firewall
        firewall = None
        if services.firewall and services.firewall.rules:
            fw = services.firewall
            rules: list[InternalFirewallRule] = []
            for rule in fw.rules:
                rules.append(
                    InternalFirewallRule(
                        action=rule.action,
                        src=rule.src,
                        dst=rule.dst,
                        proto=rule.proto,
                        dport=rule.dport,
                    )
                )
            firewall = InternalFirewall(
                impl=fw.impl or "nftables",
                rules=rules,
            )

        return InternalServices(
            http_server_port=services.http_server,
            wireguard=wireguard,
            firewall=firewall,
        )

    def _convert_bridge(self, node: Node, interfaces: list[InternalInterface]) -> InternalBridge | None:
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

    def convert(self) -> InternalTopology:
        """Convert the topology to internal representation."""

        topo = self.topology
        topo_id = topo.meta.id

        # First pass: assign interfaces based on links
        # Track which interfaces belong to which node
        node_interfaces: dict[str, list[InternalInterface]] = {node.name: [] for node in topo.nodes}
        internal_links: list[InternalLink] = []

        for link in topo.links:
            node_a, node_b = link.endpoints

            iface_a = self._next_interface_name(node_a)
            iface_b = self._next_interface_name(node_b)

            vbox_net = _generate_vbox_network_name(topo_id, node_a, node_b)

            internal_links.append(
                InternalLink(
                    node_a=node_a,
                    node_b=node_b,
                    interface_a=iface_a,
                    interface_b=iface_b,
                    vbox_network_name=vbox_net,
                )
            )

            node_interfaces[node_a].append(
                InternalInterface(
                    name=iface_a,
                    vbox_nic_index=ifname_to_vbox_adapter_index(iface_a),
                    peer_node=node_b,
                    vbox_network_name=vbox_net,
                )
            )
            node_interfaces[node_b].append(
                InternalInterface(
                    name=iface_b,
                    vbox_nic_index=ifname_to_vbox_adapter_index(iface_b),
                    peer_node=node_a,
                    vbox_network_name=vbox_net,
                )
            )

        # Second pass: merge interface configs from nodes
        for node in topo.nodes:
            if node.interfaces:
                interfaces = node_interfaces[node.name]
                for idx, iface_config in enumerate(node.interfaces):
                    if idx < len(interfaces):
                        # Update the interface with config values
                        interfaces[idx].ip = iface_config.ip
                        interfaces[idx].gateway = iface_config.gateway
                        interfaces[idx].configured = iface_config.configured

        # Third pass: build internal nodes
        internal_nodes: list[InternalNode] = []
        for node in topo.nodes:
            interfaces = node_interfaces.get(node.name, [])

            # Set config directories if workdir is provided
            config_dir = None
            saved_configs_dir = None
            if self.workdir:
                config_dir = f"{self.workdir}/configs/{node.name}"
                saved_configs_dir = f"{self.workdir}/saved/{node.name}"

            internal_node = InternalNode(
                name=node.name,
                role=node.role,
                interfaces=interfaces,
                bridge=self._convert_bridge(node, interfaces),
                sysctl=self._convert_sysctl(node),
                routing=self._convert_routing(node),
                services=self._convert_services(node),
                commands=node.commands or [],
                config_dir=config_dir,
                saved_configs_dir=saved_configs_dir,
            )
            internal_nodes.append(internal_node)

        return InternalTopology(
            id=topo_id,
            name=topo.meta.name,
            description=topo.meta.description,
            vbox=self._convert_vbox_settings(),
            nodes=internal_nodes,
            links=internal_links,
        )


def convert_topology(topology: Topology, workdir: str | None = None) -> InternalTopology:
    """Convert a Topology config to InternalTopology."""

    converter = TopologyConverter(topology, workdir=workdir)
    return converter.convert()
