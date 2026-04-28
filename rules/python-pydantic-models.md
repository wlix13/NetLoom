# Rule: Pydantic Model Patterns

## Base Config

Always enable `validate_assignment` so invariants are enforced after construction, not just at creation:

```python
class MyModel(BaseModel):
    class Config:
        validate_assignment = True
        allow_population_by_field_name = True
        json_encoders = {
            SecretStr: lambda v: v.get_secret_value() if v else None,
        }
```

## Sensitive Fields

Use `pydantic.SecretStr` (or `SecretBytes`) for tokens, passwords, API keys. Never `str`:

```python
class ApiConfig(BaseModel):
    token: SecretStr | None = None
    endpoint: str = "https://api.example.com"

# Access only when needed:
headers = {"Authorization": f"Bearer {config.token.get_secret_value()}"}
```

## Dotted Key Access

Implement `__getitem__` / `__setitem__` for hierarchical dotted paths. This is useful when config key paths come from external sources (CLI args, files):

```python
def __getitem__(self, key: str) -> Any:
    head, _, tail = key.partition(".")
    value = self.__getattribute__(head)
    return value[tail] if tail else value

def __setitem__(self, key: str, value: Any) -> None:
    if "." in key:
        head, _, tail = key.rpartition(".")
        setattr(self[head], tail, value)
    else:
        setattr(self, key, value)
```

## Runtime Field Validation

Add `require_field()` for runtime presence checks. Call it at the start of any operation that needs a field:

```python
def require_field(
    self,
    field_name: str,
    ignore_values: set | None = None,
) -> None:
    value = getattr(self, field_name, None)
    if value is None or value in (ignore_values or set()):
        raise FieldMustBeSet(self.__class__.__name__, field_name)

# In controller — validate before doing work:
def publish(self) -> None:
    self.app.config.require_field("api_token")
    self.app.config.require_field("endpoint")
```

## Interactive Factory

Provide a `from_user_input()` classmethod that prompts for fields annotated with prompt metadata. Keeps interactive logic inside the model, not scattered in commands:

```python
@classmethod
def from_user_input(cls: type[ModelT], **known: Any) -> ModelT:
    data = dict(known)
    for name, field in cls.__fields__.items():
        if name in data:
            continue
        prompt_cfg = field.field_info.extra.get("prompt")
        if prompt_cfg:
            data[name] = click.prompt(prompt_cfg.text, default=prompt_cfg.default)
    return cls(**data)

# Usage:
profile = ProfileModel.from_user_input(name="dev")  # prompts for remaining fields
```

## Self-Display

Models own their display logic. Controllers call `model.display()` rather than formatting fields themselves:

```python
def display(self, indent: int = 0) -> None:
    app = Application.current()
    for name, field in self.__fields__.items():
        value = getattr(self, name)
        if isinstance(value, BaseModel):
            app.console.print(f"{'  ' * indent}[cyan]{name}[/cyan]:")
            value.display(indent + 1)
        else:
            app.console.print(f"{'  ' * indent}[cyan]{name}[/cyan]: [bold]{value}[/bold]")
```

## Shared Validators via Factory

Extract reusable validators into static factory methods to avoid duplication:

```python
@staticmethod
def expand_path(*fields: str) -> classmethod:
    def _expand(path: Path) -> Path:
        return path.expanduser().resolve()
    return pydantic.validator(*fields, allow_reuse=True)(_expand)

class Config(BaseModel):
    home_dir: Path
    cache_dir: Path
    _expand = Config.expand_path("home_dir", "cache_dir")
```
