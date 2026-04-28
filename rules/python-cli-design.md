# Rule: Click CLI Design

## Command Hierarchy

Organise commands into semantic groups. Each group's docstring becomes its `--help` section heading:

```
app
├── user
│   ├── create
│   ├── delete
│   └── list
└── order
    ├── place
    └── cancel
```

```python
@base.group()
def user() -> None:
    """User management."""

@user.command("create")
@click.argument("email")
def user_create(email: str) -> None:
    """Create a new user account."""
    self.controller.create_user(email)
```

## Command Naming

Use kebab-case for all commands and argument metavars: `send-message`, `from-date`, `to-date`.

## Custom Parameter Types

Create a `click.ParamType` subclass for every domain concept that needs validation or conversion. Always implement `shell_complete()`:

```python
class UserEmailType(click.ParamType):
    name = "email"

    def convert(self, value: str, param, ctx) -> User:
        user = db.find_by_email(value)
        if not user:
            self.fail(f"No user with email {value!r}", param, ctx)
        return user

    def shell_complete(self, ctx, param, incomplete: str) -> list[CompletionItem]:
        return [
            CompletionItem(u.email)
            for u in db.list_users()
            if u.email.startswith(incomplete)
        ]
```

Never validate inside command bodies — put all validation in `convert()`.

## Config Defaults for Options

Pull defaults from config so users don't repeat themselves:

```python
@cmd.command("deploy")
@click.option(
    "--env",
    default=lambda: app.config.default_env,   # dynamic default from config
    show_default="from config",
)
def deploy(env: str) -> None:
    ...
```

## Immediate Delegation

Command bodies must only parse input and call the controller. No logic:

```python
# Good
@cmd.command("transfer")
@click.argument("from_account", type=AccountType())
@click.argument("to_account", type=AccountType())
@click.argument("amount", type=float)
def transfer(from_account: Account, to_account: Account, amount: float) -> None:
    """Transfer funds between accounts."""
    self.controller.transfer(from_account, to_account, amount)

# Bad
@cmd.command("transfer")
def transfer(...) -> None:
    if amount <= 0:                              # logic in command = bad
        raise click.ClickException("negative amount")
    if from_account.balance < amount:
        raise click.ClickException("insufficient funds")
    from_account.debit(amount)
    to_account.credit(amount)
```

## Rich Markup in Docstrings

Click uses the command docstring as help text. Use Rich markup for visual emphasis:

```python
@admin.group("nuke")
def nuke() -> None:
    """Destroy all data. [bold red]Irreversible.[/]"""
```

## `click.launch()` for URLs

Open URLs and files in the default application rather than spawning subprocesses:

```python
click.launch("https://example.com/issue/123")   # browser
click.launch(str(report_path))                  # file manager / viewer
```

## Mutually Exclusive Options

Validate exclusivity inside the command (the only logic allowed there), or use a custom decorator:

```python
@cmd.command("export")
@click.option("--json", "fmt", flag_value="json")
@click.option("--csv", "fmt", flag_value="csv")
def export(fmt: str) -> None:
    self.controller.export(fmt)
```

Use `flag_value` to let Click enforce single-selection automatically.
