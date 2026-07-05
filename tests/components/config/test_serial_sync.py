"""Serial-sync command builder and save(sync=True) orchestration."""

import pytest

from netloom.components.config.serial_sync import GUEST_SYNC_PATHS, build_sync_command
from netloom.connect import ExecResult
from netloom.core.enums import VMState
from tests.components.infrastructure.test_controller import FakeDriver


pytestmark = pytest.mark.component


@pytest.mark.unit
def test_build_sync_command_shape():
    command = build_sync_command()

    assert "\n" not in command, "serial channel sends a single line"
    assert command.startswith("sh -c '") and command.endswith("'")
    body = command[len("sh -c '") : -1]
    assert "'" not in body, "body must not contain single quotes (it is single-quoted)"

    assert "/dev/disk/by-label/NETLOOM" in command
    assert "/dev/sdb" in command, "fallback for pre-label drives"
    for path in GUEST_SYNC_PATHS:
        assert path in command
    assert "umount" in command


@pytest.mark.unit
def test_build_sync_command_custom_label():
    command = build_sync_command(label="CUSTOM", fallback_device="/dev/vdb")
    assert "/dev/disk/by-label/CUSTOM" in command
    assert "/dev/vdb" in command


def test_save_sync_runs_shell_only_for_running_nodes(app, internal, mocker):
    driver = FakeDriver(states={"R1": VMState.RUNNING, "R2": VMState.POWEROFF})
    app.hypervisor = driver

    shell = mocker.MagicMock()
    shell.run.return_value = ExecResult(command="sync", output="", exit_code=0)
    shell_cls = mocker.patch("netloom.connect.SerialShell")
    shell_cls.return_value.__enter__.return_value = shell

    app.config.save(internal, sync=True)

    shell_cls.assert_called_once_with("127.0.0.1", 5000)
    assert shell.run.call_count == 1, "only the single RUNNING node gets a serial sync"
    command = shell.run.call_args.args[0]
    assert "mount" in command and "umount" in command

    extracted = {name for op, name in driver.calls if op == "extract_configs"}
    assert extracted == {n.name for n in internal.nodes}, "extraction still runs for every node"


def test_save_without_sync_never_touches_serial(app, internal, mocker):
    app.hypervisor = FakeDriver()
    shell_cls = mocker.patch("netloom.connect.SerialShell")

    app.config.save(internal, sync=False)

    shell_cls.assert_not_called()
