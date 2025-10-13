"""Topology controller for loading, validation, and conversion."""

from pathlib import Path
from typing import TYPE_CHECKING

from ..core.controller import BaseController
from ..models.common import load_topology
from ..models.config import Topology
from ..models.internal import (
    InternalFirewall,
    InternalFirewallRule,
    InternalNode,
    InternalServices,
    InternalSysctl,
    InternalTopology,
    InternalWireguard,
    InternalWireguardPeer,
)


if TYPE_CHECKING:
    from ..core.application import Application  # noqa: F401
    from ..models.config import Node


class TopologyController(BaseController["Application"]):
    """Controller for topology loading and conversion.

    Handles loading YAML topology files, validation, and conversion
    to internal representation.
    """

    def load(self, path: str | Path) -> Topology:
        """Load a topology from a YAML file."""

        return load_topology(path)

    def convert(self, topology: Topology, workdir: str | Path | None = None) -> InternalTopology:
        """Convert a topology config to internal representation."""

        topo_id = topology.meta.id
        network = self.app.network

        network.reset_counters()

        # first pass: assign interfaces based on links
        node_interfaces: dict[str, list] = {node.name: [] for node in topology.nodes}
        internal_links = []

        for link in topology.links:
            node_a, node_b = link.endpoints

            iface_a = network.next_interface_name(node_a)
            iface_b = network.next_interface_name(node_b)

            vbox_net = network.generate_vbox_network_name(topo_id, node_a, node_b)

            internal_links.append(network.create_link(node_a, node_b, iface_a, iface_b, vbox_net))

            node_interfaces[node_a].append(network.create_interface(iface_a, node_b, vbox_net))
            node_interfaces[node_b].append(network.create_interface(iface_b, node_a, vbox_net))

        # second pass: merge interface configs from nodes
        for node in topology.nodes:
            interfaces = node_interfaces[node.name]
            network.apply_interface_configs(node, interfaces)

        # third pass: build internal nodes
        internal_nodes = []
        for node in topology.nodes:
            interfaces = node_interfaces.get(node.name, [])

            # Set config directories if workdir is provided
            config_dir = None
            saved_configs_dir = None
            if workdir:
                config_dir = f"{workdir}/configs/{node.name}"
                saved_configs_dir = f"{workdir}/saved/{node.name}"

            internal_node = InternalNode(
                name=node.name,
                role=node.role,
                interfaces=interfaces,
                bridge=network.convert_bridge(node, interfaces),
                sysctl=self._convert_sysctl(node, topology),
                routing=network.convert_routing(node),
                services=self._convert_services(node),
                commands=node.commands or [],
                config_dir=config_dir,
                saved_configs_dir=saved_configs_dir,
            )
            internal_nodes.append(internal_node)

        return InternalTopology(
            id=topo_id,
            name=topology.meta.name,
            description=topology.meta.description,
            nodes=internal_nodes,
            links=internal_links,
        )

    def _convert_sysctl(self, node: "Node", topology: Topology) -> InternalSysctl:
        """Build sysctl config from defaults and node-specific settings."""

        defaults = topology.defaults

        ip_forwarding = defaults.ip_forwarding if defaults else False
        custom: dict[str, object] = {}

        # global sysctl
        if defaults and defaults.sysctl:
            custom.update(defaults.sysctl)

        # node-specific sysctl (overrides globals)
        if node.sysctl:
            custom.update(node.sysctl)

        # don't allow users to break router
        # ? or do we allow it
        if node.role == "router":
            ip_forwarding = True

        return InternalSysctl(ip_forwarding=ip_forwarding, custom=custom)

    def _convert_services(self, node: "Node") -> InternalServices | None:
        """Convert services config to internal format."""

        if not node.services:
            return None

        services = node.services

        # wireguard
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

        # firewall
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
