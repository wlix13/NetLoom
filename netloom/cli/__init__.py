"""NetLoom CLI package."""

# Import submodules to register commands on the cli group
from . import completion, infra, lifecycle, manage, show  # noqa: F401
from ._group import cli


__all__ = ["cli"]
