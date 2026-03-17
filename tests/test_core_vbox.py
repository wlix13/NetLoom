"""Tests for netloom.core.vbox module."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from netloom.core.enums import VMStartType
from netloom.core.vbox import VBoxManage, VBoxSettings


class TestVBoxSettings:
    """Test VBoxSettings dataclass."""

    def test_default_values(self):
        """VBoxSettings should have sensible defaults."""
        settings = VBoxSettings()
        assert settings.basefolder == Path.cwd() / ".labs_vms"
        assert settings.ova_path is None
        assert settings.base_vm_name == "Labs-Base"
        assert settings.snapshot_name == "golden"
        assert settings.configdrive_mb == 128
        assert settings.controller_name == "Disks"

    def test_custom_values(self):
        """VBoxSettings should accept custom values."""
        settings = VBoxSettings(
            basefolder=Path("/custom/path"),
            ova_path=Path("/custom/base.ova"),
            base_vm_name="CustomBase",
            snapshot_name="custom-snap",
            configdrive_mb=256,
            controller_name="Storage",
        )
        assert settings.basefolder == Path("/custom/path")
        assert settings.ova_path == Path("/custom/base.ova")
        assert settings.base_vm_name == "CustomBase"
        assert settings.snapshot_name == "custom-snap"
        assert settings.configdrive_mb == 256
        assert settings.controller_name == "Storage"

    def test_partial_initialization(self):
        """VBoxSettings should use defaults for unspecified values."""
        settings = VBoxSettings(base_vm_name="MyBase")
        assert settings.base_vm_name == "MyBase"
        assert settings.snapshot_name == "golden"  # default


class TestVBoxManageListVms:
    """Test VBoxManage.list_vms method."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_list_vms_empty(self, mock_run):
        """Should handle empty VM list."""
        mock_run.return_value = MagicMock(stdout="")
        vbox = VBoxManage()
        result = vbox.list_vms()
        assert result == {}
        mock_run.assert_called_once()

    @patch("netloom.core.vbox.subprocess.run")
    def test_list_vms_single(self, mock_run):
        """Should parse single VM correctly."""
        mock_run.return_value = MagicMock(
            stdout='"TestVM" {12345678-1234-1234-1234-123456789abc}\n'
        )
        vbox = VBoxManage()
        result = vbox.list_vms()
        assert result == {"TestVM": "12345678-1234-1234-1234-123456789abc"}

    @patch("netloom.core.vbox.subprocess.run")
    def test_list_vms_multiple(self, mock_run):
        """Should parse multiple VMs correctly."""
        mock_run.return_value = MagicMock(
            stdout=(
                '"VM1" {11111111-1111-1111-1111-111111111111}\n'
                '"VM2" {22222222-2222-2222-2222-222222222222}\n'
            )
        )
        vbox = VBoxManage()
        result = vbox.list_vms()
        assert len(result) == 2
        assert result["VM1"] == "11111111-1111-1111-1111-111111111111"
        assert result["VM2"] == "22222222-2222-2222-2222-222222222222"

    @patch("netloom.core.vbox.subprocess.run")
    def test_list_vms_with_blank_lines(self, mock_run):
        """Should ignore blank lines."""
        mock_run.return_value = MagicMock(
            stdout=(
                '"VM1" {11111111-1111-1111-1111-111111111111}\n'
                '\n'
                '"VM2" {22222222-2222-2222-2222-222222222222}\n'
            )
        )
        vbox = VBoxManage()
        result = vbox.list_vms()
        assert len(result) == 2


class TestVBoxManageBasicCommands:
    """Test basic VBoxManage command methods."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_list_hdds(self, mock_run):
        """Should return raw stdout from list hdds."""
        expected = "UUID: 12345\nLocation: /path/to/disk.vdi\n"
        mock_run.return_value = MagicMock(stdout=expected)
        vbox = VBoxManage()
        result = vbox.list_hdds()
        assert result == expected
        mock_run.assert_called_once_with(
            ["VBoxManage", "list", "hdds"],
            check=True,
            capture_output=True,
            text=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_show_vm_info(self, mock_run):
        """Should return VM info."""
        expected = 'VMState="running"\n'
        mock_run.return_value = MagicMock(stdout=expected)
        vbox = VBoxManage()
        result = vbox.show_vm_info("TestVM")
        assert result == expected

    @patch("netloom.core.vbox.subprocess.run")
    def test_list_snapshots(self, mock_run):
        """Should return snapshot list."""
        expected = "SnapshotName: golden\n"
        mock_run.return_value = MagicMock(stdout=expected)
        vbox = VBoxManage()
        result = vbox.list_snapshots("TestVM")
        assert result == expected


class TestVBoxManageImportAndSnapshot:
    """Test import and snapshot operations."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_import_ova(self, mock_run):
        """Should call VBoxManage import with correct args."""
        vbox = VBoxManage()
        vbox.import_ova(
            ova_path=Path("/path/to/base.ova"),
            vm_name="BaseVM",
            basefolder=Path("/vms"),
        )
        mock_run.assert_called_once_with(
            [
                "VBoxManage",
                "import",
                "/path/to/base.ova",
                "--vsys",
                "0",
                "--vmname",
                "BaseVM",
                "--basefolder",
                "/vms",
            ],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_take_snapshot(self, mock_run):
        """Should call VBoxManage snapshot take."""
        vbox = VBoxManage()
        vbox.take_snapshot("TestVM", "snapshot1")
        mock_run.assert_called_once_with(
            ["VBoxManage", "snapshot", "TestVM", "take", "snapshot1"],
            check=True,
            capture_output=True,
        )


class TestVBoxManageCloneAndStart:
    """Test clone and start operations."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_clone_vm(self, mock_run):
        """Should call VBoxManage clonevm with correct args."""
        vbox = VBoxManage()
        vbox.clone_vm(
            source="BaseVM",
            snapshot="golden",
            name="CloneVM",
            basefolder=Path("/vms"),
        )
        mock_run.assert_called_once_with(
            [
                "VBoxManage",
                "clonevm",
                "BaseVM",
                "--snapshot",
                "golden",
                "--name",
                "CloneVM",
                "--options",
                "link",
                "--register",
                "--basefolder",
                "/vms",
            ],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_start_vm(self, mock_run):
        """Should call VBoxManage startvm in headless mode."""
        vbox = VBoxManage()
        vbox.start_vm("TestVM")
        mock_run.assert_called_once_with(
            ["VBoxManage", "startvm", "TestVM", "--type", "headless"],
            check=True,
            capture_output=True,
        )


class TestVBoxManageControl:
    """Test VM control operations."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_control_vm(self, mock_run):
        """Should call VBoxManage controlvm with action."""
        vbox = VBoxManage()
        vbox.control_vm("TestVM", "acpipowerbutton")
        mock_run.assert_called_once_with(
            ["VBoxManage", "controlvm", "TestVM", "acpipowerbutton"],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_unregister_vm_without_delete(self, mock_run):
        """Should unregister VM without deleting files."""
        vbox = VBoxManage()
        vbox.unregister_vm("TestVM", delete=False)
        mock_run.assert_called_once_with(
            ["VBoxManage", "unregistervm", "TestVM"],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_unregister_vm_with_delete(self, mock_run):
        """Should unregister and delete VM files."""
        vbox = VBoxManage()
        vbox.unregister_vm("TestVM", delete=True)
        mock_run.assert_called_once_with(
            ["VBoxManage", "unregistervm", "TestVM", "--delete"],
            check=True,
            capture_output=True,
        )


class TestVBoxManageModify:
    """Test modify VM operations."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_modify_vm(self, mock_run):
        """Should call VBoxManage modifyvm with args."""
        vbox = VBoxManage()
        vbox.modify_vm("TestVM", "--memory", "2048", "--cpus", "2")
        mock_run.assert_called_once_with(
            ["VBoxManage", "modifyvm", "TestVM", "--memory", "2048", "--cpus", "2"],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_modify_vm_no_args(self, mock_run):
        """Should handle modifyvm with no additional args."""
        vbox = VBoxManage()
        vbox.modify_vm("TestVM")
        mock_run.assert_called_once_with(
            ["VBoxManage", "modifyvm", "TestVM"],
            check=True,
            capture_output=True,
        )


class TestVBoxManageStorage:
    """Test storage operations."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_storage_ctl(self, mock_run):
        """Should add storage controller."""
        vbox = VBoxManage()
        vbox.storage_ctl("TestVM", "SATA", add="sata", controller="IntelAhci")
        mock_run.assert_called_once_with(
            [
                "VBoxManage",
                "storagectl",
                "TestVM",
                "--name",
                "SATA",
                "--add",
                "sata",
                "--controller",
                "IntelAhci",
            ],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_storage_attach(self, mock_run):
        """Should attach storage medium."""
        vbox = VBoxManage()
        vbox.storage_attach(
            "TestVM",
            storagectl="SATA",
            port=1,
            device=0,
            medium_type="hdd",
            medium="/path/to/disk.vmdk",
        )
        mock_run.assert_called_once_with(
            [
                "VBoxManage",
                "storageattach",
                "TestVM",
                "--storagectl",
                "SATA",
                "--port",
                "1",
                "--device",
                "0",
                "--type",
                "hdd",
                "--medium",
                "/path/to/disk.vmdk",
            ],
            check=True,
            capture_output=True,
        )


class TestVBoxManageMedium:
    """Test medium operations."""

    @patch("netloom.core.vbox.subprocess.run")
    def test_create_medium_defaults(self, mock_run):
        """Should create medium with default format and variant."""
        vbox = VBoxManage()
        vbox.create_medium(Path("/path/to/disk.vmdk"), size_mb=128)
        mock_run.assert_called_once_with(
            [
                "VBoxManage",
                "createmedium",
                "disk",
                "--format=VMDK",
                "--variant=fixed",
                "--size",
                "128",
                "--filename",
                "/path/to/disk.vmdk",
            ],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_create_medium_custom_format(self, mock_run):
        """Should create medium with custom format."""
        vbox = VBoxManage()
        vbox.create_medium(
            Path("/path/to/disk.vdi"),
            size_mb=256,
            fmt="VDI",
            variant="dynamic",
        )
        mock_run.assert_called_once_with(
            [
                "VBoxManage",
                "createmedium",
                "disk",
                "--format=VDI",
                "--variant=dynamic",
                "--size",
                "256",
                "--filename",
                "/path/to/disk.vdi",
            ],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_close_medium_without_delete(self, mock_run):
        """Should close medium without deleting."""
        vbox = VBoxManage()
        vbox.close_medium("12345-uuid", delete=False)
        mock_run.assert_called_once_with(
            ["VBoxManage", "closemedium", "disk", "12345-uuid"],
            check=True,
            capture_output=True,
        )

    @patch("netloom.core.vbox.subprocess.run")
    def test_close_medium_with_delete(self, mock_run):
        """Should close and delete medium."""
        vbox = VBoxManage()
        vbox.close_medium("12345-uuid", delete=True)
        mock_run.assert_called_once_with(
            ["VBoxManage", "closemedium", "disk", "12345-uuid", "--delete"],
            check=True,
            capture_output=True,
        )