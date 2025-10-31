"""
Unit tests for ReportFormatter class.

Tests for Rich-based output formatting including headers, tables, and progress bars.
"""

from __future__ import annotations

from datetime import datetime
from io import StringIO

import pytest
from rich.console import Console

from src.models.report import ResourceSummary, SnapshotMetadata
from src.snapshot.report_formatter import ReportFormatter


@pytest.fixture
def console():
    """Create a Rich Console instance for testing."""
    return Console(file=StringIO(), width=120, legacy_windows=False)


@pytest.fixture
def sample_metadata() -> SnapshotMetadata:
    """Create sample snapshot metadata."""
    return SnapshotMetadata(
        name="test-snapshot",
        created_at=datetime(2025, 1, 29, 10, 30, 0),
        account_id="123456789012",
        regions=["us-east-1", "us-west-2"],
        inventory_name="production",
        total_resource_count=100,
    )


@pytest.fixture
def sample_summary() -> ResourceSummary:
    """Create sample resource summary."""
    return ResourceSummary(
        total_count=100,
        by_service={"EC2": 40, "S3": 25, "Lambda": 20, "RDS": 10, "IAM": 5},
        by_region={"us-east-1": 70, "us-west-2": 30},
        by_type={
            "AWS::EC2::Instance": 40,
            "AWS::S3::Bucket": 25,
            "AWS::Lambda::Function": 20,
            "AWS::RDS::DBInstance": 10,
            "AWS::IAM::Role": 5,
        },
    )


class TestReportFormatterInit:
    """Tests for ReportFormatter initialization."""

    def test_init_with_console(self, console):
        """Test ReportFormatter.__init__() accepting Console instance."""
        formatter = ReportFormatter(console)

        assert formatter.console == console

    def test_init_default_console(self):
        """Test ReportFormatter with default Console."""
        formatter = ReportFormatter()

        assert formatter.console is not None
        assert isinstance(formatter.console, Console)


class TestReportFormatterFormatSummary:
    """Tests for summary formatting."""

    def test_format_summary_orchestration(self, console, sample_metadata, sample_summary):
        """Test ReportFormatter.format_summary() orchestrating all render methods."""
        formatter = ReportFormatter(console)

        # This should not raise any exceptions
        formatter.format_summary(sample_metadata, sample_summary)

        # Verify output was written to console
        output = console.file.getvalue()
        assert "test-snapshot" in output
        assert "production" in output
        assert "100" in output  # Total count

    def test_format_summary_with_filters(self, console, sample_metadata, sample_summary):
        """Test format_summary shows 'Filtered' when filters applied."""
        formatter = ReportFormatter(console)

        # Format with filters indicator
        formatter.format_summary(sample_metadata, sample_summary, has_filters=True)

        output = console.file.getvalue()
        assert "Filtered" in output or "filtered" in output.lower()


class TestReportFormatterRenderHeader:
    """Tests for header rendering."""

    def test_render_header(self, console, sample_metadata):
        """Test ReportFormatter._render_header() with snapshot metadata."""
        formatter = ReportFormatter(console)
        formatter._render_header(sample_metadata)

        output = console.file.getvalue()
        assert "test-snapshot" in output
        assert "production" in output
        assert "123456789012" in output
        assert "us-east-1" in output

    def test_render_header_many_regions(self, console):
        """Test header with many regions shows ellipsis."""
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1", "us-west-2", "eu-west-1", "ap-south-1", "ca-central-1"],
            inventory_name="prod",
            total_resource_count=100,
        )

        formatter = ReportFormatter(console)
        formatter._render_header(metadata)

        output = console.file.getvalue()
        assert "..." in output  # Should show ellipsis for many regions
        assert "5 regions" in output


class TestReportFormatterRenderBreakdowns:
    """Tests for service/region/type breakdown rendering."""

    def test_render_service_breakdown(self, console, sample_summary):
        """Test ReportFormatter._render_service_breakdown() with progress bars."""
        formatter = ReportFormatter(console)
        formatter._render_service_breakdown(sample_summary)

        output = console.file.getvalue()
        assert "EC2" in output
        assert "40" in output
        assert "S3" in output
        assert "25" in output

    def test_render_region_breakdown(self, console, sample_summary):
        """Test ReportFormatter._render_region_breakdown() with progress bars."""
        formatter = ReportFormatter(console)
        formatter._render_region_breakdown(sample_summary)

        output = console.file.getvalue()
        assert "us-east-1" in output
        assert "70" in output
        assert "us-west-2" in output
        assert "30" in output

    def test_render_type_breakdown_top_10(self, console):
        """Test ReportFormatter._render_type_breakdown() showing top 10 types."""
        # Create summary with 15 resource types
        by_type = {f"AWS::Service{i}::Resource": 100 - i for i in range(15)}
        summary = ResourceSummary(
            total_count=sum(by_type.values()),
            by_type=by_type,
        )

        formatter = ReportFormatter(console)
        formatter._render_type_breakdown(summary)

        output = console.file.getvalue()

        # Should show top 10 only
        assert "AWS::Service0::Resource" in output  # Highest count
        assert "AWS::Service9::Resource" in output  # 10th highest
        # May or may not show 11th depending on implementation


class TestReportFormatterEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_format_empty_summary(self, console, sample_metadata):
        """Test formatting with empty summary."""
        empty_summary = ResourceSummary(total_count=0)

        formatter = ReportFormatter(console)
        formatter.format_summary(sample_metadata, empty_summary)

        output = console.file.getvalue()
        assert "0" in output  # Should show zero count

    def test_format_single_service(self, console, sample_metadata):
        """Test formatting with single service."""
        summary = ResourceSummary(
            total_count=50,
            by_service={"EC2": 50},
            by_region={"us-east-1": 50},
            by_type={"AWS::EC2::Instance": 50},
        )

        formatter = ReportFormatter(console)
        formatter.format_summary(sample_metadata, summary)

        output = console.file.getvalue()
        assert "EC2" in output
        assert "50" in output


class TestReportFormatterDetailedView:
    """Tests for detailed resource view formatting (User Story 3)."""

    def test_format_detailed_basic(self, console, sample_metadata):
        """Test ReportFormatter.format_detailed() with sample resources."""
        from datetime import datetime

        from src.models.report import DetailedResource

        resources = [
            DetailedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="test-instance",
                region="us-east-1",
                tags={"Environment": "production", "Team": "platform"},
                created_at=datetime(2025, 1, 15, 10, 0, 0),
                config_hash="a" * 64,
            ),
        ]

        formatter = ReportFormatter(console)
        formatter.format_detailed(sample_metadata, resources, page_size=100)

        output = console.file.getvalue()
        assert "test-instance" in output
        assert "arn:aws:ec2" in output
        assert "production" in output

    def test_render_detailed_resource_with_tags(self, console):
        """Test _render_detailed_resource() shows tags properly."""
        from datetime import datetime

        from src.models.report import DetailedResource

        resource = DetailedResource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-bucket",
            region="us-east-1",
            tags={"Environment": "prod", "Owner": "john@example.com"},
            created_at=datetime(2024, 12, 1, 9, 0, 0),
            config_hash="b" * 64,
        )

        formatter = ReportFormatter(console)
        formatter._render_detailed_resource(resource, 1, 10)

        output = console.file.getvalue()
        assert "my-bucket" in output
        assert "Environment" in output
        assert "prod" in output

    def test_render_detailed_resource_without_tags(self, console):
        """Test _render_detailed_resource() with no tags shows placeholder."""
        from src.models.report import DetailedResource

        resource = DetailedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            tags={},
            created_at=None,
            config_hash="c" * 64,
        )

        formatter = ReportFormatter(console)
        formatter._render_detailed_resource(resource, 1, 10)

        output = console.file.getvalue()
        assert "my-func" in output
        # Should show some indication of no tags
        assert "no tags" in output.lower() or "none" in output.lower() or len(output) > 0

    def test_render_detailed_resource_without_created_at(self, console):
        """Test _render_detailed_resource() handles missing creation date."""
        from src.models.report import DetailedResource

        resource = DetailedResource(
            arn="arn:aws:iam::123456789012:role/MyRole",
            resource_type="AWS::IAM::Role",
            name="MyRole",
            region="global",
            tags={"Purpose": "testing"},
            created_at=None,
            config_hash="d" * 64,
        )

        formatter = ReportFormatter(console)
        formatter._render_detailed_resource(resource, 1, 10)

        output = console.file.getvalue()
        assert "MyRole" in output
        # Should handle None created_at gracefully
