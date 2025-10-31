"""
Unit tests for report data models.

Tests for SnapshotMetadata, ResourceSummary, FilteredResource, DetailedResource,
FilterCriteria, and ResourceReport dataclasses.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.models.report import (
    DetailedResource,
    FilterCriteria,
    FilteredResource,
    ResourceReport,
    ResourceSummary,
    SnapshotMetadata,
)


class TestSnapshotMetadata:
    """Tests for SnapshotMetadata dataclass."""

    def test_snapshot_metadata_properties(self):
        """Test SnapshotMetadata dataclass initialization and properties."""
        metadata = SnapshotMetadata(
            name="test-snapshot",
            created_at=datetime(2025, 1, 29, 10, 30, 0),
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            inventory_name="production",
            total_resource_count=1547,
        )

        assert metadata.name == "test-snapshot"
        assert metadata.created_at == datetime(2025, 1, 29, 10, 30, 0)
        assert metadata.account_id == "123456789012"
        assert metadata.regions == ["us-east-1", "us-west-2"]
        assert metadata.inventory_name == "production"
        assert metadata.total_resource_count == 1547

    def test_region_summary_few_regions(self):
        """Test region_summary property with 3 or fewer regions."""
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1", "us-west-2", "eu-west-1"],
            inventory_name="prod",
            total_resource_count=100,
        )

        assert metadata.region_summary == "us-east-1, us-west-2, eu-west-1"

    def test_region_summary_many_regions(self):
        """Test region_summary property with more than 3 regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1", "ca-central-1"]
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=regions,
            inventory_name="prod",
            total_resource_count=100,
        )

        expected = "us-east-1, us-west-2, eu-west-1 ... (5 regions)"
        assert metadata.region_summary == expected


class TestResourceSummary:
    """Tests for ResourceSummary dataclass."""

    def test_resource_summary_initialization(self):
        """Test ResourceSummary dataclass with default initialization."""
        summary = ResourceSummary()

        assert summary.total_count == 0
        assert isinstance(summary.by_service, dict)
        assert isinstance(summary.by_region, dict)
        assert isinstance(summary.by_type, dict)

    def test_resource_summary_with_data(self):
        """Test ResourceSummary with aggregation helpers."""
        summary = ResourceSummary(
            total_count=1547,
            by_service={"EC2": 450, "IAM": 512, "Lambda": 380, "S3": 120, "RDS": 85},
            by_region={"us-east-1": 890, "us-west-2": 520, "eu-west-1": 137},
            by_type={
                "AWS::EC2::Instance": 450,
                "AWS::IAM::Role": 512,
                "AWS::Lambda::Function": 380,
            },
        )

        assert summary.total_count == 1547
        assert summary.service_count == 5
        assert summary.region_count == 3
        assert summary.type_count == 3

    def test_top_services(self):
        """Test top_services() method."""
        summary = ResourceSummary(
            total_count=1547,
            by_service={"EC2": 450, "IAM": 512, "Lambda": 380, "S3": 120, "RDS": 85},
        )

        top5 = summary.top_services(limit=5)
        assert len(top5) == 5
        assert top5[0] == ("IAM", 512)
        assert top5[1] == ("EC2", 450)
        assert top5[2] == ("Lambda", 380)

        top3 = summary.top_services(limit=3)
        assert len(top3) == 3

    def test_top_regions(self):
        """Test top_regions() method."""
        summary = ResourceSummary(
            total_count=1547,
            by_region={"us-east-1": 890, "us-west-2": 520, "eu-west-1": 137},
        )

        top_regions = summary.top_regions(limit=5)
        assert len(top_regions) == 3
        assert top_regions[0] == ("us-east-1", 890)
        assert top_regions[1] == ("us-west-2", 520)
        assert top_regions[2] == ("eu-west-1", 137)


class TestFilteredResource:
    """Tests for FilteredResource dataclass."""

    def test_filtered_resource_properties(self):
        """Test FilteredResource dataclass and property methods."""
        resource = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type="AWS::EC2::Instance",
            name="web-server-01",
            region="us-east-1",
        )

        assert resource.arn == "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        assert resource.resource_type == "AWS::EC2::Instance"
        assert resource.name == "web-server-01"
        assert resource.region == "us-east-1"

    def test_service_property(self):
        """Test service property extracting from resource_type."""
        resource = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
        )

        assert resource.service == "EC2"

    def test_service_property_unknown(self):
        """Test service property with malformed resource type."""
        resource = FilteredResource(
            arn="arn:aws:unknown:::resource",
            resource_type="InvalidType",
            name="test",
            region="us-east-1",
        )

        assert resource.service == "Unknown"

    def test_short_type_property(self):
        """Test short_type property."""
        resource = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
        )

        assert resource.short_type == "Instance"


class TestDetailedResource:
    """Tests for DetailedResource dataclass."""

    def test_detailed_resource_properties(self):
        """Test DetailedResource dataclass and property methods."""
        created_at = datetime(2025, 1, 15, 10, 30, 0)
        resource = DetailedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type="AWS::EC2::Instance",
            name="web-server-01",
            region="us-east-1",
            tags={"Environment": "production", "Team": "platform"},
            created_at=created_at,
            config_hash="a3f5b2c1d4e6f7a8b9c0d1e2f3a4b5c6",
        )

        assert resource.arn == "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        assert resource.resource_type == "AWS::EC2::Instance"
        assert resource.name == "web-server-01"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Environment": "production", "Team": "platform"}
        assert resource.created_at == created_at
        assert resource.config_hash == "a3f5b2c1d4e6f7a8b9c0d1e2f3a4b5c6"

    def test_service_property(self):
        """Test service property for DetailedResource."""
        resource = DetailedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-function",
            resource_type="AWS::Lambda::Function",
            name="my-function",
            region="us-east-1",
            tags={},
            created_at=None,
            config_hash="hash123",
        )

        assert resource.service == "Lambda"

    def test_age_days_property(self):
        """Test age_days property calculating days since creation."""
        created_at = datetime.now() - timedelta(days=14)
        resource = DetailedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
            tags={},
            created_at=created_at,
            config_hash="hash123",
        )

        assert resource.age_days == 14

    def test_age_days_none(self):
        """Test age_days returns None when created_at is None."""
        resource = DetailedResource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-bucket",
            region="us-east-1",
            tags={},
            created_at=None,
            config_hash="hash123",
        )

        assert resource.age_days is None

    def test_tag_count_property(self):
        """Test tag_count property."""
        resource = DetailedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
            tags={"Environment": "prod", "Team": "platform", "Owner": "john@example.com"},
            created_at=None,
            config_hash="hash123",
        )

        assert resource.tag_count == 3

    def test_has_tag_method(self):
        """Test has_tag() method with optional value check."""
        resource = DetailedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
            tags={"Environment": "production", "Team": "platform"},
            created_at=None,
            config_hash="hash123",
        )

        # Test key exists
        assert resource.has_tag("Environment") is True
        assert resource.has_tag("NonExistent") is False

        # Test key and value match
        assert resource.has_tag("Environment", "production") is True
        assert resource.has_tag("Environment", "development") is False


class TestFilterCriteria:
    """Tests for FilterCriteria dataclass."""

    def test_filter_criteria_initialization(self):
        """Test FilterCriteria with post_init normalization."""
        criteria = FilterCriteria(
            resource_types=["EC2", "Lambda"],
            regions=["us-east-1", "US-WEST-2"],
            match_mode="flexible",
        )

        # Should normalize to lowercase
        assert criteria.resource_types == ["ec2", "lambda"]
        assert criteria.regions == ["us-east-1", "us-west-2"]

    def test_has_filters_property(self):
        """Test has_filters property."""
        criteria_with_filters = FilterCriteria(resource_types=["ec2"], regions=None)
        assert criteria_with_filters.has_filters is True

        criteria_no_filters = FilterCriteria(resource_types=None, regions=None)
        assert criteria_no_filters.has_filters is False

    def test_filter_count_property(self):
        """Test filter_count property."""
        criteria = FilterCriteria(
            resource_types=["ec2", "lambda", "s3"],
            regions=["us-east-1", "us-west-2"],
        )

        assert criteria.filter_count == 5  # 3 types + 2 regions

    def test_matches_resource_exact_match(self):
        """Test FilterCriteria exact match tier."""
        criteria = FilterCriteria(
            resource_types=["aws::ec2::instance"],
            regions=None,
        )

        resource = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
        )

        assert criteria.matches_resource(resource) is True

    def test_matches_resource_service_prefix_match(self):
        """Test FilterCriteria service prefix match tier."""
        criteria = FilterCriteria(
            resource_types=["ec2"],
            regions=None,
        )

        instance = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test-instance",
            region="us-east-1",
        )

        volume = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:volume/vol-123",
            resource_type="AWS::EC2::Volume",
            name="test-volume",
            region="us-east-1",
        )

        assert criteria.matches_resource(instance) is True
        assert criteria.matches_resource(volume) is True

    def test_matches_resource_contains_match(self):
        """Test FilterCriteria contains match tier."""
        criteria = FilterCriteria(
            resource_types=["bucket"],
            regions=None,
        )

        s3_bucket = FilteredResource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-bucket",
            region="us-east-1",
        )

        assert criteria.matches_resource(s3_bucket) is True

    def test_matches_resource_region_filter(self):
        """Test FilterCriteria region filtering (case-insensitive)."""
        criteria = FilterCriteria(
            resource_types=None,
            regions=["us-east-1"],
        )

        matching = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
        )

        non_matching = FilteredResource(
            arn="arn:aws:ec2:us-west-2:123456789012:instance/i-456",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-west-2",
        )

        assert criteria.matches_resource(matching) is True
        assert criteria.matches_resource(non_matching) is False

    def test_matches_resource_combined_filters(self):
        """Test FilterCriteria combined filters (AND logic)."""
        criteria = FilterCriteria(
            resource_types=["lambda"],
            regions=["us-east-1"],
        )

        matching = FilteredResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
        )

        wrong_region = FilteredResource(
            arn="arn:aws:lambda:us-west-2:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-west-2",
        )

        wrong_type = FilteredResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test",
            region="us-east-1",
        )

        assert criteria.matches_resource(matching) is True
        assert criteria.matches_resource(wrong_region) is False
        assert criteria.matches_resource(wrong_type) is False


class TestResourceReport:
    """Tests for ResourceReport dataclass."""

    def test_resource_report_initialization(self):
        """Test ResourceReport top-level container."""
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="prod",
            total_resource_count=100,
        )

        summary = ResourceSummary(total_count=100)

        report = ResourceReport(
            snapshot_metadata=metadata,
            summary=summary,
            filtered_resources=None,
            detailed_resources=None,
        )

        assert report.snapshot_metadata == metadata
        assert report.summary == summary
        assert report.filtered_resources is None
        assert report.detailed_resources is None

    def test_has_filters_property(self):
        """Test has_filters property."""
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="prod",
            total_resource_count=100,
        )
        summary = ResourceSummary(total_count=100)

        report_no_filters = ResourceReport(
            snapshot_metadata=metadata,
            summary=summary,
            filtered_resources=None,
        )

        report_with_filters = ResourceReport(
            snapshot_metadata=metadata,
            summary=summary,
            filtered_resources=[],
        )

        assert report_no_filters.has_filters is False
        assert report_with_filters.has_filters is True

    def test_has_details_property(self):
        """Test has_details property."""
        metadata = SnapshotMetadata(
            name="test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            inventory_name="prod",
            total_resource_count=100,
        )
        summary = ResourceSummary(total_count=100)

        report_no_details = ResourceReport(
            snapshot_metadata=metadata,
            summary=summary,
        )

        report_with_details = ResourceReport(
            snapshot_metadata=metadata,
            summary=summary,
            detailed_resources=[],
        )

        assert report_no_details.has_details is False
        assert report_with_details.has_details is True
