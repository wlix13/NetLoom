"""ConfigDrive dataclass and operations."""

from dataclasses import dataclass
from pathlib import Path

from ._fat import copy_dir_recursive, makedirs, open_fat_fs


@dataclass
class ConfigDrive:
    """Represents a config-drive VMDK."""

    vmdk: Path
    """The VMDK file path."""

    @property
    def flat(self) -> Path:
        return self.vmdk.with_name(self.vmdk.stem + "-flat.vmdk")

    def copy_in(self, src_dir: Path) -> None:
        """Copy local directory tree into this config-drive."""

        src_dir = src_dir.resolve()
        if not src_dir.exists() or not any(src_dir.iterdir()):
            return

        with open_fat_fs(self.flat, "r+b") as fs:
            for src_path in src_dir.rglob("*"):
                if src_path.is_file():
                    rel_path = src_path.relative_to(src_dir)
                    parent_dir = makedirs(fs, rel_path.parent)
                    content = src_path.read_bytes()
                    f = parent_dir.create(rel_path.name)
                    try:
                        f.write(content)
                    finally:
                        f.close()

    def copy_out(self, dst_dir: Path) -> list[Path]:
        """Copy all files from this config-drive to local directory."""

        dst_dir.mkdir(parents=True, exist_ok=True)
        copied: list[Path] = []

        with open_fat_fs(self.flat, "rb") as fs:
            copy_dir_recursive(fs, dst_dir, copied)

        return copied
