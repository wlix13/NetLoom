from collections.abc import Iterable
from pathlib import Path

from models.internal import InternalNode, InternalTopology

from .engine import TemplateSet, make_env, register_template_set


HOSTNAME_J2 = "{{ node.name }}\n"

NETWORK_J2 = """\
[Match]
Name={{ iface.name }}

[Link]
# MTU={{ iface.mtu if iface.mtu else 1500 }}

[Network]
{% if iface.dhcp -%}
DHCP=yes
{% else -%}
LinkLocalAddressing=no
{% for a in iface.addresses -%}
Address={{ a }}
{% endfor -%}
{% if iface.gateway -%}
Gateway={{ iface.gateway }}
{% endif -%}
{% endif %}
"""

ROUTES_J2 = """\
{% for r in routes -%}
[Route]
Destination={{ r.to }}
Gateway={{ r.via }}
{% endfor %}
"""


def _iface_context(node: InternalNode, topo: InternalTopology):
    for nic in node.nics:
        net = topo.net(nic.network_id) if nic.network_id else None
        yield {
            "name": nic.name,
            "mtu": net.mtu if net else None,
            "dhcp": bool(net.dhcp if net else False),
            "addresses": [str(a) for a in (nic.addresses or [])],
            "gateway": node.mgmt.gw if (node.mgmt.net_id == nic.network_id and node.mgmt.gw) else None,
        }


def _routes_context(node: InternalNode):
    return []


def render_networkd(node: InternalNode, topo: InternalTopology, outdir: Path, extra_search: Iterable[str | Path] = ()):
    outdir.mkdir(parents=True, exist_ok=True)
    netdir = outdir / "etc" / "systemd" / "network"
    netdir.mkdir(parents=True, exist_ok=True)

    env = make_env(extra_search)
    hostname_t = env.from_string(HOSTNAME_J2)
    network_t = env.from_string(NETWORK_J2)
    routes_t = env.from_string(ROUTES_J2)

    # hostname
    (outdir / "etc").mkdir(parents=True, exist_ok=True)
    (outdir / "etc" / "hostname").write_text(hostname_t.render(node=node), encoding="utf-8")

    # per-interface .network
    for iface in _iface_context(node, topo):
        fname = f"10-{iface['name']}.network"
        (netdir / fname).write_text(network_t.render(iface=iface), encoding="utf-8")

    # optional routes
    routes = _routes_context(node)
    if routes:
        (netdir / "10-routes.network").write_text(routes_t.render(routes=routes), encoding="utf-8")


def register():
    register_template_set(
        TemplateSet(
            name="networkd",
            render=lambda ctx, out: render_networkd(ctx["node"], ctx["topology"], out),
        ),
    )


register()
