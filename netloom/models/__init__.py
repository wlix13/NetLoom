"""NetLoom topology models.

This package contains:
- common: Shared types and utilities
- internal: Internal representations for infrastructure controllers
- converters: Conversion utilities between config and internal models
- config: User-facing topology configuration models (based on topology-schema.json)

Note: For the recommended approach, use the Application and TopologyController:
    from netloom import Application
    app = Application.current()
    topology = app.topology.load("topology.yaml")
    internal = app.topology.convert(topology, workdir="./work")
"""

from .common import (
    CIDRStr,
    IPv4Str,
    NameID,
    PortNum,
    RouterIdStr,
    load_topology,
)
from .config import (
    BridgeConfig,
    Defaults,
    FirewallConfig,
    FirewallRule,
    InterfaceConfig,
    Link,
    Meta,
    Node,
    OSPFArea,
    OSPFConfig,
    RoutingConfig,
    ServicesConfig,
    Topology,
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
    InternalNode,
    InternalOSPFArea,
    InternalResources,
    InternalRouting,
    InternalServices,
    InternalStaticRoute,
    InternalSysctl,
    InternalTopology,
    InternalWireguard,
    InternalWireguardPeer,
    NicModel,
    ifname_to_vbox_adapter_index,
)


__all__ = [
    # Common types
    "CIDRStr",
    "IPv4Str",
    "NameID",
    "PortNum",
    "RouterIdStr",
    "load_topology",
    # Config models
    "BridgeConfig",
    "Defaults",
    "FirewallConfig",
    "FirewallRule",
    "InterfaceConfig",
    "Link",
    "Meta",
    "Node",
    "OSPFArea",
    "OSPFConfig",
    "RoutingConfig",
    "ServicesConfig",
    "Topology",
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
    "InternalNode",
    "InternalOSPFArea",
    "InternalResources",
    "InternalRouting",
    "InternalServices",
    "InternalStaticRoute",
    "InternalSysctl",
    "InternalTopology",
    "InternalWireguard",
    "InternalWireguardPeer",
    "NicModel",
    "ifname_to_vbox_adapter_index",
]
