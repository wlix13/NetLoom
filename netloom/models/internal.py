from ipaddress import IPv4Interface, IPv4Network
from typing import Literal

from pydantic import BaseModel, Field, field_validator


NicModel = Literal["virtio", "e1000", "rtl8139"]


def ifname_to_vbox_adapter_index(ifname: str) -> int:
    """
    eth0 -> 1, eth1 -> 2, ...
    lo is not mapped.
    """

    if not ifname.startswith("eth"):
        raise ValueError(f"Only ethN are mappable to VirtualBox NICs: {ifname!r}")
    idx = int(ifname[3:])
    return idx + 1  # VBox NICs start at 1


class InternalResources(BaseModel):
    cpu: int
    ram_mb: int
    disk_gb: int


class InternalMgmt(BaseModel):
    ip: IPv4Interface | None = None
    gw: str | None = None
    net_id: str | None = None


class InternalInterface(BaseModel):
    name: str  # ethX
    vbox_nic_index: int = Field(ge=1, le=32)
    network_id: str | None = None
    addresses: list[IPv4Interface] = Field(default_factory=list)


class InternalNode(BaseModel):
    name: str
    role: Literal["router", "switch", "host"]
    image: str | None = None
    resources: InternalResources
    mgmt: InternalMgmt
    nic_model: NicModel
    nics: list[InternalInterface]
    config_dir: str | None = None
    saved_configs_dir: str | None = None

    @field_validator("nics")
    @classmethod
    def _nic_slots(cls, v: list[InternalInterface]) -> list[InternalInterface]:
        for itf in v:
            if not (1 <= itf.vbox_nic_index <= 8):
                raise ValueError(f"VirtualBox supports up to 8 NICs: got nic{itf.vbox_nic_index}")
        return v


class InternalNetwork(BaseModel):
    id: str
    type: Literal["l2", "l3"]
    mtu: int = 1500
    cidr: IPv4Network | None = None
    dhcp: bool = False
    vbox_network_name: str


class InternalDefaults(BaseModel):
    routing_stack: Literal["bird", "frr", "linux"] = "bird"
    switch_impl: Literal["linux-bridge", "ovs"] = "linux-bridge"
    firewall_impl: Literal["nftables", "none"] = "nftables"
    ssh_user: str = "lab"
    ssh_key: str | None = None
    nic_model: NicModel = "virtio"
    os_image: str | None = None
    cpu: int = 1
    ram_mb: int = 512
    disk_gb: int = 8


class InternalTopology(BaseModel):
    schema: str
    id: str
    title: str
    description: str | None = None

    variables: dict[str, object] = Field(default_factory=dict)
    defaults: InternalDefaults
    networks: list[InternalNetwork]
    nodes: list[InternalNode]

    _net_index: dict[str, InternalNetwork] = Field(default_factory=dict, exclude=True)
    _node_index: dict[str, InternalNode] = Field(default_factory=dict, exclude=True)

    def index(self) -> None:
        self._net_index = {n.id: n for n in self.networks}
        self._node_index = {n.name: n for n in self.nodes}

    def net(self, net_id: str) -> InternalNetwork:
        return self._net_index[net_id]

    def node(self, node_name: str) -> InternalNode:
        return self._node_index[node_name]
