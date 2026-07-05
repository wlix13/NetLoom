"""FAT16 config-drive formatting, volume label, and round-trip copy."""

from pathlib import Path

import pytest

from netloom.data import ConfigDrive, format_fat16, set_fat16_volume_label
from netloom.data.constants import FAT16_EXT_BOOT_SIG_OFFSET, FAT16_LABEL_OFFSET, FAT16_LABEL_SIZE, MB


pytestmark = pytest.mark.component

DRIVE_MB = 16


@pytest.fixture
def flat_image(tmp_path: Path) -> Path:
    flat = tmp_path / "cfg-flat.vmdk"
    flat.write_bytes(b"\x00" * (DRIVE_MB * MB))
    return flat


def test_format_with_label_stamps_boot_sector(flat_image: Path):
    format_fat16(flat_image, DRIVE_MB, label="NETLOOM")

    raw = flat_image.read_bytes()
    assert raw[FAT16_EXT_BOOT_SIG_OFFSET] == 0x29, "extended boot signature expected after fat_mkfs"
    label_field = raw[FAT16_LABEL_OFFSET : FAT16_LABEL_OFFSET + FAT16_LABEL_SIZE]
    assert label_field == b"NETLOOM    "


def test_label_is_uppercased_and_validated(flat_image: Path):
    format_fat16(flat_image, DRIVE_MB)
    set_fat16_volume_label(flat_image, "netloom")
    raw = flat_image.read_bytes()
    assert raw[FAT16_LABEL_OFFSET : FAT16_LABEL_OFFSET + FAT16_LABEL_SIZE] == b"NETLOOM    "

    with pytest.raises(ValueError, match="1-11"):
        set_fat16_volume_label(flat_image, "WAY-TOO-LONG-LABEL")


def test_unformatted_image_rejects_label(flat_image: Path):
    with pytest.raises(RuntimeError, match="boot signature"):
        set_fat16_volume_label(flat_image, "NETLOOM")


def test_config_drive_round_trip(flat_image: Path, tmp_path: Path):
    format_fat16(flat_image, DRIVE_MB, label="NETLOOM")
    drive = ConfigDrive(tmp_path / "cfg.vmdk")
    assert drive.flat == flat_image

    src = tmp_path / "src"
    (src / "etc" / "systemd" / "network").mkdir(parents=True)
    (src / "etc" / "hostname").write_text("R1\n", encoding="utf-8")
    (src / "etc" / "systemd" / "network" / "10-eth1.network").write_text("[Match]\nName=eth1\n", encoding="utf-8")

    drive.copy_in(src)

    out = tmp_path / "out"
    copied = drive.copy_out(out)

    assert (out / "etc" / "hostname").read_text(encoding="utf-8") == "R1\n"
    assert (out / "etc" / "systemd" / "network" / "10-eth1.network").read_text(encoding="utf-8").startswith("[Match]")
    assert len(copied) == 2
