from enum import StrEnum


class RoutingEngine(StrEnum):
    BIRD = "bird"
    FRR = "frr"
    NONE = "none"


class InterfaceKind(StrEnum):
    PHYSICAL = "physical"
    LOOPBACK = "loopback"


class NodeRole(StrEnum):
    ROUTER = "router"
    SWITCH = "switch"
    HOST = "host"


class TunnelType(StrEnum):
    IPIP = "ipip"
    GRE = "gre"
    SIT = "sit"


class FirewallAction(StrEnum):
    ACCEPT = "accept"
    DROP = "drop"
    REJECT = "reject"


class FirewallImpl(StrEnum):
    NFTABLES = "nftables"


class NicModel(StrEnum):
    """Guest-visible NIC model; each hypervisor driver maps it to its own adapter type."""

    VIRTIO = "virtio"
    E1000 = "e1000"
    RTL8139 = "rtl8139"


class VBoxChipset(StrEnum):
    PIIX3 = "piix3"
    ICH9 = "ich9"


class ParavirtProvider(StrEnum):
    DEFAULT = "default"
    LEGACY = "legacy"
    MINIMAL = "minimal"
    HYPERV = "hyperv"
    KVM = "kvm"
    NONE = "none"


class VMState(StrEnum):
    RUNNING = "running"
    POWEROFF = "poweroff"
    SAVED = "saved"
    ABORTED = "aborted"


class VMControlAction(StrEnum):
    ACPI_POWER_BUTTON = "acpipowerbutton"
    POWEROFF = "poweroff"


class VMStartType(StrEnum):
    HEADLESS = "headless"
    GUI = "gui"
    SDL = "sdl"
