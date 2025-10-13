"""Topology configuration models based on topology-schema.json (v3.0).

This module implements the ASVK Structured Topology (No-Files/No-Packages) schema.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Topology metadata."""

    id: str
    name: str
    description: str | None = None


class VBoxConfig(BaseModel):
    """VirtualBox-specific VM settings."""

    paravirt_provider: Literal["default", "legacy", "minimal", "hyperv", "kvm", "none"] = "kvm"
    """Paravirtualization provider."""

    chipset: Literal["piix3", "ich9"] = "ich9"
    """Chipset type."""

    ioapic: bool = True
    """Enable I/O APIC."""

    hpet: bool = True
    """Enable High Precision Event Timer."""


class Defaults(BaseModel):
    """Global defaults applied to all nodes."""

    ip_forwarding: bool = False
    sysctl: dict[str, Any] | None = Field(
        default=None,
        description="Global kernel parameters (e.g. net.ipv4.ip_forward=1)",
    )
    vbox: VBoxConfig | None = Field(
        default=None,
        description="VirtualBox-specific VM settings.",
    )


class Link(BaseModel):
    """Physical connection between two nodes."""

    endpoints: Annotated[list[str], Field(min_length=2, max_length=2)]
    """Exactly two node names that this link connects."""


class InterfaceConfig(BaseModel):
    """Logical configuration for a physical interface (eth1, eth2, etc.)."""

    ip: str | None = Field(
        default=None,
        description="CIDR (e.g. 10.0.12.1/24)",
    )
    gateway: str | None = None
    configured: bool = Field(
        default=True,
        description="If false, config file is NOT generated.",
    )


class BridgeConfig(BaseModel):
    """Bridge configuration for switch nodes."""

    name: str = "br0"
    stp: bool = False
    configured: bool = Field(
        default=True,
        description="If false, config file is NOT generated.",
    )


class OSPFArea(BaseModel):
    """OSPF area configuration."""

    id: str = "0.0.0.0"  # noqa: S104 [possible-binding-to-all-interfaces]
    interfaces: list[str] | None = Field(
        default=None,
        description="List of interfaces in this area.",
    )


class OSPFConfig(BaseModel):
    """OSPF routing configuration."""

    enabled: bool = False
    areas: list[OSPFArea] | None = Field(
        default=None,
        description="List of OSPF areas.",
    )


class RoutingConfig(BaseModel):
    """Routing configuration for a node."""

    engine: Literal["bird", "frr", "none"] | None = None
    router_id: str | None = None
    static: list[str] | None = Field(
        default=None,
        description="Static routes (e.g., '10.0.0.0/8 via 192.168.1.1')",
    )
    ospf: OSPFConfig | None = None
    configured: bool = Field(
        default=True,
        description="If false, config file is NOT generated.",
    )


class WireguardPeer(BaseModel):
    """WireGuard peer configuration."""

    public_key: str | None = None
    allowed_ips: str | None = None
    endpoint: str | None = None


class WireguardConfig(BaseModel):
    """WireGuard VPN configuration."""

    private_key: str | None = None
    listen_port: int | None = None
    address: str | None = None
    peers: list[WireguardPeer] | None = Field(
        default=None,
        description="List of WireGuard peers.",
    )


class FirewallRule(BaseModel):
    """Firewall rule definition."""

    action: Literal["accept", "drop", "reject"]
    src: str | None = None
    dst: str | None = None
    proto: str | None = None
    dport: int | None = None


class FirewallConfig(BaseModel):
    """Firewall configuration."""

    impl: Literal["nftables"] | None = None
    rules: list[FirewallRule] | None = Field(
        default=None,
        description="List of firewall rules.",
    )


class ServicesConfig(BaseModel):
    """Services configuration for a node."""

    http_server: int | None = Field(default=None, description="HTTP server port")
    wireguard: WireguardConfig | None = None
    firewall: FirewallConfig | None = None


class Node(BaseModel):
    """A node in the topology (router, switch, or host)."""

    name: str
    role: Literal["router", "switch", "host"] = "host"
    sysctl: dict[str, Any] | None = Field(
        default=None,
        description="Node-specific kernel parameters.",
    )
    interfaces: list[InterfaceConfig] | None = Field(
        default=None,
        description="Logical config for physical interfaces (eth1, eth2...).",
    )
    bridge: BridgeConfig | None = None
    routing: RoutingConfig | None = None
    services: ServicesConfig | None = None
    commands: list[str] | None = Field(
        default=None,
        description="Raw shell commands for edge cases.",
    )


class Topology(BaseModel):
    """Root topology configuration model."""

    meta: Meta
    links: list[Link]
    nodes: list[Node]
    defaults: Defaults | None = None

    def get_node(self, name: str) -> Node | None:
        """Find a node by name."""

        for node in self.nodes:
            if node.name == name:
                return node
        return None

    def get_node_links(self, node_name: str) -> list[Link]:
        """Get all links connected to a specific node."""

        return [link for link in self.links if node_name in link.endpoints]

    def get_peer_node(self, link: Link, node_name: str) -> str | None:
        """Get the peer node name for a given link and node."""

        if node_name not in link.endpoints:
            return None
        return link.endpoints[0] if link.endpoints[1] == node_name else link.endpoints[1]
