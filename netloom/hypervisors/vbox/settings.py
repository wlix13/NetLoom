"""VirtualBox-specific settings and UART configuration."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UartConfig:
    """Parsed UART configuration from VBoxManage showvminfo output."""

    enabled: bool
    io_base: str = "0x03f8"
    irq: int = 4
    mode: str = "disconnected"
    endpoint: str = ""


@dataclass
class VBoxSettings:
    """Settings for the VirtualBox hypervisor driver."""

    basefolder: Path = field(default_factory=lambda: Path.cwd() / ".labs_vms")
    ova_path: Path | None = None
    base_vm_name: str = "Labs-Base"
    snapshot_name: str = "golden"
    configdrive_mb: int = 128
    controller_name: str = "Disks"
