"""VirtualBox hypervisor driver implementation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import rich_click as click
from rich.console import Console

from netloom.core.enums import VMControlAction, VMState
from netloom.data import ConfigDrive, format_fat16

from ..base import BaseHypervisorDriver, ConnectionInfo
from .manage import VBoxManage
from .settings import VBoxSettings


if TYPE_CHECKING:
    from netloom.models.internal import InternalNode, InternalTopology


class VBoxHypervisorDriver(BaseHypervisorDriver):
    """Hypervisor driver for Oracle VirtualBox via the VBoxManage CLI."""

    def __init__(self, settings: VBoxSettings, console: Console | None = None) -> None:
        self._s = settings
        self._vbox = VBoxManage()
        self._console = console

    def _log(self, msg: str) -> None:
        if self._console:
            self._console.print(msg)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _vm_dir(self, node: InternalNode) -> Path:
        return self._s.basefolder / node.name

    def _cfg_vmdk(self, node: InternalNode) -> Path:
        return self._vm_dir(node) / f"{node.name}-configdrive.vmdk"

    def _has_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        return snapshot_name in self._vbox.list_snapshots(vm_name)

    def _ensure_sata_controller(self, vm_name: str) -> None:
        info = self._vbox.show_vm_info(vm_name)
        if f'storagecontrollername0="{self._s.controller_name.lower()}"' in info.lower():
            return
        self._vbox.storage_ctl(vm_name, self._s.controller_name, add="sata", controller="IntelAhci")

    def _cleanup_orphaned_base_media(self) -> None:
        output = self._vbox.list_hdds()

        disks_info: dict[str, dict[str, str]] = {}
        current_uuid = current_parent = current_location = None

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
                current_uuid = current_parent = current_location = None

        orphaned_roots: set[str] = set()
        for uuid, info in disks_info.items():
            loc_lower = info["location"].lower()
            if str(self._s.basefolder).lower() in loc_lower and self._s.base_vm_name.lower() in loc_lower:
                orphaned_roots.add(uuid)

        def get_descendants(uuids: set[str]) -> list[str]:
            descendants: list[str] = []
            queue = list(uuids)
            while queue:
                current = queue.pop(0)
                descendants.append(current)
                for child_uuid, child_info in disks_info.items():
                    if child_info["parent"] == current:
                        queue.append(child_uuid)
            return descendants

        to_delete: list[str] = []
        for root in orphaned_roots:
            for item in reversed(get_descendants({root})):
                if item not in to_delete:
                    to_delete.append(item)

        for disk_uuid in to_delete:
            self._log(f"[yellow]Cleaning up orphaned disk: {disk_uuid}[/yellow]")
            try:
                self._vbox.close_medium(disk_uuid, delete=True)
            except subprocess.CalledProcessError:
                try:
                    self._vbox.close_medium(disk_uuid)
                except subprocess.CalledProcessError:
                    self._log(f"[dim]Could not cleanup disk {disk_uuid}, continuing...[/dim]")

        if self._s.basefolder.exists():
            for folder in self._s.basefolder.rglob(self._s.base_vm_name):
                if folder.is_dir():
                    self._log(f"[yellow]Removing leftover folder: {folder}[/yellow]")
                    shutil.rmtree(folder, ignore_errors=True)

    def _modify_vm_hw(self, node: InternalNode, topo: InternalTopology, node_idx: int) -> None:
        uart = self._vbox.get_uart_config(self._s.base_vm_name)
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
                        f"UART endpoint for tcpserver mode must be an integer port number, got: '{endpoint}'"
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

    def _wire_nics(self, node: InternalNode) -> None:
        for i in range(1, 37):
            self._vbox.modify_vm(node.name, f"--nic{i}", "none")

        for iface in node.interfaces:
            if iface.vbox_nic_index is None:
                continue

            idx = iface.vbox_nic_index
            nic_type = node.nic_model.vbox_type
            mac_address = iface.mac_address.replace(":", "") if iface.mac_address else None

            if iface.nat:
                args = [f"--nic{idx}", "nat", f"--nictype{idx}", nic_type, f"--cableconnected{idx}", "on"]
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
                args = [f"--nic{idx}", "null", f"--nictype{idx}", nic_type, f"--cableconnected{idx}", "on"]
                if mac_address:
                    args.extend([f"--macaddress{idx}", mac_address])

            self._vbox.modify_vm(node.name, *args)

    def _create_configdrive(self, node: InternalNode) -> None:
        path = self._cfg_vmdk(node)
        self._vbox.create_medium(path, size_mb=self._s.configdrive_mb)
        cd = ConfigDrive(path)
        format_fat16(cd.flat, self._s.configdrive_mb)

    # ── BaseHypervisorDriver implementation ──────────────────────────────────

    def list_vms(self) -> dict[str, str]:
        return self._vbox.list_vms()

    def get_vm_state(self, name: str) -> VMState | None:
        info = self._vbox.show_vm_info(name)
        if not info:
            return None
        for line in info.splitlines():
            if line.startswith("VMState="):
                try:
                    return VMState(line.split("=", 1)[1].strip('"'))
                except ValueError:
                    return None
        return None

    def get_connection_info(self, name: str) -> ConnectionInfo | None:
        cfg = self._vbox.get_uart_config(name)
        if not cfg.enabled or cfg.mode != "tcpserver" or not cfg.endpoint.isdigit():
            return None
        return ConnectionInfo(protocol="tcp-serial", host="127.0.0.1", port=int(cfg.endpoint))

    def ensure_base_vm(self, topo: InternalTopology) -> None:
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

    def create_node_vm(self, node: InternalNode, topo: InternalTopology, node_idx: int) -> None:
        vm_dir = self._vm_dir(node)
        vm_dir.mkdir(parents=True, exist_ok=True)

        if node.name not in self._vbox.list_vms():
            self._vbox.clone_vm(
                self._s.base_vm_name,
                snapshot=self._s.snapshot_name,
                name=node.name,
                basefolder=self._s.basefolder,
            )

        self._modify_vm_hw(node, topo, node_idx)
        self._wire_nics(node)

        cfg_vmdk = self._cfg_vmdk(node)
        if not cfg_vmdk.exists():
            try:
                self._vbox.close_medium(cfg_vmdk.as_posix())
            except subprocess.CalledProcessError:
                pass
            self._create_configdrive(node)

        # Attach at SATA port 1 (port 0 is the OS disk from the clone)
        self._ensure_sata_controller(node.name)
        self._vbox.storage_attach(
            node.name,
            storagectl=self._s.controller_name,
            port=1,
            device=0,
            medium_type="hdd",
            medium=cfg_vmdk.as_posix(),
        )

    def inject_configs(self, node: InternalNode, config_dir: Path) -> None:
        ConfigDrive(self._cfg_vmdk(node)).copy_in(config_dir)

    def extract_configs(self, node: InternalNode, dest_dir: Path) -> list[Path]:
        return ConfigDrive(self._cfg_vmdk(node)).copy_out(dest_dir)

    def start_vm(self, name: str) -> None:
        self._vbox.start_vm(name)

    def stop_vm(self, name: str) -> None:
        self._vbox.control_vm(name, VMControlAction.ACPI_POWER_BUTTON)

    def destroy_vm(self, name: str) -> bool:
        state = self.get_vm_state(name)
        if state is None:
            self._log(f"[yellow]VM '{name}' not found, skipping.[/yellow]")
            return False

        if state == VMState.RUNNING:
            self._log(f"[dim]Powering off '{name}'...[/dim]")
            try:
                self._vbox.control_vm(name, VMControlAction.POWEROFF)
            except subprocess.CalledProcessError as e:
                self._log(f"[red]Failed to power off '{name}': {e}[/red]")
                return False

        try:
            self._vbox.unregister_vm(name, delete=True)
            return True
        except subprocess.CalledProcessError as e:
            self._log(f"[red]Failed to destroy '{name}': {e}[/red]")
            return False

    def destroy_base_vm(self) -> None:
        self._log(f"[dim]Destroying base VM '{self._s.base_vm_name}'...[/dim]")
        self.destroy_vm(self._s.base_vm_name)

    @classmethod
    def cli_options(cls) -> list[click.Option]:
        return [
            click.Option(
                ["--basefolder"],
                default=None,
                help="VirtualBox VM base folder.",
                metavar="DIR",
            ),
            click.Option(
                ["--ova", "ova_path"],
                default=None,
                help="Path to base OVA (used on first init).",
                metavar="FILE",
            ),
            click.Option(
                ["--base-vm", "base_vm_name"],
                default="Labs-Base",
                show_default=True,
                help="Name for the imported base VM.",
            ),
            click.Option(
                ["--snapshot", "snapshot_name"],
                default="golden",
                show_default=True,
                help="Snapshot used for linked clones.",
            ),
        ]

    @classmethod
    def from_cli_params(cls, console: object | None = None, **kwargs: object) -> VBoxHypervisorDriver:
        rich_console: Console | None = console if isinstance(console, Console) else None
        settings = VBoxSettings(
            base_vm_name=str(kwargs.get("base_vm_name", "Labs-Base")),
            snapshot_name=str(kwargs.get("snapshot_name", "golden")),
        )
        basefolder = kwargs.get("basefolder")
        if basefolder:
            settings.basefolder = Path(str(basefolder))
        ova_path = kwargs.get("ova_path")
        if ova_path:
            settings.ova_path = Path(str(ova_path))
        return cls(settings, console=rich_console)
