"""TypeVars and shared type aliases for NetLoom core."""

from typing import TYPE_CHECKING, Annotated, TypeVar

from pydantic import Field, StringConstraints


if TYPE_CHECKING:
    from .application import Application

AppT = TypeVar("AppT", bound="Application")

NameID = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]+$")]
"""Safe identifier for use in filesystem paths: alphanumeric, underscores, and dashes only."""

CIDRStr = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")]
"""IPv4 CIDR notation (e.g., 10.0.12.1/24)."""

IPv4Str = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")]
"""IPv4 address without prefix."""

RouterIdStr = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")]
"""Router ID in dotted-quad format."""

PortNum = Annotated[int, Field(ge=1, le=65535)]
"""Valid TCP/UDP port number."""
