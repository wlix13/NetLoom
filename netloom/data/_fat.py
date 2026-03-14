"""Low-level FAT filesystem helpers for config-drive I/O."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from FATtools import FAT, mkfat
from FATtools.disk import disk

from .constants import BOOT_SECTOR_SIZE, FAT_BITS, MB


@contextmanager
def open_fat_fs(flat_path: Path, mode: str = "r+b") -> Generator[Any]:
    """Context manager that opens a FAT16 filesystem on a raw flat VMDK file."""

    d = disk(str(flat_path), mode)
    d.seek(0)
    d.mbr = None  # ty: ignore[unresolved-attribute] # No MBR, direct FAT filesystem

    # read boot sector and detect FAT type
    bs = d.read(BOOT_SECTOR_SIZE)
    boot = FAT.boot_fat16(bs, stream=d)

    if boot.wBytesPerSector == 0:
        d.close()
        raise RuntimeError(f"No valid FAT filesystem found on {flat_path}")

    # create FAT table object
    fat = FAT.FAT(d, boot.fatoffs, boot.clusters(), bitsize=FAT_BITS)

    # create root directory table
    fs = FAT.Dirtable(boot, fat, boot.dwRootCluster)
    fs.parent = d

    try:
        yield fs
    finally:
        if "+" in mode or "w" in mode:
            fs.flush()
        d.close()


def format_fat16(flat_path: Path, size_mb: int) -> None:
    """Format raw flat VMDK file as FAT16."""

    d = disk(str(flat_path), "r+b")
    try:
        mkfat.fat_mkfs(d, size_mb * MB, params={"fat_bits": FAT_BITS})
    finally:
        d.close()


def makedirs(fs: Any, rel_path: Path) -> Any:
    """Create necessary directories in FAT filesystem and return the final directory."""

    current = fs
    for part in rel_path.parts:
        if not part:
            continue
        try:
            current.mkdir(part)
        except Exception:  # noqa: S110 — directory already exists
            pass
        current = current.opendir(part)

    return current


def copy_dir_recursive(cur_dir: Any, dst_dir: Path, copied: list[Path]) -> None:
    """Recursively copy directory contents from FAT filesystem to local path."""

    try:
        entries = list(cur_dir.iterator())
    except Exception:
        return

    for entry in entries:
        name = entry.Name()
        if name in (".", ".."):
            continue

        full_dst = dst_dir / name

        if entry.IsDir():
            full_dst.mkdir(parents=True, exist_ok=True)
            try:
                subdir = cur_dir.opendir(name)
                copy_dir_recursive(subdir, full_dst, copied)
            except Exception:  # noqa: S110
                pass
        else:
            try:
                f = cur_dir.open(name)
                content = f.read()
                f.close()
                full_dst.parent.mkdir(parents=True, exist_ok=True)
                full_dst.write_bytes(content)
                copied.append(full_dst)
            except Exception:  # noqa: S110
                pass
