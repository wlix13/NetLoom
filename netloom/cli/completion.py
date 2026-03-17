"""Shell completion installation command."""

from pathlib import Path

import rich_click as click

from ..core.application import Application
from ._group import cli


@cli.command("install-completion")
@click.option(
    "--install",
    "install_shell",
    type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    help="Install completion script for the specified shell.",
)
@click.pass_obj
def install_completion(obj: dict | None, install_shell: str | None) -> None:
    """Generate or install shell completion scripts for netloom."""

    app = Application.current()

    if install_shell:
        shell = install_shell.lower()
        home = Path.home()

        if shell == "bash":
            config_file = home / ".bashrc"
            completion_line = 'eval "$(_NETLOOM_COMPLETE=bash_source netloom)"'
        elif shell == "zsh":
            config_file = home / ".zshrc"
            completion_line = 'eval "$(_NETLOOM_COMPLETE=zsh_source netloom)"'
        elif shell == "fish":
            config_dir = home / ".config" / "fish"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "config.fish"
            completion_line = "eval (env _NETLOOM_COMPLETE=fish_source netloom)"
        else:
            raise ValueError(f"Unsupported shell: {shell}")

        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                if "# NetLoom completion" in config_file.read_text(encoding="utf-8"):
                    app.console.print(f"[yellow]Completion already installed in {config_file}[/yellow]")
                    return
            except FileNotFoundError:
                pass

            with open(config_file, "a", encoding="utf-8") as f:
                f.write(f"\n# NetLoom completion\n{completion_line}\n")

            app.console.print(f"[green]✓ Completion installed for {shell}[/green]")
            app.console.print(f"[dim]Added to: {config_file}[/dim]")
        except OSError as e:
            app.console.print(f"[red]Error: {e}[/red]")
            app.console.print(f"[yellow]Add manually to {config_file}:[/yellow]")
            app.console.print(f"  {completion_line}")
            raise click.ClickException("Completion installation failed.")
    else:
        app.console.print("[bold]Shell Completion Setup[/bold]\n")
        app.console.print("Add one of the following to your shell config:\n")
        app.console.print("[cyan]Bash (~/.bashrc):[/cyan]")
        app.console.print('  eval "$(_NETLOOM_COMPLETE=bash_source netloom)"')
        app.console.print("\n[cyan]Zsh (~/.zshrc):[/cyan]")
        app.console.print('  eval "$(_NETLOOM_COMPLETE=zsh_source netloom)"')
        app.console.print("\n[cyan]Fish (~/.config/fish/config.fish):[/cyan]")
        app.console.print("  eval (env _NETLOOM_COMPLETE=fish_source netloom)")
        app.console.print("\n[yellow]Or use --install to handle both steps automatically:[/yellow]")
        app.console.print("  netloom install-completion --install bash")
