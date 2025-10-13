import shutil
import subprocess
from pathlib import Path

import orjson
from data.configdrive import ConfigDrive, copy_tree_to_configdrive, create_configdrive
from models.internal import InternalNode, InternalTopology
from renderers.engine import get_template_set


def run(cmd: list[str]) -> None:
    subprocess.run(  # noqa: S603
        cmd,
        check=True,
    )


def need(bin_name: str) -> str:
    p = shutil.which(bin_name)
    if not p:
        raise SystemExit(f"Required binary not found in PATH: {bin_name}")
    return p


class VirtualBoxProvider:
    """
    VirtualBox provider that:
      - imports a *single* base VM from OVA (on first init),
      - takes a 'golden' snapshot,
      - creates **linked clones** per node,
      - generates a *config-drive* fixed VMDK per node and fills it with files via mtools,
      - wires NICs to intnets and sets CPU/RAM.
    """

    name = "virtualbox"

    def __init__(
        self,
        basefolder: str | None = None,
        ova_path: str | None = None,
        base_vm_name: str = "ASVK-Base",
        snapshot_name: str = "golden",
        configdrive_mb: int = 10,
        controller_name: str = "SATA Controller",
    ):
        self.basefolder = Path(basefolder or Path.cwd() / ".asvk_vms")
        self.ova_path = Path(ova_path) if ova_path else None
        self.base_vm_name = base_vm_name
        self.snapshot_name = snapshot_name
        self.configdrive_mb = configdrive_mb
        self.controller_name = controller_name

    # ---------- helpers ----------

    def _vm_dir(self, node: InternalNode) -> Path:
        return self.basefolder / node.name

    def _cfg_vmdk(self, node: InternalNode) -> Path:
        return self._vm_dir(node) / f"{node.name}-configdrive.vmdk"

    def _list_vms(self) -> dict[str, str]:
        out = subprocess.run(
            ["VBoxManage", "list", "vms"],  # noqa: S607
            check=True,
            capture_output=True,
            text=True,
        ).stdout

        # Lines like:  "ASVK-Base" {UUID}
        res = {}
        for line in out.strip().splitlines():
            if not line.strip():
                continue
            name, rest = line.split('"', 2)[1], line.split('"', 2)[2]
            uuid = rest.strip().strip("{}").strip()
            res[name] = uuid
        return res

    def _ensure_base_imported(self):
        need("VBoxManage")
        vms = self._list_vms()
        if self.base_vm_name in vms:
            return
        if not self.ova_path:
            raise SystemExit("Base VM not found and --ova is not provided to import it.")
        self.basefolder.mkdir(parents=True, exist_ok=True)
        run(
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
        run(
            [
                "VBoxManage",
                "controlvm",
                self.base_vm_name,
                "poweroff",
            ]
        )
        run(
            [
                "VBoxManage",
                "snapshot",
                self.base_vm_name,
                "take",
                self.snapshot_name,
            ]
        )

    def _ensure_storage_controller(self, vm_name: str):
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

        run(
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

    def _modify_vm_hw(self, node: InternalNode):
        run(
            [
                "VBoxManage",
                "modifyvm",
                node.name,
                "--memory",
                str(node.resources.ram_mb),
                "--cpus",
                str(node.resources.cpu),
                "--ioapic",
                "on",
                "--firmware",
                "EFI",
            ]
        )

    def _wire_nics(self, node: InternalNode, topo: InternalTopology):
        # Reset NICs 1..8
        for i in range(1, 9):
            run(
                [
                    "VBoxManage",
                    "modifyvm",
                    node.name,
                    f"--nic{i}",
                    "none",
                ]
            )

        # Attach intnets per interface
        type_map = {
            "virtio": "virtio-net",
            "e1000": "82540EM",
            "rtl8139": "Am79C973",
        }
        nic_type = type_map[node.nic_model]
        for nic in node.nics:
            intnet = topo.net(nic.network_id).vbox_network_name if nic.network_id else f"intnet:{node.name}-{nic.name}"
            run(
                [
                    "VBoxManage",
                    "modifyvm",
                    node.name,
                    f"--nic{nic.vbox_nic_index}",
                    "intnet",
                    f"--intnet{nic.vbox_nic_index}",
                    intnet,
                    f"--nictype{nic.vbox_nic_index}",
                    nic_type,
                    f"--cableconnected{nic.vbox_nic_index}",
                    "on",
                ]
            )

    def init(self, topo: InternalTopology, workdir: str | Path) -> None:
        need("VBoxManage")
        self._ensure_base_imported()
        Path(workdir).mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "configs").mkdir(parents=True, exist_ok=True)
        (Path(workdir) / "saved").mkdir(parents=True, exist_ok=True)

    def create(self, topo: InternalTopology, workdir: str | Path) -> None:
        """Create linked clones from the snapshot and attach a config-drive per node."""

        self._ensure_base_imported()
        for node in topo.nodes:
            vm_dir = self._vm_dir(node)
            vm_dir.mkdir(parents=True, exist_ok=True)

            run(
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

            self._ensure_storage_controller(node.name)
            self._modify_vm_hw(node)
            self._wire_nics(node, topo)

            cfg_vmdk = self._cfg_vmdk(node)
            if not cfg_vmdk.exists():
                create_configdrive(cfg_vmdk, size_mb=self.configdrive_mb)
            # Attach at SATA port 1 (port 0 is the OS disk from the clone)
            run(
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

    def generate_configs(self, topo: InternalTopology, workdir: str | Path, template_name: str = "networkd") -> None:
        """Render Jinja templates into the node's config dir (staged for the config-drive)."""

        tpl = get_template_set(template_name)

        for node in topo.nodes:
            outdir = Path(node.config_dir)
            context = {"node": node, "topology": topo}
            # Render the template set for *this* node
            tpl.render(context, outdir)

            # Optional: keep a summary JSON for debugging
            (outdir / "_node.json").write_bytes(
                orjson.dumps(
                    {
                        "name": node.name,
                        "nics": [
                            {"name": n.name, "net": n.network_id, "addresses": [str(a) for a in n.addresses]}
                            for n in node.nics
                        ],
                        "mgmt": {
                            "ip": str(node.mgmt.ip) if node.mgmt.ip else None,
                            "gw": node.mgmt.gw,
                            "net": node.mgmt.net_id,
                        },
                    },
                    indent=2,
                ),
            )

    def attach_raw_config_disks(self, topo: InternalTopology, workdir: str | Path) -> None:
        """Fill each node's config-drive with files from its config_dir using mtools."""

        for node in topo.nodes:
            cfg = ConfigDrive(self._cfg_vmdk(node))
            copy_tree_to_configdrive(cfg, Path(node.config_dir))

    def start(self, topo: InternalTopology) -> None:
        for node in topo.nodes:
            run(
                [
                    "VBoxManage",
                    "startvm",
                    node.name,
                    "--type",
                    "headless",
                ]
            )

    def shutdown(self, topo: InternalTopology) -> None:
        for node in topo.nodes:
            run(
                [
                    "VBoxManage",
                    "controlvm",
                    node.name,
                    "acpipowerbutton",
                ]
            )

    def save_changed_configs(self, topo: InternalTopology, workdir: str | Path) -> None:
        """Pull whatever the guest wrote to the config-drive back to host (uses mtools, no NBD)."""

        need("mdir")
        need("mcopy")
        for node in topo.nodes:
            saved = Path(node.saved_configs_dir)
            saved.mkdir(parents=True, exist_ok=True)
            flat = ConfigDrive(self._cfg_vmdk(node)).flat.as_posix()
            # Copy everything from root (::/) into saved/<node>/
            run(
                [
                    "mcopy",
                    "-s",
                    "-i",
                    flat,
                    "::/",
                    saved.as_posix(),
                ]
            )

    def restore_saved_configs(self, topo: InternalTopology, workdir: str | Path) -> None:
        """Pre-stage last saved configs into config_dir (so 'attach' will push them)."""

        for node in topo.nodes:
            saved = Path(node.saved_configs_dir)
            if not saved.exists():
                continue
            target = Path(node.config_dir)
            target.mkdir(parents=True, exist_ok=True)
            for p in saved.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(saved)
                    dst = target / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(p.read_bytes())
