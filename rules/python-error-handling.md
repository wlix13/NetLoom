# Rule: Error Handling Hierarchy

## Single Base Error

Define one base `Error` for the application. All domain errors extend it. The base class applies consistent formatting to every message:

```python
class Error(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
```

If using Rich for terminal output, apply markup in the base:

```python
class Error(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"[red]{message}[/red]")
```

## Named Errors for Every Failure Mode

Create a specific class for each distinct failure. Tight `__init__` signatures keep call sites clean and make errors greppable:

```python
class RecordNotFound(Error):
    def __init__(self, name: str) -> None:
        super().__init__(f"Record [bold]{name}[/bold] not found.")

class RecordAlreadyExists(Error):
    def __init__(self, name: str) -> None:
        super().__init__(f"Record [bold]{name}[/bold] already exists.")

class MutuallyExclusiveOptions(Error):
    def __init__(self, *options: str) -> None:
        joined = " and ".join(f"[bold]{o}[/bold]" for o in options)
        super().__init__(f"Options {joined} are mutually exclusive.")

class FieldMustBeSet(Error):
    def __init__(self, model: str, field: str) -> None:
        super().__init__(f"{model}: field [bold]{field}[/bold] must be set.")
```

## `Unreachable` for Impossible Branches

Use a dedicated error for branches that are logically impossible. This satisfies the type checker and documents intent:

```python
class Unreachable(Error):
    def __init__(self) -> None:
        super().__init__("Reached unreachable code — this is a bug.")

# Usage after type narrowing the checker can't follow:
if not isinstance(value, ExpectedType):
    raise Unreachable()
```

## Wrap Third-Party Exceptions at the Boundary

Never let raw library exceptions reach the user. Wrap them in domain errors at the controller layer:

```python
class ServiceUnavailable(Error):
    @classmethod
    def from_exc(cls, exc: requests.ConnectionError) -> "ServiceUnavailable":
        return cls(f"Service unreachable: {exc}")

# In controller:
try:
    return self.client.fetch(url)
except requests.ConnectionError as exc:
    raise ServiceUnavailable.from_exc(exc) from exc
```

## Raise Early at Boundaries

Validate required state at the top of any method that depends on it. Never guard mid-function:

```python
# Good
def upload(self, path: Path) -> None:
    self.config.require_field("endpoint")
    self.config.require_field("token")
    # proceed with confidence

# Bad
def upload(self, path: Path) -> None:
    data = read(path)
    if not self.config.endpoint:       # buried guard
        raise Error("endpoint not set")
    send(data)
```

## Error File Organisation

- `core/errors.py` — framework-level errors (lifecycle, registration, unreachable)
- `errors.py` — application-level errors (auth, network, config)
- `components/<name>/errors.py` — component-specific errors when there are several
