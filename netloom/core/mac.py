"""MAC address generation utilities."""

import hashlib
import random


def _set_locally_administered(mac_bytes: bytearray) -> None:
    """Set the locally administered bit and unset the multicast bit."""

    mac_bytes[0] &= 0xFE  # Unset multicast bit
    mac_bytes[0] |= 0x02  # Set locally administered bit


def generate_mac(seed: str | None = None, random_mac: bool = False) -> str:
    """Generate a MAC address."""

    if random_mac or seed is None:
        mac_bytes = bytearray(random.getrandbits(8) for _ in range(6))
    else:
        # Deterministic generation using MD5 of the seed
        hash_bytes = hashlib.md5(seed.encode("utf-8")).digest()  # noqa: S324
        mac_bytes = bytearray(hash_bytes[:6])

    _set_locally_administered(mac_bytes)

    return ":".join(f"{b:02x}" for b in mac_bytes).upper()
