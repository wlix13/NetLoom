"""Fault-injection component: deploy deliberately broken labs for students to fix."""

from .component import FaultsComponent
from .controller import FaultsController


__all__ = ["FaultsComponent", "FaultsController"]
