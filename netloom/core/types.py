"""TypeVars for generic base classes."""

from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from .application import Application

AppT = TypeVar("AppT", bound="Application")
