"""VirtualBox adapter: VBoxManage CLI wrapper and VBoxSettings dataclass."""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .enums import VMStartType


X86_ON_ARM_KEY = "VBoxInternal2/EnableX86OnArm"


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
    """Settings for VirtualBox infrastructure."""

    basefolder: Path = field(default_factory=lambda: Path.cwd() / ".labs_vms")
    ova_path: Path | None = None
    base_vm_name: str = "Labs-Base"
    snapshot_name: str = "golden"
    configdrive_mb: int = 128
    controller_name: str = "Disks"
    enable_x86_on_arm: bool = True


class VBoxManage:
    """Adapter for the VBoxManage CLI."""

    def _run(self, cmd: list[str]) -> None:
        """Run VBoxManage command, capturing output and raising on non-zero exit."""

        subprocess.run(cmd, check=True, capture_output=True, timeout=60)  # noqa: S603

    def _query(self, cmd: list[str]) -> str:
        """Run VBoxManage command and return its stdout as text."""

        return subprocess.run(  # noqa: S603
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout

    def _probe(self, cmd: list[str]) -> str:
        """Run VBoxManage command without raising on failure; return stdout."""

        return subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        ).stdout

    def get_extradata_global(self, key: str) -> str | None:
        """Get global extradata value for `key`."""

        out = self._probe(["VBoxManage", "getextradata", "global", key]).strip()
        if not out or "No value set" in out:
            return None
        prefix = "Value:"
        if out.startswith(prefix):
            return out.removeprefix(prefix).strip()
        return out

    def set_extradata_global(self, key: str, value: str | None = None) -> None:
        """Set or delete global extradata key."""

        cmd = ["VBoxManage", "setextradata", "global", key]
        if value is not None:
            cmd.append(value)
        self._run(cmd)

    def list_vms(self) -> dict[str, str]:
        """Return {name: uuid} for all registered VMs."""

        out = self._query(["VBoxManage", "list", "vms"])
        result: dict[str, str] = {}
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            name, rest = line.split('"', 2)[1], line.split('"', 2)[2]
            uuid = rest.strip().strip("{}").strip()
            result[name] = uuid

        return result

    def list_hdds(self) -> str:
        """Return raw stdout of ``VBoxManage list hdds``."""

        return self._query(["VBoxManage", "list", "hdds"])

    def show_vm_info(self, vm_name: str) -> str:
        """Return VM info, or empty string if the VM does not exist."""

        return self._probe(["VBoxManage", "showvminfo", vm_name, "--machinereadable"])

    def get_uart_config(self, vm_name: str) -> UartConfig:
        """Parse UART1 configuration from a VM's showvminfo output."""

        info = self.show_vm_info(vm_name)
        uart_match = re.search(r'^uart1="(.+?)"', info, re.MULTILINE)
        mode_match = re.search(r'^uartmode1="(.+?)"', info, re.MULTILINE)

        if not uart_match or uart_match.group(1) == "off":
            return UartConfig(enabled=False)

        uart_params = uart_match.group(1).split(",")
        if len(uart_params) != 2:
            return UartConfig(enabled=False)
        io_base, irq_str = uart_params

        try:
            irq = int(irq_str)
        except ValueError:
            return UartConfig(enabled=False)

        if not mode_match:
            return UartConfig(enabled=True, io_base=io_base, irq=irq)

        mode_parts = mode_match.group(1).split(",", 1)
        mode = mode_parts[0]
        endpoint = mode_parts[1] if len(mode_parts) > 1 else ""

        return UartConfig(
            enabled=True,
            io_base=io_base,
            irq=irq,
            mode=mode,
            endpoint=endpoint,
        )

    def list_snapshots(self, vm_name: str) -> str:
        """Return raw stdout of ``VBoxManage snapshot <vm> list``."""

        return self._probe(["VBoxManage", "snapshot", vm_name, "list"])

    def import_ova(self, ova_path: Path, vm_name: str, basefolder: Path) -> None:
        """Import OVA as new named VM into basefolder."""

        self._run(
            [  # noqa: S607
                "VBoxManage",
                "import",
                ova_path.as_posix(),
                "--vsys",
                "0",
                "--vmname",
                vm_name,
                "--basefolder",
                basefolder.as_posix(),
            ]
        )

    def take_snapshot(self, vm_name: str, snapshot_name: str) -> None:
        """Take named snapshot of VM."""

        self._run(["VBoxManage", "snapshot", vm_name, "take", snapshot_name])

    def clone_vm(self, source: str, *, snapshot: str, name: str, basefolder: Path) -> None:
        """Create linked clone of *source* from *snapshot*."""

        self._run(
            [  # noqa: S607
                "VBoxManage",
                "clonevm",
                source,
                "--snapshot",
                snapshot,
                "--name",
                name,
                "--options",
                "link",
                "--register",
                "--basefolder",
                basefolder.as_posix(),
            ]
        )

    def start_vm(self, vm_name: str) -> None:
        """Start VM in headless mode."""

        self._run(["VBoxManage", "startvm", vm_name, "--type", VMStartType.HEADLESS.value])

    def control_vm(self, vm_name: str, action: str) -> None:
        """Send controlvm action (e.g. ``acpipowerbutton``, ``poweroff``)."""

        self._run(["VBoxManage", "controlvm", vm_name, action])

    def unregister_vm(self, vm_name: str, *, delete: bool = False) -> None:
        """Unregister (and optionally delete files for) VM."""

        cmd = ["VBoxManage", "unregistervm", vm_name]
        if delete:
            cmd.append("--delete")
        self._run(cmd)

    def modify_vm(self, vm_name: str, *args: str) -> None:
        """Run ``VBoxManage modifyvm <vm_name> <args>``."""
        self._run(["VBoxManage", "modifyvm", vm_name, *args])  # noqa: S607

    def storage_ctl(self, vm_name: str, name: str, *, add: str, controller: str) -> None:
        """Add storage controller to VM."""

        self._run(
            [  # noqa: S607
                "VBoxManage",
                "storagectl",
                vm_name,
                "--name",
                name,
                "--add",
                add,
                "--controller",
                controller,
            ]
        )

    def storage_attach(
        self,
        vm_name: str,
        *,
        storagectl: str,
        port: int,
        device: int,
        medium_type: str,
        medium: str,
    ) -> None:
        """Attach medium to storage controller port."""

        self._run(
            [  # noqa: S607
                "VBoxManage",
                "storageattach",
                vm_name,
                "--storagectl",
                storagectl,
                "--port",
                str(port),
                "--device",
                str(device),
                "--type",
                medium_type,
                "--medium",
                medium,
            ]
        )

    def create_medium(self, filename: Path, *, size_mb: int, fmt: str = "VMDK", variant: str = "fixed") -> None:
        """Create new virtual disk medium."""

        self._run(
            [  # noqa: S607
                "VBoxManage",
                "createmedium",
                "disk",
                f"--format={fmt}",
                f"--variant={variant}",
                "--size",
                str(size_mb),
                "--filename",
                filename.as_posix(),
            ]
        )

    def close_medium(self, uuid: str, *, delete: bool = False) -> None:
        """Close (and optionally delete) disk medium by UUID."""

        cmd = ["VBoxManage", "closemedium", "disk", uuid]  # noqa: S607
        if delete:
            cmd.append("--delete")
        self._run(cmd)
