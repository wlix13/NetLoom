"""Internal model invariants."""

import pytest
from pydantic import ValidationError

from netloom.core.enums import InterfaceKind, NodeRole
from netloom.models.internal import (
    InternalInterface,
    InternalNode,
    InternalTopology,
    InternalVBoxSettings,
    InternalVLAN,
    ifname_to_nic_slot,
)


@pytest.mark.unit
def test_loopback_interface_rejects_physical_only_fields():
    with pytest.raises(ValidationError):
        InternalInterface(name="lo0", kind=InterfaceKind.LOOPBACK, mac_address="08:00:27:00:00:01")
    with pytest.raises(ValidationError):
        InternalInterface(name="lo0", kind=InterfaceKind.LOOPBACK, nic_slot=1)


@pytest.mark.unit
def test_vlan_id_bounds():
    with pytest.raises(ValidationError):
        InternalVLAN(id=0, parent="eth1", name="eth1-0")
    with pytest.raises(ValidationError):
        InternalVLAN(id=4095, parent="eth1", name="eth1-4095")
    assert InternalVLAN(id=100, parent="eth1", name="eth1-100").id == 100


@pytest.mark.unit
def test_ifname_to_nic_slot():
    assert ifname_to_nic_slot("eth0") == 1
    assert ifname_to_nic_slot("eth3") == 4
    with pytest.raises(ValueError, match="ethN"):
        ifname_to_nic_slot("wlan0")


@pytest.mark.unit
def test_get_vbox_settings_falls_back_to_topology_default():
    default = InternalVBoxSettings(ioapic=False)
    node_specific = InternalVBoxSettings(ioapic=True)
    plain = InternalNode(name="A", role=NodeRole.HOST)
    custom = InternalNode(name="B", role=NodeRole.HOST, vbox=node_specific)
    topo = InternalTopology(id="t", name="T", vbox=default, nodes=[plain, custom])

    assert topo.get_vbox_settings(plain) is default
    assert topo.get_vbox_settings(custom) is node_specific
