# Rule: Component / Plugin Architecture

When building an extensible Python application, split every feature into two classes with distinct responsibilities:

## The Component–Controller Split

**Component** — owns lifecycle only. Registers with the application, wires up CLI/API, fires hooks. Contains zero business logic.

**Controller** — owns all business logic. No knowledge of transport (Click, FastAPI). Stateless where possible; holds only a reference to the application.

```python
# component.py
class PaymentComponent(BaseComponent):
    name = "payment"
    controller_class = PaymentController
    expose_controller = True      # app.payment → PaymentController

    def on_register(self) -> None:
        self.app.event_bus.subscribe("order.created", self.controller.handle_order)

    def expose_cli(self, base: click.Group) -> None:
        @base.group()
        def payment() -> None:
            """Payment operations."""

        @payment.command("charge")
        @click.argument("amount", type=float)
        def charge(amount: float) -> None:
            """Charge the given amount."""
            self.controller.charge(amount)          # delegate immediately; zero logic here

    def expose_api(self, router: APIRouter) -> None:
        @router.post("/charge")
        def api_charge(amount: float) -> dict:
            return self.controller.charge(amount)


# controller.py
class PaymentController(BaseController):
    def charge(self, amount: float) -> dict:
        ...   # all logic here; no click / fastapi imports
```

## Registration

- A central `Application` singleton owns a registry of components.
- Components register by class, not by string name.
- `expose_controller = True` promotes the controller to `app.<name>` for peer access.
- Registration order matters — infrastructure components (config, db) must come first.

## Cross-Component Reuse

Controllers access sibling controllers through the application:

```python
class OrderController(BaseController):
    def complete(self, order_id: str) -> None:
        self.app.payment.charge(order.total)   # reuse PaymentController
        self.app.email.send_receipt(order)     # reuse EmailController
```

## CLI Binding Rule

CLI command bodies are pure dispatch — they never contain logic:

```python
# Good
@cmd.command("process")
@click.argument("id")
def process(id: str) -> None:
    self.controller.process(id)

# Bad — logic in the command body
@cmd.command("process")
@click.argument("id")
def process(id: str) -> None:
    item = db.get(id)
    if not item:
        raise click.ClickException("not found")
    item.run()
```
