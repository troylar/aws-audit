"""Tests for export utilities."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.models.report import DetailedResource, ResourceSummary, SnapshotMetadata
from src.utils.export import (
    detect_format,
    export_report_csv,
    export_report_json,
    export_report_txt,
    export_to_csv,
    export_to_json,
    flatten_dict,
)


def make_snapshot_metadata(
    name="test-snapshot",
    account_id="123456789012",
    regions=None,
    inventory_name="test-inventory",
    total_resource_count=100,
):
    """Helper to create SnapshotMetadata objects."""
    return SnapshotMetadata(
        name=name,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        account_id=account_id,
        regions=regions or ["us-east-1", "us-west-2"],
        inventory_name=inventory_name,
        total_resource_count=total_resource_count,
    )


def make_resource_summary(
    total_count=100,
    by_service=None,
    by_region=None,
    by_type=None,
):
    """Helper to create ResourceSummary objects."""
    return ResourceSummary(
        total_count=total_count,
        by_service=by_service or {"EC2": 50, "S3": 30, "Lambda": 20},
        by_region=by_region or {"us-east-1": 60, "us-west-2": 40},
        by_type=by_type or {"AWS::EC2::Instance": 50, "AWS::S3::Bucket": 30},
    )


def make_detailed_resource(
    arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
    resource_type="AWS::EC2::Instance",
    name="test-instance",
    region="us-east-1",
    tags=None,
    created_at="default",  # Use sentinel to allow None
    config_hash="abc123",
):
    """Helper to create DetailedResource objects."""
    if created_at == "default":
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return DetailedResource(
        arn=arn,
        resource_type=resource_type,
        name=name,
        region=region,
        tags=tags or {"Name": "test", "Environment": "dev"},
        created_at=created_at,
        config_hash=config_hash,
    )


class TestExportToJson:
    """Tests for export_to_json function."""

    def test_export_dict(self, tmp_path):
        """Test exporting a dictionary to JSON."""
        data = {"key": "value", "number": 42}
        filepath = tmp_path / "test.json"

        result = export_to_json(data, str(filepath))

        assert result == filepath
        assert filepath.exists()
        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_export_list(self, tmp_path):
        """Test exporting a list to JSON."""
        data = [1, 2, 3, "four"]
        filepath = tmp_path / "test.json"

        result = export_to_json(data, str(filepath))

        assert result == filepath
        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_export_with_datetime(self, tmp_path):
        """Test that datetime objects are serialized."""
        data = {"created_at": datetime(2025, 1, 1, 12, 0, 0)}
        filepath = tmp_path / "test.json"

        export_to_json(data, str(filepath))

        with open(filepath) as f:
            loaded = json.load(f)
        assert "2025-01-01" in loaded["created_at"]

    def test_export_nested_dict(self, tmp_path):
        """Test exporting nested dictionary."""
        data = {"level1": {"level2": {"level3": "value"}}}
        filepath = tmp_path / "test.json"

        export_to_json(data, str(filepath))

        with open(filepath) as f:
            loaded = json.load(f)
        assert loaded["level1"]["level2"]["level3"] == "value"

    def test_export_indented(self, tmp_path):
        """Test that JSON is indented."""
        data = {"key": "value"}
        filepath = tmp_path / "test.json"

        export_to_json(data, str(filepath))

        content = filepath.read_text()
        assert "\n" in content  # Indentation adds newlines


class TestExportToCsv:
    """Tests for export_to_csv function."""

    def test_export_list_of_dicts(self, tmp_path):
        """Test exporting list of dictionaries to CSV."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]
        filepath = tmp_path / "test.csv"

        result = export_to_csv(data, str(filepath))

        assert result == filepath
        assert filepath.exists()
        content = filepath.read_text()
        assert "name,age" in content
        assert "Alice,30" in content
        assert "Bob,25" in content

    def test_export_empty_raises_error(self, tmp_path):
        """Test that empty data raises ValueError."""
        filepath = tmp_path / "test.csv"

        with pytest.raises(ValueError) as exc_info:
            export_to_csv([], str(filepath))

        assert "empty" in str(exc_info.value).lower()

    def test_export_non_dict_raises_error(self, tmp_path):
        """Test that non-dict list raises ValueError."""
        filepath = tmp_path / "test.csv"

        with pytest.raises(ValueError) as exc_info:
            export_to_csv(["not", "dicts"], str(filepath))

        assert "list of dictionaries" in str(exc_info.value).lower()

    def test_export_preserves_order(self, tmp_path):
        """Test that column order is preserved from first row."""
        data = [{"z": 1, "a": 2, "m": 3}]
        filepath = tmp_path / "test.csv"

        export_to_csv(data, str(filepath))

        content = filepath.read_text()
        lines = content.strip().split("\n")
        # Header should match order from data
        assert lines[0] == "z,a,m"


class TestFlattenDict:
    """Tests for flatten_dict function."""

    def test_simple_dict(self):
        """Test flattening simple dictionary."""
        d = {"a": 1, "b": 2}
        result = flatten_dict(d)
        assert result == {"a": 1, "b": 2}

    def test_nested_dict(self):
        """Test flattening nested dictionary."""
        d = {"outer": {"inner": "value"}}
        result = flatten_dict(d)
        assert result == {"outer_inner": "value"}

    def test_deeply_nested(self):
        """Test flattening deeply nested dictionary."""
        d = {"a": {"b": {"c": "deep"}}}
        result = flatten_dict(d)
        assert result == {"a_b_c": "deep"}

    def test_list_values(self):
        """Test that list values are joined."""
        d = {"items": [1, 2, 3]}
        result = flatten_dict(d)
        assert result == {"items": "1, 2, 3"}

    def test_mixed_types(self):
        """Test flattening mixed value types."""
        d = {
            "string": "text",
            "number": 42,
            "nested": {"key": "val"},
            "array": ["a", "b"],
        }
        result = flatten_dict(d)
        assert result["string"] == "text"
        assert result["number"] == 42
        assert result["nested_key"] == "val"
        assert result["array"] == "a, b"

    def test_custom_separator(self):
        """Test flattening with custom separator."""
        d = {"outer": {"inner": "value"}}
        result = flatten_dict(d, sep=".")
        assert result == {"outer.inner": "value"}

    def test_empty_dict(self):
        """Test flattening empty dictionary."""
        result = flatten_dict({})
        assert result == {}


class TestDetectFormat:
    """Tests for detect_format function."""

    def test_detect_json(self):
        """Test detecting JSON format."""
        assert detect_format("file.json") == "json"
        assert detect_format("path/to/file.JSON") == "json"

    def test_detect_csv(self):
        """Test detecting CSV format."""
        assert detect_format("file.csv") == "csv"
        assert detect_format("path/to/file.CSV") == "csv"

    def test_detect_txt(self):
        """Test detecting TXT format."""
        assert detect_format("file.txt") == "txt"
        assert detect_format("path/to/file.TXT") == "txt"

    def test_unsupported_format_raises(self):
        """Test that unsupported format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            detect_format("file.xml")
        assert "unsupported" in str(exc_info.value).lower()
        assert ".xml" in str(exc_info.value)

    def test_no_extension_raises(self):
        """Test that file without extension raises ValueError."""
        with pytest.raises(ValueError):
            detect_format("noextension")


class TestExportReportJson:
    """Tests for export_report_json function."""

    def test_export_success(self, tmp_path):
        """Test successful JSON report export."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary()
        resources = [make_detailed_resource()]
        filepath = tmp_path / "report.json"

        result = export_report_json(str(filepath), metadata, summary, resources)

        assert result == filepath
        assert filepath.exists()
        with open(filepath) as f:
            data = json.load(f)
        assert "snapshot_metadata" in data
        assert "summary" in data
        assert "resources" in data

    def test_export_metadata_fields(self, tmp_path):
        """Test that metadata fields are exported correctly."""
        metadata = make_snapshot_metadata(name="my-snapshot", account_id="111222333444")
        summary = make_resource_summary()
        resources = []
        filepath = tmp_path / "report.json"

        export_report_json(str(filepath), metadata, summary, resources)

        with open(filepath) as f:
            data = json.load(f)
        assert data["snapshot_metadata"]["name"] == "my-snapshot"
        assert data["snapshot_metadata"]["account_id"] == "111222333444"

    def test_export_summary_fields(self, tmp_path):
        """Test that summary fields are exported correctly."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary(total_count=500)
        resources = []
        filepath = tmp_path / "report.json"

        export_report_json(str(filepath), metadata, summary, resources)

        with open(filepath) as f:
            data = json.load(f)
        assert data["summary"]["total_count"] == 500
        assert "by_service" in data["summary"]

    def test_export_resources(self, tmp_path):
        """Test that resources are exported correctly."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary()
        resources = [
            make_detailed_resource(name="instance-1"),
            make_detailed_resource(name="instance-2"),
        ]
        filepath = tmp_path / "report.json"

        export_report_json(str(filepath), metadata, summary, resources)

        with open(filepath) as f:
            data = json.load(f)
        assert len(data["resources"]) == 2
        assert data["resources"][0]["name"] == "instance-1"

    def test_export_file_exists_raises(self, tmp_path):
        """Test that existing file raises FileExistsError."""
        filepath = tmp_path / "report.json"
        filepath.write_text("{}")  # Create existing file

        metadata = make_snapshot_metadata()
        summary = make_resource_summary()

        with pytest.raises(FileExistsError):
            export_report_json(str(filepath), metadata, summary, [])

    def test_export_parent_not_exists_raises(self, tmp_path):
        """Test that missing parent directory raises FileNotFoundError."""
        filepath = tmp_path / "nonexistent" / "report.json"

        metadata = make_snapshot_metadata()
        summary = make_resource_summary()

        with pytest.raises(FileNotFoundError):
            export_report_json(str(filepath), metadata, summary, [])

    def test_export_resource_without_created_at(self, tmp_path):
        """Test exporting resource without creation date."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary()
        resources = [make_detailed_resource(created_at=None)]
        filepath = tmp_path / "report.json"

        export_report_json(str(filepath), metadata, summary, resources)

        with open(filepath) as f:
            data = json.load(f)
        assert data["resources"][0]["created_at"] is None


class TestExportReportCsv:
    """Tests for export_report_csv function."""

    def test_export_success(self, tmp_path):
        """Test successful CSV export."""
        resources = [make_detailed_resource()]
        filepath = tmp_path / "report.csv"

        result = export_report_csv(str(filepath), resources)

        assert result == filepath
        assert filepath.exists()
        content = filepath.read_text()
        assert "ARN,ResourceType,Name,Region,CreatedAt,Tags" in content

    def test_export_multiple_resources(self, tmp_path):
        """Test exporting multiple resources."""
        resources = [
            make_detailed_resource(name="instance-1"),
            make_detailed_resource(name="instance-2"),
        ]
        filepath = tmp_path / "report.csv"

        export_report_csv(str(filepath), resources)

        content = filepath.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # Header + 2 resources

    def test_export_empty_resources(self, tmp_path):
        """Test exporting empty resource list."""
        filepath = tmp_path / "report.csv"

        export_report_csv(str(filepath), [])

        content = filepath.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 1  # Only header

    def test_export_file_exists_raises(self, tmp_path):
        """Test that existing file raises FileExistsError."""
        filepath = tmp_path / "report.csv"
        filepath.write_text("existing")

        with pytest.raises(FileExistsError):
            export_report_csv(str(filepath), [])

    def test_export_parent_not_exists_raises(self, tmp_path):
        """Test that missing parent raises FileNotFoundError."""
        filepath = tmp_path / "nonexistent" / "report.csv"

        with pytest.raises(FileNotFoundError):
            export_report_csv(str(filepath), [])

    def test_export_tags_as_json(self, tmp_path):
        """Test that tags are exported as JSON."""
        resources = [make_detailed_resource(tags={"Name": "test"})]
        filepath = tmp_path / "report.csv"

        export_report_csv(str(filepath), resources)

        content = filepath.read_text()
        # CSV escapes quotes by doubling them
        assert "Name" in content and "test" in content

    def test_export_resource_without_created_at(self, tmp_path):
        """Test exporting resource without creation date."""
        resources = [make_detailed_resource(created_at=None)]
        filepath = tmp_path / "report.csv"

        export_report_csv(str(filepath), resources)

        # Should not crash, just have empty field
        assert filepath.exists()


class TestExportReportTxt:
    """Tests for export_report_txt function."""

    def test_export_success(self, tmp_path):
        """Test successful TXT export."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary()
        filepath = tmp_path / "report.txt"

        result = export_report_txt(str(filepath), metadata, summary)

        assert result == filepath
        assert filepath.exists()

    def test_export_contains_metadata(self, tmp_path):
        """Test that TXT contains metadata."""
        metadata = make_snapshot_metadata(name="my-snapshot", account_id="123456789012")
        summary = make_resource_summary()
        filepath = tmp_path / "report.txt"

        export_report_txt(str(filepath), metadata, summary)

        content = filepath.read_text()
        assert "my-snapshot" in content
        assert "123456789012" in content

    def test_export_contains_summary(self, tmp_path):
        """Test that TXT contains summary."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary(total_count=500)
        filepath = tmp_path / "report.txt"

        export_report_txt(str(filepath), metadata, summary)

        content = filepath.read_text()
        assert "Resource Summary" in content
        assert "500" in content

    def test_export_contains_services(self, tmp_path):
        """Test that TXT contains service breakdown."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary(by_service={"EC2": 100, "S3": 50})
        filepath = tmp_path / "report.txt"

        export_report_txt(str(filepath), metadata, summary)

        content = filepath.read_text()
        assert "By Service" in content

    def test_export_contains_regions(self, tmp_path):
        """Test that TXT contains region breakdown."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary(by_region={"us-east-1": 80, "us-west-2": 20})
        filepath = tmp_path / "report.txt"

        export_report_txt(str(filepath), metadata, summary)

        content = filepath.read_text()
        assert "By Region" in content

    def test_export_file_exists_raises(self, tmp_path):
        """Test that existing file raises FileExistsError."""
        filepath = tmp_path / "report.txt"
        filepath.write_text("existing")

        metadata = make_snapshot_metadata()
        summary = make_resource_summary()

        with pytest.raises(FileExistsError):
            export_report_txt(str(filepath), metadata, summary)

    def test_export_parent_not_exists_raises(self, tmp_path):
        """Test that missing parent raises FileNotFoundError."""
        filepath = tmp_path / "nonexistent" / "report.txt"

        metadata = make_snapshot_metadata()
        summary = make_resource_summary()

        with pytest.raises(FileNotFoundError):
            export_report_txt(str(filepath), metadata, summary)

    def test_export_empty_services(self, tmp_path):
        """Test export with empty services."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary(by_service={})
        filepath = tmp_path / "report.txt"

        export_report_txt(str(filepath), metadata, summary)

        # Should not crash
        assert filepath.exists()

    def test_export_empty_regions(self, tmp_path):
        """Test export with empty regions."""
        metadata = make_snapshot_metadata()
        summary = make_resource_summary(by_region={})
        filepath = tmp_path / "report.txt"

        export_report_txt(str(filepath), metadata, summary)

        # Should not crash
        assert filepath.exists()
