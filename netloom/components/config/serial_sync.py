"""Guest-side config sync command for `save --sync` — skeleton.

Builds the single-line shell command sent over the serial console that makes
the guest mount its config drive read-write, copy the (currently hardcoded)
managed paths onto it, and unmount. The host then extracts the drive contents
as usual, so `save` reflects what students actually changed in /etc.
"""

from __future__ import annotations

from netloom.data import CONFIG_DRIVE_LABEL


GUEST_SYNC_PATHS: tuple[str, ...] = (
    "/etc/systemd/network",
    "/etc/bird",
    "/etc/wireguard",
    "/etc/sysctl.d",
    "/etc/nftables.conf",
    "/etc/hostname",
)
"""Paths copied from the guest onto the config drive. Hardcoded for now."""

GUEST_MOUNT_POINT = "/mnt/netloom-config"
"""Where the guest temporarily mounts the config drive during sync."""

FALLBACK_DEVICE = "/dev/sdb"
"""Device used when the by-label symlink is missing (drives created before labelling)."""


def build_sync_command(
    label: str = CONFIG_DRIVE_LABEL,
    mount_point: str = GUEST_MOUNT_POINT,
    fallback_device: str = FALLBACK_DEVICE,
    paths: tuple[str, ...] = GUEST_SYNC_PATHS,
) -> str:
    """Return the single-line `sh -c` command executed in the guest.

    The script must not contain single quotes (it is wrapped in them) or
    newlines (the serial channel sends one line). Its exit code is the exit
    code of the final ``umount``, so a clean run reports 0.
    """
    body = (
        f'DEV=/dev/disk/by-label/{label}; [ -e "$DEV" ] || DEV={fallback_device}; '
        f'mkdir -p {mount_point} && mount -o rw "$DEV" {mount_point} && '
        f"{{ for p in {' '.join(paths)}; do "
        f'[ -e "$p" ] || continue; d="{mount_point}${{p%/*}}"; mkdir -p "$d"; cp -ar "$p" "$d/"; '
        f"done; sync; umount {mount_point}; }}"
    )
    return f"sh -c '{body}'"
