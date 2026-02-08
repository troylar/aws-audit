"""Tests for snapshot export CLI command."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from src.cli.main import app


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


def make_resource(
    arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
    resource_type="AWS::EC2::Instance",
    name="test-instance",
    region="us-east-1",
    tags=None,
    created_at=None,
    config_hash="a" * 64,
    raw_config=None,
    source="direct_api",
):
    """Create a mock Resource object."""
    r = MagicMock()
    r.arn = arn
    r.resource_type = resource_type
    r.name = name
    r.region = region
    r.tags = tags or {"Name": "test", "Environment": "dev"}
    r.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
    r.config_hash = config_hash
    r.raw_config = raw_config or {"InstanceId": "i-abc123", "InstanceType": "t3.micro"}
    r.source = source
    return r


def make_snapshot(resources=None, name="test-snapshot"):
    """Create a mock snapshot."""
    snapshot = MagicMock()
    snapshot.name = name
    snapshot.collection_name = "test-collection"
    snapshot.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    snapshot.resources = resources if resources is not None else [make_resource()]
    snapshot.resource_count = len(snapshot.resources)
    return snapshot


class TestSnapshotExportYaml:
    """Tests for YAML output."""

    @patch("src.cli.main.SnapshotStorage")
    def test_export_yaml_to_stdout(self, mock_storage_cls, cli_runner):
        """Default format is YAML to stdout."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert "resources" in data
        assert "count" in data
        assert data["count"] == 1
        assert data["resources"][0]["arn"] == "arn:aws:ec2:us-east-1:123456789012:instance/i-abc123"
        assert data["resources"][0]["resource_type"] == "AWS::EC2::Instance"
        assert "config" in data["resources"][0]

    @patch("src.cli.main.SnapshotStorage")
    def test_export_yaml_to_file(self, mock_storage_cls, cli_runner, tmp_path):
        """Export YAML to file."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        out = tmp_path / "resources.yaml"
        result = cli_runner.invoke(app, ["snapshot", "export", "-o", str(out)])

        assert result.exit_code == 0
        assert out.exists()
        data = yaml.safe_load(out.read_text())
        assert data["count"] == 1


class TestSnapshotExportJson:
    """Tests for JSON output."""

    @patch("src.cli.main.SnapshotStorage")
    def test_export_json_to_file(self, mock_storage_cls, cli_runner, tmp_path):
        """Auto-detect JSON from file extension."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        out = tmp_path / "resources.json"
        result = cli_runner.invoke(app, ["snapshot", "export", "-o", str(out)])

        assert result.exit_code == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["count"] == 1
        assert data["resources"][0]["name"] == "test-instance"

    @patch("src.cli.main.SnapshotStorage")
    def test_export_json_format_flag(self, mock_storage_cls, cli_runner, tmp_path):
        """Explicit --format json overrides extension."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        out = tmp_path / "resources.yaml"
        result = cli_runner.invoke(app, ["snapshot", "export", "--format", "json", "-o", str(out)])

        assert result.exit_code == 0
        data = json.loads(out.read_text())
        assert data["count"] == 1


class TestSnapshotExportCsv:
    """Tests for CSV output."""

    @patch("src.cli.main.SnapshotStorage")
    def test_export_csv_to_file(self, mock_storage_cls, cli_runner, tmp_path):
        """Export CSV with flattened tags."""
        resource = make_resource(tags={"Environment": "prod", "Team": "platform"})
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot(resources=[resource])
        mock_storage_cls.return_value = mock_storage

        out = tmp_path / "resources.csv"
        result = cli_runner.invoke(app, ["snapshot", "export", "-o", str(out)])

        assert result.exit_code == 0
        assert out.exists()
        content = out.read_text()
        assert "ARN,ResourceType,Name,Region,Tags,CreatedAt,ConfigHash,Source" in content
        assert "arn:aws:ec2:us-east-1:123456789012:instance/i-abc123" in content
        # Tags should be flattened as key=value; key=value
        assert "Environment=prod" in content


class TestSnapshotExportFilters:
    """Tests for filtering options."""

    @patch("src.cli.main.SnapshotStorage")
    def test_export_type_filter(self, mock_storage_cls, cli_runner):
        """Filter by --type."""
        resources = [
            make_resource(arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1", resource_type="AWS::EC2::Instance"),
            make_resource(arn="arn:aws:s3:::my-bucket", resource_type="AWS::S3::Bucket", name="my-bucket"),
        ]
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot(resources=resources)
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--type", "s3"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert data["count"] == 1
        assert data["resources"][0]["name"] == "my-bucket"

    @patch("src.cli.main.SnapshotStorage")
    def test_export_region_filter(self, mock_storage_cls, cli_runner):
        """Filter by --region."""
        resources = [
            make_resource(arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1", region="us-east-1"),
            make_resource(arn="arn:aws:ec2:us-west-2:123456789012:instance/i-2", region="us-west-2"),
        ]
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot(resources=resources)
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--region", "us-west-2"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert data["count"] == 1
        assert data["resources"][0]["region"] == "us-west-2"

    @patch("src.cli.main.SnapshotStorage")
    def test_export_tag_filter(self, mock_storage_cls, cli_runner):
        """Filter by --tag Key=Value."""
        resources = [
            make_resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1",
                name="prod-instance",
                tags={"Environment": "production", "Name": "prod-instance"},
            ),
            make_resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-2",
                name="dev-instance",
                tags={"Environment": "dev", "Name": "dev-instance"},
            ),
        ]
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot(resources=resources)
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--tag", "Environment=production"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert data["count"] == 1
        assert data["resources"][0]["name"] == "prod-instance"

    @patch("src.cli.main.SnapshotStorage")
    def test_export_search_filter(self, mock_storage_cls, cli_runner):
        """Filter by --search ARN substring."""
        resources = [
            make_resource(arn="arn:aws:s3:::my-bucket", name="my-bucket", resource_type="AWS::S3::Bucket"),
            make_resource(arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1", name="instance"),
        ]
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot(resources=resources)
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--search", "my-bucket"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert data["count"] == 1
        assert data["resources"][0]["name"] == "my-bucket"

    @patch("src.cli.main.SnapshotStorage")
    def test_export_no_matching_resources(self, mock_storage_cls, cli_runner):
        """Clean exit when filters match nothing."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--type", "nonexistent"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert data["count"] == 0
        assert data["resources"] == []


class TestSnapshotExportOptions:
    """Tests for various export options."""

    @patch("src.cli.main.SnapshotStorage")
    def test_export_no_config(self, mock_storage_cls, cli_runner):
        """--no-config excludes raw config from output."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--no-config"])

        assert result.exit_code == 0
        data = yaml.safe_load(result.stdout)
        assert "config" not in data["resources"][0]

    @patch("src.cli.main.SnapshotStorage")
    def test_export_file_exists_error(self, mock_storage_cls, cli_runner, tmp_path):
        """Error when output file exists."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        out = tmp_path / "existing.yaml"
        out.write_text("existing content")

        result = cli_runner.invoke(app, ["snapshot", "export", "-o", str(out)])

        assert result.exit_code == 1
        assert "already exists" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_export_explicit_snapshot_name(self, mock_storage_cls, cli_runner):
        """Use explicit snapshot name argument."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = make_snapshot(name="my-snap")
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "my-snap"])

        assert result.exit_code == 0
        mock_storage.load_snapshot.assert_called_with("my-snap")

    @patch("src.cli.main.SnapshotStorage")
    def test_export_no_active_snapshot(self, mock_storage_cls, cli_runner):
        """Error when no active snapshot."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export"])

        assert result.exit_code == 1
        assert "No active snapshot" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_export_invalid_tag_format(self, mock_storage_cls, cli_runner):
        """Error on malformed --tag value."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--tag", "no-equals-sign"])

        assert result.exit_code == 1
        assert "Key=Value" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_export_unsupported_format(self, mock_storage_cls, cli_runner):
        """Error on unsupported --format."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = make_snapshot()
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["snapshot", "export", "--format", "xml"])

        assert result.exit_code == 1
        assert "Unsupported format" in result.stdout
