"""Application singleton with dependency injection for controllers."""

from pathlib import Path
from typing import Any, Self

from rich.console import Console

from ..controllers.config import ConfigController
from ..controllers.infrastructure import InfrastructureController


class Application:
    """Main application."""

    _instance: Self | None = None

    def __init__(self) -> None:
        self._console = Console()
        self._controllers: dict[str, Any] = {}

        # workdir and topology state
        self._workdir: Path | None = None
        self._debug: bool = True

    @classmethod
    def current(cls) -> Self:
        """Get current application instance."""

        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance."""

        cls._instance = None

    @property
    def console(self) -> "Console":
        """Get rich console for displaying messages."""

        return self._console

    @property
    def workdir(self) -> Path | None:
        """Get the current working directory."""

        return self._workdir

    @workdir.setter
    def workdir(self, value: Path | str | None) -> None:
        """Set the current working directory."""

        self._workdir = Path(value) if value else None

    @property
    def debug(self) -> bool:
        """Get debug mode flag."""

        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        """Set debug mode flag."""

        self._debug = value

    @property
    def infrastructure(self) -> InfrastructureController:
        """Get infrastructure controller."""

        if "infrastructure" not in self._controllers:
            self._controllers["infrastructure"] = InfrastructureController(self)
        return self._controllers["infrastructure"]

    @property
    def config(self) -> ConfigController:
        """Get config controller."""

        if "config" not in self._controllers:
            self._controllers["config"] = ConfigController(self)
        return self._controllers["config"]
