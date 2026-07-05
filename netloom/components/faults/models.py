"""Models for fault-injection specs, applied-fault records and answer keys."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field, ValidationError

from .errors import FaultSpecInvalid


if TYPE_CHECKING:
    from rich.console import Console


RANDOM_FAULT_TYPE = "random"


class FaultCategory(StrEnum):
    INTERFACE = "interface"
    ADDRESSING = "addressing"
    VLAN = "vlan"
    ROUTING = "routing"
    FIREWALL = "firewall"
    SYSTEM = "system"


class FaultSpecEntry(BaseModel):
    """One entry in a faults spec.

    ``type`` is a catalog fault id, or ``"random"`` to let the selector pick.
    ``node``/``target`` narrow explicit entries; ``count``/``categories``/
    ``exclude`` only apply to ``random`` entries.
    """

    type: str
    node: str | None = None
    target: str | None = None
    count: int = Field(default=1, ge=1)
    categories: list[FaultCategory] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class FaultSpec(BaseModel):
    """A fault-injection scenario for a topology."""

    version: int = 1
    seed: int | None = None
    faults: list[FaultSpecEntry] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> FaultSpec:
        p = Path(path)
        try:
            raw = p.read_text(encoding="utf-8")
        except OSError as exc:
            raise FaultSpecInvalid(str(p), str(exc)) from exc
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise FaultSpecInvalid(str(p), f"YAML parse error:\n{exc}") from exc
        if not isinstance(data, dict):
            raise FaultSpecInvalid(str(p), "top level must be a YAML mapping")
        try:
            return cls(**data)
        except ValidationError as exc:
            raise FaultSpecInvalid(str(p), str(exc)) from exc

    def to_yaml(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            yaml.safe_dump(self.model_dump(mode="json", exclude_defaults=True), sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )


class AppliedFault(BaseModel):
    """Record of one injected fault — the unit of the answer key."""

    type: str
    category: FaultCategory
    difficulty: int = Field(ge=1, le=3)
    node: str
    target: str | None = None
    hint: str
    """Student-facing nudge; deliberately does not name the node."""
    description: str
    """Instructor-facing answer: what was broken, where."""
    before: str | None = None
    after: str | None = None


class FaultReport(BaseModel):
    """Answer key written next to the generated configs after fault injection."""

    topology_id: str
    seed: int | None = None
    spec_file: str | None = None
    generated_at: str = ""
    faults: list[AppliedFault] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> FaultReport:
        p = Path(path)
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
        except OSError as exc:
            raise FaultSpecInvalid(str(p), str(exc)) from exc
        except yaml.YAMLError as exc:
            raise FaultSpecInvalid(str(p), f"YAML parse error:\n{exc}") from exc
        if not isinstance(data, dict):
            raise FaultSpecInvalid(str(p), "top level must be a YAML mapping")
        try:
            return cls(**data)
        except ValidationError as exc:
            raise FaultSpecInvalid(str(p), str(exc)) from exc

    def to_yaml(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )

    def display(self, console: Console, *, answers: bool = False) -> None:
        """Render the report: hints only by default, full answers with *answers*."""
        from rich.box import ROUNDED
        from rich.table import Table

        table = Table(box=ROUNDED, show_header=True, border_style="dim", expand=False)
        table.add_column("#", no_wrap=True, style="dim")
        table.add_column("Category")
        table.add_column("Difficulty", no_wrap=True)
        if answers:
            table.add_column("Type")
            table.add_column("Where", style="bold")
            table.add_column("What changed")
        else:
            table.add_column("Hint")

        for i, fault in enumerate(self.faults, start=1):
            diff = "●" * fault.difficulty + "○" * (3 - fault.difficulty)
            if answers:
                where = fault.node if fault.target is None else f"{fault.node}/{fault.target}"
                change = fault.description
                if fault.before is not None or fault.after is not None:
                    change += f"\n[dim]{fault.before} → {fault.after}[/dim]"
                table.add_row(str(i), str(fault.category), f"[yellow]{diff}[/yellow]", fault.type, where, change)
            else:
                table.add_row(str(i), str(fault.category), f"[yellow]{diff}[/yellow]", fault.hint)

        console.print(table)
        if not answers:
            console.print("[dim]Run 'netloom faults reveal --answers' for the full answer key.[/dim]")
