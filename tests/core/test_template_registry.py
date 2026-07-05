"""Template registry: registration, lookup and per-node conditions."""

import pytest

from netloom.core.enums import NodeRole
from netloom.models.internal import InternalNode
from netloom.templates.registry import TemplateRegistry, TemplateSetDescriptor


@pytest.mark.unit
def test_templates_subdir_defaults_to_name():
    desc = TemplateSetDescriptor(name="networkd", output_paths={})
    assert desc.templates_subdir == "networkd"

    custom = TemplateSetDescriptor(name="fw", output_paths={}, templates_subdir="nftables")
    assert custom.templates_subdir == "nftables"


@pytest.mark.unit
def test_register_get_names_sorted():
    registry = TemplateRegistry()
    registry.register(TemplateSetDescriptor(name="zeta", output_paths={}))
    registry.register(TemplateSetDescriptor(name="alpha", output_paths={}))

    assert registry.names() == ["alpha", "zeta"]
    assert registry.get("zeta") is not None
    assert registry.get("missing") is None


@pytest.mark.unit
def test_iter_applicable_respects_condition():
    node = InternalNode(name="R1", role=NodeRole.ROUTER)
    registry = TemplateRegistry()
    registry.register(TemplateSetDescriptor(name="always", output_paths={}))
    registry.register(
        TemplateSetDescriptor(name="never", output_paths={}, condition=lambda _n: False),
    )
    registry.register(
        TemplateSetDescriptor(name="routers", output_paths={}, condition=lambda n: n.role == NodeRole.ROUTER),
    )

    names = {desc.name for desc in registry.iter_applicable(node)}
    assert names == {"always", "routers"}
