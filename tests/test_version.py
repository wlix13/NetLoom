"""Tests for netloom package version."""

import netloom


class TestVersion:
    """Test package version."""

    def test_version_is_string(self):
        """Version should be a string."""
        assert isinstance(netloom.__version__, str)

    def test_version_format(self):
        """Version should follow semantic versioning."""
        version = netloom.__version__
        parts = version.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"
        # Check that parts are numeric
        assert parts[0].isdigit(), "Major version should be numeric"
        assert parts[1].isdigit(), "Minor version should be numeric"

    def test_current_version(self):
        """Test current version is 0.2.0."""
        assert netloom.__version__ == "0.2.0"