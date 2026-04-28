# Rule: Python Type Hints (Strict)

Always run mypy in strict mode. Every public method must have a return type, including `-> None`.

```toml
# pyproject.toml
[tool.mypy]
strict = true
```

## Generics for Framework Classes

When a base class behaviour depends on a concrete subtype, use `Generic[T]`. This gives subclasses full type safety without casts at call sites:

```python
from typing import Generic, TypeVar, ClassVar, cast

AppT = TypeVar("AppT", bound="BaseApplication")
CtrlT = TypeVar("CtrlT", bound="BaseController")

class BaseComponent(Generic[AppT, CtrlT]):
    controller_class: ClassVar[type[CtrlT]]

    def __init__(self, app: AppT) -> None:
        self.app = app
        self.controller: CtrlT = self.controller_class(app)

class BaseApplication(Generic[AppT]):
    @classmethod
    def current(cls: type[BaseApplication[AppT]]) -> AppT:
        return cast(AppT, BaseApplication.__instance__)
```

## `ClassVar` for Class-Level Metadata

Use `ClassVar` for attributes that configure a class, not a specific instance:

```python
class MyComponent(BaseComponent):
    name: ClassVar[str] = "my_component"
    expose_controller: ClassVar[bool] = True
```

## `cached_property` for Lazy Initialization

Use `@cached_property` for expensive objects created once per instance (API clients, DB connections). Validate required config before constructing:

```python
from functools import cached_property

class ApiController(BaseController):
    @cached_property
    def client(self) -> ApiClient:
        self.app.config.require_field("api_key")
        return ApiClient(
            key=self.app.config.api_key.get_secret_value(),
            connect_on_init=False,   # defer connection until first call
        )
```

## `cast()` Only With a Comment

When the type checker cannot follow a narrowing you know is safe, use `cast()` and document why — never silently:

```python
# NOTE: [typing] __instance__ is set before this branch is reachable
return cast(AppT, BaseApplication.__instance__)
```

Never use `# type: ignore` without explaining the reason.

## Union Syntax

Use `X | Y` over `Optional[X]` or `Union[X, Y]`:

```python
def find(self, key: str) -> Record | None: ...
```

## Bounded TypeVar for Classmethods

Bound `TypeVar` on classmethods so the return type tracks the concrete subclass:

```python
ModelT = TypeVar("ModelT", bound="BaseModel")

@classmethod
def from_dict(cls: type[ModelT], data: dict) -> ModelT:
    return cls(**data)
```
