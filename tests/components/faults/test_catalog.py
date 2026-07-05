"""Fault catalog: applicability, mutations and determinism on the example topology."""

import ipaddress
import random

import pytest

from netloom.components.faults.catalog import FaultCatalog, register_builtin_faults
from netloom.components.faults.errors import FaultNotApplicable
from netloom.core.enums import FirewallAction


pytestmark = pytest.mark.unit


@pytest.fixture
def catalog() -> FaultCatalog:
    cat = FaultCatalog()
    register_builtin_faults(cat)
    return cat


def _apply_first(catalog, type_id, topo, seed=1):
    definition = catalog.get(type_id)
    assert definition is not None, f"{type_id} missing from catalog"
    targets = definition.find_targets(topo)
    assert targets, f"{type_id} has no targets in the example topology"
    return definition.apply(topo, targets[0], random.Random(seed)), targets[0]


def test_every_builtin_fault_applies_to_example(catalog, internal):
    for definition in catalog.all():
        targets = definition.find_targets(internal)
        assert targets, f"'{definition.type_id}' should be applicable to the all-features example lab"
        assert targets == sorted(targets, key=lambda t: t.sort_key), f"'{definition.type_id}' targets not sorted"


def test_wrong_ip_stays_in_subnet(catalog, internal):
    applied, _ = _apply_first(catalog, "wrong-ip-address", internal)
    before = ipaddress.ip_interface(applied.before)
    after = ipaddress.ip_interface(applied.after)
    assert before.ip != after.ip
    assert before.network == after.network, "faulted IP must stay in the original subnet"


def test_wrong_prefix_grows_length(catalog, internal):
    applied, _ = _apply_first(catalog, "wrong-prefix-length", internal)
    before = ipaddress.ip_interface(applied.before)
    after = ipaddress.ip_interface(applied.after)
    assert after.network.prefixlen in (before.network.prefixlen + 1, before.network.prefixlen + 2)
    assert before.ip == after.ip


def test_duplicate_ip_copies_peer_address(catalog, internal):
    applied, _ = _apply_first(catalog, "duplicate-ip", internal)
    node = internal.get_node(applied.node)
    iface = next(i for i in node.interfaces if i.name == applied.target)
    others = {i.ip for n in internal.nodes if n.name != applied.node for i in n.interfaces}
    assert iface.ip in others, "faulted interface must now collide with a peer"


def test_interface_unconfigured_suppresses_config(catalog, internal):
    applied, _ = _apply_first(catalog, "interface-unconfigured", internal)
    node = internal.get_node(applied.node)
    iface = next(i for i in node.interfaces if i.name == applied.target)
    assert iface.configured is False


def test_wrong_vlan_id_changes_within_bounds(catalog, internal):
    applied, _ = _apply_first(catalog, "wrong-vlan-id", internal)
    node = internal.get_node(applied.node)
    vlan = next(v for v in node.vlans if v.name == applied.target)
    assert str(vlan.id) == applied.after
    assert applied.after != applied.before
    assert 1 <= vlan.id <= 4094
    assert len({v.id for v in node.vlans}) == len(node.vlans), "VLAN ids must stay unique per node"


def test_missing_static_route_removes_route(catalog, internal):
    node_routes_before = {
        n.name: len(n.routing.static_routes) for n in internal.nodes if n.routing and n.routing.static_routes
    }
    applied, _ = _apply_first(catalog, "missing-static-route", internal)
    node = internal.get_node(applied.node)
    assert len(node.routing.static_routes) == node_routes_before[applied.node] - 1


def test_wrong_static_gateway_changes_next_hop(catalog, internal):
    applied, _ = _apply_first(catalog, "wrong-static-gateway", internal)
    assert applied.before != applied.after
    node = internal.get_node(applied.node)
    route = next(r for r in node.routing.static_routes if r.destination == applied.target)
    assert f"via {route.gateway}" == applied.after


def test_ospf_wrong_area_moves_area(catalog, internal):
    applied, _ = _apply_first(catalog, "ospf-wrong-area", internal)
    node = internal.get_node(applied.node)
    assert applied.after in {a.id for a in node.routing.ospf_areas}
    assert applied.before not in {a.id for a in node.routing.ospf_areas}


def test_rip_version_flips(catalog, internal):
    applied, _ = _apply_first(catalog, "rip-version-mismatch", internal)
    node = internal.get_node(applied.node)
    assert applied.before == "v2"
    assert applied.after == "v1"
    assert node.routing.rip.version == 1


def test_ip_forwarding_disabled_clears_both_signals(catalog, internal):
    applied, _ = _apply_first(catalog, "ip-forwarding-disabled", internal)
    node = internal.get_node(applied.node)
    assert node.sysctl.ip_forwarding is False
    assert str(node.sysctl.custom.get("net.ipv4.ip_forward", 0)) in ("0", "False")


def test_firewall_accept_removed_shrinks_rules(catalog, internal):
    definition = catalog.get("firewall-accept-removed")
    target = definition.find_targets(internal)[0]
    node = internal.get_node(target.node)
    before = len(node.services.firewall.rules)

    definition.apply(internal, target, random.Random(1))
    assert len(node.services.firewall.rules) == before - 1


def test_firewall_accept_flipped_sets_drop(catalog, internal):
    applied, target = _apply_first(catalog, "firewall-accept-flipped", internal)
    node = internal.get_node(applied.node)
    rule = node.services.firewall.rules[int(target.item)]
    assert rule.action == FirewallAction.DROP


def test_apply_is_deterministic_per_seed(catalog, app):
    from netloom.models.common import load_topology
    from netloom.models.converters import convert_topology
    from tests.conftest import EXAMPLE_TOPOLOGY

    results = []
    for _ in range(2):
        topo = convert_topology(load_topology(EXAMPLE_TOPOLOGY), workdir=app.workdir)
        definition = catalog.get("wrong-ip-address")
        target = definition.find_targets(topo)[0]
        results.append(definition.apply(topo, target, random.Random(42)).model_dump())

    assert results[0] == results[1], "same seed + same topology must produce the identical fault"


def test_inapplicable_target_raises(catalog, internal):
    definition = catalog.get("missing-static-route")
    from netloom.components.faults.catalog import FaultTarget

    with pytest.raises(FaultNotApplicable):
        definition.apply(internal, FaultTarget(node="SW1", item="10.9.9.0/24"), random.Random(1))
