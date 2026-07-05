"""Config generation against the real example topology and real templates."""

from pathlib import Path

import pytest

from netloom.core.errors import TopologyError


pytestmark = pytest.mark.component


def _config_dir(internal, name: str) -> Path:
    return Path(internal.get_node(name).config_dir)


def test_rendered_sets_detects_all_families(app, internal):
    assert app.config.rendered_sets(internal) == {"networkd", "bird", "nftables", "wireguard"}


def test_generate_writes_expected_files(app, internal):
    app.config.generate(internal)

    r1 = _config_dir(internal, "R1")
    assert (r1 / "etc" / "hostname").is_file()
    eth1 = (r1 / "etc" / "systemd" / "network" / "10-eth1.network").read_text(encoding="utf-8")
    assert "Address=10.0.12.1/24" in eth1
    assert (r1 / "etc" / "bird" / "bird.conf").is_file(), "R1 uses the bird engine"

    r3_static = (_config_dir(internal, "R3") / "etc" / "bird" / "conf.d" / "static.conf").read_text(encoding="utf-8")
    assert "route 0.0.0.0/0 via 10.0.23.1;" in r3_static


def test_generate_single_node_keeps_full_topology_context(app, internal):
    app.config.generate(internal, node_name="R1")

    assert _config_dir(internal, "R1").is_dir()
    r2_dir = _config_dir(internal, "R2")
    assert not r2_dir.exists() or not any(r2_dir.rglob("*")), "only R1 should have been rendered"


def test_generate_unknown_node_raises(app, internal):
    with pytest.raises(TopologyError):
        app.config.generate(internal, node_name="ghost")


def test_firewall_config_only_where_configured(app, internal):
    app.config.generate(internal)

    with_firewall = [node.name for node in internal.nodes if node.services and node.services.firewall]
    assert with_firewall, "example topology should have at least one firewalled node"
    for node in internal.nodes:
        nft = _config_dir(internal, node.name) / "etc" / "nftables.conf"
        if node.name in with_firewall:
            assert nft.is_file(), f"{node.name} should have nftables.conf"
        else:
            assert not nft.exists(), f"{node.name} should not have nftables.conf"
