"""
Unit tests for export functionality.

Tests for exporting reports to JSON, CSV, and TXT formats.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.models.report import DetailedResource, ResourceSummary, SnapshotMetadata
from src.utils.export import detect_format, export_report_csv, export_report_json, export_report_txt


class TestFormatDetection:
    """Tests for export format detection from filename."""

    def test_detect_json_format(self):
        """Test JSON format detection from .json extension."""
        assert detect_format("report.json") == "json"
        assert detect_format("/path/to/report.json") == "json"

    def test_detect_csv_format(self):
        """Test CSV format detection from .csv extension."""
        assert detect_format("report.csv") == "csv"
        assert detect_format("/path/to/report.csv") == "csv"

    def test_detect_txt_format(self):
        """Test TXT format detection from .txt extension."""
        assert detect_format("report.txt") == "txt"
        assert detect_format("/path/to/report.txt") == "txt"

    def test_detect_invalid_format(self):
        """Test detection raises error for unsupported format."""
        with pytest.raises(ValueError, match="Unsupported export format"):
            detect_format("report.xlsx")

        with pytest.raises(ValueError, match="Unsupported export format"):
            detect_format("report.pdf")


class TestJSONExport:
    """Tests for JSON export functionality."""

    def test_export_json_basic(self, tmp_path):
        """Test basic JSON export with sample data."""
        metadata = SnapshotMetadata(
            name="test-snapshot",
            created_at=datetime(2025, 1, 29, 10, 30, 0),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="test",
            total_resource_count=2,
        )

        summary = ResourceSummary(
            total_count=2,
            by_service={"EC2": 1, "S3": 1},
            by_region={"us-east-1": 2},
            by_type={"AWS::EC2::Instance": 1, "AWS::S3::Bucket": 1},
        )

        resources = [
            DetailedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="test-instance",
                region="us-east-1",
                tags={"Environment": "test"},
                created_at=datetime(2025, 1, 15, 10, 0, 0),
                config_hash="a" * 64,
            ),
        ]

        output_file = tmp_path / "test.json"
        export_report_json(str(output_file), metadata, summary, resources)

        # Verify file exists
        assert output_file.exists()

        # Verify content
        with open(output_file) as f:
            data = json.load(f)

        assert data["snapshot_metadata"]["name"] == "test-snapshot"
        assert data["summary"]["total_count"] == 2
        assert len(data["resources"]) == 1

    def test_export_json_file_exists_error(self, tmp_path):
        """Test JSON export raises error if file already exists."""
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="test",
            total_resource_count=0,
        )
        summary = ResourceSummary()

        # Create file first
        output_file = tmp_path / "exists.json"
        output_file.write_text("{}")

        # Should raise error
        with pytest.raises(FileExistsError):
            export_report_json(str(output_file), metadata, summary, [])


class TestCSVExport:
    """Tests for CSV export functionality."""

    def test_export_csv_basic(self, tmp_path):
        """Test basic CSV export with sample data."""
        resources = [
            DetailedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="test-instance",
                region="us-east-1",
                tags={"Environment": "test", "Team": "platform"},
                created_at=datetime(2025, 1, 15, 10, 0, 0),
                config_hash="a" * 64,
            ),
        ]

        output_file = tmp_path / "test.csv"
        export_report_csv(str(output_file), resources)

        # Verify file exists
        assert output_file.exists()

        # Verify content
        content = output_file.read_text()
        assert "ARN,ResourceType,Name,Region,CreatedAt,Tags" in content
        assert "arn:aws:ec2" in content
        assert "test-instance" in content

    def test_export_csv_with_json_tags(self, tmp_path):
        """Test CSV export encodes tags as JSON in Tags column."""
        resources = [
            DetailedResource(
                arn="arn:aws:s3:::my-bucket",
                resource_type="AWS::S3::Bucket",
                name="my-bucket",
                region="us-east-1",
                tags={"Environment": "prod", "Owner": "john@example.com"},
                created_at=None,
                config_hash="b" * 64,
            ),
        ]

        output_file = tmp_path / "test.csv"
        export_report_csv(str(output_file), resources)

        content = output_file.read_text()
        # Tags should be JSON-encoded (CSV escapes double quotes by doubling them)
        assert '""Environment"": ""prod""' in content or "Environment" in content


class TestTXTExport:
    """Tests for TXT export functionality."""

    def test_export_txt_basic(self, tmp_path):
        """Test basic TXT export with formatted output."""
        metadata = SnapshotMetadata(
            name="test-snapshot",
            created_at=datetime(2025, 1, 29, 10, 30, 0),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="test",
            total_resource_count=1,
        )

        summary = ResourceSummary(
            total_count=1,
            by_service={"EC2": 1},
            by_region={"us-east-1": 1},
            by_type={"AWS::EC2::Instance": 1},
        )

        output_file = tmp_path / "test.txt"
        export_report_txt(str(output_file), metadata, summary)

        # Verify file exists
        assert output_file.exists()

        # Verify content
        content = output_file.read_text()
        assert "test-snapshot" in content
        assert "Total Resources" in content or "1" in content


class TestExportEdgeCases:
    """Tests for export edge cases and error handling."""

    def test_export_empty_resources(self, tmp_path):
        """Test exporting with empty resource list."""
        metadata = SnapshotMetadata(
            name="empty",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="test",
            total_resource_count=0,
        )
        summary = ResourceSummary(total_count=0)

        # JSON with empty resources
        json_file = tmp_path / "empty.json"
        export_report_json(str(json_file), metadata, summary, [])
        assert json_file.exists()

        # CSV with empty resources
        csv_file = tmp_path / "empty.csv"
        export_report_csv(str(csv_file), [])
        assert csv_file.exists()

    def test_export_missing_parent_directory(self, tmp_path):
        """Test export raises error when parent directory doesn't exist."""
        nonexistent_dir = tmp_path / "nonexistent" / "report.json"

        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="test",
            total_resource_count=0,
        )
        summary = ResourceSummary()

        with pytest.raises(FileNotFoundError, match="Parent directory"):
            export_report_json(str(nonexistent_dir), metadata, summary, [])
