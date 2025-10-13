"""Enhanced BaseModel with rich display capabilities."""

from typing import Any

from pydantic import BaseModel
from rich.console import Console
from rich.table import Table
from rich.tree import Tree


class DisplayModel(BaseModel):
    def display(self, console: Console | None = None, title: str | None = None) -> None:
        """Display the model as a formatted table."""

        if console is None:
            console = Console()

        table = Table(title=title or self.__class__.__name__, show_header=True)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        for field_name, field_value in self:
            if field_value is not None:
                table.add_row(field_name, self._format_value(field_value))

        console.print(table)

    def display_tree(self, console: Console | None = None, title: str | None = None) -> None:
        """Display the model as a tree structure."""

        if console is None:
            console = Console()

        tree = Tree(f"[bold]{title or self.__class__.__name__}[/bold]")
        self._build_tree(tree, dict(self))
        console.print(tree)

    def _format_value(self, value: Any) -> str:
        """Format a value for display."""

        if isinstance(value, list):
            if not value:
                return "[]"
            if len(value) <= 3:
                return ", ".join(str(v) for v in value)
            return f"[{len(value)} items]"
        if isinstance(value, dict):
            if not value:
                return "{}"
            return f"{{{len(value)} keys}}"
        if isinstance(value, BaseModel):
            return f"<{value.__class__.__name__}>"
        return str(value)

    def _build_tree(self, parent: Tree, data: dict[str, Any]) -> None:
        """Build a tree from nested data."""

        for key, value in data.items():
            if value is None:
                continue

            if isinstance(value, BaseModel):
                branch = parent.add(f"[cyan]{key}[/cyan]")
                self._build_tree(branch, dict(value))
            elif isinstance(value, list):
                if not value:
                    parent.add(f"[cyan]{key}[/cyan]: []")
                elif isinstance(value[0], BaseModel):
                    branch = parent.add(f"[cyan]{key}[/cyan] [{len(value)} items]")
                    for i, item in enumerate(value):
                        item_branch = branch.add(f"[dim]{i}[/dim]")
                        self._build_tree(item_branch, dict(item))
                else:
                    parent.add(f"[cyan]{key}[/cyan]: {', '.join(str(v) for v in value)}")
            elif isinstance(value, dict):
                if not value:
                    parent.add(f"[cyan]{key}[/cyan]: {{}}")
                else:
                    branch = parent.add(f"[cyan]{key}[/cyan]")
                    for k, v in value.items():
                        branch.add(f"[dim]{k}[/dim]: {v}")
            else:
                parent.add(f"[cyan]{key}[/cyan]: [green]{value}[/green]")
