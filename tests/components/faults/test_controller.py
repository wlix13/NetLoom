"""Faults controller: spec resolution, application, answer key round-trip."""

import pytest
import yaml

from netloom.components.faults.errors import (
    FaultNotApplicable,
    NoFaultsApplied,
    NotEnoughFaultCandidates,
    UnknownFaultType,
)
from netloom.components.faults.models import FaultCategory, FaultSpec, FaultSpecEntry


pytestmark = pytest.mark.component


def _write_spec(tmp_path, data) -> str:
    path = tmp_path / "spec.faults.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


def test_generate_spec_is_reproducible(app, internal):
    first = app.faults.generate_spec(internal, count=4, seed=42)
    second = app.faults.generate_spec(internal, count=4, seed=42)
    assert first.model_dump() == second.model_dump()
    assert len(first.faults) == 4
    assert all(entry.node for entry in first.faults), "generated entries must be explicit"


def test_generate_spec_respects_category_filter(app, internal):
    spec = app.faults.generate_spec(internal, count=2, seed=7, categories=[FaultCategory.ROUTING])
    for entry in spec.faults:
        definition = app.faults.catalog.get(entry.type)
        assert definition.category == FaultCategory.ROUTING


def test_apply_spec_mutates_topology_and_writes_answer_key(app, internal, tmp_path):
    spec_path = _write_spec(
        tmp_path,
        {"seed": 1, "faults": [{"type": "duplicate-ip", "node": "R2", "target": "eth1"}]},
    )

    r1_ip = next(i.ip for i in internal.get_node("R1").interfaces if i.name == "eth1")
    report = app.faults.apply_spec(internal, spec_path)

    r2_ip = next(i.ip for i in internal.get_node("R2").interfaces if i.name == "eth1")
    assert r2_ip == r1_ip, "duplicate-ip must copy the peer address"
    assert len(report.faults) == 1
    assert app.faults.answer_key_path.is_file()


def test_reveal_round_trips_the_report(app, internal, tmp_path):
    spec_path = _write_spec(tmp_path, {"seed": 5, "faults": [{"type": "random", "count": 3}]})
    written = app.faults.apply_spec(internal, spec_path)

    loaded = app.faults.reveal()
    assert loaded.model_dump() == written.model_dump()


def test_reveal_without_deploy_raises(app):
    with pytest.raises(NoFaultsApplied):
        app.faults.reveal()


def test_unknown_fault_type_raises(app, internal, tmp_path):
    spec_path = _write_spec(tmp_path, {"faults": [{"type": "flux-capacitor"}]})
    with pytest.raises(UnknownFaultType):
        app.faults.apply_spec(internal, spec_path)


def test_random_overallocation_raises(app, internal):
    probe = FaultSpec(seed=1, faults=[FaultSpecEntry(type="random", count=99)])
    with pytest.raises(NotEnoughFaultCandidates):
        app.faults.resolve(internal, probe)


def test_explicit_entry_on_wrong_node_raises(app, internal, tmp_path):
    spec_path = _write_spec(tmp_path, {"faults": [{"type": "missing-static-route", "node": "SW1"}]})
    with pytest.raises(FaultNotApplicable):
        app.faults.apply_spec(internal, spec_path)


def test_no_two_faults_share_a_target(app, internal):
    spec = FaultSpec(seed=3, faults=[FaultSpecEntry(type="random", count=6)])
    plan = app.faults.resolve(internal, spec)
    pairs = [(target.node, target.item) for _, target in plan]
    assert len(pairs) == len(set(pairs)), f"duplicate targets in plan: {pairs}"


def test_broken_config_render_differs_from_clean(app, internal, tmp_path):
    """End-to-end: faulted topology renders different configs than the clean one."""
    from netloom.models.common import load_topology
    from netloom.models.converters import convert_topology
    from tests.conftest import EXAMPLE_TOPOLOGY

    clean_dir = tmp_path / "clean"
    clean_topo = convert_topology(load_topology(EXAMPLE_TOPOLOGY), workdir=clean_dir)
    app.config.generate(clean_topo)

    spec_path = _write_spec(
        tmp_path,
        {"seed": 1, "faults": [{"type": "wrong-ip-address", "node": "R1", "target": "eth1"}]},
    )
    app.faults.apply_spec(internal, spec_path)
    app.config.generate(internal)

    from pathlib import Path

    clean_dir_str = clean_topo.get_node("R1").config_dir
    broken_dir_str = internal.get_node("R1").config_dir
    assert clean_dir_str and broken_dir_str

    rel = ("etc", "systemd", "network", "10-eth1.network")
    clean_file = Path(clean_dir_str).joinpath(*rel)
    broken_file = Path(broken_dir_str).joinpath(*rel)
    assert clean_file.read_text(encoding="utf-8") != broken_file.read_text(encoding="utf-8")
