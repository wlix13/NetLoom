"""Application singleton with component registry and hypervisor slot."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from rich.console import Console

from .errors import HypervisorError


if TYPE_CHECKING:
    from netloom.components.config.controller import ConfigController
    from netloom.components.infrastructure.controller import InfrastructureController
    from netloom.core.component import BaseComponent
    from netloom.hypervisors.base import BaseHypervisorDriver


class Application:
    """Main application singleton.

    Components are registered by class via ``register()``; each component
    exposes its controller as ``app.<name>`` (e.g. ``app.infrastructure``,
    ``app.config``).

    The active hypervisor driver is held in ``app.hypervisor``; it must be
    set before any infrastructure commands are invoked.
    """

    # Class-level sentinel — absent until the first instance is created.
    # hasattr() avoids carrying None as a valid type on every access.
    _instance: ClassVar[Application]

    if TYPE_CHECKING:
        # Populated dynamically by register(); declared here for the type checker.
        config: ConfigController
        infrastructure: InfrastructureController

    def __init__(self) -> None:
        if hasattr(Application, "_instance"):
            return
        Application._instance = self
        self._console = Console()
        self._workdir: Path = Path()
        self._debug: bool = False
        self._hypervisor: BaseHypervisorDriver | None = None
        self.components: dict[type[BaseComponent], BaseComponent] = {}

    # ── singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def current(cls) -> Application:
        """Return (or lazily create) the singleton instance."""
        if not hasattr(Application, "_instance"):
            Application._instance = cls()
        return Application._instance

    @classmethod
    def reset(cls) -> None:
        """Destroy the singleton — useful in tests."""
        if hasattr(Application, "_instance"):
            del Application._instance

    # ── component registry ────────────────────────────────────────────────────

    def register(self, cls: type[BaseComponent]) -> None:
        """Instantiate *cls*, expose its controller, then call ``on_register()``."""
        instance = cls(self)  # type: ignore[arg-type]
        self.components[cls] = instance
        if instance.expose_controller:
            setattr(self, instance.name, instance.controller)
        instance.on_register()

    def deregister(self, cls: type[BaseComponent]) -> None:
        """Reverse ``register()`` — calls ``on_deregister()`` and removes the attribute."""
        instance = self.components.pop(cls)
        instance.on_deregister()
        if instance.expose_controller:
            delattr(self, instance.name)

    # ── properties ────────────────────────────────────────────────────────────

    @property
    def console(self) -> Console:
        return self._console

    @property
    def workdir(self) -> Path:
        return self._workdir

    @workdir.setter
    def workdir(self, value: Path | str) -> None:
        self._workdir = Path(value)

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        self._debug = value

    @property
    def hypervisor(self) -> BaseHypervisorDriver:
        if self._hypervisor is None:
            raise HypervisorError("No hypervisor driver registered. Pass --hypervisor or check CLI setup.")
        return self._hypervisor

    @hypervisor.setter
    def hypervisor(self, driver: BaseHypervisorDriver) -> None:
        self._hypervisor = driver
