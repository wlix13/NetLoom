"""Host and OVA architecture detection for x86-on-ARM emulation support."""

import platform
import tarfile
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path


def host_needs_x86_emulation() -> bool:
    """True if host is arm64 macOS — where x86 guests need VBox's x86-on-ARM emulator."""

    return platform.system() == "Darwin" and platform.machine() == "arm64"


def ova_is_x86(ova_path: Path) -> bool:
    """Detect whether an OVA targets x86. Defaults to True when architecture is unspecified."""

    try:
        with tarfile.open(ova_path) as tar:
            ovf_member = next((m for m in tar.getmembers() if m.name.lower().endswith(".ovf")), None)
            if ovf_member is None:
                return True
            extracted = tar.extractfile(ovf_member)
            if extracted is None:
                return True
            data = extracted.read()
    except (tarfile.TarError, OSError):
        return True

    try:
        root = ET.fromstring(data)  # noqa: S314
    except ET.ParseError:
        return True

    # VirtualBox-specific OVF extension; non-VBox OVAs won't have this element
    # and correctly fall through to the default True below.
    for platform_el in root.iter("{http://www.virtualbox.org/ovf/machine}Platform"):
        arch = (platform_el.get("architecture") or "").lower()
        if arch == "arm":
            return False
        if arch == "x86":
            return True

    return True
