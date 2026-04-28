"""Abstract base class for hypervisor drivers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click


if TYPE_CHECKING:
    from netloom.core.enums import VMState
    from netloom.models.internal import InternalNode, InternalTopology


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    """Describes how to reach a VM's console or management interface."""

    protocol: str  # e.g. "tcp-serial", "ssh", "vnc", "spice"
    host: str
    port: int

    @property
    def uri(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


class BaseHypervisorDriver(ABC):
    """Hypervisor-specific VM operations.

    The controller orchestrates *what* to do; the driver knows *how* to do
    it for a specific hypervisor.  All VirtualBox-specific logic lives in
    ``VBoxHypervisorDriver``; alternative drivers (QEMU, libvirt, …) implement
    the same interface without touching any core code.
    """

    @abstractmethod
    def list_vms(self) -> dict[str, str]:
        """Return ``{name: uuid}`` for all VMs known to this hypervisor."""

    @abstractmethod
    def get_vm_state(self, name: str) -> VMState | None:
        """Return the current VM state, or ``None`` if the VM does not exist."""

    @abstractmethod
    def get_connection_info(self, name: str) -> ConnectionInfo | None:
        """Return connection details for console/serial access, or ``None`` if unavailable."""

    @abstractmethod
    def ensure_base_vm(self, topo: InternalTopology) -> None:
        """Import the base VM image (if absent) and take an initial snapshot."""

    @abstractmethod
    def create_node_vm(self, node: InternalNode, topo: InternalTopology, node_idx: int) -> None:
        """Clone, configure hardware, wire NICs and attach a config medium for *node*."""

    @abstractmethod
    def inject_configs(self, node: InternalNode, config_dir: Path) -> None:
        """Copy files from *config_dir* into the VM's config medium."""

    @abstractmethod
    def extract_configs(self, node: InternalNode, dest_dir: Path) -> list[Path]:
        """Pull files from the VM's config medium into *dest_dir*.  Returns copied paths."""

    @abstractmethod
    def start_vm(self, name: str) -> None:
        """Boot the named VM."""

    @abstractmethod
    def stop_vm(self, name: str) -> None:
        """Send a graceful shutdown signal to the named VM."""

    @abstractmethod
    def destroy_vm(self, name: str) -> bool:
        """Power off and unregister the named VM.  Returns ``True`` on success."""

    @abstractmethod
    def destroy_base_vm(self) -> None:
        """Power off and unregister the hypervisor's base/template VM."""

    @classmethod
    def cli_options(cls) -> list[click.Option]:
        """Return driver-specific Click options to inject into the main CLI group."""
        return []

    @classmethod
    def from_cli_params(cls, console: object | None = None, **kwargs: object) -> BaseHypervisorDriver:
        """Construct a driver instance from parsed CLI option values.

        Subclasses override this to build their settings from *kwargs*.
        Default calls ``cls()`` (no-args constructor).
        """
        return cls()  # type: ignore[call-arg]
