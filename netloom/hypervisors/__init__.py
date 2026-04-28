"""Hypervisor driver registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseHypervisorDriver
from .vbox import VBoxHypervisorDriver


if TYPE_CHECKING:
    pass

_registry: dict[str, type[BaseHypervisorDriver]] = {}


def register_hypervisor(name: str, cls: type[BaseHypervisorDriver]) -> None:
    """Register a hypervisor driver class under *name*."""
    _registry[name] = cls


def get_hypervisor_class(name: str) -> type[BaseHypervisorDriver]:
    """Return the driver class for *name*, raising ``KeyError`` if unknown."""
    if name not in _registry:
        available = ", ".join(sorted(_registry))
        raise KeyError(f"Unknown hypervisor '{name}'. Available: {available or '(none)'}")
    return _registry[name]


def available_hypervisors() -> list[str]:
    """Return sorted list of registered hypervisor names."""
    return sorted(_registry)


register_hypervisor("vbox", VBoxHypervisorDriver)

__all__ = [
    "BaseHypervisorDriver",
    "VBoxHypervisorDriver",
    "available_hypervisors",
    "get_hypervisor_class",
    "register_hypervisor",
]
