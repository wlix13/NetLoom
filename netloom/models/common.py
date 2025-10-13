from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import Field, StringConstraints, ValidationError

from .config import TopologyConfig


SchemaStr = Annotated[str, StringConstraints(pattern=r"^asvk\.topology/[0-9]+\.[0-9]+$")]
NameID = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_-]+$")]
IfNameEthOrLo = Annotated[str, StringConstraints(pattern=r"^(eth[0-9]+|lo)$")]
IfNameEth = Annotated[str, StringConstraints(pattern=r"^eth[0-9]+$")]
IfaceLike = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9._-]+$")]
ExpectStr = Annotated[str, StringConstraints(pattern=r"^(success|failure|timeout|via .*)$")]

PortNum = Annotated[int, Field(ge=1, le=65535)]
Vid = Annotated[int, Field(ge=1, le=4094)]
MTU = Annotated[int, Field(ge=68, le=9000)]


def load_topology(path: str | Path) -> TopologyConfig:
    """Load YAML -> TopologyConfig (Pydantic)."""

    p = Path(path)
    data: dict[str, Any] = yaml.safe_load(p.read_text(encoding="utf-8"))
    try:
        return TopologyConfig(**data)
    except ValidationError as ve:
        raise SystemExit(f"[Topology Validation Error]\n{ve}") from ve
