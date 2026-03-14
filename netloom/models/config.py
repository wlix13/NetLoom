"""Topology configuration models based on topology-schema.json.

This module implements the ASVK Structured Topology schema.
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..core.enums import (
    FirewallAction,
    FirewallImpl,
    InterfaceKind,
    NodeRole,
    ParavirtProvider,
    RoutingEngine,
    TunnelType,
    VBoxChipset,
)
from ..core.types import NameID


class Meta(BaseModel):
    """Topology metadata."""

    id: str
    name: str
    description: str | None = None


class VBoxConfig(BaseModel):
    """VirtualBox-specific VM settings."""

    paravirt_provider: ParavirtProvider = ParavirtProvider.KVM
    """Paravirtualization provider."""

    chipset: VBoxChipset = VBoxChipset.ICH9
    """Chipset type."""

    ioapic: bool = True
    """Enable I/O APIC."""

    hpet: bool = True
    """Enable High Precision Event Timer."""


class Defaults(BaseModel):
    """Global defaults applied to all nodes."""

    ip_forwarding: bool = Field(False, description="Separate sysctl option for forwarding")
    sysctl: dict[str, Any] | None = Field(
        default=None,
        description="Global kernel parameters (e.g. net.ipv4.ip_forward=1)",
    )
    vbox: VBoxConfig | None = Field(
        default=None,
        description="VirtualBox-specific VM settings.",
    )


class Network(BaseModel):
    """L2 network definition, mapped to a VirtualBox internal network."""

    name: str
    """Unique name of the L2 network."""


class InterfaceConfig(BaseModel):
    """Logical configuration for a named interface (map value in node.interfaces)."""

    network: str | None = Field(
        None,
        description="The L2 network this interface is connected to. Omit for standalone interfaces (e.g. loopback).",
    )
    kind: InterfaceKind = Field(
        default=InterfaceKind.PHYSICAL,
        description=(
            "Interface kind. 'physical' gets a VirtualBox NIC when 'network' is set. "
            "'loopback' is OS-only: no VirtualBox NIC, no MAC, skips .link template."
        ),
    )
    mac: str | None = Field(
        default=None,
        description="Static MAC address (e.g. 02:00:00:00:00:01). Auto-generated if omitted.",
    )
    ip: str | None = Field(
        default=None,
        description="CIDR (e.g. 10.0.12.1/24)",
    )
    gateway: str | None = Field(
        default=None,
        description="Gateway IP address (e.g. 10.0.12.254)",
    )
    dhcp: bool = Field(
        default=False,
        description="Enable DHCP on this interface.",
    )
    mtu: int | None = Field(
        default=None,
        description="MTU for this interface. Uses OS default if omitted.",
    )
    configured: bool = Field(
        default=True,
        description="If false, config file is NOT generated.",
    )

    @model_validator(mode="after")
    def _loopback_must_not_have_network(self) -> "InterfaceConfig":
        if self.kind == InterfaceKind.LOOPBACK and self.network is not None:
            raise ValueError("A 'loopback' interface cannot have 'network' set.")
        return self


class VLANConfig(BaseModel):
    """VLAN (802.1Q) interface configuration."""

    id: Annotated[
        int,
        Field(ge=1, le=4094, description="VLAN ID (1-4094)."),
    ]
    parent: NameID = Field(
        ...,
        description="Parent interface name (e.g., eth1).",
    )
    name: NameID | None = Field(
        default=None,
        description="Custom interface name (e.g. 'vlan5'). Defaults to '{parent}-{id}'.",
    )
    ip: str | None = Field(
        default=None,
        description="IP address in CIDR notation for the VLAN interface.",
    )
    gateway: str | None = Field(
        default=None,
        description="Gateway IP address for the VLAN interface.",
    )


class TunnelConfig(BaseModel):
    """IP tunnel configuration (IPIP, GRE, SIT)."""

    name: NameID = "tun0"
    """Tunnel interface name."""
    type: TunnelType
    """Tunnel type."""
    local: str
    """Local endpoint IP address."""
    remote: str
    """Remote endpoint IP address."""
    ip: str | None = Field(
        default=None,
        description="IP address in CIDR notation for the tunnel interface.",
    )


class BridgeConfig(BaseModel):
    """Bridge configuration for switch nodes."""

    name: NameID = "br0"
    stp: bool = False
    members: list[NameID] | None = Field(
        default=None,
        description=(
            "Interface or VLAN names that are bridge ports. "
            "If omitted, all non-loopback interfaces on the node are used."
        ),
    )
    configured: bool = Field(
        default=True,
        description="If false, config file is NOT generated.",
    )


class StaticRoute(BaseModel):
    """A static route entry."""

    destination: str
    """Destination network in CIDR notation (e.g., 10.0.0.0/8)."""

    gateway: str
    """Next-hop gateway IP address (e.g., 192.168.1.1)."""


class OSPFArea(BaseModel):
    """OSPF area configuration."""

    id: str = "0.0.0.0"  # noqa: S104 [possible-binding-to-all-interfaces]
    interfaces: list[str] | None = Field(
        default=None,
        description="List of interfaces in this area.",
    )
    hello: int = Field(default=10, description="OSPF hello interval in seconds.")
    dead: int = Field(default=40, description="OSPF dead interval in seconds.")
    cost: int = Field(default=10, description="OSPF interface cost.")
    retransmit: int = Field(default=5, description="OSPF retransmit interval in seconds.")


class OSPFConfig(BaseModel):
    """OSPF routing configuration."""

    enabled: bool = False
    areas: list[OSPFArea] | None = Field(
        default=None,
        description="List of OSPF areas.",
    )


class RIPConfig(BaseModel):
    """RIP routing configuration."""

    enabled: bool = False
    version: Literal[1, 2] = 2
    """RIP version (1 or 2)."""
    interfaces: list[str] | None = Field(
        default=None,
        description="List of interfaces participating in RIP.",
    )
    update_time: int = Field(default=30, description="RIP update interval in seconds.")
    timeout_time: int = Field(default=180, description="RIP timeout in seconds.")
    garbage_time: int = Field(default=120, description="RIP garbage collection time in seconds.")


class RoutingConfig(BaseModel):
    """Routing configuration for a node."""

    engine: RoutingEngine | None = None
    router_id: str | None = None
    static: list[StaticRoute] | None = Field(
        default=None,
        description="Static routes.",
    )
    ospf: OSPFConfig | None = None
    rip: RIPConfig | None = None
    configured: bool = Field(
        default=True,
        description="If false, config file is NOT generated.",
    )


class WireguardPeer(BaseModel):
    """WireGuard peer configuration."""

    public_key: str | None = None
    allowed_ips: str | None = None
    endpoint: str | None = None
    keepalive: int = Field(default=25, description="PersistentKeepalive interval in seconds.")


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

    action: FirewallAction
    src: str | None = None
    dst: str | None = None
    proto: str | None = None
    dport: int | None = None


class FirewallConfig(BaseModel):
    """Firewall configuration."""

    impl: FirewallImpl | None = None
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
    role: NodeRole
    sysctl: dict[str, Any] | None = Field(
        default=None,
        description="Node-specific kernel parameters.",
    )
    interfaces: dict[NameID, InterfaceConfig] | None = Field(
        default=None,
        description="Map of interface name to config (e.g. {'eth1': {network: 'lan1', ip: '10.0.0.1/24'}}).",
    )
    vlans: list[VLANConfig] | None = Field(
        default=None,
        description="VLAN (802.1Q) interface configurations.",
    )
    tunnels: list[TunnelConfig] | None = Field(
        default=None,
        description="IP tunnel configurations (IPIP, GRE, SIT).",
    )
    bridges: list[BridgeConfig] | None = Field(
        default=None,
        description="Bridge configurations. Each bridge groups interfaces/VLANs into one L2 domain.",
    )
    routing: RoutingConfig | None = None
    services: ServicesConfig | None = None
    commands: list[str] | None = Field(
        default=None,
        description="Raw shell commands for edge cases.",
    )


class Topology(BaseModel):
    """Root topology configuration model."""

    meta: Meta
    networks: list[Network]
    nodes: list[Node]
    defaults: Defaults | None = None

    def get_node(self, name: str) -> Node | None:
        """Find a node by name."""

        for node in self.nodes:
            if node.name == name:
                return node
        return None
