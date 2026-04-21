"""Interactive TCP <-> terminal bridge for VirtualBox UART tcpserver sockets."""

from __future__ import annotations

import socket
import sys
import threading
from typing import TYPE_CHECKING

from ._terminal import host_term_size, raw_terminal, size_cmd


if TYPE_CHECKING:
    from rich.console import Console


CTRL_RSB = 0x1D  # Ctrl-]: classic telnet escape
_POLL_INTERVAL = 0.2


def run_bridge(host: str, port: int, console: Console, escape: int = CTRL_RSB) -> int:
    """Open interactive TCP-UART bridge."""

    try:
        sock = socket.create_connection((host, port), timeout=3)
    except (ConnectionRefusedError, TimeoutError, OSError) as e:
        console.print(
            f"[red]Cannot connect to {host}:{port}:[/red] {e}. [dim]VM may still be booting — retry in a moment.[/dim]"
        )
        return 2

    sock.settimeout(None)

    term_size = host_term_size()
    if term_size:
        cols, rows = term_size
        console.print(
            f"[green]Connected to[/green] {host}:{port} "
            f"[dim](host: {cols}×{rows})[/dim]. "
            "[dim]Press Ctrl-] to disconnect.[/dim]"
        )
        if sys.platform == "win32":
            console.print(f"[dim]Resize hint: stty rows {rows} cols {cols}[/dim]")
    else:
        console.print(f"[green]Connected to[/green] {host}:{port}. [dim]Press Ctrl-] to disconnect.[/dim]")

    stop_evt = threading.Event()

    def reader() -> None:
        try:
            while not stop_evt.is_set():
                data = sock.recv(4096)
                if not data:
                    break
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()
        except OSError:
            pass
        finally:
            stop_evt.set()

    thread = threading.Thread(target=reader, name="serial-bridge-reader", daemon=True)
    thread.start()

    # On POSIX, queue stty commands when the host terminal is resized.
    _pending_resize: list[tuple[int, int]] = [term_size] if term_size else []
    _old_sigwinch = None

    if sys.platform != "win32":
        import signal

        def _on_winch(signum: int, frame: object) -> None:
            sz = host_term_size()
            if sz:
                _pending_resize.append(sz)

        _old_sigwinch = signal.signal(signal.SIGWINCH, _on_winch)

    try:
        with raw_terminal() as read_byte:
            while not stop_evt.is_set():
                if _pending_resize:
                    cols, rows = _pending_resize[-1]
                    _pending_resize.clear()
                    try:
                        sock.sendall(size_cmd(cols, rows))
                    except OSError:
                        stop_evt.set()

                try:
                    b: bytes | None = read_byte(_POLL_INTERVAL)
                except EOFError:
                    break
                if not b:
                    continue
                if b[0] == escape:
                    break
                try:
                    sock.sendall(b)
                except OSError:
                    break
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError) as e:
        stop_evt.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        thread.join(timeout=1)
        console.print(f"[red]Terminal error:[/red] {e}")
        return 1
    finally:
        if _old_sigwinch is not None:
            import signal

            signal.signal(signal.SIGWINCH, _old_sigwinch)
        stop_evt.set()
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()
        thread.join(timeout=1)
        console.print()
        console.print("[dim]Disconnected.[/dim]")

    return 0
