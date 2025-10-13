from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from models.internal import InternalTopology


class Provider(Protocol):
    """Provider lifecycle interface."""

    name: str

    def init(self, topo: InternalTopology, workdir: str | Path) -> None: ...
    def create(self, topo: InternalTopology, workdir: str | Path) -> None: ...
    def generate_configs(self, topo: InternalTopology, workdir: str | Path) -> None: ...
    def attach_raw_config_disks(self, topo: InternalTopology, workdir: str | Path) -> None: ...
    def start(self, topo: InternalTopology) -> None: ...
    def shutdown(self, topo: InternalTopology) -> None: ...
    def save_changed_configs(self, topo: InternalTopology, workdir: str | Path) -> None: ...
    def restore_saved_configs(self, topo: InternalTopology, workdir: str | Path) -> None: ...


def which_or_die(bin_name: str) -> str:
    p = shutil.which(bin_name)
    if not p:
        raise SystemExit(f"Required binary not found in PATH: {bin_name}")
    return p


def run(cmd: list[str]) -> None:
    subprocess.run(  # noqa: S603
        cmd,
        check=True,
    )
