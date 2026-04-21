"""Infrastructure controller for VirtualBox VM lifecycle management."""

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.controller import BaseController
from ..core.enums import VMControlAction, VMState
from ..core.vbox import VBoxManage
from ..data import ConfigDrive, format_fat16


if TYPE_CHECKING:
    from ..core.application import Application
    from ..core.vbox import UartConfig, VBoxSettings
    from ..models.internal import InternalNode, InternalTopology


class InfrastructureController(BaseController["Application"]):
    """Orchestrates VirtualBox VM lifecycle: import, clone, start, stop, destroy."""

    def __init__(self, app: "Application") -> None:
        super().__init__(app)
        self._vbox = VBoxManage()

    @property
    def _s(self) -> "VBoxSettings":
        """Shortcut to ``app.vbox_settings``."""

        return self.app.vbox_settings

    def _vm_dir(self, node: "InternalNode") -> Path:
        """Get the VM directory for a node."""

        return self._s.basefolder / node.name

    def _cfg_vmdk(self, node: "InternalNode") -> Path:
        """Get the config-drive VMDK path for a node."""

        return self._vm_dir(node) / f"{node.name}-configdrive.vmdk"

    def _has_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        return snapshot_name in self._vbox.list_snapshots(vm_name)

    def _get_vm_state(self, vm_name: str) -> str | None:
        info = self._vbox.show_vm_info(vm_name)
        if not info:
            return None
        for line in info.splitlines():
            if line.startswith("VMState="):
                return line.split("=", 1)[1].strip('"')

        return None

    def _cleanup_orphaned_base_media(self) -> None:
        """Remove any orphaned disk media from a previous failed import."""

        output = self._vbox.list_hdds()

        disks_info: dict[str, dict[str, str]] = {}
        current_uuid = None
        current_parent = None
        current_location = None

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("UUID:"):
                current_uuid = line.split(":", 1)[1].strip()
            elif line.startswith("Parent UUID:"):
                current_parent = line.split(":", 1)[1].strip()
            elif line.startswith("Location:"):
                current_location = line.split(":", 1)[1].strip()
                if current_uuid and current_location:
                    disks_info[current_uuid] = {
                        "parent": current_parent or "base",
                        "location": current_location,
                    }
                current_uuid = None
                current_parent = None
                current_location = None

        orphaned_roots = set()
        for uuid, info in disks_info.items():
            loc_lower = info["location"].lower()
            if str(self._s.basefolder).lower() in loc_lower and self._s.base_vm_name.lower() in loc_lower:
                orphaned_roots.add(uuid)

        def get_descendants(uuids: set[str]) -> list[str]:
            descendants = []
            queue = list(uuids)
            while queue:
                current = queue.pop(0)
                descendants.append(current)
                for child_uuid, child_info in disks_info.items():
                    if child_info["parent"] == current:
                        queue.append(child_uuid)
            return descendants

        to_delete = []
        for root in orphaned_roots:
            family = get_descendants({root})
            for item in reversed(family):
                if item not in to_delete:
                    to_delete.append(item)

        for disk_uuid in to_delete:
            self.console.print(f"[yellow]Cleaning up orphaned disk: {disk_uuid}[/yellow]")
            try:
                self._vbox.close_medium(disk_uuid, delete=True)
            except subprocess.CalledProcessError:
                try:
                    self._vbox.close_medium(disk_uuid)
                except subprocess.CalledProcessError:
                    self.console.print(f"[dim]Could not cleanup disk {disk_uuid}, continuing...[/dim]")

        if self._s.basefolder.exists():
            for folder in self._s.basefolder.rglob(self._s.base_vm_name):
                if folder.is_dir():
                    self.console.print(f"[yellow]Removing leftover folder: {folder}[/yellow]")
                    shutil.rmtree(folder, ignore_errors=True)

    def _ensure_base_imported(self, topo: "InternalTopology") -> None:
        """Ensure the base VM is imported from OVA and has a snapshot."""

        if self._s.base_vm_name in self._vbox.list_vms():
            if not self._has_snapshot(self._s.base_vm_name, self._s.snapshot_name):
                self._vbox.take_snapshot(self._s.base_vm_name, self._s.snapshot_name)
            return

        if not self._s.ova_path:
            raise SystemExit("Base VM not found and --ova is not provided to import it.")

        self._cleanup_orphaned_base_media()
        self._s.basefolder.mkdir(parents=True, exist_ok=True)

        self._vbox.import_ova(self._s.ova_path, self._s.base_vm_name, self._s.basefolder)

        vbox = topo.vbox
        self._vbox.modify_vm(
            self._s.base_vm_name,
            "--chipset",
            vbox.chipset,
            "--ioapic",
            "on" if vbox.ioapic else "off",
            "--hpet",
            "on" if vbox.hpet else "off",
            "--paravirtprovider",
            vbox.paravirt_provider,
        )

        if not self._has_snapshot(self._s.base_vm_name, self._s.snapshot_name):
            self._vbox.take_snapshot(self._s.base_vm_name, self._s.snapshot_name)

    def _ensure_sata_storage_controller(self, vm_name: str) -> None:
        """Ensure the VM has a SATA storage controller."""

        info = self._vbox.show_vm_info(vm_name)
        if f'storagecontrollername0="{self._s.controller_name.lower()}"' in info.lower():
            return

        self._vbox.storage_ctl(vm_name, self._s.controller_name, add="sata", controller="IntelAhci")

    def _modify_vm_hw(self, node: "InternalNode", topo: "InternalTopology", uart: "UartConfig", node_idx: int) -> None:
        """Configure VM hardware (RAM, CPU, chipset, boot order)."""

        vbox = topo.get_vbox_settings(node)

        if not uart.enabled:
            uart_args = ["--uart1", "off"]
        else:
            uart_args = ["--uart1", uart.io_base, str(uart.irq), "--uartmode1"]
            mode = uart.mode
            endpoint = uart.endpoint

            if mode == "tcpserver":
                if not endpoint.isdigit():
                    raise ValueError(
                        f"UART endpoint for tcpserver mode must be an integer port number, but got: '{endpoint}'"
                    )
                endpoint = str(int(endpoint) + node_idx)
            elif mode == "server":
                endpoint = f"{endpoint}-{node.name}"

            uart_args.extend([mode, endpoint])

        self._vbox.modify_vm(
            node.name,
            "--memory",
            str(node.resources.ram_mb),
            "--cpus",
            str(node.resources.cpu),
            "--chipset",
            vbox.chipset,
            "--ioapic",
            "on" if vbox.ioapic else "off",
            "--hpet",
            "on" if vbox.hpet else "off",
            "--paravirtprovider",
            vbox.paravirt_provider,
            *uart_args,
            "--boot1",
            "disk",
            "--boot2",
            "none",
            "--boot3",
            "none",
            "--boot4",
            "none",
            "--audio-enabled",
            "off",
            "--audio-in",
            "off",
            "--audio-out",
            "off",
            "--audio-driver",
            "none",
        )

    def _wire_nics(self, node: "InternalNode") -> None:
        """Wire network interfaces to VirtualBox internal networks."""

        for i in range(1, 37):
            self._vbox.modify_vm(node.name, f"--nic{i}", "none")

        for iface in node.interfaces:
            if iface.vbox_nic_index is None:
                continue

            idx = iface.vbox_nic_index
            nic_type = node.nic_model.vbox_type
            mac_address = iface.mac_address.replace(":", "") if iface.mac_address else None

            if iface.nat:
                args = [
                    f"--nic{idx}",
                    "nat",
                    f"--nictype{idx}",
                    nic_type,
                    f"--cableconnected{idx}",
                    "on",
                ]
                if mac_address:
                    args.extend([f"--macaddress{idx}", mac_address])

            elif iface.network is not None:
                args = [
                    f"--nic{idx}",
                    "intnet",
                    f"--intnet{idx}",
                    iface.network,
                    f"--nictype{idx}",
                    nic_type,
                    f"--cableconnected{idx}",
                    "on",
                    f"--nicpromisc{idx}",
                    "allow-all",
                ]
                if mac_address:
                    args.extend([f"--macaddress{idx}", mac_address])

            else:
                # Null mode: NIC hardware present in guest but no internet connectivity.
                args = [
                    f"--nic{idx}",
                    "null",
                    f"--nictype{idx}",
                    nic_type,
                    f"--cableconnected{idx}",
                    "on",
                ]
                if mac_address:
                    args.extend([f"--macaddress{idx}", mac_address])

            self._vbox.modify_vm(node.name, *args)

    def init(self, topo: "InternalTopology", workdir: str | Path) -> None:
        """Initialize: import base OVA and create workdir structure."""

        self._ensure_base_imported(topo)
        Path(workdir).mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "configs").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "saved").mkdir(parents=True, exist_ok=True)

    def create(self, topo: "InternalTopology") -> None:
        """Create linked clones and attach config-drives."""

        self._ensure_base_imported(topo)
        existing_vms = self._vbox.list_vms()
        uart = self._vbox.get_uart_config(self._s.base_vm_name)

        for node_idx, node in enumerate(topo.nodes, start=1):
            vm_dir = self._vm_dir(node)
            vm_dir.mkdir(parents=True, exist_ok=True)

            if node.name not in existing_vms:
                self._vbox.clone_vm(
                    self._s.base_vm_name,
                    snapshot=self._s.snapshot_name,
                    name=node.name,
                    basefolder=self._s.basefolder,
                )

            self._modify_vm_hw(node, topo, uart, node_idx)
            self._wire_nics(node)

            cfg_vmdk = self._cfg_vmdk(node)
            if not cfg_vmdk.exists():
                try:
                    self._vbox.close_medium(cfg_vmdk.as_posix())
                except subprocess.CalledProcessError:
                    pass
                self._create_configdrive(cfg_vmdk)

            # attach at SATA port 1 (port 0 is the OS disk from the clone)
            self._ensure_sata_storage_controller(node.name)
            self._vbox.storage_attach(
                node.name,
                storagectl=self._s.controller_name,
                port=1,
                device=0,
                medium_type="hdd",
                medium=cfg_vmdk.as_posix(),
            )

    def start(self, topo: "InternalTopology") -> None:
        """Start all VMs in the topology."""

        for node in topo.nodes:
            self._vbox.start_vm(node.name)

    def stop(self, topo: "InternalTopology") -> None:
        """Send stop signals to all VMs."""

        for node in topo.nodes:
            state = self._get_vm_state(node.name)

            if state is None:
                self.console.print(f"[yellow]VM '{node.name}' not found, skipping.[/yellow]")
                continue

            if state != VMState.RUNNING:
                self.console.print(f"[yellow]VM '{node.name}' is not running (state: {state}), skipping.[/yellow]")
                continue

            try:
                self._vbox.control_vm(node.name, VMControlAction.ACPI_POWER_BUTTON)
                self.console.print(f"[green]Sent ACPI power button to '{node.name}'[/green]")
            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]Failed to stop '{node.name}': {e}[/red]")

    def _destroy_vm(self, vm_name: str) -> bool:
        """Stop and remove a single VM. Returns True on success."""

        state = self._get_vm_state(vm_name)

        if state is None:
            self.console.print(f"[yellow]VM '{vm_name}' not found, skipping.[/yellow]")
            return False

        if state == VMState.RUNNING:
            self.console.print(f"[dim]Powering off '{vm_name}'...[/dim]")
            try:
                self._vbox.control_vm(vm_name, VMControlAction.POWEROFF)
            except subprocess.CalledProcessError as e:
                self.console.print(f"[red]Failed to power off '{vm_name}': {e}[/red]")
                return False

        try:
            self._vbox.unregister_vm(vm_name, delete=True)
            self.console.print(f"[green]Destroyed VM '{vm_name}'[/green]")
            return True
        except subprocess.CalledProcessError as e:
            self.console.print(f"[red]Failed to destroy '{vm_name}': {e}[/red]")
            return False

    def destroy(self, topo: "InternalTopology", *, destroy_base: bool = False) -> None:
        """Stop and remove all VMs in the topology."""

        for node in topo.nodes:
            self._destroy_vm(node.name)

        if destroy_base:
            self.console.print(f"[dim]Destroying base VM '{self._s.base_vm_name}'...[/dim]")
            self._destroy_vm(self._s.base_vm_name)

    def get_configdrive(self, node: "InternalNode") -> ConfigDrive:
        """Return the ConfigDrive handle for a node."""

        return ConfigDrive(self._cfg_vmdk(node))

    def _create_configdrive(self, vmdk_path: Path) -> ConfigDrive:
        """Create and format a new config-drive VMDK."""

        self._vbox.create_medium(vmdk_path, size_mb=self._s.configdrive_mb)
        cd = ConfigDrive(vmdk_path)
        format_fat16(cd.flat, self._s.configdrive_mb)

        return cd
