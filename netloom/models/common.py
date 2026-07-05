"""Common type annotations and utilities for topology models."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..core.errors import TopologyError
from .config import Topology


def load_topology(path: str | Path) -> Topology:
    """Load a YAML topology file and validate it against the schema.

    Raises ``TopologyError`` for missing files, malformed YAML and schema
    violations — callers never see raw pydantic/yaml exceptions.
    """

    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise TopologyError(f"Cannot read topology file '{p}': {exc}") from exc

    try:
        data: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise TopologyError(f"Invalid YAML in topology file '{p}':\n{exc}") from exc

    if not isinstance(data, dict):
        raise TopologyError(f"Topology file '{p}' must contain a YAML mapping at the top level.")

    try:
        return Topology(**data)
    except ValidationError as exc:
        raise TopologyError(f"Topology validation failed for '{p}':\n{exc}") from exc
