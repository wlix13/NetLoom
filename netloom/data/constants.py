"""Constants for FAT filesystem helpers."""

MB = 1024 * 1024
"""One megabyte in bytes."""

FAT_BITS = 16
"""Cluster slot bits"""

BOOT_SECTOR_SIZE = 512
"""Size of the boot sector in bytes."""

FAT16_EXT_BOOT_SIG_OFFSET = 0x26
"""Offset of the FAT12/16 EBPB extended boot signature byte (0x29 when present)."""

FAT16_LABEL_OFFSET = 0x2B
"""Offset of the 11-byte volume label field in the FAT12/16 EBPB."""

FAT16_LABEL_SIZE = 11
"""Length of the FAT volume label field."""

CONFIG_DRIVE_LABEL = "NETLOOM"
"""Volume label stamped on config drives so guests can mount /dev/disk/by-label/NETLOOM."""
