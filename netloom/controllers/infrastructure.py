"""Infrastructure controller for VirtualBox VM lifecycle management."""

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ..core.controller import BaseController
from ..data import ConfigDrive, create_configdrive


if TYPE_CHECKING:
    from ..core.application import Application
    from ..models.internal import InternalNode, InternalTopology


def _run(cmd: list[str]) -> None:
    """Run a command and raise on failure."""

    subprocess.run(cmd, check=True)  # noqa: S603


class InfrastructureController(BaseController["Application"]):
    """Controller for VirtualBox infrastructure operations.

    Handles VM lifecycle: import, clone, start, stop, destroy.
    Also manages config-drive creation and attachment.
    """

    def __init__(self, app: "Application") -> None:
        super().__init__(app)
        # VirtualBox settings
        self.basefolder: Path = Path.cwd() / ".labs_vms"
        self.ova_path: Path | None = Path.cwd() / "base.ova"
        self.base_vm_name: str = "Labs-Base"
        self.snapshot_name: str = "golden"
        self.configdrive_mb: int = 128
        self.controller_name: str = "Disks"

    def configure(
        self,
        basefolder: str | Path | None = None,
        ova_path: str | Path | None = None,
        base_vm_name: str | None = None,
        snapshot_name: str | None = None,
    ) -> None:
        """Configure VirtualBox settings."""

        if basefolder:
            self.basefolder = Path(basefolder)
        if ova_path:
            self.ova_path = Path(ova_path)
        if base_vm_name:
            self.base_vm_name = base_vm_name
        if snapshot_name:
            self.snapshot_name = snapshot_name

    def _vm_dir(self, node: "InternalNode") -> Path:
        """Get the VM directory for a node."""

        return self.basefolder / node.name

    def _cfg_vmdk(self, node: "InternalNode") -> Path:
        """Get the config-drive VMDK path for a node."""

        return self._vm_dir(node) / f"{node.name}-configdrive.vmdk"

    # ---------- VirtualBox helpers ----------

    def _list_vms(self) -> dict[str, str]:
        """List all registered VMs."""

        out = subprocess.run(
            [  # noqa: S607
                "VBoxManage",
                "list",
                "vms",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        res = {}
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            name, rest = line.split('"', 2)[1], line.split('"', 2)[2]
            uuid = rest.strip().strip("{}").strip()
            res[name] = uuid
        return res

    def _has_snapshot(self, vm_name: str, snapshot_name: str) -> bool:
        """Check if a VM has a specific snapshot."""

        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "VBoxManage",
                "snapshot",
                vm_name,
                "list",
            ],
            capture_output=True,
            text=True,
        )
        return snapshot_name in result.stdout

    def _cleanup_orphaned_base_media(self) -> None:
        """Remove any orphaned disk media from a previous failed import."""

        result = subprocess.run(
            [  # noqa: S607
                "VBoxManage",
                "list",
                "hdds",
            ],  # noqa: S603
            capture_output=True,
            text=True,
        )

        orphaned_disks: list[str] = []
        current_uuid = None
        current_location = None

        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("UUID:"):
                current_uuid = line.split(":", 1)[1].strip()
            elif line.startswith("Location:"):
                current_location = line.split(":", 1)[1].strip()
                if current_location and current_uuid:
                    loc_lower = current_location.lower()
                    base_lower = self.base_vm_name.lower()
                    basefolder_lower = str(self.basefolder).lower()
                    if basefolder_lower in loc_lower and base_lower in loc_lower:
                        orphaned_disks.append(current_uuid)
                current_uuid = None
                current_location = None

        for disk_uuid in orphaned_disks:
            self.app.console.print(f"[yellow]Cleaning up orphaned disk: {disk_uuid}[/yellow]")
            try:
                subprocess.run(  # noqa: S603
                    [  # noqa: S607
                        "VBoxManage",
                        "closemedium",
                        "disk",
                        disk_uuid,
                        "--delete",
                    ],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError:
                try:
                    subprocess.run(  # noqa: S603
                        [  # noqa: S607
                            "VBoxManage",
                            "closemedium",
                            "disk",
                            disk_uuid,
                        ],
                        check=True,
                        capture_output=True,
                    )
                except subprocess.CalledProcessError:
                    self.app.console.print(f"[dim]Could not cleanup disk {disk_uuid}, continuing...[/dim]")

        if self.basefolder.exists():
            for folder in self.basefolder.rglob(self.base_vm_name):
                if folder.is_dir():
                    self.app.console.print(f"[yellow]Removing leftover folder: {folder}[/yellow]")
                    shutil.rmtree(folder, ignore_errors=True)

    def _ensure_base_imported(self, topo: "InternalTopology") -> None:
        """Ensure the base VM is imported from OVA and has a snapshot."""

        vms = self._list_vms()

        if self.base_vm_name in vms:
            return
        elif not self.ova_path:
            raise SystemExit("Base VM not found and --ova is not provided to import it.")

        self._cleanup_orphaned_base_media()

        self.basefolder.mkdir(parents=True, exist_ok=True)
        _run(
            [
                "VBoxManage",
                "import",
                self.ova_path.as_posix(),
                "--vsys",
                "0",
                "--vmname",
                self.base_vm_name,
                "--basefolder",
                self.basefolder.as_posix(),
            ]
        )

        vbox = topo.vbox
        _run(
            [
                "VBoxManage",
                "modifyvm",
                self.base_vm_name,
                "--chipset",
                vbox.chipset,
                "--ioapic",
                "on" if vbox.ioapic else "off",
                "--hpet",
                "on" if vbox.hpet else "off",
                "--paravirtprovider",
                vbox.paravirt_provider,
            ]
        )

        if not self._has_snapshot(self.base_vm_name, self.snapshot_name):
            _run(
                [
                    "VBoxManage",
                    "snapshot",
                    self.base_vm_name,
                    "take",
                    self.snapshot_name,
                ]
            )

    def _ensure_sata_storage_controller(self, vm_name: str) -> None:
        """Ensure the VM has a SATA storage controller."""

        info = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "VBoxManage",
                "showvminfo",
                vm_name,
                "--machinereadable",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        if f'StorageControllerName0="{self.controller_name}"' in info:
            return

        _run(
            [
                "VBoxManage",
                "storagectl",
                vm_name,
                "--name",
                self.controller_name,
                "--add",
                "sata",
                "--controller",
                "IntelAhci",
            ]
        )

    def _modify_vm_hw(self, node: "InternalNode", topo: "InternalTopology") -> None:
        """Configure VM hardware (RAM, CPU, boot order)."""

        vbox = topo.get_vbox_settings(node)

        _run(
            [
                "VBoxManage",
                "modifyvm",
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
                "--boot1",
                "disk",
                "--boot2",
                "none",
                "--boot3",
                "none",
                "--boot4",
                "none",
            ]
        )

    def _wire_nics(self, node: "InternalNode") -> None:
        """Wire network interfaces to VirtualBox internal networks."""

        for i in range(1, 9):
            _run(
                [
                    "VBoxManage",
                    "modifyvm",
                    node.name,
                    f"--nic{i}",
                    "none",
                ]
            )

        # Mapping of NIC models to VirtualBox NIC types
        type_map = {
            "virtio": "virtio",
            "e1000": "82540EM",
            "rtl8139": "Am79C973",
        }
        nic_type = type_map[node.nic_model]

        for iface in node.interfaces:
            intnet = iface.vbox_network_name or f"intnet:{node.name}-{iface.name}"
            _run(
                [
                    "VBoxManage",
                    "modifyvm",
                    node.name,
                    f"--nic{iface.vbox_nic_index}",
                    "intnet",
                    f"--intnet{iface.vbox_nic_index}",
                    intnet,
                    f"--nictype{iface.vbox_nic_index}",
                    nic_type,
                    f"--cableconnected{iface.vbox_nic_index}",
                    "on",
                ]
            )

    def init(self, topo: "InternalTopology", workdir: str | Path) -> None:
        """Initialize: import base OVA and create workdir structure."""

        self._ensure_base_imported(topo)
        Path(workdir).mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "configs").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "saved").mkdir(parents=True, exist_ok=True)

    def create(self, topo: "InternalTopology") -> None:
        """Create linked clones and attach config-drives."""

        self._ensure_base_imported(topo)

        for node in topo.nodes:
            vm_dir = self._vm_dir(node)
            vm_dir.mkdir(parents=True, exist_ok=True)

            _run(
                [
                    "VBoxManage",
                    "clonevm",
                    self.base_vm_name,
                    "--snapshot",
                    self.snapshot_name,
                    "--name",
                    node.name,
                    "--options",
                    "link",
                    "--register",
                    "--basefolder",
                    self.basefolder.as_posix(),
                ]
            )

            self._modify_vm_hw(node, topo)
            self._wire_nics(node)

            cfg_vmdk = self._cfg_vmdk(node)
            if not cfg_vmdk.exists():
                create_configdrive(cfg_vmdk, size_mb=self.configdrive_mb)

            # attach at SATA port 1 (port 0 is the OS disk from the clone)
            _run(
                [
                    "VBoxManage",
                    "storageattach",
                    node.name,
                    "--storagectl",
                    self.controller_name,
                    "--port",
                    "1",
                    "--device",
                    "0",
                    "--type",
                    "hdd",
                    "--medium",
                    cfg_vmdk.as_posix(),
                ]
            )

    def start(self, topo: "InternalTopology") -> None:
        """Start all VMs in the topology."""

        for node in topo.nodes:
            _run(
                [
                    "VBoxManage",
                    "startvm",
                    node.name,
                    "--type",
                    "headless",
                ]
            )

    def _get_vm_state(self, vm_name: str) -> str | None:
        """Get the current state of a VM."""

        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "VBoxManage",
                "showvminfo",
                vm_name,
                "--machinereadable",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.splitlines():
            if line.startswith("VMState="):
                # VMState="running" -> running
                return line.split("=", 1)[1].strip('"')
        return None

    def stop(self, topo: "InternalTopology") -> None:
        """Send stop signals to all VMs."""

        for node in topo.nodes:
            state = self._get_vm_state(node.name)

            if state is None:
                self.app.console.print(f"[yellow]VM '{node.name}' not found, skipping.[/yellow]")
                continue

            if state != "running":
                self.app.console.print(f"[yellow]VM '{node.name}' is not running (state: {state}), skipping.[/yellow]")
                continue

            try:
                _run(
                    [
                        "VBoxManage",
                        "controlvm",
                        node.name,
                        "acpipowerbutton",
                    ]
                )
                self.app.console.print(f"[green]Sent ACPI power button to '{node.name}'[/green]")
            except subprocess.CalledProcessError as e:
                self.app.console.print(f"[red]Failed to stop '{node.name}': {e}[/red]")

    def _destroy_vm(self, vm_name: str) -> bool:
        """Stop and remove a single VM. Returns True on success."""

        state = self._get_vm_state(vm_name)

        if state is None:
            self.app.console.print(f"[yellow]VM '{vm_name}' not found, skipping.[/yellow]")
            return False

        if state == "running":
            self.app.console.print(f"[dim]Powering off '{vm_name}'...[/dim]")
            try:
                _run(
                    [
                        "VBoxManage",
                        "controlvm",
                        vm_name,
                        "poweroff",
                    ]
                )
            except subprocess.CalledProcessError as e:
                self.app.console.print(f"[red]Failed to power off '{vm_name}': {e}[/red]")
                return False

        try:
            _run(
                [
                    "VBoxManage",
                    "unregistervm",
                    vm_name,
                    "--delete",
                ]
            )
            self.app.console.print(f"[green]Destroyed VM '{vm_name}'[/green]")
            return True
        except subprocess.CalledProcessError as e:
            self.app.console.print(f"[red]Failed to destroy '{vm_name}': {e}[/red]")
            return False

    def destroy(self, topo: "InternalTopology", *, destroy_base: bool = False) -> None:
        """Stop and remove all VMs in the topology."""

        for node in topo.nodes:
            self._destroy_vm(node.name)

        if destroy_base:
            self.app.console.print(f"[dim]Destroying base VM '{self.base_vm_name}'...[/dim]")
            self._destroy_vm(self.base_vm_name)

    def get_configdrive(self, node: "InternalNode") -> ConfigDrive:
        """Get the ConfigDrive for a node."""

        return ConfigDrive(self._cfg_vmdk(node))
