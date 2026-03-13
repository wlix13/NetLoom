"""NetLoom topology models.

This package contains:
- common: Shared types and utilities
- internal: Internal representations for infrastructure controllers
- converters: Conversion utilities between config and internal models
- config: User-facing topology configuration models (based on topology-schema.json)
"""

from .common import (
    load_topology,
)
from .config import (
    BridgeConfig,
    Defaults,
    FirewallConfig,
    FirewallRule,
    InterfaceConfig,
    Meta,
    Network,
    Node,
    OSPFArea,
    OSPFConfig,
    RIPConfig,
    RoutingConfig,
    ServicesConfig,
    StaticRoute,
    Topology,
    TunnelConfig,
    VLANConfig,
    WireguardConfig,
    WireguardPeer,
)
from .converters import (
    TopologyConverter,
    convert_topology,
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
    InternalResources,
    InternalRIP,
    InternalRouting,
    InternalServices,
    InternalStaticRoute,
    InternalSysctl,
    InternalTopology,
    InternalTunnel,
    InternalVLAN,
    InternalWireguard,
    InternalWireguardPeer,
    NicModel,
    ifname_to_vbox_adapter_index,
)


__all__ = [
    # Common types
    "load_topology",
    # Config models
    "BridgeConfig",
    "Defaults",
    "FirewallConfig",
    "FirewallRule",
    "InterfaceConfig",
    "Meta",
    "Network",
    "Node",
    "OSPFArea",
    "OSPFConfig",
    "RIPConfig",
    "RoutingConfig",
    "ServicesConfig",
    "StaticRoute",
    "Topology",
    "TunnelConfig",
    "VLANConfig",
    "WireguardConfig",
    "WireguardPeer",
    # Converters
    "TopologyConverter",
    "convert_topology",
    # Internal models
    "InternalBridge",
    "InternalFirewall",
    "InternalFirewallRule",
    "InternalInterface",
    "InternalLink",
    "InternalNetwork",
    "InternalNode",
    "InternalOSPFArea",
    "InternalRIP",
    "InternalResources",
    "InternalRouting",
    "InternalServices",
    "InternalStaticRoute",
    "InternalSysctl",
    "InternalTopology",
    "InternalTunnel",
    "InternalVLAN",
    "InternalWireguard",
    "InternalWireguardPeer",
    "NicModel",
    "ifname_to_vbox_adapter_index",
]
