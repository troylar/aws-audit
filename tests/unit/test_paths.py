"""Unit tests for path resolution utilities."""

import os
from pathlib import Path
from unittest.mock import patch

from src.utils.paths import get_snapshot_storage_path


class TestGetSnapshotStoragePath:
    """Tests for get_snapshot_storage_path function."""

    def test_default_path(self):
        """Test default path resolution (~/.snapshots)."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear any existing environment variables
            if "AWS_INVENTORY_STORAGE_PATH" in os.environ:
                del os.environ["AWS_INVENTORY_STORAGE_PATH"]

            result = get_snapshot_storage_path()

            assert result == Path.home() / ".snapshots"
            assert result.is_absolute()

    def test_environment_variable(self):
        """Test that environment variable overrides default."""
        test_path = "/custom/env/path"

        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": test_path}):
            result = get_snapshot_storage_path()

            assert result == Path(test_path).resolve()

    def test_parameter_overrides_environment(self):
        """Test that parameter takes precedence over environment variable."""
        env_path = "/env/path"
        param_path = "/param/path"

        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": env_path}):
            result = get_snapshot_storage_path(param_path)

            assert result == Path(param_path).resolve()
            assert result != Path(env_path)

    def test_parameter_overrides_default(self):
        """Test that parameter overrides default path."""
        custom_path = "/custom/path"

        with patch.dict(os.environ, {}, clear=True):
            if "AWS_INVENTORY_STORAGE_PATH" in os.environ:
                del os.environ["AWS_INVENTORY_STORAGE_PATH"]

            result = get_snapshot_storage_path(custom_path)

            assert result == Path(custom_path).resolve()
            assert result != Path.home() / ".snapshots"

    def test_tilde_expansion_in_parameter(self):
        """Test that tilde (~) is expanded in custom path."""
        result = get_snapshot_storage_path("~/my-snapshots")

        assert result == Path.home() / "my-snapshots"
        assert "~" not in str(result)

    def test_tilde_expansion_in_environment(self):
        """Test that tilde (~) is expanded in environment variable."""
        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": "~/env-snapshots"}):
            result = get_snapshot_storage_path()

            assert result == Path.home() / "env-snapshots"
            assert "~" not in str(result)

    def test_relative_path_resolution(self):
        """Test that relative paths are resolved to absolute paths."""
        result = get_snapshot_storage_path("./snapshots")

        assert result.is_absolute()
        assert result == Path("./snapshots").resolve()

    def test_empty_string_parameter(self):
        """Test that empty string parameter falls back to environment/default."""
        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": "/env/path"}):
            # Empty string should be falsy and fall back to env var
            result = get_snapshot_storage_path("")

            # Empty string falls back to env var
            assert result == Path("/env/path").resolve()

    def test_none_parameter(self):
        """Test that None parameter falls back to environment/default."""
        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": "/env/path"}):
            result = get_snapshot_storage_path(None)

            assert result == Path("/env/path").resolve()

    def test_precedence_order(self):
        """Test full precedence: parameter > env > default."""
        param = "/param"
        env_val = "/env"

        # Test 1: Parameter wins
        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": env_val}):
            result = get_snapshot_storage_path(param)
            assert result == Path(param).resolve()

        # Test 2: Env wins when no parameter
        with patch.dict(os.environ, {"AWS_INVENTORY_STORAGE_PATH": env_val}):
            result = get_snapshot_storage_path(None)
            assert result == Path(env_val).resolve()

        # Test 3: Default when no parameter or env
        with patch.dict(os.environ, {}, clear=True):
            if "AWS_INVENTORY_STORAGE_PATH" in os.environ:
                del os.environ["AWS_INVENTORY_STORAGE_PATH"]
            result = get_snapshot_storage_path(None)
            assert result == Path.home() / ".snapshots"

    def test_path_with_spaces(self):
        """Test path with spaces is handled correctly."""
        path_with_spaces = "/path/with spaces/snapshots"

        result = get_snapshot_storage_path(path_with_spaces)

        assert result == Path(path_with_spaces).resolve()
        assert " " in str(result)

    def test_returns_path_object(self):
        """Test that function returns Path object, not string."""
        result = get_snapshot_storage_path()

        assert isinstance(result, Path)
        assert not isinstance(result, str)
