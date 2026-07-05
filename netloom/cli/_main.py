"""CLI entry point: UTF-8 console setup and centralized error handling."""

from __future__ import annotations

import io
import sys


def _ensure_utf8_io() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows.

    Piped or redirected output on Windows defaults to the legacy ANSI code
    page (e.g. cp1252), which cannot encode the box-drawing and arrow glyphs
    Rich emits — ``netloom show > out.txt`` would crash with
    ``UnicodeEncodeError``.
    """

    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper) and stream.encoding.lower().replace("-", "") != "utf8":
            stream.reconfigure(encoding="utf-8", errors="replace")


# Must run before the Rich Console is created (Application is instantiated at
# import time in ._group, and Rich probes the streams when a Console is built).
_ensure_utf8_io()

from click.exceptions import Abort, ClickException, Exit  # noqa: E402
from rich.console import Console  # noqa: E402

from netloom.core.application import Application  # noqa: E402
from netloom.core.errors import NetLoomError  # noqa: E402

from . import completion  # noqa: E402, F401  — registers the install-completion command
from ._group import cli  # noqa: E402


_err = Console(stderr=True)


def main() -> None:
    """Console-script entry point with centralized error handling.

    ``standalone_mode=False`` makes Click raise instead of calling
    ``sys.exit()`` internally, so every failure mode is translated to an
    exit code in exactly one place.
    """

    try:
        cli(standalone_mode=False)
    except ClickException as e:
        e.show()
        raise SystemExit(e.exit_code) from None
    except NetLoomError as e:
        _err.print(f"[red bold]Error:[/red bold] {e}")
        raise SystemExit(1) from None
    except Exit as e:
        raise SystemExit(e.exit_code) from None
    except Abort:
        _err.print("\n[yellow]Aborted.[/yellow]")
        raise SystemExit(130) from None
    except KeyboardInterrupt:
        _err.print("\n[yellow]Interrupted.[/yellow]")
        raise SystemExit(130) from None
    except Exception as e:
        if Application.current().debug:
            raise
        _err.print(f"[red bold]Unexpected error:[/red bold] {e}")
        _err.print("[dim]Run with --debug for the full traceback.[/dim]")
        raise SystemExit(1) from None
