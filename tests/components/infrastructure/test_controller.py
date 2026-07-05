"""Infrastructure controller orchestration against a fake hypervisor driver."""

from pathlib import Path

import pytest

from netloom.components.infrastructure.errors import NoConsoleConnection, VMNotCreated, VMNotRunning
from netloom.core.enums import VMState
from netloom.hypervisors.base import BaseHypervisorDriver, ConnectionInfo


class FakeDriver(BaseHypervisorDriver):
    """In-memory driver: system boundary fake, records every call."""

    def __init__(self, states: dict[str, VMState] | None = None, with_console: bool = True) -> None:
        self.states: dict[str, VMState] = dict(states or {})
        self.with_console = with_console
        self.calls: list[tuple[str, str]] = []

    def list_vms(self) -> dict[str, str]:
        return {name: f"uuid-{name}" for name in self.states}

    def get_vm_state(self, name: str) -> VMState | None:
        return self.states.get(name)

    def get_connection_info(self, name: str) -> ConnectionInfo | None:
        if not self.with_console:
            return None
        return ConnectionInfo(protocol="tcp-serial", host="127.0.0.1", port=5000)

    def ensure_base_vm(self, topo) -> None:
        self.calls.append(("ensure_base_vm", topo.id))

    def create_node_vm(self, node, topo, node_idx: int) -> None:
        self.calls.append(("create_node_vm", node.name))
        self.states[node.name] = VMState.POWEROFF

    def inject_configs(self, node, config_dir: Path) -> None:
        self.calls.append(("inject_configs", node.name))

    def extract_configs(self, node, dest_dir: Path) -> list[Path]:
        self.calls.append(("extract_configs", node.name))
        return []

    def start_vm(self, name: str) -> None:
        self.calls.append(("start_vm", name))
        self.states[name] = VMState.RUNNING

    def stop_vm(self, name: str) -> None:
        self.calls.append(("stop_vm", name))
        self.states[name] = VMState.POWEROFF

    def destroy_vm(self, name: str) -> bool:
        self.calls.append(("destroy_vm", name))
        return self.states.pop(name, None) is not None

    def destroy_base_vm(self) -> None:
        self.calls.append(("destroy_base_vm", ""))


@pytest.fixture
def driver(app):
    fake = FakeDriver()
    app.hypervisor = fake
    return fake


@pytest.mark.component
def test_create_then_start_boots_every_node(app, internal, driver):
    app.infrastructure.create(internal)
    app.infrastructure.start(internal)

    started = {name for op, name in driver.calls if op == "start_vm"}
    assert started == {n.name for n in internal.nodes}
    assert all(state == VMState.RUNNING for state in driver.states.values())


@pytest.mark.component
def test_status_reports_connection_only_for_running(app, internal, driver):
    driver.states = {"R1": VMState.RUNNING, "R2": VMState.POWEROFF}

    rows = {row.name: row for row in app.infrastructure.status(internal)}
    assert rows["R1"].state == VMState.RUNNING
    assert rows["R1"].connection is not None
    assert rows["R2"].connection is None
    assert rows["R3"].state is None, "uncreated VM reports state None"


@pytest.mark.component
def test_stop_only_signals_running_vms(app, internal, driver):
    driver.states = {"R1": VMState.RUNNING, "R2": VMState.POWEROFF}

    app.infrastructure.stop(internal)

    stopped = [name for op, name in driver.calls if op == "stop_vm"]
    assert stopped == ["R1"]


@pytest.mark.component
def test_destroy_base_only_when_requested(app, internal, driver):
    driver.states = {n.name: VMState.POWEROFF for n in internal.nodes}

    app.infrastructure.destroy(internal)
    assert ("destroy_base_vm", "") not in driver.calls

    app.infrastructure.destroy(internal, destroy_base=True)
    assert ("destroy_base_vm", "") in driver.calls


@pytest.mark.component
def test_prepare_connect_error_paths(app, internal, driver):
    driver.states = {"R2": VMState.POWEROFF, "R1": VMState.RUNNING}

    with pytest.raises(VMNotCreated):
        app.infrastructure.prepare_connect("R3")
    with pytest.raises(VMNotRunning):
        app.infrastructure.prepare_connect("R2")

    info = app.infrastructure.prepare_connect("R1")
    assert (info.protocol, info.host, info.port) == ("tcp-serial", "127.0.0.1", 5000)

    driver.with_console = False
    with pytest.raises(NoConsoleConnection):
        app.infrastructure.prepare_connect("R1")
