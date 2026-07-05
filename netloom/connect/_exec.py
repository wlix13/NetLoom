"""Minimal serial-console command execution — skeleton.

Drives a root shell exposed on a VM's serial console (an autologin getty on
ttyS0, reachable through the hypervisor's tcp-serial endpoint). Commands are
bracketed with a unique sentinel so their exit status can be picked out of
the raw console stream.

Skeleton limitations (documented on purpose):
- assumes a shell is already at a prompt (autologin getty, nobody mid-login);
- console echo is not stripped from captured output beyond the marker scan;
- no terminal-size or control-sequence handling — commands should be plain,
  single-line POSIX sh.
"""

from __future__ import annotations

import re
import socket
import time
import uuid
from dataclasses import dataclass

from netloom.core.errors import SerialConsoleError


_MARKER_TEMPLATE = "__NETLOOM_{token}_{{status}}__"


@dataclass(frozen=True, slots=True)
class ExecResult:
    """Outcome of one command executed over the serial console."""

    command: str
    output: str
    exit_code: int


class SerialShell:
    """A tiny exec channel over a tcp-serial console.

    Usage::

        with SerialShell(host, port) as shell:
            result = shell.run("cat /etc/hostname")
    """

    def __init__(self, host: str, port: int, *, connect_timeout: float = 5.0, read_timeout: float = 60.0) -> None:
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self._sock: socket.socket | None = None

    def __enter__(self) -> SerialShell:
        try:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout)
        except OSError as exc:
            raise SerialConsoleError(f"Cannot connect to serial console {self.host}:{self.port}: {exc}") from exc
        self._sock.settimeout(0.5)
        self._wake()
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _require_sock(self) -> socket.socket:
        if self._sock is None:
            raise SerialConsoleError("Serial shell is not connected — use it as a context manager.")
        return self._sock

    def _wake(self) -> None:
        """Nudge the console so a prompt is drawn, and drain pending output."""
        sock = self._require_sock()
        try:
            sock.sendall(b"\r\n")
        except OSError as exc:
            raise SerialConsoleError(f"Serial console write failed: {exc}") from exc
        self._drain(0.5)

    def _drain(self, duration: float) -> None:
        sock = self._require_sock()
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            try:
                if not sock.recv(4096):
                    raise SerialConsoleError("Serial console closed by peer.")
            except TimeoutError:
                continue
            except OSError as exc:
                raise SerialConsoleError(f"Serial console read failed: {exc}") from exc

    def run(self, command: str, *, timeout: float | None = None) -> ExecResult:
        """Execute *command* in the guest shell and return output + exit code.

        The command is wrapped so the guest prints
        ``__NETLOOM_<token>_<status>__`` when it finishes; everything received
        up to that marker is returned as raw output.
        """
        if "\n" in command:
            raise SerialConsoleError("Serial commands must be single-line; join with '&&' or ';' instead.")

        sock = self._require_sock()
        token = uuid.uuid4().hex[:12]
        marker = _MARKER_TEMPLATE.format(token=token)
        marker_re = re.compile(marker.format(status=r"(\d+)").encode("ascii"))
        wrapped = f"{command}; printf '\\n{marker.format(status='%s')}\\n' $?\r\n"

        try:
            sock.sendall(wrapped.encode("utf-8"))
        except OSError as exc:
            raise SerialConsoleError(f"Serial console write failed: {exc}") from exc

        buffer = bytearray()
        deadline = time.monotonic() + (timeout if timeout is not None else self.read_timeout)
        while True:
            match = marker_re.search(buffer)
            if match:
                output = buffer[: match.start()].decode("utf-8", errors="replace")
                return ExecResult(command=command, output=output.strip(), exit_code=int(match.group(1)))
            if time.monotonic() > deadline:
                raise SerialConsoleError(
                    f"Timed out after {timeout or self.read_timeout:.0f}s waiting for command to finish: {command!r}"
                )
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue
            except OSError as exc:
                raise SerialConsoleError(f"Serial console read failed: {exc}") from exc
            if not chunk:
                raise SerialConsoleError("Serial console closed by peer while waiting for command output.")
            buffer.extend(chunk)
