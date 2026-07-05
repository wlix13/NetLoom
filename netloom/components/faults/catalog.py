"""Built-in fault catalog: deterministic, seeded mutations of an InternalTopology.

Every fault is a pair of pure functions over the internal models:

- ``find_targets(topo)`` returns the sorted list of places the fault can hit;
- ``apply(topo, target, rng)`` mutates the topology in place and returns an
  ``AppliedFault`` record for the answer key.

Faults change *intent* (the internal model) before config generation, so the
lab deploys and boots normally — it just misbehaves the way a real
misconfiguration would.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from netloom.core.enums import FirewallAction, InterfaceKind, NodeRole

from .errors import FaultNotApplicable
from .models import AppliedFault, FaultCategory


if TYPE_CHECKING:
    import random

    from netloom.models.internal import InternalFirewallRule, InternalInterface, InternalTopology


@dataclass(frozen=True, slots=True)
class FaultTarget:
    """A concrete place a fault can be injected: a node, plus an optional item key."""

    node: str
    item: str | None = None

    @property
    def sort_key(self) -> tuple[str, str]:
        return (self.node, self.item or "")


@dataclass(frozen=True, slots=True)
class FaultDefinition:
    """One catalog entry."""

    type_id: str
    category: FaultCategory
    difficulty: int
    summary: str
    hint: str
    find_targets: Callable[[InternalTopology], list[FaultTarget]]
    apply: Callable[[InternalTopology, FaultTarget, random.Random], AppliedFault]


class FaultCatalog:
    """Registry of available fault definitions."""

    def __init__(self) -> None:
        self._defs: dict[str, FaultDefinition] = {}

    def register(self, definition: FaultDefinition) -> None:
        self._defs[definition.type_id] = definition

    def get(self, type_id: str) -> FaultDefinition | None:
        return self._defs.get(type_id)

    def names(self) -> list[str]:
        return sorted(self._defs)

    def all(self) -> list[FaultDefinition]:
        return [self._defs[name] for name in self.names()]


# ── helpers ───────────────────────────────────────────────────────────────────


def _get_iface(topo: InternalTopology, node_name: str, iface_name: str) -> InternalInterface:
    node = topo.get_node(node_name)
    for iface in node.interfaces:
        if iface.name == iface_name:
            return iface
    raise FaultNotApplicable("<internal>", f"interface '{iface_name}' not found on node '{node_name}'")


def _ipv4_interface(value: str | None) -> ipaddress.IPv4Interface | None:
    if not value or "/" not in value:
        return None
    try:
        parsed = ipaddress.ip_interface(value)
    except ValueError:
        return None
    return parsed if isinstance(parsed, ipaddress.IPv4Interface) else None


def _used_ips(topo: InternalTopology) -> set[str]:
    used: set[str] = set()
    for node in topo.nodes:
        for iface in node.interfaces:
            if iface.ip:
                used.add(iface.ip.split("/")[0])
        for vlan in node.vlans:
            if vlan.ip:
                used.add(vlan.ip.split("/")[0])
        for tunnel in node.tunnels:
            if tunnel.ip:
                used.add(tunnel.ip.split("/")[0])
    return used


def _sorted(targets: list[FaultTarget]) -> list[FaultTarget]:
    return sorted(targets, key=lambda t: t.sort_key)


def _made(  # noqa: PLR0913
    definition_id: str,
    category: FaultCategory,
    difficulty: int,
    hint: str,
    target: FaultTarget,
    description: str,
    before: str | None,
    after: str | None,
) -> AppliedFault:
    return AppliedFault(
        type=definition_id,
        category=category,
        difficulty=difficulty,
        node=target.node,
        target=target.item,
        hint=hint,
        description=description,
        before=before,
        after=after,
    )


# ── addressing faults ─────────────────────────────────────────────────────────

_WRONG_IP_HINT = "One node's interface has an IP address that is not what the lab design intends."


def _wrong_ip_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        for iface in node.interfaces:
            parsed = _ipv4_interface(iface.ip)
            if (
                iface.kind == InterfaceKind.PHYSICAL
                and iface.configured
                and parsed
                and 8 <= parsed.network.prefixlen <= 29
            ):
                targets.append(FaultTarget(node=node.name, item=iface.name))
    return _sorted(targets)


def _wrong_ip_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:
    iface = _get_iface(topo, target.node, target.item or "")
    parsed = _ipv4_interface(iface.ip)
    if parsed is None:
        raise FaultNotApplicable("wrong-ip-address", f"{target.node}/{target.item} has no IPv4 CIDR address")

    network = parsed.network
    used = _used_ips(topo)
    span = min(network.num_addresses - 1, 255)
    for _ in range(64):
        candidate = network.network_address + rng.randrange(1, span)
        if candidate in (parsed.ip, network.broadcast_address) or str(candidate) in used:
            continue
        before = iface.ip
        iface.ip = f"{candidate}/{network.prefixlen}"
        return _made(
            "wrong-ip-address",
            FaultCategory.ADDRESSING,
            1,
            _WRONG_IP_HINT,
            target,
            f"{target.node}/{target.item}: IP address changed from {before} to {iface.ip}",
            before,
            iface.ip,
        )
    raise FaultNotApplicable("wrong-ip-address", f"no free address found in {network}")


_WRONG_PREFIX_HINT = "A subnet mask somewhere does not match the link's addressing plan."


def _wrong_prefix_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        for iface in node.interfaces:
            parsed = _ipv4_interface(iface.ip)
            if (
                iface.kind == InterfaceKind.PHYSICAL
                and iface.configured
                and parsed
                and 8 <= parsed.network.prefixlen <= 28
            ):
                targets.append(FaultTarget(node=node.name, item=iface.name))
    return _sorted(targets)


def _wrong_prefix_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:
    iface = _get_iface(topo, target.node, target.item or "")
    parsed = _ipv4_interface(iface.ip)
    if parsed is None:
        raise FaultNotApplicable("wrong-prefix-length", f"{target.node}/{target.item} has no IPv4 CIDR address")

    before = iface.ip
    new_prefix = parsed.network.prefixlen + rng.choice([1, 2])
    iface.ip = f"{parsed.ip}/{new_prefix}"
    return _made(
        "wrong-prefix-length",
        FaultCategory.ADDRESSING,
        2,
        _WRONG_PREFIX_HINT,
        target,
        f"{target.node}/{target.item}: prefix length changed from /{parsed.network.prefixlen} to /{new_prefix}",
        before,
        iface.ip,
    )


_DUPLICATE_IP_HINT = "Two devices on the same link answer to the same IP address."


def _duplicate_ip_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for link in topo.links:
        iface_a = _get_iface(topo, link.node_a, link.interface_a)
        iface_b = _get_iface(topo, link.node_b, link.interface_b)
        if iface_a.ip and iface_b.ip:
            targets.append(FaultTarget(node=link.node_a, item=link.interface_a))
            targets.append(FaultTarget(node=link.node_b, item=link.interface_b))
    return _sorted(targets)


def _duplicate_ip_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    for link in topo.links:
        if (link.node_a, link.interface_a) == (target.node, target.item):
            peer_node, peer_iface_name = link.node_b, link.interface_b
            break
        if (link.node_b, link.interface_b) == (target.node, target.item):
            peer_node, peer_iface_name = link.node_a, link.interface_a
            break
    else:
        raise FaultNotApplicable("duplicate-ip", f"no link found for {target.node}/{target.item}")

    iface = _get_iface(topo, target.node, target.item or "")
    peer = _get_iface(topo, peer_node, peer_iface_name)
    if not peer.ip:
        raise FaultNotApplicable("duplicate-ip", f"peer {peer_node}/{peer_iface_name} has no IP")

    before = iface.ip
    iface.ip = peer.ip
    return _made(
        "duplicate-ip",
        FaultCategory.ADDRESSING,
        2,
        _DUPLICATE_IP_HINT,
        target,
        f"{target.node}/{target.item}: IP set to {peer.ip}, duplicating {peer_node}/{peer_iface_name}",
        before,
        iface.ip,
    )


# ── interface faults ──────────────────────────────────────────────────────────

_IFACE_UNCONFIGURED_HINT = "One interface never received its network configuration."


def _iface_unconfigured_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        for iface in node.interfaces:
            if iface.kind == InterfaceKind.PHYSICAL and iface.configured and iface.ip:
                targets.append(FaultTarget(node=node.name, item=iface.name))
    return _sorted(targets)


def _iface_unconfigured_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    iface = _get_iface(topo, target.node, target.item or "")
    before = iface.ip
    iface.configured = False
    return _made(
        "interface-unconfigured",
        FaultCategory.INTERFACE,
        1,
        _IFACE_UNCONFIGURED_HINT,
        target,
        f"{target.node}/{target.item}: interface config suppressed (was {before})",
        before,
        "(no config rendered)",
    )


# ── VLAN faults ───────────────────────────────────────────────────────────────

_WRONG_VLAN_HINT = "A VLAN tag does not match on both ends of a trunk."


def _wrong_vlan_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        for vlan in node.vlans:
            targets.append(FaultTarget(node=node.name, item=vlan.name))
    return _sorted(targets)


def _wrong_vlan_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:
    node = topo.get_node(target.node)
    vlan = next((v for v in node.vlans if v.name == target.item), None)
    if vlan is None:
        raise FaultNotApplicable("wrong-vlan-id", f"VLAN '{target.item}' not found on node '{target.node}'")

    used_ids = {v.id for v in node.vlans}
    candidates = [
        c for c in (vlan.id + 1, vlan.id - 1, vlan.id + 10, vlan.id + 100) if 1 <= c <= 4094 and c not in used_ids
    ]
    if not candidates:
        candidates = [c for c in range(1, 4095) if c not in used_ids][:1]
    if not candidates:
        raise FaultNotApplicable("wrong-vlan-id", f"no free VLAN id near {vlan.id}")

    before = str(vlan.id)
    vlan.id = rng.choice(candidates)
    return _made(
        "wrong-vlan-id",
        FaultCategory.VLAN,
        2,
        _WRONG_VLAN_HINT,
        target,
        f"{target.node}/{target.item}: VLAN id changed from {before} to {vlan.id}",
        before,
        str(vlan.id),
    )


# ── routing faults ────────────────────────────────────────────────────────────

_MISSING_ROUTE_HINT = "A route that should exist is missing from someone's table."


def _missing_route_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        if node.routing:
            for route in node.routing.static_routes:
                targets.append(FaultTarget(node=node.name, item=route.destination))
    return _sorted(targets)


def _missing_route_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    node = topo.get_node(target.node)
    if not node.routing:
        raise FaultNotApplicable("missing-static-route", f"node '{target.node}' has no routing config")
    route = next((r for r in node.routing.static_routes if r.destination == target.item), None)
    if route is None:
        raise FaultNotApplicable("missing-static-route", f"route to '{target.item}' not found on '{target.node}'")

    before = f"{route.destination} via {route.gateway}"
    node.routing.static_routes.remove(route)
    return _made(
        "missing-static-route",
        FaultCategory.ROUTING,
        1,
        _MISSING_ROUTE_HINT,
        target,
        f"{target.node}: static route '{before}' removed",
        before,
        "(removed)",
    )


_WRONG_GATEWAY_HINT = "A static route points at the wrong next hop."


def _wrong_gateway_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:
    node = topo.get_node(target.node)
    if not node.routing:
        raise FaultNotApplicable("wrong-static-gateway", f"node '{target.node}' has no routing config")
    route = next((r for r in node.routing.static_routes if r.destination == target.item), None)
    if route is None:
        raise FaultNotApplicable("wrong-static-gateway", f"route to '{target.item}' not found on '{target.node}'")

    try:
        gateway = ipaddress.IPv4Address(route.gateway)
    except ValueError as exc:
        raise FaultNotApplicable("wrong-static-gateway", f"gateway '{route.gateway}' is not IPv4") from exc

    base = int(gateway) & ~0xFF
    before = route.gateway
    for _ in range(32):
        candidate = ipaddress.IPv4Address(base | rng.randrange(2, 255))
        if candidate != gateway:
            route.gateway = str(candidate)
            break
    return _made(
        "wrong-static-gateway",
        FaultCategory.ROUTING,
        1,
        _WRONG_GATEWAY_HINT,
        target,
        f"{target.node}: route to {route.destination} now points via {route.gateway} (was via {before})",
        f"via {before}",
        f"via {route.gateway}",
    )


_OSPF_AREA_HINT = "Two OSPF neighbors refuse to form an adjacency."


def _ospf_area_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        if node.routing and node.routing.ospf_enabled:
            for area in node.routing.ospf_areas:
                targets.append(FaultTarget(node=node.name, item=area.id))
    return _sorted(targets)


def _ospf_area_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:
    node = topo.get_node(target.node)
    if not node.routing:
        raise FaultNotApplicable("ospf-wrong-area", f"node '{target.node}' has no routing config")
    area = next((a for a in node.routing.ospf_areas if a.id == target.item), None)
    if area is None:
        raise FaultNotApplicable("ospf-wrong-area", f"OSPF area '{target.item}' not found on '{target.node}'")

    before = area.id
    parts = area.id.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        last = int(parts[3])
        parts[3] = str((last + rng.randrange(1, 10)) % 256)
        if parts[3] == str(last):
            parts[3] = str((last + 1) % 256)
        area.id = ".".join(parts)
    else:
        area.id = f"{area.id}.1"
    return _made(
        "ospf-wrong-area",
        FaultCategory.ROUTING,
        2,
        _OSPF_AREA_HINT,
        target,
        f"{target.node}: OSPF area id changed from {before} to {area.id}",
        before,
        area.id,
    )


_RIP_VERSION_HINT = "A distance-vector protocol speaks a different dialect on each end."


def _rip_version_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        if node.routing and node.routing.rip and node.routing.rip.enabled:
            targets.append(FaultTarget(node=node.name))
    return _sorted(targets)


def _rip_version_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    node = topo.get_node(target.node)
    if not (node.routing and node.routing.rip):
        raise FaultNotApplicable("rip-version-mismatch", f"node '{target.node}' has no RIP config")

    rip = node.routing.rip
    before = f"v{rip.version}"
    rip.version = 1 if rip.version == 2 else 2  # type: ignore[assignment]
    return _made(
        "rip-version-mismatch",
        FaultCategory.ROUTING,
        2,
        _RIP_VERSION_HINT,
        target,
        f"{target.node}: RIP version changed from {before} to v{rip.version}",
        before,
        f"v{rip.version}",
    )


# ── system faults ─────────────────────────────────────────────────────────────

_IP_FORWARD_HINT = "A router receives packets but never passes them along."

_IP_FORWARD_KEY = "net.ipv4.ip_forward"


def _ip_forward_enabled(node_sysctl_forwarding: bool, custom: dict) -> bool:
    return node_sysctl_forwarding or str(custom.get(_IP_FORWARD_KEY, "0")) in ("1", "True", "true")


def _ip_forward_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        if node.role == NodeRole.ROUTER and _ip_forward_enabled(node.sysctl.ip_forwarding, node.sysctl.custom):
            targets.append(FaultTarget(node=node.name))
    return _sorted(targets)


def _ip_forward_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    node = topo.get_node(target.node)
    if not _ip_forward_enabled(node.sysctl.ip_forwarding, node.sysctl.custom):
        raise FaultNotApplicable("ip-forwarding-disabled", f"'{target.node}' does not have IP forwarding enabled")

    node.sysctl.ip_forwarding = False
    if _IP_FORWARD_KEY in node.sysctl.custom:
        node.sysctl.custom[_IP_FORWARD_KEY] = 0
    return _made(
        "ip-forwarding-disabled",
        FaultCategory.SYSTEM,
        1,
        _IP_FORWARD_HINT,
        target,
        f"{target.node}: IP forwarding disabled",
        "enabled",
        "disabled",
    )


# ── firewall faults ───────────────────────────────────────────────────────────

_FW_REMOVED_HINT = "A service that should be reachable is blocked by a firewall."
_FW_FLIPPED_HINT = "Traffic that should be allowed is being dropped by a firewall."


def _describe_rule(rule: InternalFirewallRule) -> str:
    parts = []
    if rule.proto:
        parts.append(f"{rule.proto}/{rule.dport}" if rule.dport else rule.proto)
    if rule.src:
        parts.append(f"from {rule.src}")
    if rule.dst:
        parts.append(f"to {rule.dst}")
    return " ".join(parts) or "any"


def _fw_accept_rule_targets(topo: InternalTopology) -> list[FaultTarget]:
    targets = []
    for node in topo.nodes:
        if node.services and node.services.firewall:
            for idx, rule in enumerate(node.services.firewall.rules):
                if rule.action == FirewallAction.ACCEPT:
                    targets.append(FaultTarget(node=node.name, item=str(idx)))
    return _sorted(targets)


def _fw_rule_at(
    topo: InternalTopology,
    target: FaultTarget,
    type_id: str,
) -> tuple[list[InternalFirewallRule], InternalFirewallRule, int]:
    node = topo.get_node(target.node)
    if not (node.services and node.services.firewall):
        raise FaultNotApplicable(type_id, f"node '{target.node}' has no firewall config")
    try:
        idx = int(target.item or "")
    except ValueError as exc:
        raise FaultNotApplicable(type_id, f"invalid rule index '{target.item}'") from exc
    rules = node.services.firewall.rules
    if idx < 0 or idx >= len(rules):
        raise FaultNotApplicable(type_id, f"rule index {idx} out of range on '{target.node}'")
    return rules, rules[idx], idx


def _fw_removed_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    rules, rule, idx = _fw_rule_at(topo, target, "firewall-accept-removed")
    desc = _describe_rule(rule)
    rules.pop(idx)
    return _made(
        "firewall-accept-removed",
        FaultCategory.FIREWALL,
        1,
        _FW_REMOVED_HINT,
        target,
        f"{target.node}: firewall accept rule for '{desc}' removed (default policy now drops it)",
        f"accept {desc}",
        "(removed)",
    )


def _fw_flipped_apply(topo: InternalTopology, target: FaultTarget, rng: random.Random) -> AppliedFault:  # noqa: ARG001
    _, rule, _ = _fw_rule_at(topo, target, "firewall-accept-flipped")
    desc = _describe_rule(rule)
    rule.action = FirewallAction.DROP
    return _made(
        "firewall-accept-flipped",
        FaultCategory.FIREWALL,
        2,
        _FW_FLIPPED_HINT,
        target,
        f"{target.node}: firewall rule for '{desc}' flipped from accept to drop",
        f"accept {desc}",
        f"drop {desc}",
    )


# ── registration ──────────────────────────────────────────────────────────────


def register_builtin_faults(catalog: FaultCatalog) -> None:
    """Register the built-in fault definitions on *catalog*."""

    for definition in (
        FaultDefinition(
            "wrong-ip-address",
            FaultCategory.ADDRESSING,
            1,
            "Change an interface IP to a wrong address in the same subnet",
            _WRONG_IP_HINT,
            _wrong_ip_targets,
            _wrong_ip_apply,
        ),
        FaultDefinition(
            "wrong-prefix-length",
            FaultCategory.ADDRESSING,
            2,
            "Grow an interface's prefix length so the subnets no longer match",
            _WRONG_PREFIX_HINT,
            _wrong_prefix_targets,
            _wrong_prefix_apply,
        ),
        FaultDefinition(
            "duplicate-ip",
            FaultCategory.ADDRESSING,
            2,
            "Give one link endpoint the same IP as its peer",
            _DUPLICATE_IP_HINT,
            _duplicate_ip_targets,
            _duplicate_ip_apply,
        ),
        FaultDefinition(
            "interface-unconfigured",
            FaultCategory.INTERFACE,
            1,
            "Suppress config generation for one interface",
            _IFACE_UNCONFIGURED_HINT,
            _iface_unconfigured_targets,
            _iface_unconfigured_apply,
        ),
        FaultDefinition(
            "wrong-vlan-id",
            FaultCategory.VLAN,
            2,
            "Change a VLAN id so tagging no longer matches",
            _WRONG_VLAN_HINT,
            _wrong_vlan_targets,
            _wrong_vlan_apply,
        ),
        FaultDefinition(
            "missing-static-route",
            FaultCategory.ROUTING,
            1,
            "Delete a static route",
            _MISSING_ROUTE_HINT,
            _missing_route_targets,
            _missing_route_apply,
        ),
        FaultDefinition(
            "wrong-static-gateway",
            FaultCategory.ROUTING,
            1,
            "Point a static route at a wrong next hop",
            _WRONG_GATEWAY_HINT,
            _missing_route_targets,
            _wrong_gateway_apply,
        ),
        FaultDefinition(
            "ospf-wrong-area",
            FaultCategory.ROUTING,
            2,
            "Move one OSPF area id so adjacencies fail",
            _OSPF_AREA_HINT,
            _ospf_area_targets,
            _ospf_area_apply,
        ),
        FaultDefinition(
            "rip-version-mismatch",
            FaultCategory.ROUTING,
            2,
            "Flip the RIP version on one node",
            _RIP_VERSION_HINT,
            _rip_version_targets,
            _rip_version_apply,
        ),
        FaultDefinition(
            "ip-forwarding-disabled",
            FaultCategory.SYSTEM,
            1,
            "Disable IP forwarding on a router",
            _IP_FORWARD_HINT,
            _ip_forward_targets,
            _ip_forward_apply,
        ),
        FaultDefinition(
            "firewall-accept-removed",
            FaultCategory.FIREWALL,
            1,
            "Remove a firewall accept rule so the default policy drops the traffic",
            _FW_REMOVED_HINT,
            _fw_accept_rule_targets,
            _fw_removed_apply,
        ),
        FaultDefinition(
            "firewall-accept-flipped",
            FaultCategory.FIREWALL,
            2,
            "Flip a firewall accept rule to drop",
            _FW_FLIPPED_HINT,
            _fw_accept_rule_targets,
            _fw_flipped_apply,
        ),
    ):
        catalog.register(definition)
