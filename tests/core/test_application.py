"""Application singleton and component registry lifecycle."""

import pytest

from netloom.core.application import Application
from netloom.core.component import BaseComponent
from netloom.core.controller import BaseController
from netloom.core.errors import HypervisorError


@pytest.fixture(autouse=True)
def _fresh_singleton():
    Application.reset()
    yield
    Application.reset()


@pytest.mark.unit
def test_current_returns_same_instance():
    assert Application.current() is Application.current()


@pytest.mark.unit
def test_reset_creates_new_instance():
    first = Application.current()
    Application.reset()
    assert Application.current() is not first


@pytest.mark.unit
def test_register_deregister_lifecycle():
    class CountingController(BaseController):
        pass

    class CountingComponent(BaseComponent["Application", CountingController]):
        name = "counting"
        controller_class = CountingController
        registered = 0
        deregistered = 0

        def on_register(self) -> None:
            type(self).registered += 1

        def on_deregister(self) -> None:
            type(self).deregistered += 1

    app = Application.current()
    app.register(CountingComponent)
    assert CountingComponent.registered == 1
    assert isinstance(app.counting, CountingController)  # ty: ignore[unresolved-attribute]

    app.deregister(CountingComponent)
    assert CountingComponent.deregistered == 1
    assert not hasattr(app, "counting"), "deregister must remove the exposed controller attribute"


@pytest.mark.unit
def test_expose_controller_false_does_not_set_attribute():
    class HiddenController(BaseController):
        pass

    class HiddenComponent(BaseComponent["Application", HiddenController]):
        name = "hidden"
        controller_class = HiddenController
        expose_controller = False

    app = Application.current()
    app.register(HiddenComponent)
    assert not hasattr(app, "hidden")


@pytest.mark.unit
def test_hypervisor_unset_raises():
    app = Application.current()
    with pytest.raises(HypervisorError):
        _ = app.hypervisor
