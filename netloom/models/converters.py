"""Converters from user-facing config models to internal representations."""

from __future__ import annotations

import re
from typing import cast

from ..core.mac import generate_mac
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
    InternalRIP,
    InternalRouting,
    InternalServices,
    InternalStaticRoute,
    InternalSysctl,
    InternalTopology,
    InternalTunnel,
    InternalVBoxSettings,
    InternalVLAN,
    InternalWireguard,
    InternalWireguardPeer,
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
        self._nic_allocations: dict[str, set[int]] = {}
        """Allocator for VirtualBox NIC indices per node."""

    def _allocate_nic_index(self, node_name: str, ifname: str) -> int:
        """Allocate a VirtualBox NIC index for an interface."""

        allocations = self._nic_allocations.setdefault(node_name, set())

        # If name is ethN, try to force specific slot
        if ifname.startswith("eth") and ifname[3:].isdigit():
            # eth0 -> 1, eth1 -> 2
            requested_idx = int(ifname[3:]) + 1
            if requested_idx in allocations:
                raise ValueError(
                    f"NIC index collision on node '{node_name}': Slot {requested_idx} (for {ifname}) is already used."
                )
            allocations.add(requested_idx)
            return requested_idx

        # For custom names, find first available slot
        for i in range(1, 37):
            if i not in allocations:
                allocations.add(i)
                return i

        raise ValueError(f"Node '{node_name}' has too many interfaces (max 36).")

    def _next_interface_name(self, node_name: str) -> str:
        """Get the next available interface name for a node."""

        reserved_names = set()
        node = self.topology.get_node(node_name)
        if node and node.interfaces:
            for iface in node.interfaces:
                if iface.name:
                    reserved_names.add(iface.name)

        idx = self._interface_counters.get(node_name, 1)
        while f"eth{idx}" in reserved_names:
            idx += 1

        self._interface_counters[node_name] = idx + 1
        return f"eth{idx}"

    def _resolve_endpoint(self, endpoint: str) -> tuple[str, str | None]:
        """Parse endpoint string into (node_name, interface_name)."""

        if "." in endpoint:
            node_name, iface_name = endpoint.split(".", 1)
            return node_name, iface_name
        return endpoint, None

    def _get_node_interface_config(
        self,
        node_name: str,
        requested_iface_name: str | None,
        used_indices: set[int],
    ) -> tuple[str, str | None, int | None]:
        """Get interface name and MAC for a specific connection."""

        node = self.topology.get_node(node_name)
        if not node:
            raise ValueError(f"Node '{node_name}' not found.")

        # Case 1: Explicit interface name requested
        if requested_iface_name:
            if not node.interfaces:
                raise ValueError(
                    f"Node '{node_name}' has no interfaces defined, but '{requested_iface_name}' was requested."
                )

            for idx, iface in enumerate(node.interfaces):
                if iface.name == requested_iface_name:
                    if idx in used_indices:
                        raise ValueError(f"Interface '{requested_iface_name}' on '{node_name}' is already connected.")
                    return iface.name, iface.mac, idx

            raise ValueError(f"Interface '{requested_iface_name}' not found in node '{node_name}'.")

        # Case 2: Next available interface (automatic)
        if node.interfaces:
            for idx, iface in enumerate(node.interfaces):
                if idx not in used_indices:
                    # Use this config
                    # If name is custom, use it. If not, generate one.
                    name = iface.name if iface.name else self._next_interface_name(node_name)
                    return name, iface.mac, idx

        # Case 3: No available configs, auto-generate
        return self._next_interface_name(node_name), None, None

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

        # Convert RIP configuration
        rip = None
        if routing.rip and routing.rip.enabled:
            rip = InternalRIP(
                enabled=routing.rip.enabled,
                version=routing.rip.version,
                interfaces=routing.rip.interfaces or [],
            )

        return InternalRouting(
            engine=routing.engine,
            router_id=routing.router_id,
            static_routes=static_routes,
            ospf_enabled=ospf_enabled,
            ospf_areas=ospf_areas,
            rip=rip,
            configured=routing.configured,
        )

    def _convert_vlans(self, node: Node) -> list[InternalVLAN]:
        """Convert VLAN configs to internal format."""

        if not node.vlans:
            return []

        vlans: list[InternalVLAN] = []
        for vlan in node.vlans:
            vlans.append(
                InternalVLAN(
                    id=vlan.id,
                    parent=vlan.parent,
                    name=f"{vlan.parent}.{vlan.id}",
                    ip=vlan.ip,
                    gateway=vlan.gateway,
                )
            )
        return vlans

    def _convert_tunnels(self, node: Node) -> list[InternalTunnel]:
        """Convert tunnel configs to internal format."""

        if not node.tunnels:
            return []

        tunnels: list[InternalTunnel] = []
        for tunnel in node.tunnels:
            tunnels.append(
                InternalTunnel(
                    name=tunnel.name,
                    type=tunnel.type,
                    local=tunnel.local,
                    remote=tunnel.remote,
                    ip=tunnel.ip,
                )
            )
        return tunnels

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
                    private_key=cast(str, wg.private_key),
                    listen_port=wg.listen_port,
                    address=wg.address,
                    peers=peers,
                )

        # Firewall
        firewall = None
        if services.firewall and services.firewall.rules:
            fw = services.firewall
            rules: list[InternalFirewallRule] = []
            for rule in cast(list[InternalFirewallRule], fw.rules):
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

        random_mac = topo.defaults.mac_generation == "random" if topo.defaults else False

        # First pass: assign interfaces based on links
        # Track which interfaces belong to which node
        node_interfaces: dict[str, list[InternalInterface]] = {node.name: [] for node in topo.nodes}
        internal_links: list[InternalLink] = []

        node_used_indices: dict[str, set[int]] = {node.name: set() for node in topo.nodes}
        node_name_to_index: dict[str, dict[str, int]] = {node.name: {} for node in topo.nodes}

        for link in topo.links:
            ep_a, ep_b = link.endpoints

            node_a, req_iface_a = self._resolve_endpoint(ep_a)
            node_b, req_iface_b = self._resolve_endpoint(ep_b)

            iface_a, mac_a, idx_a = self._get_node_interface_config(node_a, req_iface_a, node_used_indices[node_a])
            if idx_a is not None:
                node_used_indices[node_a].add(idx_a)
                node_name_to_index[node_a][iface_a] = idx_a

            iface_b, mac_b, idx_b = self._get_node_interface_config(node_b, req_iface_b, node_used_indices[node_b])
            if idx_b is not None:
                node_used_indices[node_b].add(idx_b)
                node_name_to_index[node_b][iface_b] = idx_b

            if not mac_a:
                mac_a = generate_mac(seed=f"{topo_id}-{node_a}-{iface_a}", random_mac=random_mac)
            if not mac_b:
                mac_b = generate_mac(seed=f"{topo_id}-{node_b}-{iface_b}", random_mac=random_mac)

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
                    mac_address=mac_a,
                    vbox_nic_index=self._allocate_nic_index(node_a, iface_a),
                    peer_node=node_b,
                    vbox_network_name=vbox_net,
                )
            )
            node_interfaces[node_b].append(
                InternalInterface(
                    name=iface_b,
                    mac_address=mac_b,
                    vbox_nic_index=self._allocate_nic_index(node_b, iface_b),
                    peer_node=node_a,
                    vbox_network_name=vbox_net,
                )
            )

        # Second pass: merge interface configs from nodes and add standalone interfaces
        for node in topo.nodes:
            if node.interfaces:
                interfaces = node_interfaces[node.name]
                # Map existing interfaces (from links) by name for easy lookup
                existing_map = {iface.name: iface for iface in interfaces}

                for iface_config in node.interfaces:
                    if not iface_config.name:
                        continue

                    if iface_config.name in existing_map:
                        iface = existing_map[iface_config.name]
                        iface.ip = iface_config.ip
                        iface.gateway = iface_config.gateway
                        iface.configured = iface_config.configured
                    else:
                        # Add standalone interface (e.g. lo)
                        new_iface = InternalInterface(
                            name=iface_config.name,
                            ip=iface_config.ip,
                            gateway=iface_config.gateway,
                            configured=iface_config.configured,
                            mac_address=iface_config.mac,
                            vbox_nic_index=None,
                            vbox_network_name=None,
                        )
                        interfaces.append(new_iface)

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
                vlans=self._convert_vlans(node),
                tunnels=self._convert_tunnels(node),
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
