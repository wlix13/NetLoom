from ipaddress import IPv4Address, IPv4Interface, IPv4Network, ip_network
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import MTU, ExpectStr, IfaceLike, IfNameEth, IfNameEthOrLo, NameID, PortNum, SchemaStr, Vid


# --- Provider ----------------------------------------------------------------


class ProviderDefaults(BaseModel):
    cpu: Annotated[int, Field(ge=1)] = 1
    ram_mb: Annotated[int, Field(ge=128)] = 512
    disk_gb: Annotated[int, Field(ge=1)] = 8
    os_image: str | None = None
    nic_model: Literal["virtio", "e1000", "rtl8139"] | None = None
    promiscuous: Literal["deny", "allow-vms", "allow-all"] | None = None


class ProviderImages(BaseModel):
    router: str | None = None
    switch: str | None = None
    host: str | None = None


class Provider(BaseModel):
    name: Literal["virtualbox", "kvm", "container"]
    defaults: ProviderDefaults | None = None
    images: ProviderImages | None = None


# --- Meta --------------------------------------------------------------------


class Meta(BaseModel):
    id: NameID
    title: str
    description: str | None = None


# --- Defaults (behavior/software) --------------------------------------------


class RoutingDefaults(BaseModel):
    stack: Literal["bird", "frr", "linux"] = "bird"
    protocols_enabled: list[Literal["ospf", "rip", "bgp", "static"]] = Field(default_factory=list)


class SwitchDefaults(BaseModel):
    impl: Literal["linux-bridge", "ovs"] = "linux-bridge"


class FirewallDefaults(BaseModel):
    impl: Literal["nftables", "none"] = "nftables"


class MgmtDefaults(BaseModel):
    ssh_user: str = "lab"
    ssh_key: str | None = None


class Defaults(BaseModel):
    routing: RoutingDefaults | None = None
    switch: SwitchDefaults | None = None
    firewall: FirewallDefaults | None = None
    mgmt: MgmtDefaults | None = None


# --- Networks ----------------------------------------------------------------


class VlanConfig(BaseModel):
    mode: Literal["access", "trunk"] | None = None
    allowed: list[Vid] | None = None
    vid: Vid | None = None


class Network(BaseModel):
    id: NameID
    type: Literal["l2", "l3"]
    mtu: MTU = 1500
    # L3 only: keep as IPv4Network (users are expected to use proper network addresses)
    cidr: IPv4Network | None = None
    dhcp: bool = False
    vlan: VlanConfig | None = None


# --- Nodes -------------------------------------------------------------------


class NodeResources(BaseModel):
    cpu: Annotated[int, Field(ge=1)] | None = None
    ram_mb: Annotated[int, Field(ge=128)] | None = None
    disk_gb: Annotated[int, Field(ge=1)] | None = None


class NodeMgmt(BaseModel):
    ip: IPv4Interface | None = None  # "192.168.1.2/24"
    gw: IPv4Address | None = None
    net: str | None = None


class Interface(BaseModel):
    name: IfNameEthOrLo
    network: str | None = None
    loopback: bool | None = None
    addresses: list[IPv4Interface] | None = None

    @model_validator(mode="after")
    def _either_network_or_loopback(self, m: "Interface") -> "Interface":
        # JSON Schema anyOf: require "network" OR loopback == true
        if not (m.network or m.loopback):
            raise ValueError('interface must have "network" or set "loopback: true"')
        return m


class StaticRoute(BaseModel):
    to: str  # accept 0.0.0.0/0 and general CIDR; validate below
    via: IPv4Address

    @field_validator("to")
    @classmethod
    def _check_to_cidr(cls, v: str) -> str:
        # Accept "0.0.0.0/0" or any IPv4 net; be lenient on host/prefix by strict=False
        try:
            _ = ip_network(v, strict=False)
        except Exception as e:
            raise ValueError(f'invalid route "to": {v!r} ({e})')
        return v


class OSPFConfig(BaseModel):
    enabled: bool = False
    impl: Literal["bird", "frr"] | None = None


class RIPConfig(BaseModel):
    enabled: bool = False


class BGPConfig(BaseModel):
    enabled: bool = False
    asn: int | None = None


class Protocols(BaseModel):
    static: BaseModel | None = None
    ospf: OSPFConfig | None = None
    rip: RIPConfig | None = None
    bgp: BGPConfig | None = None

    # JSON Schema shapes "static.routes[].{to,via}"
    @model_validator(mode="before")
    @classmethod
    def _normalize_static(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        st = data.get("static")
        if isinstance(st, dict) and "routes" in st:
            # Wrap into a small typed object on the fly
            class StaticBlock(BaseModel):
                routes: list[StaticRoute]

            data["static"] = StaticBlock(**st)
        return data


class NodeRouting(BaseModel):
    stack: Literal["bird", "frr", "linux"] | None = None
    protocols: Protocols | None = None


class Service(BaseModel):
    name: str
    enabled: bool = True


class Node(BaseModel):
    name: NameID
    role: Literal["router", "switch", "host"]
    image: str | None = None
    resources: NodeResources | None = None
    mgmt: NodeMgmt | None = None
    interfaces: list[Interface] | None = None
    routing: NodeRouting | None = None
    services: list[Service] | None = None


# --- Switching (L2) -----------------------------------------------------------


class BridgePort(BaseModel):
    if_: IfNameEth = Field(alias="if")
    vlan: VlanConfig | None = None


class SVI(BaseModel):
    vid: Vid
    ifname: IfaceLike
    addresses: list[IPv4Interface] | None = None


class Bridge(BaseModel):
    name: str
    ports: list[BridgePort] | None = None
    svis: list[SVI] | None = None


class SwitchingItem(BaseModel):
    node: str
    impl: Literal["linux-bridge", "ovs"]
    bridges: list[Bridge] | None = None


# --- Firewall ----------------------------------------------------------------


class L4Match(BaseModel):
    proto: Literal["tcp", "udp"]
    # allow single int or list of ints, with constraints, for sport/dport/dports
    sport: PortNum | list[PortNum] | None = None
    dport: PortNum | list[PortNum] | None = None
    dports: PortNum | list[PortNum] | None = None


class RuleMatch(BaseModel):
    in_if: str | None = None
    out_if: str | None = None
    src: str | None = None  # IP or CIDR; validate below
    dst: str | None = None
    ip_proto: Literal["tcp", "udp", "icmp", "ospf", "all"] | None = None
    l4: L4Match | None = None

    @field_validator("src", "dst")
    @classmethod
    def _validate_ip_or_cidr(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            # valid if it's a single address or a network (host/prefix allowed)
            _ = ip_network(v, strict=False)
            return v
        except Exception:
            # try pure address without prefix
            try:
                IPv4Address(v)
                return v
            except Exception as e:
                raise ValueError(f"expected IPv4 or IPv4/CIDR, got {v!r} ({e})")


class FirewallRule(BaseModel):
    id: NameID
    match: RuleMatch | None = None
    action: Literal["accept", "drop", "reject"]


class FirewallItem(BaseModel):
    node: str
    rules: list[FirewallRule]


# --- Profiles ----------------------------------------------------------------


class PatchOp(BaseModel):
    op: Literal["add", "replace", "remove"]
    path: str
    value: Any | None = None
    where: dict[str, Any] | None = None
    patch: Any | None = None


class Profile(BaseModel):
    name: str
    description: str | None = None
    patches: list[PatchOp]


# --- Tests -------------------------------------------------------------------


class TestTargetObj(BaseModel):
    ip: IPv4Address | None = None
    node: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "TestTargetObj":
        if not (self.ip or self.node):
            raise ValueError('test "to" object must have at least one of: ip, node')
        return self


class TestCase(BaseModel):
    name: str
    from_: str = Field(alias="from")
    to: str | TestTargetObj
    expect: ExpectStr


# --- Root --------------------------------------------------------------------


class TopologyConfig(BaseModel):
    schema: SchemaStr
    meta: Meta
    provider: Provider
    nodes: list[Node]

    # Optional blocks
    defaults: Defaults | None = None
    variables: dict[str, Any] = Field(default_factory=dict)
    networks: list[Network] | None = None
    switching: list[SwitchingItem] | None = None
    firewall: list[FirewallItem] | None = None
    profiles: list[Profile] | None = None
    tests: list[TestCase] | None = None
