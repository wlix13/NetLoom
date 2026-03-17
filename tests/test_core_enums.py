"""Tests for netloom.core.enums module."""

import pytest

from netloom.core.enums import (
    FirewallAction,
    FirewallImpl,
    InterfaceKind,
    NicModel,
    NodeRole,
    ParavirtProvider,
    RoutingEngine,
    TemplateSet,
    TunnelType,
    VBoxChipset,
    VMControlAction,
    VMStartType,
    VMState,
)


class TestRoutingEngine:
    """Test RoutingEngine enum."""

    def test_values(self):
        assert RoutingEngine.BIRD == "bird"
        assert RoutingEngine.FRR == "frr"
        assert RoutingEngine.NONE == "none"

    def test_str_conversion(self):
        assert str(RoutingEngine.BIRD) == "bird"
        assert str(RoutingEngine.FRR) == "frr"


class TestInterfaceKind:
    """Test InterfaceKind enum."""

    def test_values(self):
        assert InterfaceKind.PHYSICAL == "physical"
        assert InterfaceKind.LOOPBACK == "loopback"


class TestNodeRole:
    """Test NodeRole enum."""

    def test_values(self):
        assert NodeRole.ROUTER == "router"
        assert NodeRole.SWITCH == "switch"
        assert NodeRole.HOST == "host"

    def test_all_roles_present(self):
        """Ensure common node roles are available."""
        roles = {NodeRole.ROUTER, NodeRole.SWITCH, NodeRole.HOST}
        assert len(roles) == 3


class TestTunnelType:
    """Test TunnelType enum."""

    def test_values(self):
        assert TunnelType.IPIP == "ipip"
        assert TunnelType.GRE == "gre"
        assert TunnelType.SIT == "sit"


class TestFirewallAction:
    """Test FirewallAction enum."""

    def test_values(self):
        assert FirewallAction.ACCEPT == "accept"
        assert FirewallAction.DROP == "drop"
        assert FirewallAction.REJECT == "reject"


class TestFirewallImpl:
    """Test FirewallImpl enum."""

    def test_values(self):
        assert FirewallImpl.NFTABLES == "nftables"


class TestNicModel:
    """Test NicModel enum with vbox_type property."""

    def test_values(self):
        assert NicModel.VIRTIO == "virtio"
        assert NicModel.E1000 == "e1000"
        assert NicModel.RTL8139 == "rtl8139"

    def test_vbox_type_virtio(self):
        """Test VirtualBox type mapping for virtio."""
        assert NicModel.VIRTIO.vbox_type == "virtio"

    def test_vbox_type_e1000(self):
        """Test VirtualBox type mapping for e1000."""
        assert NicModel.E1000.vbox_type == "82540EM"

    def test_vbox_type_rtl8139(self):
        """Test VirtualBox type mapping for rtl8139."""
        assert NicModel.RTL8139.vbox_type == "Am79C973"

    def test_all_models_have_vbox_type(self):
        """Ensure all NIC models have a vbox_type mapping."""
        for model in NicModel:
            assert isinstance(model.vbox_type, str)
            assert len(model.vbox_type) > 0


class TestVBoxChipset:
    """Test VBoxChipset enum."""

    def test_values(self):
        assert VBoxChipset.PIIX3 == "piix3"
        assert VBoxChipset.ICH9 == "ich9"


class TestParavirtProvider:
    """Test ParavirtProvider enum."""

    def test_values(self):
        assert ParavirtProvider.DEFAULT == "default"
        assert ParavirtProvider.LEGACY == "legacy"
        assert ParavirtProvider.MINIMAL == "minimal"
        assert ParavirtProvider.HYPERV == "hyperv"
        assert ParavirtProvider.KVM == "kvm"
        assert ParavirtProvider.NONE == "none"

    def test_all_providers_present(self):
        """Ensure all paravirt providers are available."""
        providers = list(ParavirtProvider)
        assert len(providers) == 6


class TestVMState:
    """Test VMState enum."""

    def test_values(self):
        assert VMState.RUNNING == "running"
        assert VMState.POWEROFF == "poweroff"
        assert VMState.SAVED == "saved"
        assert VMState.ABORTED == "aborted"


class TestVMControlAction:
    """Test VMControlAction enum."""

    def test_values(self):
        assert VMControlAction.ACPI_POWER_BUTTON == "acpipowerbutton"
        assert VMControlAction.POWEROFF == "poweroff"


class TestVMStartType:
    """Test VMStartType enum."""

    def test_values(self):
        assert VMStartType.HEADLESS == "headless"
        assert VMStartType.GUI == "gui"
        assert VMStartType.SDL == "sdl"


class TestTemplateSet:
    """Test TemplateSet enum."""

    def test_values(self):
        assert TemplateSet.NETWORKD == "networkd"
        assert TemplateSet.BIRD == "bird"
        assert TemplateSet.NFTABLES == "nftables"
        assert TemplateSet.WIREGUARD == "wireguard"

    def test_all_template_sets(self):
        """Ensure all template sets are defined."""
        templates = list(TemplateSet)
        assert len(templates) == 4