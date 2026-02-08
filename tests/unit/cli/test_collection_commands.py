"""Tests for CLI collection commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_config():
    """Create a mock Config that behaves like a real Config object."""
    cfg = MagicMock()
    cfg.aws_profile = None
    cfg.storage_path = None
    cfg.log_level = "INFO"
    cfg.snapshot_dir = ".snapshots"
    cfg.regions = []
    cfg.resource_types = []
    cfg.parallel_workers = 10
    cfg.auto_compress_mb = 10
    return cfg


@pytest.fixture
def mock_collection():
    """Create a mock Collection object with sensible defaults."""
    coll = MagicMock()
    coll.name = "test-collection"
    coll.account_id = "123456789012"
    coll.description = "Test collection"
    coll.include_tags = {}
    coll.exclude_tags = {}
    coll.snapshots = []
    coll.active_snapshot = None
    coll.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    coll.last_updated = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return coll


MOCK_IDENTITY = {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/test",
}


class TestCollectionCreate:
    """Tests for awsinv collection create command."""

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_create_basic_collection(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config
    ):
        """Test creating a basic collection with no filters."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.exists.return_value = False
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(
            app,
            ["collection", "create", "my-baseline", "--description", "Baseline resources"],
        )

        assert result.exit_code == 0
        assert "my-baseline" in result.stdout
        mock_storage.save.assert_called_once()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_create_collection_with_tags(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config
    ):
        """Test creating a collection with include and exclude tag filters."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.exists.return_value = False
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(
            app,
            [
                "collection",
                "create",
                "team-alpha",
                "--include-tags",
                "team=alpha,env=prod",
                "--exclude-tags",
                "managed-by=terraform",
            ],
        )

        assert result.exit_code == 0
        assert "team-alpha" in result.stdout
        mock_storage.save.assert_called_once()
        saved_collection = mock_storage.save.call_args[0][0]
        assert saved_collection.include_tags == {"team": "alpha", "env": "prod"}
        assert saved_collection.exclude_tags == {"managed-by": "terraform"}

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_create_duplicate_collection_fails(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config
    ):
        """Test that creating a duplicate collection name returns an error."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(
            app,
            ["collection", "create", "existing-collection"],
        )

        assert result.exit_code == 1
        assert "already exists" in result.stdout
        mock_storage.save.assert_not_called()

    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_create_collection_invalid_name(self, mock_config_load, mock_get_account_id, cli_runner, mock_config):
        """Test that an invalid collection name is rejected."""
        mock_config_load.return_value = mock_config

        result = cli_runner.invoke(
            app,
            ["collection", "create", "invalid name with spaces"],
        )

        assert result.exit_code == 1
        assert "Invalid collection name" in result.stdout

    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_create_collection_name_too_long(self, mock_config_load, mock_get_account_id, cli_runner, mock_config):
        """Test that a collection name over 50 chars is rejected."""
        mock_config_load.return_value = mock_config
        long_name = "a" * 51

        result = cli_runner.invoke(
            app,
            ["collection", "create", long_name],
        )

        assert result.exit_code == 1
        assert "too long" in result.stdout


class TestCollectionList:
    """Tests for awsinv collection list command."""

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_list_collections(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config, mock_collection
    ):
        """Test listing collections returns a table."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.load_by_account.return_value = [mock_collection]
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["collection", "list"])

        assert result.exit_code == 0
        assert "test-collection" in result.stdout
        assert "Total Collections: 1" in result.stdout

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_list_collections_empty(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config
    ):
        """Test listing collections when none exist."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.load_by_account.return_value = []
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["collection", "list"])

        assert result.exit_code == 0
        assert "No collections found" in result.stdout


class TestCollectionShow:
    """Tests for awsinv collection show command."""

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_show_collection(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config, mock_collection
    ):
        """Test showing details for a specific collection."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.get_by_name.return_value = mock_collection
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["collection", "show", "test-collection"])

        assert result.exit_code == 0
        assert "test-collection" in result.stdout
        assert "123456789012" in result.stdout

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_show_collection_not_found(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config
    ):
        """Test showing a collection that does not exist."""
        from src.snapshot.collection_storage import CollectionNotFoundError

        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.get_by_name.side_effect = CollectionNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["collection", "show", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.aws.credentials.get_account_id", return_value="123456789012")
    @patch("src.cli.main.Config.load")
    def test_show_collection_with_snapshots(
        self, mock_config_load, mock_get_account_id, mock_storage_cls, cli_runner, mock_config, mock_collection
    ):
        """Test showing a collection that has snapshots and an active baseline."""
        mock_config_load.return_value = mock_config
        mock_collection.snapshots = ["snap-001.yaml", "snap-002.yaml"]
        mock_collection.active_snapshot = "snap-002.yaml"

        mock_storage = MagicMock()
        mock_storage.get_by_name.return_value = mock_collection
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["collection", "show", "test-collection"])

        assert result.exit_code == 0
        assert "snap-001.yaml" in result.stdout
        assert "snap-002.yaml" in result.stdout
        assert "Active Baseline" in result.stdout


class TestCollectionDelete:
    """Tests for awsinv collection delete command."""

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.validate_credentials", return_value=MOCK_IDENTITY)
    @patch("src.cli.main.Config.load")
    def test_delete_collection_with_yes_flag(
        self, mock_config_load, mock_validate, mock_storage_cls, cli_runner, mock_config, mock_collection
    ):
        """Test deleting a collection with --yes to skip confirmation."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.get_by_name.return_value = mock_collection
        mock_storage.load_by_account.return_value = [mock_collection, MagicMock()]
        mock_storage.delete.return_value = 0
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(
            app,
            ["collection", "delete", "test-collection", "--yes"],
        )

        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()
        mock_storage.delete.assert_called_once_with("test-collection", "123456789012", delete_snapshots=False)

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.validate_credentials", return_value=MOCK_IDENTITY)
    @patch("src.cli.main.Config.load")
    def test_delete_collection_not_found(
        self, mock_config_load, mock_validate, mock_storage_cls, cli_runner, mock_config
    ):
        """Test deleting a collection that does not exist."""
        from src.snapshot.collection_storage import CollectionNotFoundError

        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.get_by_name.side_effect = CollectionNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(
            app,
            ["collection", "delete", "ghost-collection", "--yes"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.validate_credentials", return_value=MOCK_IDENTITY)
    @patch("src.cli.main.Config.load")
    def test_delete_last_collection_blocked(
        self, mock_config_load, mock_validate, mock_storage_cls, cli_runner, mock_config, mock_collection
    ):
        """Test that deleting the only collection for an account is blocked."""
        mock_config_load.return_value = mock_config
        mock_storage = MagicMock()
        mock_storage.get_by_name.return_value = mock_collection
        mock_storage.load_by_account.return_value = [mock_collection]
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(
            app,
            ["collection", "delete", "test-collection", "--yes"],
        )

        assert result.exit_code == 1
        assert "only collection" in result.stdout.lower() or "cannot delete" in result.stdout.lower()
        mock_storage.delete.assert_not_called()


class TestCollectionMigrate:
    """Tests for awsinv collection migrate command."""

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials", return_value=MOCK_IDENTITY)
    @patch("src.cli.main.Config.load")
    def test_migrate_no_legacy_snapshots(
        self, mock_config_load, mock_validate, mock_snap_storage_cls, mock_coll_storage_cls, cli_runner, mock_config
    ):
        """Test migration when no legacy snapshot files exist."""
        mock_config_load.return_value = mock_config
        mock_snap_storage = MagicMock()
        mock_snap_storage.storage_dir.glob.return_value = []
        mock_snap_storage_cls.return_value = mock_snap_storage

        result = cli_runner.invoke(app, ["collection", "migrate"])

        assert result.exit_code == 0
        assert "No legacy snapshots found" in result.stdout

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials", return_value=MOCK_IDENTITY)
    @patch("src.cli.main.Config.load")
    def test_migrate_with_legacy_snapshots(
        self, mock_config_load, mock_validate, mock_snap_storage_cls, mock_coll_storage_cls, cli_runner, mock_config
    ):
        """Test migration when legacy snapshots are found and migrated."""
        from pathlib import Path

        mock_config_load.return_value = mock_config

        mock_snap_file = MagicMock(spec=Path)
        mock_snap_file.name = "old-snapshot.yaml"

        mock_snap_storage = MagicMock()
        mock_snap_storage.storage_dir.glob.side_effect = [
            [mock_snap_file],  # *.yaml
            [],  # *.yaml.gz
        ]
        mock_snap_storage_cls.return_value = mock_snap_storage

        mock_snapshot = MagicMock()
        mock_snapshot.account_id = "123456789012"
        mock_snapshot.collection_name = "default"
        mock_snap_storage.load_snapshot.return_value = mock_snapshot

        mock_default_collection = MagicMock()
        mock_default_collection.snapshots = []
        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_default_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = cli_runner.invoke(app, ["collection", "migrate"])

        assert result.exit_code == 0
        mock_default_collection.add_snapshot.assert_called_once_with("old-snapshot.yaml", set_active=False)
        mock_coll_storage.save.assert_called_once()
