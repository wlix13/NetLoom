"""Application singleton with dependency injection for controllers."""

from functools import cached_property
from pathlib import Path
from typing import ClassVar

from rich.console import Console

from ..controllers.config import ConfigController
from ..controllers.infrastructure import InfrastructureController
from .vbox import VBoxSettings


class Application:
    """Main application."""

    _instance: ClassVar["Application | None"] = None

    def __init__(self) -> None:
        self._console = Console()
        self._workdir: Path | None = None
        self._debug: bool = True
        self.vbox_settings: VBoxSettings = VBoxSettings()

    @classmethod
    def current(cls) -> "Application":
        """Get current application instance."""

        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance."""

        cls._instance = None

    @property
    def console(self) -> Console:
        """Rich console for user-facing output."""
        return self._console

    @property
    def workdir(self) -> Path | None:
        return self._workdir

    @workdir.setter
    def workdir(self, value: Path | str | None) -> None:
        self._workdir = Path(value) if value else None

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        self._debug = value

    @cached_property
    def infrastructure(self) -> InfrastructureController:
        """Infrastructure controller."""

        return InfrastructureController(self)

    @cached_property
    def config(self) -> ConfigController:
        """Config controller."""

        return ConfigController(self)
