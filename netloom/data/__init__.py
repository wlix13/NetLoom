"""Config-drive utilities for creating and managing VM configuration disks."""

from dataclasses import dataclass
from pathlib import Path

from FATtools import FAT, mkfat
from FATtools.disk import disk


@dataclass
class ConfigDrive:
    """Represents a config-drive VMDK."""

    vmdk: Path
    """The VMDK file path."""

    @property
    def flat(self) -> Path:
        return self.vmdk.with_name(self.vmdk.stem + "-flat.vmdk")


def create_configdrive(vmdk_path: Path, size_mb: int = 64) -> ConfigDrive:
    """Create a config-drive VMDK."""

    from ..controllers.infrastructure import _run

    _run(
        [
            "VBoxManage",
            "createmedium",
            "disk",
            "--format=VMDK",
            "--variant=fixed",
            "--size",
            str(size_mb),
            "--filename",
            vmdk_path.as_posix(),
        ]
    )
    cd = ConfigDrive(vmdk_path)

    # open as raw disk, bypassing VMDK detection
    d = disk(str(cd.flat), "r+b")
    mkfat.fat_mkfs(d, d.size, params={"fat_bits": 16})
    d.close()

    return cd


def _open_fat_fs(flat_path: Path, mode: str = "r+b"):
    """Open FAT filesystem on a raw flat VMDK file."""

    d = disk(str(flat_path), mode)
    d.seek(0)
    d.mbr = None  # No MBR, direct FAT filesystem

    # read boot sector and detect FAT type
    bs = d.read(512)
    boot = FAT.boot_fat16(bs, stream=d)

    if boot.wBytesPerSector == 0:
        d.close()
        raise RuntimeError(f"No valid FAT filesystem found on {flat_path}")

    # create FAT table object (FAT16 = 16 bits)
    fat = FAT.FAT(d, boot.fatoffs, boot.clusters(), bitsize=16)

    # create root directory table
    fs = FAT.Dirtable(boot, fat, boot.dwRootCluster)
    fs.parent = d

    return fs


def copy_tree_to_configdrive(cd: ConfigDrive, src_dir: Path) -> None:
    """Copy a directory tree into the config-drive."""

    src_dir = src_dir.resolve()
    if not src_dir.exists() or not any(src_dir.iterdir()):
        return

    fs = _open_fat_fs(cd.flat, "r+b")

    try:
        for src_path in src_dir.rglob("*"):
            if src_path.is_file():
                rel_path = src_path.relative_to(src_dir)
                filename = rel_path.name

                # create parent directories and get the target directory
                parent_dir = _makedirs(fs, rel_path.parent)

                # copy file - create in the target directory
                content = src_path.read_bytes()
                f = parent_dir.create(filename)
                f.write(content)
                f.close()
    finally:
        fs.flush()
        fs.parent.close()


def _makedirs(fs, rel_path: Path):
    """Create necessary directories and return the final directory."""

    current = fs
    parts = rel_path.parts

    for part in parts:
        if not part:
            continue
        try:
            current.mkdir(part)
        except Exception:  # noqa: S110
            pass
        current = current.opendir(part)

    return current


def copy_from_configdrive(cd: ConfigDrive, dst_dir: Path) -> list[Path]:
    """Copy all files from config-drive to a directory."""

    dst_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[Path] = []

    fs = _open_fat_fs(cd.flat, "rb")

    try:
        _copy_dir_recursive(fs, fs, dst_dir, copied_files)
    finally:
        fs.parent.close()

    return copied_files


def _copy_dir_recursive(
    root_fs,
    current_dir,
    dst_dir: Path,
    copied_files: list[Path],
) -> None:
    """Recursively copy directory contents from FAT filesystem."""

    try:
        entries = list(current_dir.iterator())
    except Exception:  # noqa: S110
        return

    for entry in entries:
        name = entry.Name()
        if name in (".", ".."):
            continue

        full_dst = dst_dir / name

        if entry.IsDir():
            full_dst.mkdir(parents=True, exist_ok=True)
            try:
                subdir = current_dir.opendir(name)
                _copy_dir_recursive(root_fs, subdir, full_dst, copied_files)
            except Exception:  # noqa: S110
                pass
        else:
            try:
                f = current_dir.open(name)
                content = f.read()
                f.close()
                full_dst.parent.mkdir(parents=True, exist_ok=True)
                full_dst.write_bytes(content)
                copied_files.append(full_dst)
            except Exception:  # noqa: S110
                pass
