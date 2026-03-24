"""Tests for netloom.core.errors module."""

import pytest

from netloom.core.errors import ConfigurationError, InfrastructureError, NetLoomError, TopologyError


class TestNetLoomError:
    """Test base NetLoomError exception."""

    def test_is_exception(self):
        """NetLoomError should be an Exception."""
        assert issubclass(NetLoomError, Exception)

    def test_can_be_raised(self):
        """NetLoomError can be raised and caught."""
        with pytest.raises(NetLoomError):
            raise NetLoomError("test error")

    def test_error_message(self):
        """NetLoomError preserves error message."""
        msg = "test error message"
        with pytest.raises(NetLoomError) as exc_info:
            raise NetLoomError(msg)
        assert str(exc_info.value) == msg


class TestTopologyError:
    """Test TopologyError exception."""

    def test_inherits_from_netloom_error(self):
        """TopologyError should inherit from NetLoomError."""
        assert issubclass(TopologyError, NetLoomError)

    def test_can_be_raised(self):
        """TopologyError can be raised and caught."""
        with pytest.raises(TopologyError):
            raise TopologyError("topology validation failed")

    def test_caught_as_netloom_error(self):
        """TopologyError can be caught as NetLoomError."""
        with pytest.raises(NetLoomError):
            raise TopologyError("test")


class TestInfrastructureError:
    """Test InfrastructureError exception."""

    def test_inherits_from_netloom_error(self):
        """InfrastructureError should inherit from NetLoomError."""
        assert issubclass(InfrastructureError, NetLoomError)

    def test_can_be_raised(self):
        """InfrastructureError can be raised and caught."""
        with pytest.raises(InfrastructureError):
            raise InfrastructureError("VirtualBox operation failed")

    def test_caught_as_netloom_error(self):
        """InfrastructureError can be caught as NetLoomError."""
        with pytest.raises(NetLoomError):
            raise InfrastructureError("test")


class TestConfigurationError:
    """Test ConfigurationError exception."""

    def test_inherits_from_netloom_error(self):
        """ConfigurationError should inherit from NetLoomError."""
        assert issubclass(ConfigurationError, NetLoomError)

    def test_can_be_raised(self):
        """ConfigurationError can be raised and caught."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("template rendering failed")

    def test_caught_as_netloom_error(self):
        """ConfigurationError can be caught as NetLoomError."""
        with pytest.raises(NetLoomError):
            raise ConfigurationError("test")


class TestErrorHierarchy:
    """Test the complete error hierarchy."""

    def test_all_errors_inherit_from_base(self):
        """All custom errors should inherit from NetLoomError."""
        error_classes = [TopologyError, InfrastructureError, ConfigurationError]
        for error_cls in error_classes:
            assert issubclass(error_cls, NetLoomError)

    def test_catch_all_with_base_class(self):
        """Base class can catch all derived errors."""
        errors = [
            TopologyError("topology"),
            InfrastructureError("infra"),
            ConfigurationError("config"),
        ]
        for error in errors:
            with pytest.raises(NetLoomError):
                raise error

    def test_specific_catch_doesnt_catch_siblings(self):
        """Specific error types don't catch sibling errors."""
        with pytest.raises(InfrastructureError):
            with pytest.raises(TopologyError):
                raise InfrastructureError("different error")