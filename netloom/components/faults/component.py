"""Faults component: lifecycle wrapper + CLI for broken-lab fault injection."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import rich_click as click
from rich.box import ROUNDED
from rich.table import Table

from netloom.core.component import BaseComponent

from .catalog import register_builtin_faults
from .controller import FaultsController
from .models import FaultCategory


if TYPE_CHECKING:
    from netloom.core.application import Application  # noqa: F401
    from netloom.models.internal import InternalTopology


class FaultsComponent(BaseComponent["Application", FaultsController]):
    """Owns the fault catalog and wires the broken-lab CLI commands."""

    name: ClassVar[str] = "faults"
    controller_class: ClassVar[type] = FaultsController

    def on_register(self) -> None:
        """Populate the controller's catalog with the built-in fault types."""
        register_builtin_faults(self.controller.catalog)

    def expose_cli(self, base: click.Group) -> None:
        @base.group("faults")
        def faults() -> None:
            """Broken-lab fault injection — [yellow]instructor tooling[/yellow].

            \b
            Typical flow:
              1. netloom --topology lab.yaml faults generate --count 3 --seed 42
              2. netloom --topology lab.yaml --faults lab-example.faults.yaml up
              3. students debug the lab from inside the VMs
              4. netloom --topology lab.yaml faults reveal [--answers]
            """

        @faults.command("catalog")
        @click.pass_obj
        def catalog_cmd(obj: dict) -> None:
            """List fault types and how many injection targets each has in this topology."""
            app = obj["app"]
            internal: InternalTopology = obj["internal"]

            table = Table(box=ROUNDED, show_header=True, border_style="dim", expand=False)
            table.add_column("Type", style="bold", no_wrap=True)
            table.add_column("Category")
            table.add_column("Difficulty", no_wrap=True)
            table.add_column("Targets", justify="right")
            table.add_column("Summary")

            for definition, n_targets in app.faults.catalog_overview(internal):
                diff = "●" * definition.difficulty + "○" * (3 - definition.difficulty)
                target_cell = f"[green]{n_targets}[/green]" if n_targets else "[dim]0[/dim]"
                table.add_row(
                    definition.type_id,
                    str(definition.category),
                    f"[yellow]{diff}[/yellow]",
                    target_cell,
                    definition.summary,
                )

            app.console.print(table)

        @faults.command("generate")
        @click.option("--count", "-c", default=3, show_default=True, type=click.IntRange(1, 20))
        @click.option("--seed", "-s", default=None, type=int, help="Seed for reproducible selection.")
        @click.option(
            "--category",
            "categories",
            multiple=True,
            type=click.Choice([c.value for c in FaultCategory]),
            help="Restrict selection to these categories (repeatable).",
        )
        @click.option("--exclude", "excludes", multiple=True, help="Fault type ids to exclude (repeatable).")
        @click.option(
            "--output", "-o", "output", default=None, help="Spec output path [default: <topology-id>.faults.yaml]."
        )
        @click.pass_obj
        def generate_cmd(  # noqa: PLR0913
            obj: dict,
            count: int,
            seed: int | None,
            categories: tuple[str, ...],
            excludes: tuple[str, ...],
            output: str | None,
        ) -> None:
            """Randomly pick faults from the catalog and write an editable spec file."""
            app = obj["app"]
            internal: InternalTopology = obj["internal"]

            spec = app.faults.generate_spec(
                internal,
                count=count,
                seed=seed,
                categories=[FaultCategory(c) for c in categories],
                exclude=list(excludes),
            )
            out = Path(output) if output else Path(f"{internal.id}.faults.yaml")
            spec.to_yaml(out)

            app.console.print(f"[green]✓ Fault spec written:[/green] [bold]{out}[/bold] [dim](seed {spec.seed})[/dim]")
            for entry in spec.faults:
                where = entry.node if entry.target is None else f"{entry.node}/{entry.target}"
                app.console.print(f"  - [cyan]{entry.type}[/cyan] → {where}")
            app.console.print(f"\n[dim]Deploy broken lab:[/dim] netloom --topology <file> --faults {out} up")

        @faults.command("reveal")
        @click.option("--answers", "-a", is_flag=True, help="Show the full answers, not just hints.")
        @click.pass_obj
        def reveal_cmd(obj: dict, answers: bool) -> None:
            """Show hints (or with --answers the full key) for the deployed broken lab."""
            app = obj["app"]
            report = app.faults.reveal()

            app.console.print(
                f"[bold]Broken lab:[/bold] {report.topology_id}  "
                f"[dim]seed={report.seed}  applied={report.generated_at}[/dim]"
            )
            report.display(app.console, answers=answers)
