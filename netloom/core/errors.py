"""Base exception classes for NetLoom."""


class NetLoomError(Exception):
    """Base class for all NetLoom errors."""


class TopologyError(NetLoomError):
    """Raised for topology validation and lookup failures."""


class InfrastructureError(NetLoomError):
    """Raised for VirtualBox / infrastructure operation failures."""


class ConfigurationError(NetLoomError):
    """Raised for template rendering and configuration errors."""
