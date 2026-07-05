"""Topology conversion: external YAML schema → internal graph."""

import pytest

from netloom.core.enums import InterfaceKind
from netloom.core.errors import TopologyError


pytestmark = pytest.mark.unit


def test_all_nodes_converted(internal):
    assert {n.name for n in internal.nodes} == {"R1", "R2", "R3", "SW1", "H1", "H2"}


def test_loopback_gets_no_nic_or_mac(internal):
    r1 = internal.get_node("R1")
    loopbacks = [i for i in r1.interfaces if i.kind == InterfaceKind.LOOPBACK]
    assert loopbacks, "R1 should have a loopback interface"
    for lo in loopbacks:
        assert lo.nic_slot is None
        assert lo.mac_address is None


def test_physical_interfaces_get_unique_nics_and_macs(internal):
    for node in internal.nodes:
        physical = [i for i in node.interfaces if i.kind == InterfaceKind.PHYSICAL]
        indexes = [i.nic_slot for i in physical]
        assert all(idx is not None and idx >= 1 for idx in indexes), f"{node.name}: unassigned NIC index"
        assert len(set(indexes)) == len(indexes), f"{node.name}: duplicate NIC indexes {indexes}"
        macs = [i.mac_address for i in physical]
        assert all(macs), f"{node.name}: missing MAC address"
        assert len(set(macs)) == len(macs), f"{node.name}: duplicate MACs"


def test_point_to_point_links_built(internal):
    pairs = {tuple(sorted((link.node_a, link.node_b))) for link in internal.links}
    assert ("R1", "R2") in pairs
    assert ("R2", "R3") in pairs


def test_networks_carry_participants(internal):
    by_name = {net.name: net for net in internal.networks}
    assert "r1-r2" in by_name
    assert len(by_name["r1-r2"].participants) == 2


def test_get_node_unknown_raises(internal):
    with pytest.raises(TopologyError):
        internal.get_node("nonexistent")


def test_node_config_dirs_assigned(internal):
    for node in internal.nodes:
        assert node.config_dir, f"{node.name} has no config_dir"
        assert node.name in node.config_dir
