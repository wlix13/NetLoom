import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


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


@dataclass
class ConfigDrive:
    vmdk: Path

    @property
    def flat(self) -> Path:
        return self.vmdk.with_name(self.vmdk.stem + "-flat.vmdk")


def create_configdrive(vmdk_path: Path, size_mb: int = 10) -> ConfigDrive:
    need("VBoxManage")
    run(
        [
            "VBoxManage",
            "createmedium",
            "disk",
            "--format=VMDK",
            "--variant=fixed",
            "--size",
            str(size_mb * 1024),
            "--filename",
            vmdk_path.as_posix(),
        ]
    )
    cd = ConfigDrive(vmdk_path)
    need("mformat")
    run(["mformat", "-i", cd.flat.as_posix()])
    return cd


def copy_tree_to_configdrive(cd: ConfigDrive, src_dir: Path) -> None:
    """Copy a directory tree into the drive using mtools."""

    src_dir = src_dir.resolve()
    if not any(src_dir.iterdir()):
        return

    need("mcopy")
    run(
        [
            "mcopy",
            "-s",
            "-i",
            cd.flat.as_posix(),
            src_dir.as_posix(),
            "::/",
        ]
    )
