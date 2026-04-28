"""Infrastructure controller: orchestrates VM lifecycle via the hypervisor driver."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from netloom.core.controller import BaseController
from netloom.core.enums import VMState
from netloom.hypervisors.base import ConnectionInfo


if TYPE_CHECKING:
    from netloom.core.application import Application  # noqa: F401
    from netloom.models.internal import InternalTopology


@dataclass(frozen=True, slots=True)
class NodeStatus:
    """Live status for a topology node's VM."""

    name: str
    state: str | None
    connection: ConnectionInfo | None


class InfrastructureController(BaseController["Application"]):
    """Orchestrates VM lifecycle through the registered hypervisor driver.

    All hypervisor-specific operations are delegated to ``self.app.hypervisor``.
    This controller only handles orchestration logic (order, loops, fallbacks).
    """

    def get_vm_state(self, vm_name: str) -> str | None:
        """Return ``VMState`` string or ``None`` if the VM does not exist."""
        return self.app.hypervisor.get_vm_state(vm_name)  # type: ignore[return-value]

    def get_connection_info(self, vm_name: str) -> ConnectionInfo | None:
        """Return connection details for console access, or ``None``."""
        return self.app.hypervisor.get_connection_info(vm_name)

    def status(self, topo: InternalTopology, node_name: str | None = None) -> list[NodeStatus]:
        """Collect live status for every node in the topology."""
        result: list[NodeStatus] = []
        for node in topo.nodes:
            if node_name and node.name != node_name:
                continue
            state = self.get_vm_state(node.name)
            connection = self.get_connection_info(node.name) if state == VMState.RUNNING else None
            result.append(NodeStatus(name=node.name, state=state, connection=connection))
        return result

    def init(self, topo: InternalTopology, workdir: str | Path) -> None:
        """Import base image and create workdir structure."""
        self.app.hypervisor.ensure_base_vm(topo)
        Path(workdir).mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "configs").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "saved").mkdir(parents=True, exist_ok=True)

    def create(self, topo: InternalTopology) -> None:
        """Create node VMs and attach config media."""
        driver = self.app.hypervisor
        driver.ensure_base_vm(topo)
        for node_idx, node in enumerate(topo.nodes, start=1):
            driver.create_node_vm(node, topo, node_idx)

    def start(self, topo: InternalTopology) -> None:
        """Boot all VMs in the topology."""
        for node in topo.nodes:
            self.app.hypervisor.start_vm(node.name)

    def stop(self, topo: InternalTopology) -> None:
        """Send graceful shutdown signals to all running VMs."""
        driver = self.app.hypervisor
        for node in topo.nodes:
            state = driver.get_vm_state(node.name)
            if state is None:
                self.console.print(f"[yellow]VM '{node.name}' not found, skipping.[/yellow]")
                continue
            if state != VMState.RUNNING:
                self.console.print(f"[yellow]VM '{node.name}' is not running (state: {state}), skipping.[/yellow]")
                continue
            try:
                driver.stop_vm(node.name)
                self.console.print(f"[green]Sent ACPI power button to '{node.name}'[/green]")
            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]Failed to stop '{node.name}': {e}[/red]")

    def destroy(self, topo: InternalTopology, *, destroy_base: bool = False) -> None:
        """Power off and unregister all topology VMs."""
        driver = self.app.hypervisor
        for node in topo.nodes:
            ok = driver.destroy_vm(node.name)
            if ok:
                self.console.print(f"[green]Destroyed VM '{node.name}'[/green]")

        if destroy_base:
            driver.destroy_base_vm()
