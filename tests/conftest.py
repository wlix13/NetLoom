"""Shared fixtures: application lifecycle and the example topology."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from netloom.components.config import ConfigComponent
from netloom.components.faults import FaultsComponent
from netloom.components.infrastructure import InfrastructureComponent
from netloom.core.application import Application
from netloom.models.common import load_topology
from netloom.models.converters import convert_topology
from netloom.models.internal import InternalTopology


EXAMPLE_TOPOLOGY = Path(__file__).parent.parent / "schemas" / "example.yaml"

DEFAULT_COMPONENTS = (InfrastructureComponent, ConfigComponent, FaultsComponent)


@pytest.fixture
def app(tmp_path: Path) -> Iterator[Application]:
    """Fresh Application singleton with all default components registered."""
    Application.reset()
    application = Application.current()
    application.workdir = tmp_path / "workdir"
    for component_cls in DEFAULT_COMPONENTS:
        application.register(component_cls)
    yield application
    Application.reset()


@pytest.fixture
def internal(app: Application) -> InternalTopology:
    """The example topology converted with config dirs under the app workdir."""
    return convert_topology(load_topology(EXAMPLE_TOPOLOGY), workdir=app.workdir)
