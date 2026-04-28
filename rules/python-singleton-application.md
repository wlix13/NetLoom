# Rule: Application Singleton Pattern

## Class-Level Sentinel (not `None`)

Use a class-level attribute as the singleton marker. This avoids carrying `None` as a valid type on every access and keeps the type of `__instance__` clean:

```python
class BaseApplication(Generic[AppT]):
    __instance__: "BaseApplication[Any]"    # absent until first __init__

    def __init__(self) -> None:
        if hasattr(BaseApplication, "__instance__"):
            return                           # idempotent — safe to call again
        BaseApplication.__instance__ = self
        self.console = Console()
        self._init_components()

    @classmethod
    def current(cls: type[BaseApplication[AppT]]) -> AppT:
        if not hasattr(BaseApplication, "__instance__"):
            raise RuntimeError("Application not initialized.")
        return cast(AppT, BaseApplication.__instance__)
```

`hasattr` check is cleaner than `is None` because `None` is a valid value for many attributes.

## Generic `current()` Classmethod

The classmethod uses `cls` as its own bound so that concrete subclasses return the right type without an override:

```python
# Concrete subclass:
class MyApp(BaseApplication["MyApp"]):
    ...

# At call site — no cast needed:
app: MyApp = MyApp.current()
app.my_feature.do_thing()   # fully typed
```

## Component Registry Keyed by Class

Store components by their class object, not by string name. Prevents collisions, enables O(1) lookup, and is type-safe:

```python
self.components: dict[
    type[BaseComponent[AppT, Any]],
    BaseComponent[AppT, Any],
] = {}

def register(self, cls: type[BaseComponent[AppT, Any]]) -> None:
    if cls in self.components:
        raise ComponentAlreadyRegistered(cls)
    instance = cls(cast(AppT, self))
    self.components[cls] = instance
    if instance.expose_controller:
        setattr(self, instance.name, instance.controller)
    instance.on_register()
```

## Always Clean Up in `deregister()`

Mirror every `setattr` in `register()` with a `delattr` in `deregister()`:

```python
def deregister(self, cls: type[BaseComponent]) -> None:
    instance = self.components.pop(cls)
    instance.on_deregister()
    if instance.expose_controller:
        delattr(self, instance.name)
```

## Initialization Order

Infrastructure components must be registered first. Declare order explicitly in the concrete application class:

```python
class MyApp(BaseApplication["MyApp"]):
    default_components: list[type[BaseComponent]] = [
        MigrationComponent,   # must be first — sets up schema
        ConfigComponent,      # must be second — others read config
        AuthComponent,
        PaymentComponent,
        NotificationComponent,
    ]
```

## Application is the Only Shared Bus

Components must not import each other directly. All cross-component calls go through `self.app.<name>`:

```python
# Bad — direct import creates coupling
from myapp.components.payment import PaymentController

# Good — access via the application
class OrderController(BaseController):
    def complete(self, order: Order) -> None:
        self.app.payment.charge(order.total)    # loose coupling via registry
```
