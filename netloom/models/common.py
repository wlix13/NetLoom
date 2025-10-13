"""Common type annotations and utilities for topology models."""

from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import Field, StringConstraints, ValidationError

from .config import Topology


NameID = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]+$")]
"""Valid identifier: alphanumeric with underscores and dashes."""

CIDRStr = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")]
"""IPv4 CIDR notation (e.g., 10.0.12.1/24)."""

IPv4Str = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")]
"""IPv4 address without prefix."""

RouterIdStr = Annotated[str, StringConstraints(pattern=r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")]
"""Router ID in dotted-quad format."""

PortNum = Annotated[int, Field(ge=1, le=65535)]
"""Valid TCP/UDP port number."""


def load_topology(path: str | Path) -> Topology:
    """Load YAML topology file and validate against schema."""

    p = Path(path)
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))

    try:
        return Topology(**data)
    except ValidationError as ve:
        raise SystemExit(f"[Topology Validation Error]\n{ve}") from ve
