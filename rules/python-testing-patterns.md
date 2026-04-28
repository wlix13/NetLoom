# Rule: Python Testing Patterns

## Test Real Classes, Not Mocks

Instantiate real framework classes wherever possible. Define minimal subclasses inline in the test function:

```python
def test_registration_lifecycle():
    class CountingComponent(BaseComponent):
        controller_class = BaseController
        registered = 0
        deregistered = 0

        def on_register(self) -> None:
            self.__class__.registered += 1

        def on_deregister(self) -> None:
            self.__class__.deregistered += 1

    app = Application()
    app.register(CountingComponent)
    assert CountingComponent.registered == 1

    app.deregister(CountingComponent)
    assert CountingComponent.deregistered == 1
```

Only mock at system boundaries (external HTTP, filesystem, clock) — never mock your own classes.

## Assert Domain Errors, Not Exception

Use `pytest.raises` with the specific domain error class, not the generic `Exception`:

```python
with pytest.raises(RecordAlreadyExists):
    repo.create(name="duplicate")

with pytest.raises(RecordNotFound):
    repo.get(id="nonexistent")
```

## Unit-Test Pure Logic

Controller methods that contain pure logic should be testable without instantiating the full application. Extract pure functions when it helps:

```python
# Pure function in controller module
def bump_version(version: str) -> str:
    major, minor = version.rsplit(".", 1)
    return f"{major}.{int(minor) + 1}"

# Test
def test_bump_version():
    assert bump_version("2024.1") == "2024.2"
    assert bump_version("2024.9") == "2024.10"

def test_bump_version_invalid():
    with pytest.raises(ValueError):
        bump_version("not-a-version")
```

## File Layout

Mirror the source tree under `tests/`:

```
src/
└── myapp/
    ├── core/
    └── components/
        ├── payment/
        └── order/

tests/
├── core/
│   └── test_application.py
└── components/
    ├── payment/
    │   └── test_controller.py
    └── order/
        └── test_controller.py
```

## Strict Markers

Enable `--strict-markers` in `pyproject.toml`. Register every marker before use:

```toml
[tool.pytest.ini_options]
addopts = "--strict-markers"
markers = [
    "integration: requires external services",
    "slow: takes longer than 1s",
]
```

## Descriptive Assertion Messages

Add a message to non-obvious assertions:

```python
result = controller.list_active()
assert len(result) == 2, f"Expected 2 active items, got {len(result)}: {result}"
```

## Fixtures Over Setup Classes

Prefer `pytest` fixtures over `unittest.TestCase` setup methods:

```python
@pytest.fixture
def app() -> Application:
    a = Application()
    a.register(ConfigComponent)
    yield a
    a.dispose()

def test_config_reads_default(app: Application) -> None:
    assert app.config.model.timeout == 30
```
