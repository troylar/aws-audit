"""Tests for snapshot create --from-snapshot (derived snapshots)."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def make_resource(
    arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
    resource_type="AWS::EC2::Instance",
    name="test-instance",
    region="us-east-1",
    tags=None,
):
    """Create a mock Resource object."""
    r = MagicMock()
    r.arn = arn
    r.resource_type = resource_type
    r.name = name
    r.region = region
    r.tags = tags if tags is not None else {"Name": "test", "Environment": "dev"}
    r.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    r.config_hash = "a" * 64
    r.raw_config = {}
    r.source = "direct_api"
    return r


def make_source_snapshot(resources=None, name="source-snap"):
    """Create a mock source snapshot with test resources."""
    snapshot = MagicMock()
    snapshot.name = name
    snapshot.account_id = "123456789012"
    snapshot.collection_name = "default"
    snapshot.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    snapshot.regions = ["us-east-1", "us-west-2"]
    snapshot.resources = resources if resources is not None else [
        make_resource(),
        make_resource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-bucket",
            region="us-east-1",
            tags={"Name": "my-bucket", "Environment": "prod"},
        ),
        make_resource(
            arn="arn:aws:lambda:us-west-2:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-west-2",
            tags={"Name": "my-func", "Environment": "dev"},
        ),
    ]
    snapshot.resource_count = len(snapshot.resources)
    return snapshot


class TestFromSnapshotHappyPath:
    """Tests for basic --from-snapshot functionality."""

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_no_filters_copies_all(self, mock_coll_cls, mock_storage_cls):
        """--from-snapshot with no filters copies all resources."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app, ["snapshot", "create", "derived-snap", "--from-snapshot", "source-snap"]
        )

        assert result.exit_code == 0
        assert "Derived snapshot created" in result.stdout
        assert "3 / 3" in result.stdout

        # Verify save was called with 3 resources
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 3

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_auto_generated_name(self, mock_coll_cls, mock_storage_cls):
        """Name is auto-generated when not provided."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app, ["snapshot", "create", "--from-snapshot", "source-snap"]
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert saved_snapshot.name.startswith("123456789012-default-")

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_explicit_name(self, mock_coll_cls, mock_storage_cls):
        """Explicit name is used when provided."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app, ["snapshot", "create", "my-derived", "--from-snapshot", "source-snap"]
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert saved_snapshot.name == "my-derived"


class TestFromSnapshotFilters:
    """Tests for filtering with --from-snapshot."""

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_filter_by_type(self, mock_coll_cls, mock_storage_cls):
        """--type ec2 filters to EC2 only."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "ec2-only", "--from-snapshot", "source-snap", "--type", "ec2"],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].resource_type == "AWS::EC2::Instance"

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_filter_by_region(self, mock_coll_cls, mock_storage_cls):
        """--region us-west-2 filters by region."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "west-only", "--from-snapshot", "source-snap", "--region", "us-west-2"],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].region == "us-west-2"

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_filter_by_tag(self, mock_coll_cls, mock_storage_cls):
        """--tag Environment=prod filters by tag (AND logic)."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "prod-only", "--from-snapshot", "source-snap", "--tag", "Environment=prod"],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].name == "my-bucket"

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_filter_by_search(self, mock_coll_cls, mock_storage_cls):
        """--search filters by ARN substring."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "bucket-snap", "--from-snapshot", "source-snap", "--search", "my-bucket"],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].name == "my-bucket"

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_filter_by_created_by(self, mock_coll_cls, mock_storage_cls):
        """--created-by matches _created_by tag."""
        resources = [
            make_resource(tags={"Name": "a", "_created_by": "john@example.com"}),
            make_resource(
                arn="arn:aws:s3:::other",
                resource_type="AWS::S3::Bucket",
                name="other",
                tags={"Name": "other", "_created_by": "admin@example.com"},
            ),
        ]
        source = make_source_snapshot(resources=resources)

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "john-snap", "--from-snapshot", "source-snap", "--created-by", "john"],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].tags["_created_by"] == "john@example.com"

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_filter_by_created_by_role(self, mock_coll_cls, mock_storage_cls):
        """--created-by matches _created_by_role tag."""
        resources = [
            make_resource(tags={"Name": "a", "_created_by_role": "admin-role"}),
            make_resource(
                arn="arn:aws:s3:::other",
                resource_type="AWS::S3::Bucket",
                name="other",
                tags={"Name": "other"},
            ),
        ]
        source = make_source_snapshot(resources=resources)

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "role-snap", "--from-snapshot", "source-snap", "--created-by", "admin-role"],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].tags["_created_by_role"] == "admin-role"

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_combined_type_and_created_by(self, mock_coll_cls, mock_storage_cls):
        """Combined --type and --created-by filters both apply."""
        resources = [
            make_resource(
                name="ec2-john",
                resource_type="AWS::EC2::Instance",
                tags={"Name": "ec2-john", "_created_by": "john"},
            ),
            make_resource(
                arn="arn:aws:s3:::s3-john",
                resource_type="AWS::S3::Bucket",
                name="s3-john",
                tags={"Name": "s3-john", "_created_by": "john"},
            ),
            make_resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-other",
                resource_type="AWS::EC2::Instance",
                name="ec2-admin",
                tags={"Name": "ec2-admin", "_created_by": "admin"},
            ),
        ]
        source = make_source_snapshot(resources=resources)

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            [
                "snapshot", "create", "ec2-john", "--from-snapshot", "source-snap",
                "--type", "ec2", "--created-by", "john",
            ],
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert len(saved_snapshot.resources) == 1
        assert saved_snapshot.resources[0].name == "ec2-john"


class TestFromSnapshotEdgeCases:
    """Tests for edge cases and error paths."""

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_zero_results_warns_no_save(self, mock_coll_cls, mock_storage_cls):
        """Zero filter results warns and doesn't save."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "empty", "--from-snapshot", "source-snap", "--type", "rds"],
        )

        assert result.exit_code == 0
        assert "No resources matched" in result.stdout
        mock_storage.save_snapshot.assert_not_called()

    @patch("src.cli.main.SnapshotStorage")
    def test_source_not_found(self, mock_storage_cls):
        """Source snapshot not found produces error."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage.list_snapshots.return_value = [{"name": "other-snap"}]
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(
            app,
            ["snapshot", "create", "derived", "--from-snapshot", "nonexistent"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_metadata_has_derived_from(self, mock_coll_cls, mock_storage_cls):
        """New snapshot metadata includes derived_from and source_resource_count."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app, ["snapshot", "create", "derived", "--from-snapshot", "source-snap"]
        )

        assert result.exit_code == 0
        saved_snapshot = mock_storage.save_snapshot.call_args[0][0]
        assert saved_snapshot.metadata["derived_from"] == "source-snap"
        assert saved_snapshot.metadata["source_resource_count"] == 3

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_collection_integration(self, mock_coll_cls, mock_storage_cls):
        """Collection is registered and saved."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage.save_snapshot.return_value = Path("derived.db")
        mock_storage_cls.return_value = mock_storage

        mock_collection = MagicMock(description=None)
        mock_coll = MagicMock()
        mock_coll.get_by_name.return_value = mock_collection
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "derived", "--from-snapshot", "source-snap", "--collection", "prod"],
        )

        assert result.exit_code == 0
        mock_collection.add_snapshot.assert_called_once()
        mock_coll.save.assert_called_once_with(mock_collection)

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    def test_invalid_tag_format(self, mock_coll_cls, mock_storage_cls):
        """Invalid --tag format produces error."""
        source = make_source_snapshot()

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = source
        mock_storage_cls.return_value = mock_storage

        mock_coll = MagicMock()
        mock_coll.get_or_create_default.return_value = MagicMock(description=None)
        mock_coll_cls.return_value = mock_coll

        result = runner.invoke(
            app,
            ["snapshot", "create", "derived", "--from-snapshot", "source-snap", "--tag", "invalid-no-equals"],
        )

        assert result.exit_code == 1
        assert "Invalid tag filter" in result.stdout


class TestFromSnapshotConflicts:
    """Tests for option conflicts."""

    def test_from_snapshot_with_config(self):
        """--from-snapshot + --config errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--from-snapshot", "base", "--config"],
        )

        assert result.exit_code == 1
        assert "--config" in result.stdout
        assert "--from-snapshot" in result.stdout

    def test_from_snapshot_with_track_creators(self):
        """--from-snapshot + --track-creators errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--from-snapshot", "base", "--track-creators"],
        )

        assert result.exit_code == 1
        assert "--track-creators" in result.stdout

    def test_from_snapshot_with_before_date(self):
        """--from-snapshot + --before-date errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--from-snapshot", "base", "--before-date", "2025-01-01"],
        )

        assert result.exit_code == 1
        assert "--before-date" in result.stdout

    def test_from_snapshot_with_include_tags(self):
        """--from-snapshot + --include-tags errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--from-snapshot", "base", "--include-tags", "Env=prod"],
        )

        assert result.exit_code == 1
        assert "--include-tags" in result.stdout

    def test_type_without_from_snapshot(self):
        """--type without --from-snapshot errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--type", "ec2"],
        )

        assert result.exit_code == 1
        assert "requires --from-snapshot" in result.stdout

    def test_tag_without_from_snapshot(self):
        """--tag without --from-snapshot errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--tag", "Env=prod"],
        )

        assert result.exit_code == 1
        assert "requires --from-snapshot" in result.stdout

    def test_search_without_from_snapshot(self):
        """--search without --from-snapshot errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--search", "bucket"],
        )

        assert result.exit_code == 1
        assert "requires --from-snapshot" in result.stdout

    def test_created_by_without_from_snapshot(self):
        """--created-by without --from-snapshot errors."""
        result = runner.invoke(
            app,
            ["snapshot", "create", "x", "--created-by", "john"],
        )

        assert result.exit_code == 1
        assert "requires --from-snapshot" in result.stdout
