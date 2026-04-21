"""Cross-platform terminal primitives: raw mode, size query, resize command."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from ._scancodes import WIN_SCANCODES


ReadByte = Callable[[float | None], bytes | None]


def host_term_size() -> tuple[int, int] | None:
    """Return (cols, rows) of the host terminal if attached to tty."""

    try:
        sz = os.get_terminal_size()
        return (sz.columns, sz.lines)
    except OSError:
        return None


def size_cmd(cols: int, rows: int) -> bytes:
    """Build shell command that sets guest terminal to (cols x rows)."""

    return f"stty rows {rows} cols {cols}\r".encode()


@contextmanager
def raw_terminal() -> Iterator[ReadByte]:
    """Put stdin into character-at-a-time mode; yield a polling read function.

    The yielded callable takes a timeout in seconds (None = block) and returns
    the next input byte. On POSIX, stdin is switched to cbreak and restored on exit.
    On Windows, msvcrt already bypasses line mode, and two-byte scan codes are translated to escape sequences.
    """

    if sys.platform == "win32":
        import msvcrt
        import time

        def _read_one() -> bytes:
            b = msvcrt.getch()
            if b[0] in (0x00, 0xE0):
                second = msvcrt.getch()
                return WIN_SCANCODES.get((b[0], second[0]), b"")
            return b

        def read_byte(timeout: float | None) -> bytes | None:
            if timeout is None:
                return _read_one()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if msvcrt.kbhit():
                    return _read_one()
                time.sleep(0.005)
            return None

        yield read_byte

    elif sys.platform in ("linux", "darwin"):
        import select
        import termios
        import tty

        if not sys.stdin.isatty():
            raise RuntimeError("stdin is not a TTY; cannot enter raw terminal mode")
        fd = sys.stdin.fileno()
        try:
            saved = termios.tcgetattr(fd)
        except (termios.error, OSError) as e:
            raise RuntimeError(f"Cannot configure terminal: {e}") from e
        try:
            tty.setcbreak(fd)

            def read_byte(timeout: float | None) -> bytes | None:
                r, _, _ = select.select([fd], [], [], timeout)
                if not r:
                    return None
                data = os.read(fd, 1)
                if not data:
                    raise EOFError
                return data

            yield read_byte
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)

    else:
        raise RuntimeError(f"Platform '{sys.platform}' is not supported by serial bridge.")
