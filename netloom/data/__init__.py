"""Config-drive utilities for creating and managing VM configuration disks."""

from ._fat import format_fat16
from .configdrive import ConfigDrive


__all__ = ["ConfigDrive", "format_fat16"]
