"""Base controller class for business logic."""

from typing import TYPE_CHECKING, Generic, TypeVar


if TYPE_CHECKING:
    from .application import Application


AppT = TypeVar("AppT", bound="Application")


class BaseController(Generic[AppT]):  # noqa: UP046
    """Base class for controllers."""

    def __init__(self, app: AppT) -> None:
        self._app = app

    @property
    def app(self) -> AppT:
        return self._app

    @property
    def console(self):
        return self._app.console
