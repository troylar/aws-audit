"""Tests for delta reporter."""

from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from src.delta.reporter import DeltaReporter
from src.models.delta_report import DeltaReport, ResourceChange
from src.models.resource import Resource


def make_resource(
    name="test-resource",
    resource_type="AWS::EC2::Instance",
    region="us-east-1",
    tags=None,
    created_at=None,
):
    """Helper to create Resource objects."""
    return Resource(
        name=name,
        resource_type=resource_type,
        arn=f"arn:aws:{resource_type.split('::')[1].lower()}:{region}:123456789012:{name}",
        region=region,
        config_hash="test-hash-123",
        tags=tags or {},
        created_at=created_at,
    )


def make_delta_report(
    added=None,
    deleted=None,
    modified=None,
    baseline_count=10,
    current_count=None,
):
    """Helper to create DeltaReport with proper field ordering."""
    added = added or []
    deleted = deleted or []
    modified = modified or []

    if current_count is None:
        current_count = baseline_count + len(added) - len(deleted)

    return DeltaReport(
        generated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        baseline_snapshot_name="test-snapshot",
        current_snapshot_name="current-snapshot",
        added_resources=added,
        deleted_resources=deleted,
        modified_resources=modified,
        baseline_resource_count=baseline_count,
        current_resource_count=current_count,
    )


def make_resource_change(resource, old_hash="abc123", new_hash="def456"):
    """Helper to create ResourceChange objects."""
    return ResourceChange(
        resource=resource,
        baseline_resource=resource,
        change_type="modified",
        old_config_hash=old_hash,
        new_config_hash=new_hash,
    )


class TestDeltaReporterInit:
    """Tests for DeltaReporter initialization."""

    def test_default_console(self):
        """Test reporter creates default console."""
        reporter = DeltaReporter()
        assert reporter.console is not None
        assert isinstance(reporter.console, Console)

    def test_custom_console(self):
        """Test reporter uses provided console."""
        console = Console()
        reporter = DeltaReporter(console=console)
        assert reporter.console is console


class TestDeltaReporterDisplay:
    """Tests for DeltaReporter.display method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return DeltaReporter(console=console)

    def test_display_no_changes(self, reporter, console):
        """Test display when there are no changes."""
        report = make_delta_report()
        reporter.display(report)
        output = console.file.getvalue()
        assert "No changes detected" in output
        assert "test-snapshot" in output

    def test_display_with_changes(self, reporter, console):
        """Test display with added, deleted, and modified resources."""
        added = make_resource("new-instance", "AWS::EC2::Instance")
        deleted = make_resource("old-bucket", "AWS::S3::Bucket")
        modified = make_resource_change(make_resource("mod-lambda", "AWS::Lambda::Function"))

        report = make_delta_report(added=[added], deleted=[deleted], modified=[modified])
        reporter.display(report)
        output = console.file.getvalue()
        assert "Summary" in output
        assert "Added" in output
        assert "Deleted" in output
        assert "Modified" in output

    def test_display_with_details(self, reporter, console):
        """Test display with show_details=True shows ARNs."""
        added = make_resource("new-instance")
        report = make_delta_report(added=[added])
        reporter.display(report, show_details=True)
        output = console.file.getvalue()
        assert "arn:aws" in output


class TestDeltaReporterFormatTags:
    """Tests for DeltaReporter._format_tags method."""

    @pytest.fixture
    def reporter(self):
        """Create a reporter."""
        return DeltaReporter()

    def test_empty_tags(self, reporter):
        """Test formatting empty tags."""
        result = reporter._format_tags({})
        assert result == "-"

    def test_none_tags(self, reporter):
        """Test formatting None tags."""
        result = reporter._format_tags(None)
        assert result == "-"

    def test_single_tag(self, reporter):
        """Test formatting single tag."""
        result = reporter._format_tags({"Name": "test"})
        assert "Name=test" in result

    def test_multiple_tags(self, reporter):
        """Test formatting multiple tags."""
        result = reporter._format_tags({
            "Name": "test",
            "Environment": "dev",
            "Project": "myproj",
        })
        assert "Name=test" in result
        assert "Environment=dev" in result

    def test_important_tags_prioritized(self, reporter):
        """Test that important tags are shown first."""
        result = reporter._format_tags({
            "random": "value",
            "Name": "important",
            "other": "stuff",
        })
        assert "Name=important" in result

    def test_max_three_tags(self, reporter):
        """Test that only 3 tags are shown."""
        tags = {f"key{i}": f"value{i}" for i in range(10)}
        result = reporter._format_tags(tags)
        assert result.count("=") <= 3


class TestDeltaReporterExport:
    """Tests for DeltaReporter export methods."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return DeltaReporter(console=console)

    @patch("src.utils.export.export_to_json")
    def test_export_json(self, mock_export, reporter, console):
        """Test JSON export."""
        added = make_resource("new-instance", created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        report = make_delta_report(added=[added])
        reporter.export_json(report, "/tmp/test.json")
        mock_export.assert_called_once()
        output = console.file.getvalue()
        assert "exported" in output

    @patch("src.utils.export.export_to_csv")
    def test_export_csv(self, mock_export, reporter, console):
        """Test CSV export."""
        added = make_resource("new-instance", created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        report = make_delta_report(added=[added])
        reporter.export_csv(report, "/tmp/test.csv")
        mock_export.assert_called_once()
        output = console.file.getvalue()
        assert "exported" in output

    @patch("src.utils.export.export_to_csv")
    def test_export_csv_with_modified(self, mock_export, reporter, console):
        """Test CSV export with modified resources."""
        modified = make_resource_change(make_resource("mod-func", "AWS::Lambda::Function"))
        report = make_delta_report(modified=[modified])
        reporter.export_csv(report, "/tmp/test.csv")
        mock_export.assert_called_once()
        call_args = mock_export.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["change_type"] == "modified"


class TestDeltaReporterDisplaySummary:
    """Tests for DeltaReporter._display_summary method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return DeltaReporter(console=console)

    def test_display_summary_added_only(self, reporter, console):
        """Test summary display with only added resources."""
        added = make_resource("test-instance")
        report = make_delta_report(added=[added], baseline_count=5)
        reporter._display_summary(report)
        output = console.file.getvalue()
        assert "Added" in output

    def test_display_summary_all_types(self, reporter, console):
        """Test summary display with all change types."""
        added = make_resource("added", "AWS::EC2::Instance")
        deleted = make_resource("deleted", "AWS::S3::Bucket")
        modified = make_resource_change(make_resource("modified", "AWS::Lambda::Function"))

        report = make_delta_report(added=[added], deleted=[deleted], modified=[modified])
        reporter._display_summary(report)
        output = console.file.getvalue()
        assert "Added" in output
        assert "Deleted" in output
        assert "Modified" in output


class TestDeltaReporterDisplayServiceChanges:
    """Tests for DeltaReporter._display_service_changes method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return DeltaReporter(console=console)

    def test_display_empty_changes(self, reporter, console):
        """Test display with no changes for a service."""
        changes = {"added": [], "deleted": [], "modified": []}
        reporter._display_service_changes("AWS::EC2::Instance", changes, False)
        output = console.file.getvalue()
        assert "AWS::EC2::Instance" not in output

    def test_display_service_with_added(self, reporter, console):
        """Test display with added resources."""
        added = make_resource("new-instance", tags={"Name": "Test"})
        changes = {"added": [added], "deleted": [], "modified": []}
        reporter._display_service_changes("AWS::EC2::Instance", changes, False)
        output = console.file.getvalue()
        assert "AWS::EC2::Instance" in output
        assert "new-instance" in output
