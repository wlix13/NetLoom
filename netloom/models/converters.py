"""Converters from user-facing config models to internal representations."""

from __future__ import annotations

from pathlib import Path

from ..core.enums import FirewallImpl, InterfaceKind, NodeRole
from ..core.errors import TopologyError
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
    InternalNetwork,
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


class TopologyConverter:
    """Converts a Topology config to InternalTopology."""

    def __init__(self, topology: Topology, workdir: str | None = None):
        self.topology = topology
        self.workdir = workdir
        self._nic_allocations: dict[str, set[int]] = {}

    def _allocate_nic_index(self, node_name: str, ifname: str) -> int:
        """Allocate a VirtualBox NIC index for an interface."""

        allocations = self._nic_allocations.setdefault(node_name, set())

        # If name is ethN, try to force specific slot
        if ifname.startswith("eth") and ifname[3:].isdigit():
            # eth0 -> 1, eth1 -> 2
            requested_idx = int(ifname[3:]) + 1
            if requested_idx in allocations:
                raise TopologyError(
                    f"NIC index collision on node '{node_name}': Slot {requested_idx} (for {ifname}) is already used."
                )
            allocations.add(requested_idx)
            return requested_idx

        # Prevent fallback allocations from stealing explicitly declared ethN slots
        reserved_slots = set()
        for node in self.topology.nodes:
            if node.name == node_name and node.interfaces:
                for name in node.interfaces:
                    if name.startswith("eth") and name[3:].isdigit():
                        reserved_slots.add(int(name[3:]) + 1)
                break

        # For custom names, find first available slot
        for i in range(1, 37):
            if i not in allocations and i not in reserved_slots:
                allocations.add(i)
                return i

        raise TopologyError(f"Node '{node_name}' has too many interfaces (max 36).")

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
        if node.role == NodeRole.ROUTER:
            ip_forwarding = True

        return InternalSysctl(ip_forwarding=ip_forwarding, custom=custom)

    def _convert_routing(self, node: Node) -> InternalRouting | None:
        """Convert routing config to internal format."""

        if not node.routing:
            return None

        routing = node.routing

        # Convert static routes
        static_routes: list[InternalStaticRoute] = []
        if routing.static:
            for route in routing.static:
                static_routes.append(InternalStaticRoute(destination=route.destination, gateway=route.gateway))

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
                            hello=area.hello,
                            dead=area.dead,
                            cost=area.cost,
                            retransmit=area.retransmit,
                        )
                    )

        # Convert RIP configuration
        rip = None
        if routing.rip and routing.rip.enabled:
            rip = InternalRIP(
                enabled=routing.rip.enabled,
                version=routing.rip.version,
                interfaces=routing.rip.interfaces or [],
                update_time=routing.rip.update_time,
                timeout_time=routing.rip.timeout_time,
                garbage_time=routing.rip.garbage_time,
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
                    name=vlan.name or f"{vlan.parent}-{vlan.id}",
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
                                keepalive=peer.keepalive,
                            )
                        )
            if wg.listen_port and wg.address:
                wireguard = InternalWireguard(
                    private_key=wg.private_key,  # ty:ignore[invalid-argument-type]
                    listen_port=wg.listen_port,
                    address=wg.address,
                    peers=peers,
                )

        # Firewall
        firewall = None
        if services.firewall and services.firewall.rules:
            fw = services.firewall
            rules: list[InternalFirewallRule] = []
            for rule in fw.rules:  # ty:ignore[not-iterable]
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
                impl=fw.impl or FirewallImpl.NFTABLES,
                rules=rules,
            )

        return InternalServices(
            http_server_port=services.http_server,
            wireguard=wireguard,
            firewall=firewall,
        )

    def _convert_bridges(
        self,
        node: Node,
        interfaces: list[InternalInterface],
        vlans: list[InternalVLAN],
    ) -> list[InternalBridge]:
        """Convert bridge configs and assign bridge_name to member interfaces/VLANs."""

        if not node.bridges:
            return []

        iface_map = {iface.name: iface for iface in interfaces}
        vlan_map = {vlan.name: vlan for vlan in vlans}
        result: list[InternalBridge] = []

        for bridge_cfg in node.bridges:
            if bridge_cfg.members is not None:
                member_names = bridge_cfg.members
            else:
                member_names = [iface.name for iface in interfaces if iface.kind != InterfaceKind.LOOPBACK]

            for name in member_names:
                if name in iface_map:
                    iface_map[name].bridge_name = bridge_cfg.name
                elif name in vlan_map:
                    vlan_map[name].bridge_name = bridge_cfg.name
                else:
                    raise TopologyError(
                        f"Bridge '{bridge_cfg.name}' on node '{node.name}' references unknown member '{name}'."
                    )

            result.append(
                InternalBridge(
                    name=bridge_cfg.name,
                    stp=bridge_cfg.stp,
                    interfaces=member_names,
                    configured=bridge_cfg.configured,
                )
            )

        return result

    def convert(self) -> InternalTopology:
        """Convert the topology to internal representation."""

        topo = self.topology
        topo_id = topo.meta.id

        # Build network_name -> [(node_name, iface_name)] mapping
        network_participants: dict[str, list[tuple[str, str]]] = {net.name: [] for net in topo.networks}

        for node in topo.nodes:
            if not node.interfaces:
                continue
            for iface_name, iface_config in node.interfaces.items():
                net_name = iface_config.network
                if net_name is None:
                    continue  # standalone interfaces (e.g. loopback) handled separately
                if net_name not in network_participants:
                    raise TopologyError(
                        f"Interface '{iface_name}' on node '{node.name}' references unknown network '{net_name}'."
                    )
                network_participants[net_name].append((node.name, iface_name))

        # Build per-node interface lists, internal links, and internal networks
        node_interfaces: dict[str, list[InternalInterface]] = {node.name: [] for node in topo.nodes}
        internal_links: list[InternalLink] = []
        internal_networks: list[InternalNetwork] = []

        for net_name, participants in network_participants.items():
            vbox_net = f"{topo_id}_{net_name}"
            internal_networks.append(
                InternalNetwork(
                    name=net_name,
                    network=vbox_net,
                    participants=participants,
                )
            )

            for node_name, iface_name in participants:
                participant_node = topo.get_node(node_name)
                if participant_node is None or participant_node.interfaces is None:
                    continue
                iface_config = participant_node.interfaces[iface_name]

                mac = iface_config.mac or generate_mac(seed=f"{topo_id}-{node_name}-{iface_name}")
                vbox_nic_index = self._allocate_nic_index(node_name, iface_name)

                peer_node: str | None = None
                if len(participants) == 2:
                    other = next(((pn, pi) for pn, pi in participants if (pn, pi) != (node_name, iface_name)), None)
                    peer_node = other[0] if other else None

                node_interfaces[node_name].append(
                    InternalInterface(
                        name=iface_name,
                        kind=iface_config.kind,
                        mac_address=mac,
                        ip=iface_config.ip,
                        gateway=iface_config.gateway,
                        dhcp=iface_config.dhcp,
                        mtu=iface_config.mtu,
                        vbox_nic_index=vbox_nic_index,
                        network=vbox_net,
                        peer_node=peer_node,
                        configured=iface_config.configured,
                    )
                )

            if len(participants) == 2:
                (node_a, iface_a), (node_b, iface_b) = participants
                internal_links.append(
                    InternalLink(
                        node_a=node_a,
                        node_b=node_b,
                        interface_a=iface_a,
                        interface_b=iface_b,
                        network=vbox_net,
                    )
                )

        # Add standalone interfaces (no network, e.g. loopback)
        for node in topo.nodes:
            if not node.interfaces:
                continue
            for iface_name, iface_config in node.interfaces.items():
                if iface_config.network is not None:
                    continue
                node_interfaces[node.name].append(
                    InternalInterface(
                        name=iface_name,
                        kind=iface_config.kind,
                        ip=iface_config.ip,
                        gateway=iface_config.gateway,
                        dhcp=iface_config.dhcp,
                        mtu=iface_config.mtu,
                        configured=iface_config.configured,
                    )
                )

        # Build internal nodes
        internal_nodes: list[InternalNode] = []
        for node in topo.nodes:
            interfaces = node_interfaces.get(node.name, [])
            vlans = self._convert_vlans(node)

            config_dir = None
            saved_configs_dir = None
            if self.workdir:
                config_dir = f"{self.workdir}/configs/{node.name}"
                saved_configs_dir = f"{self.workdir}/saved/{node.name}"

            internal_nodes.append(
                InternalNode(
                    name=node.name,
                    role=node.role,
                    interfaces=interfaces,
                    vlans=vlans,
                    tunnels=self._convert_tunnels(node),
                    bridges=self._convert_bridges(node, interfaces, vlans),
                    sysctl=self._convert_sysctl(node),
                    routing=self._convert_routing(node),
                    services=self._convert_services(node),
                    commands=node.commands or [],
                    config_dir=config_dir,
                    saved_configs_dir=saved_configs_dir,
                )
            )

        return InternalTopology(
            id=topo_id,
            name=topo.meta.name,
            description=topo.meta.description,
            vbox=self._convert_vbox_settings(),
            nodes=internal_nodes,
            networks=internal_networks,
            links=internal_links,
        )


def convert_topology(topology: Topology, workdir: str | None = None) -> InternalTopology:
    """Convert a Topology config to InternalTopology."""

    converter = TopologyConverter(topology, workdir=workdir)
    return converter.convert()
