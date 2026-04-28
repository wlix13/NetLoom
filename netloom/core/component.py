"""Base component class for the NetLoom plugin architecture."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar

import rich_click as click

from .types import AppT


if TYPE_CHECKING:
    pass

CtrlT = TypeVar("CtrlT")


class BaseComponent(Generic[AppT, CtrlT]):  # noqa: UP046
    """Owns lifecycle only — zero business logic.

    Business logic lives exclusively in ``controller_class``.
    Subclasses declare CLI commands via ``expose_cli()`` and react to
    registration events via ``on_register()`` / ``on_deregister()``.
    """

    name: ClassVar[str]
    controller_class: ClassVar[type]
    expose_controller: ClassVar[bool] = True

    def __init__(self, app: AppT) -> None:
        self.app = app
        self.controller: CtrlT = self.controller_class(app)  # type: ignore[assignment]

    def on_register(self) -> None:
        """Called immediately after this component is registered with the Application."""

    def on_deregister(self) -> None:
        """Called before this component is deregistered from the Application."""

    def expose_cli(self, base: click.Group) -> None:
        """Attach CLI sub-commands to *base*."""
