# Rule: Rich Terminal Output

## Single Console

Every application has exactly one `rich.Console` instance. All output goes through it. Never `print()`:

```python
class Application:
    def __init__(self) -> None:
        self.console = Console()

    def display(self, *objects: Any, **kwargs: Any) -> None:
        self.console.print(*objects, **kwargs)
```

Sharing one console prevents interleaving with `Live` displays and keeps output consistent.

## Semantic Display Methods

Wrap repeated output patterns as named methods on a display helper. Controllers call semantics, not format strings:

```python
class Display:
    def saved(self, name: str) -> None:
        self._app.display(f"[green]Saved:[/green] [bold]{name}[/bold]")

    def deleted(self, name: str) -> None:
        self._app.display(f"[red]Deleted:[/red] [bold]{name}[/bold]")

    def aborted(self) -> None:
        self._app.display("[yellow]Aborted.[/yellow]")

    def not_found(self, name: str) -> None:
        self._app.display(f"[red]Not found:[/red] {name}")

# In controller:
self.app.display.saved(profile.name)    # not: self.app.display("[green]Saved: ...")
```

## Tables

Use `rich.Table` for any multi-column structured output:

```python
from rich.table import Table

table = Table(title="Active Deployments")
table.add_column("ID", style="cyan", no_wrap=True)
table.add_column("Name")
table.add_column("Status")
table.add_column("Updated", style="dim")

for dep in deployments:
    status_style = "green" if dep.healthy else "red"
    table.add_row(
        dep.id,
        dep.name,
        f"[{status_style}]{dep.status}[/{status_style}]",
        dep.updated_at.isoformat(),
    )

self.app.display(table)
```

## Live / Streaming Output

Use `rich.Live` with the application's shared console for streaming results:

```python
from rich.live import Live

with Live(table, refresh_per_second=8, console=self.app.console):
    for item in streaming_source():
        table.add_row(...)
```

## Models Own Their Display

Models implement `display()` rather than having controllers format them:

```python
class DeploymentModel(BaseModel):
    def display(self, indent: int = 0) -> None:
        app = Application.current()
        pad = "  " * indent
        app.display(f"{pad}[cyan]id[/cyan]:     [bold]{self.id}[/bold]")
        app.display(f"{pad}[cyan]status[/cyan]: [bold]{self.status}[/bold]")
        self.config.display(indent + 1)     # recurse for nested models
```

## Colour Conventions

Use these consistently across the application:

| Colour | Meaning |
|--------|---------|
| `[bold]` | identifiers, names, important values |
| `[cyan]` | field keys, labels |
| `[green]` | success, active, healthy |
| `[red]` | errors, failure, danger, overdue |
| `[yellow]` | warnings, pending, in-progress |
| `[dim]` | completed, closed, de-emphasised rows |
| `[magenta]` | the current user specifically |
| `[blue]` | links, references |

## Two Heading Styles

Define two reusable heading styles and use them consistently:

**Simple** — for single objects with nested fields:
```
○ deployment:
  ○ id:     abc123
  ○ status: running
```

**Block** — for listing multiple objects of the same type:
```
==============================
         deployment-1
==============================
○ id:     abc123
○ status: running

==============================
         deployment-2
==============================
```
