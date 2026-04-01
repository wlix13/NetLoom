"""Internal representations for provider-specific topology data."""

from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

from ..core.enums import (
    FirewallAction,
    FirewallImpl,
    InterfaceKind,
    NicModel,
    NodeRole,
    ParavirtProvider,
    RoutingEngine,
    TunnelType,
    VBoxChipset,
)
from ..core.errors import TopologyError
from ..core.types import NameID


class InternalVBoxSettings(BaseModel):
    """VirtualBox-specific VM settings."""

    paravirt_provider: ParavirtProvider = ParavirtProvider.KVM
    """Paravirtualization provider."""

    chipset: VBoxChipset = VBoxChipset.ICH9
    """Chipset type."""

    ioapic: bool = True
    """Enable I/O APIC."""

    hpet: bool = True
    """Enable High Precision Event Timer."""


def ifname_to_vbox_adapter_index(ifname: str) -> int:
    """Convert interface name to VirtualBox adapter index."""

    if not ifname.startswith("eth"):
        raise ValueError(f"Only ethN are mappable to VirtualBox NICs: {ifname!r}")
    idx = int(ifname[3:])
    return idx + 1  # VBox NICs start at 1


class InternalResources(BaseModel):
    """VM resource allocation."""

    cpu: int = 1
    """CPU count."""

    ram_mb: int = 512
    """RAM in MB."""

    disk_gb: int = 8
    """Disk in GB."""


class InternalInterface(BaseModel):
    """Internal interface representation."""

    name: NameID
    """Interface name (eth1, eth2...)."""

    kind: InterfaceKind = InterfaceKind.PHYSICAL
    """Interface kind. Loopback interfaces have no VirtualBox NIC and no MAC."""

    mac_address: str | None = None
    """MAC address."""

    ip: str | None = None
    """IP address."""

    gateway: str | None = None
    """Gateway IP."""

    vbox_nic_index: int | None = None
    """VirtualBox NIC index."""

    network: str | None = None
    """VirtualBox internal network name (acts as L2 switch)."""

    nat: bool = False
    """Whether this interface uses VirtualBox NAT mode."""

    dhcp: bool = False
    """Enable DHCP on this interface."""

    mtu: int | None = None
    """MTU override (None = OS default)."""

    peer_node: str | None = None
    """Connected peer node name."""

    bridge_name: str | None = None
    """Name of the bridge this interface is a port of, if any."""

    configured: bool = True
    """Whether to generate config."""

    def model_post_init(self, __context: Any) -> None:
        if self.kind != InterfaceKind.PHYSICAL:
            invalid = [
                name
                for name, value in {
                    "vbox_nic_index": self.vbox_nic_index,
                    "network": self.network,
                    "mac_address": self.mac_address,
                }.items()
                if value is not None
            ]
            if self.nat:
                invalid.append("nat")
            if invalid:
                raise ValueError(f"{self.kind.value} interfaces cannot set {', '.join(invalid)}")


class InternalBridge(BaseModel):
    """Internal representation of a bridge configuration."""

    name: NameID = "br0"
    """Bridge name."""

    stp: bool = False
    """STP enabled."""

    interfaces: list[str] = Field(default_factory=list)
    """Interface names that are part of this bridge."""

    configured: bool = True
    """Whether to generate config for this bridge."""


class InternalStaticRoute(BaseModel):
    """Internal representation of a static route."""

    destination: str
    """Destination network in CIDR notation."""

    gateway: str
    """Next-hop gateway IP."""


class InternalVLAN(BaseModel):
    """Internal representation of a VLAN interface."""

    id: int = Field(..., ge=1, le=4094)
    """VLAN ID (1-4094)."""

    parent: NameID
    """Parent interface name (e.g., eth1)."""

    name: NameID
    """VLAN interface name (e.g., eth1-100)."""

    ip: str | None = None
    """IP address in CIDR notation."""

    gateway: str | None = None
    """Gateway IP address."""

    bridge_name: str | None = None
    """Name of the bridge this VLAN interface is a port of, if any."""


class InternalTunnel(BaseModel):
    """Internal representation of an IP tunnel."""

    name: NameID
    """Tunnel interface name."""

    type: TunnelType
    """Tunnel type."""

    local: str
    """Local endpoint IP address."""

    remote: str
    """Remote endpoint IP address."""

    ip: str | None = None
    """IP address in CIDR notation for the tunnel interface."""


class InternalOSPFArea(BaseModel):
    """Internal OSPF area configuration."""

    id: str = "0.0.0.0"  # noqa: S104 [possible-binding-to-all-interfaces]
    """OSPF area ID."""

    interfaces: list[str] = Field(default_factory=list)
    """Interfaces in this area."""

    hello: int = 10
    """Hello interval in seconds."""

    dead: int = 40
    """Dead interval in seconds."""

    cost: int = 10
    """Interface cost."""

    retransmit: int = 5
    """Retransmit interval in seconds."""


class InternalRIP(BaseModel):
    """Internal RIP routing configuration."""

    enabled: bool = False
    """RIP enabled."""

    version: Literal[1, 2] = 2
    """RIP version."""

    interfaces: list[str] = Field(default_factory=list)
    """Interfaces participating in RIP."""

    update_time: int = 30
    """Update interval in seconds."""

    timeout_time: int = 180
    """Timeout in seconds."""

    garbage_time: int = 120
    """Garbage collection time in seconds."""


class InternalRouting(BaseModel):
    """Internal routing configuration."""

    engine: RoutingEngine | None = None
    """Routing engine."""

    router_id: str | None = None
    """Router ID."""

    static_routes: list[InternalStaticRoute] = Field(default_factory=list)
    """Static routes."""

    ospf_enabled: bool = False
    """OSPF enabled."""

    ospf_areas: list[InternalOSPFArea] = Field(default_factory=list)
    """OSPF areas."""

    rip: InternalRIP | None = None
    """RIP configuration."""

    configured: bool = True
    """Whether to generate config for this routing."""


class InternalWireguardPeer(BaseModel):
    """Internal WireGuard peer."""

    public_key: str
    """Public key."""

    allowed_ips: str
    """Allowed IPs."""

    endpoint: str | None = None
    """Endpoint."""

    keepalive: int = 25
    """PersistentKeepalive interval in seconds."""


class InternalWireguard(BaseModel):
    """Internal WireGuard configuration."""

    private_key: str
    """Private key."""

    listen_port: int
    """Listen port."""

    address: str
    """Address."""

    peers: list[InternalWireguardPeer] = Field(default_factory=list)
    """Peers."""


class InternalFirewallRule(BaseModel):
    """Internal firewall rule."""

    action: FirewallAction
    """Action."""

    src: str | None = None
    """Source."""

    dst: str | None = None
    """Destination."""

    proto: str | None = None
    """Protocol."""

    dport: int | None = None
    """Destination port."""


class InternalFirewall(BaseModel):
    """Internal firewall configuration."""

    impl: FirewallImpl
    """Engine implementation."""

    rules: list[InternalFirewallRule] = Field(default_factory=list)
    """List of firewall rules."""


class InternalServices(BaseModel):
    """Internal services configuration."""

    http_server_port: int | None = None
    """HTTP server port."""

    wireguard: InternalWireguard | None = None
    """WireGuard configuration."""

    firewall: InternalFirewall | None = None
    """Firewall configuration."""


class InternalSysctl(BaseModel):
    """Internal sysctl configuration."""

    ip_forwarding: bool = False
    """IP forwarding."""

    custom: dict[str, Any] = Field(default_factory=dict)
    """Custom sysctl settings."""


class InternalNode(BaseModel):
    """Internal representation of a topology node."""

    name: str
    """Node name."""

    role: NodeRole
    """Node role."""

    resources: InternalResources = Field(default_factory=InternalResources)
    """Resources."""

    image: str | None = None
    """Image."""

    nic_model: NicModel = NicModel.VIRTIO
    """NIC implementation."""

    vbox: InternalVBoxSettings | None = None
    """VirtualBox-specific settings (overrides topology defaults)."""

    interfaces: list[InternalInterface] = Field(default_factory=list)
    """Network interfaces."""

    vlans: list[InternalVLAN] = Field(default_factory=list)
    """VLAN interfaces."""

    tunnels: list[InternalTunnel] = Field(default_factory=list)
    """IP tunnels."""

    bridges: list[InternalBridge] = Field(default_factory=list)
    """Bridge configurations."""

    sysctl: InternalSysctl = Field(default_factory=InternalSysctl)
    """Kernel parameters."""

    routing: InternalRouting | None = None
    """Routing configuration."""

    services: InternalServices | None = None
    """Services configuration."""

    commands: list[str] = Field(default_factory=list)
    """Raw commands."""

    config_dir: str | None = None
    """Directory for generated configs."""

    saved_configs_dir: str | None = None
    """Directory for saved configs pulled from config-drive."""


class InternalNetwork(BaseModel):
    """Internal representation of a shared L2 network (VirtualBox internal network)."""

    name: str
    """User-defined network name."""

    network: str
    """VirtualBox internal network name (acts as L2 switch)."""

    participants: list[tuple[str, str]] = Field(default_factory=list)
    """List of (node_name, interface_name) pairs connected to this network."""


class InternalLink(BaseModel):
    """Internal representation of a link between two nodes."""

    node_a: str
    """First node name."""
    node_b: str
    """Second node name."""

    interface_a: str
    """Interface name on node_a (e.g., eth1)."""

    interface_b: str
    """Interface name on node_b (e.g., eth1)."""

    network: str
    """VirtualBox internal network name for this link (acts as L2 switch)."""


class InternalTopology(BaseModel):
    """Internal representation of the complete topology."""

    id: str
    """Topology ID."""

    name: str
    """Topology name."""

    description: str | None = None
    """Topology description."""

    vbox: InternalVBoxSettings = Field(default_factory=InternalVBoxSettings)
    """Default VirtualBox settings for all nodes."""

    nodes: list[InternalNode] = Field(default_factory=list)
    """List of nodes."""

    networks: list[InternalNetwork] = Field(default_factory=list)
    """List of L2 networks (including multi-access)."""

    links: list[InternalLink] = Field(default_factory=list)
    """List of point-to-point links (networks with exactly 2 participants)."""

    # Internal indexes for fast lookup
    _node_index: dict[str, InternalNode] = PrivateAttr(default_factory=dict)
    _link_index: dict[str, list[InternalLink]] = PrivateAttr(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Build indexes after initialization."""

        self.index()

    def index(self) -> None:
        """Build lookup indexes."""

        self._node_index = {n.name: n for n in self.nodes}
        self._link_index = {}
        for link in self.links:
            self._link_index.setdefault(link.node_a, []).append(link)
            self._link_index.setdefault(link.node_b, []).append(link)

    def get_node(self, name: str) -> InternalNode:
        """Get a node by name."""

        try:
            return self._node_index[name]
        except KeyError:
            raise TopologyError(f"Node '{name}' not found in topology") from None

    def get_node_links(self, node_name: str) -> list[InternalLink]:
        """Get all links for a node."""

        return self._link_index.get(node_name, [])

    def get_vbox_settings(self, node: InternalNode) -> InternalVBoxSettings:
        """Get effective VBox settings for a node (node-specific or topology defaults)."""

        return node.vbox if node.vbox is not None else self.vbox
