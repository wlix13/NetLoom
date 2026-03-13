"""Common type annotations and utilities for topology models."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .config import Topology


def load_topology(path: str | Path) -> Topology:
    """Load YAML topology file and validate against schema."""

    p = Path(path)
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))

    try:
        return Topology(**data)
    except ValidationError as ve:
        raise SystemExit(f"[Topology Validation Error]\n{ve}") from ve
