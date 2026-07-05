"""SerialShell exec channel against a fake tcp-serial console."""

import re
import socket
import threading

import pytest

from netloom.connect import SerialShell
from netloom.core.errors import SerialConsoleError


pytestmark = pytest.mark.component

_TOKEN_RE = re.compile(rb"__NETLOOM_([0-9a-f]{12})_%s__")


class FakeConsole(threading.Thread):
    """Accepts one connection and answers marker-wrapped commands like a shell would."""

    def __init__(self, *, exit_code: int = 0, respond: bool = True) -> None:
        super().__init__(daemon=True)
        self.exit_code = exit_code
        self.respond = respond
        self.received = b""
        self._server = socket.create_server(("127.0.0.1", 0))
        self.port = self._server.getsockname()[1]

    def run(self) -> None:
        conn, _ = self._server.accept()
        conn.settimeout(5.0)
        with conn:
            while True:
                try:
                    chunk = conn.recv(4096)
                except TimeoutError:
                    return
                if not chunk:
                    return
                self.received += chunk
                match = _TOKEN_RE.search(self.received)
                if match and self.respond:
                    token = match.group(1)
                    conn.sendall(
                        b"$ echoed-command\r\nline-1\r\nline-2\r\n__NETLOOM_" + token + b"_%d__\r\n" % self.exit_code
                    )
                    return

    def close(self) -> None:
        self._server.close()


def test_run_returns_output_and_exit_code():
    console = FakeConsole(exit_code=0)
    console.start()
    try:
        with SerialShell("127.0.0.1", console.port, read_timeout=5.0) as shell:
            result = shell.run("do-something")
    finally:
        console.close()

    assert result.exit_code == 0
    assert "line-1" in result.output
    assert "line-2" in result.output
    assert b"do-something; printf" in console.received, "command must be marker-wrapped"


def test_run_reports_nonzero_exit_code():
    console = FakeConsole(exit_code=3)
    console.start()
    try:
        with SerialShell("127.0.0.1", console.port, read_timeout=5.0) as shell:
            result = shell.run("failing-command")
    finally:
        console.close()

    assert result.exit_code == 3


def test_run_times_out_without_marker():
    console = FakeConsole(respond=False)
    console.start()
    try:
        with SerialShell("127.0.0.1", console.port, read_timeout=5.0) as shell:
            with pytest.raises(SerialConsoleError, match="Timed out"):
                shell.run("never-finishes", timeout=1.0)
    finally:
        console.close()


def test_multiline_commands_rejected():
    console = FakeConsole()
    console.start()
    try:
        with SerialShell("127.0.0.1", console.port, read_timeout=5.0) as shell:
            with pytest.raises(SerialConsoleError, match="single-line"):
                shell.run("a\nb")
    finally:
        console.close()


def test_connect_refused_raises():
    sacrificial = socket.create_server(("127.0.0.1", 0))
    port = sacrificial.getsockname()[1]
    sacrificial.close()

    with pytest.raises(SerialConsoleError, match="Cannot connect"):
        with SerialShell("127.0.0.1", port, connect_timeout=1.0):
            pass
