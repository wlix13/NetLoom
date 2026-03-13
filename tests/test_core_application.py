"""Tests for netloom.core.application module."""

from pathlib import Path

import pytest

from netloom.core.application import Application
from netloom.core.vbox import VBoxSettings


class TestApplicationSingleton:
    """Test Application singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        Application.reset()

    def teardown_method(self):
        """Clean up singleton after each test."""
        Application.reset()

    def test_current_returns_instance(self):
        """current() should return an Application instance."""
        app = Application.current()
        assert isinstance(app, Application)

    def test_current_returns_same_instance(self):
        """current() should always return the same instance."""
        app1 = Application.current()
        app2 = Application.current()
        assert app1 is app2

    def test_reset_clears_instance(self):
        """reset() should clear the singleton instance."""
        app1 = Application.current()
        Application.reset()
        app2 = Application.current()
        assert app1 is not app2

    def test_direct_instantiation_allowed(self):
        """Should allow direct instantiation (not enforced singleton)."""
        app1 = Application()
        app2 = Application()
        assert app1 is not app2


class TestApplicationProperties:
    """Test Application properties and attributes."""

    def setup_method(self):
        """Reset singleton before each test."""
        Application.reset()

    def teardown_method(self):
        """Clean up singleton after each test."""
        Application.reset()

    def test_console_property(self):
        """console property should return a Console instance."""
        app = Application.current()
        console = app.console
        assert console is not None
        # Should always return same console
        assert app.console is console

    def test_workdir_default_none(self):
        """workdir should default to None."""
        app = Application.current()
        assert app.workdir is None

    def test_workdir_setter_with_path(self):
        """Should accept Path object for workdir."""
        app = Application.current()
        app.workdir = Path("/test/path")
        assert app.workdir == Path("/test/path")

    def test_workdir_setter_with_string(self):
        """Should accept string for workdir and convert to Path."""
        app = Application.current()
        app.workdir = "/test/path"
        assert app.workdir == Path("/test/path")
        assert isinstance(app.workdir, Path)

    def test_workdir_setter_with_none(self):
        """Should accept None for workdir."""
        app = Application.current()
        app.workdir = Path("/test")
        app.workdir = None
        assert app.workdir is None

    def test_debug_default_true(self):
        """debug should default to True."""
        app = Application.current()
        assert app.debug is True

    def test_debug_setter(self):
        """Should be able to set debug flag."""
        app = Application.current()
        app.debug = False
        assert app.debug is False
        app.debug = True
        assert app.debug is True

    def test_vbox_settings_default(self):
        """vbox_settings should have default VBoxSettings."""
        app = Application.current()
        assert isinstance(app.vbox_settings, VBoxSettings)

    def test_vbox_settings_can_be_set(self):
        """Should be able to set custom vbox_settings."""
        app = Application.current()
        custom_settings = VBoxSettings(base_vm_name="CustomBase")
        app.vbox_settings = custom_settings
        assert app.vbox_settings.base_vm_name == "CustomBase"


class TestApplicationControllers:
    """Test Application controller properties."""

    def setup_method(self):
        """Reset singleton before each test."""
        Application.reset()

    def teardown_method(self):
        """Clean up singleton after each test."""
        Application.reset()

    def test_infrastructure_controller(self):
        """infrastructure property should return InfrastructureController."""
        app = Application.current()
        controller = app.infrastructure
        assert controller is not None
        # Should be cached (same instance)
        assert app.infrastructure is controller

    def test_config_controller(self):
        """config property should return ConfigController."""
        app = Application.current()
        controller = app.config
        assert controller is not None
        # Should be cached (same instance)
        assert app.config is controller

    def test_controllers_have_app_reference(self):
        """Controllers should have reference to app."""
        app = Application.current()
        assert app.infrastructure.app is app
        assert app.config.app is app


class TestApplicationInitialization:
    """Test Application initialization."""

    def setup_method(self):
        """Reset singleton before each test."""
        Application.reset()

    def teardown_method(self):
        """Clean up singleton after each test."""
        Application.reset()

    def test_initial_state(self):
        """Application should have correct initial state."""
        app = Application()
        assert app.workdir is None
        assert app.debug is True
        assert isinstance(app.vbox_settings, VBoxSettings)
        assert app.console is not None

    def test_independent_instances_have_own_state(self):
        """Direct instances should have independent state."""
        app1 = Application()
        app2 = Application()

        app1.workdir = Path("/path1")
        app2.workdir = Path("/path2")

        assert app1.workdir != app2.workdir

    def test_singleton_state_persistence(self):
        """Singleton should maintain state across current() calls."""
        app1 = Application.current()
        app1.workdir = Path("/persistent")

        app2 = Application.current()
        assert app2.workdir == Path("/persistent")