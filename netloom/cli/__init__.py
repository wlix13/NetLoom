"""NetLoom CLI package."""

# Commands are registered on the cli group by components in _group.py at import time.
from . import completion  # noqa: F401
from ._group import cli


__all__ = ["cli"]
