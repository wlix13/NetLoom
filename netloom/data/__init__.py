"""Config-drive utilities for creating and managing VM configuration disks."""

from ._fat import format_fat16, set_fat16_volume_label
from .configdrive import ConfigDrive
from .constants import CONFIG_DRIVE_LABEL


__all__ = ["CONFIG_DRIVE_LABEL", "ConfigDrive", "format_fat16", "set_fat16_volume_label"]
