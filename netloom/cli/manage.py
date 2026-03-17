"""Config management commands: save, restore, list-templates."""

import rich_click as click

from ..core.application import Application
from ._group import cli


@cli.command()
@click.pass_obj
def save(obj: dict) -> None:
    """Pull changed files from config-drive back to workdir/saved/<node>/."""

    app: Application = obj["app"]
    app.config.save(obj["internal"])
    app.console.print("[green]✓ Saved config-drive contents to host.[/green]")


@cli.command()
@click.pass_obj
def restore(obj: dict) -> None:
    """Restore last saved configs into workdir/configs/<node>/."""

    app: Application = obj["app"]
    app.config.restore(obj["internal"])
    app.console.print("[green]✓ Restored saved configs into staging.[/green]")


@cli.command("list-templates")
@click.pass_obj
def list_templates(obj: dict) -> None:
    """List available template sets."""

    app: Application = obj["app"]
    templates = app.config.list_template_sets()
    if templates:
        app.console.print("[bold]Available template sets:[/bold]")
        for tpl in templates:
            app.console.print(f"  - {tpl}")
    else:
        app.console.print("[yellow]No template sets found.[/yellow]")
