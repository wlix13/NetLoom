from pathlib import Path

from .config import TopologyConfig
from .internal import (
    InternalDefaults,
    InternalInterface,
    InternalMgmt,
    InternalNetwork,
    InternalNode,
    InternalResources,
    InternalTopology,
    NicModel,
    ifname_to_vbox_adapter_index,
)


def _nic_model_from_provider(top: TopologyConfig) -> NicModel:
    prov_model = top.provider.defaults.nic_model if top.provider and top.provider.defaults else None

    if prov_model not in ("virtio", "e1000", "rtl8139"):
        raise ValueError(f"Unsupported nic model: {prov_model!r}")
    return prov_model


def to_internal(top: TopologyConfig, workdir: str | Path) -> InternalTopology:
    """Apply defaults; compute NIC indices; map VB internal networks; return InternalTopology."""

    workdir = Path(workdir)

    pd = top.provider.defaults or type(top.provider).defaults
    nic_model: NicModel = _nic_model_from_provider(top)
    os_image = pd.os_image if pd else None
    cpu = pd.cpu if pd and pd.cpu else 1
    ram_mb = pd.ram_mb if pd and pd.ram_mb else 512
    disk_gb = pd.disk_gb if pd and pd.disk_gb else 8

    dd = top.defaults or type(top.defaults)
    routing_stack = dd.routing.stack if (dd and dd.routing and dd.routing.stack) else "bird"
    switch_impl = dd.switch.impl if (dd and dd.switch and dd.switch.impl) else "linux-bridge"
    firewall_impl = dd.firewall.impl if (dd and dd.firewall and dd.firewall.impl) else "nftables"
    ssh_user = dd.mgmt.ssh_user if (dd and dd.mgmt and dd.mgmt.ssh_user) else "lab"
    ssh_key = dd.mgmt.ssh_key if (dd and dd.mgmt) else None

    idef = InternalDefaults(
        routing_stack=routing_stack,
        switch_impl=switch_impl,
        firewall_impl=firewall_impl,
        ssh_user=ssh_user,
        ssh_key=ssh_key,
        nic_model=nic_model,
        os_image=os_image,
        cpu=cpu,
        ram_mb=ram_mb,
        disk_gb=disk_gb,
    )

    internal_networks: list[InternalNetwork] = []
    for n in top.networks or []:
        internal_networks.append(
            InternalNetwork(
                id=n.id,
                type=n.type,
                mtu=n.mtu,
                cidr=n.cidr,
                dhcp=n.dhcp,
                vbox_network_name=f"intnet:{n.id}",
            )
        )

    internal_nodes: list[InternalNode] = []
    for node in top.nodes:
        res = node.resources or type(node.resources)
        n_cpu = res.cpu if res and res.cpu else idef.cpu
        n_ram = res.ram_mb if res and res.ram_mb else idef.ram_mb
        n_disk = res.disk_gb if res and res.disk_gb else idef.disk_gb

        mgmt_ip = node.mgmt.ip if (node.mgmt and node.mgmt.ip) else None
        mgmt_gw = str(node.mgmt.gw) if (node.mgmt and node.mgmt.gw) else None
        mgmt_net = node.mgmt.net if (node.mgmt and node.mgmt.net) else None

        nics: list[InternalInterface] = []
        for itf in node.interfaces or []:
            if itf.name == "lo":
                continue
            nics.append(
                InternalInterface(
                    name=itf.name,
                    vbox_nic_index=ifname_to_vbox_adapter_index(itf.name),
                    network_id=itf.network,
                    addresses=itf.addresses or [],
                )
            )

        config_dir = (workdir / "configs" / node.name).as_posix()
        saved_dir = (workdir / "saved" / node.name).as_posix()

        internal_nodes.append(
            InternalNode(
                name=node.name,
                role=node.role,
                image=node.image or idef.os_image,
                resources=InternalResources(cpu=n_cpu, ram_mb=n_ram, disk_gb=n_disk),
                mgmt=InternalMgmt(ip=mgmt_ip, gw=mgmt_gw, net_id=mgmt_net),
                nic_model=idef.nic_model,
                nics=nics,
                config_dir=config_dir,
                saved_configs_dir=saved_dir,
            )
        )

    it = InternalTopology(
        schema=top.schema,
        id=top.meta.id,
        title=top.meta.title,
        description=top.meta.description,
        variables=top.variables or {},
        defaults=idef,
        networks=internal_networks,
        nodes=internal_nodes,
    )
    it.index()
    return it
