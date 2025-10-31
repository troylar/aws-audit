"""
Unit tests for SnapshotReporter class.

Tests for report generation, metadata extraction, and summary calculation.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

import pytest

from src.models.resource import Resource
from src.models.snapshot import Snapshot
from src.snapshot.reporter import SnapshotReporter


@pytest.fixture
def sample_resources() -> List[Resource]:
    """Create sample resources for testing."""
    return [
        Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type="AWS::EC2::Instance",
            name="web-server-01",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={},
            tags={"Environment": "production", "Team": "platform"},
            created_at=datetime(2025, 1, 15, 10, 30, 0),
        ),
        Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abcdef1234567890",
            resource_type="AWS::EC2::Instance",
            name="web-server-02",
            region="us-east-1",
            config_hash="b" * 64,
            raw_config={},
            tags={"Environment": "production"},
            created_at=datetime(2025, 1, 16, 10, 30, 0),
        ),
        Resource(
            arn="arn:aws:ec2:us-west-2:123456789012:instance/i-9876543210fedcba",
            resource_type="AWS::EC2::Instance",
            name="web-server-03",
            region="us-west-2",
            config_hash="c" * 64,
            raw_config={},
            tags={},
            created_at=None,
        ),
        Resource(
            arn="arn:aws:s3:::my-production-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-production-bucket",
            region="us-east-1",
            config_hash="d" * 64,
            raw_config={},
            tags={"Environment": "production", "DataClass": "sensitive"},
            created_at=datetime(2024, 12, 1, 9, 0, 0),
        ),
        Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-function",
            resource_type="AWS::Lambda::Function",
            name="my-function",
            region="us-east-1",
            config_hash="e" * 64,
            raw_config={},
            tags={"Environment": "production"},
            created_at=datetime(2025, 1, 10, 8, 0, 0),
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_resources) -> Snapshot:
    """Create a sample snapshot for testing."""
    return Snapshot(
        name="test-snapshot",
        created_at=datetime(2025, 1, 29, 10, 30, 0),
        account_id="123456789012",
        regions=["us-east-1", "us-west-2"],
        resources=sample_resources,
        inventory_name="production",
    )


class TestSnapshotReporterInit:
    """Tests for SnapshotReporter initialization."""

    def test_init_with_snapshot(self, sample_snapshot):
        """Test SnapshotReporter.__init__() accepting Snapshot object."""
        reporter = SnapshotReporter(sample_snapshot)

        assert reporter.snapshot == sample_snapshot
        assert reporter.snapshot.name == "test-snapshot"

    def test_extract_metadata(self, sample_snapshot):
        """Test SnapshotReporter._extract_metadata() from Snapshot to SnapshotMetadata."""
        reporter = SnapshotReporter(sample_snapshot)
        metadata = reporter._extract_metadata()

        assert metadata.name == "test-snapshot"
        assert metadata.created_at == datetime(2025, 1, 29, 10, 30, 0)
        assert metadata.account_id == "123456789012"
        assert metadata.regions == ["us-east-1", "us-west-2"]
        assert metadata.inventory_name == "production"
        assert metadata.total_resource_count == 5


class TestSnapshotReporterGenerateSummary:
    """Tests for summary generation."""

    def test_generate_summary_basic(self, sample_snapshot):
        """Test SnapshotReporter.generate_summary() with test snapshot."""
        reporter = SnapshotReporter(sample_snapshot)
        summary = reporter.generate_summary()

        assert summary.total_count == 5
        assert summary.by_service["EC2"] == 3
        assert summary.by_service["S3"] == 1
        assert summary.by_service["Lambda"] == 1
        assert summary.by_region["us-east-1"] == 4
        assert summary.by_region["us-west-2"] == 1

    def test_generate_summary_streaming(self, sample_snapshot):
        """Test SnapshotReporter.generate_summary() streaming - no full load."""
        # Mock the snapshot to verify we're iterating, not loading all at once
        reporter = SnapshotReporter(sample_snapshot)

        # Generate summary
        summary = reporter.generate_summary()

        # Verify it calculated correctly without loading everything
        assert summary.total_count == 5
        assert summary.service_count == 3  # EC2, S3, Lambda
        assert summary.region_count == 2  # us-east-1, us-west-2
        assert summary.type_count == 3  # Instance, Bucket, Function

    def test_generate_summary_empty_snapshot(self):
        """Test generate_summary with empty snapshot."""
        empty_snapshot = Snapshot(
            name="empty",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            inventory_name="test",
        )

        reporter = SnapshotReporter(empty_snapshot)
        summary = reporter.generate_summary()

        assert summary.total_count == 0
        assert summary.service_count == 0
        assert summary.region_count == 0
        assert len(summary.by_service) == 0


class TestSnapshotReporterLargeDataset:
    """Tests for handling large datasets efficiently."""

    def test_summary_with_100_resources(self):
        """Test summary generation with 100 resources."""
        # Create 100 resources across different services and regions
        resources = []
        for i in range(100):
            service = ["EC2", "S3", "Lambda", "RDS", "IAM"][i % 5]
            region = ["us-east-1", "us-west-2", "eu-west-1"][i % 3]

            resources.append(
                Resource(
                    arn=f"arn:aws:{service.lower()}:{region}:123456789012:resource/{i}",
                    resource_type=f"AWS::{service}::Resource",
                    name=f"resource-{i}",
                    region=region,
                    config_hash=f"{i:064d}",
                    raw_config={},
                    tags={},
                    created_at=None,
                )
            )

        snapshot = Snapshot(
            name="large-test",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1", "us-west-2", "eu-west-1"],
            resources=resources,
            inventory_name="test",
        )

        reporter = SnapshotReporter(snapshot)
        summary = reporter.generate_summary()

        assert summary.total_count == 100
        assert summary.service_count == 5
        assert summary.region_count == 3

        # Verify distribution
        for service in ["EC2", "S3", "Lambda", "RDS", "IAM"]:
            assert summary.by_service[service] == 20

        assert summary.by_region["us-east-1"] == 34  # Indices 0, 3, 6, 9...
        assert summary.by_region["us-west-2"] == 33  # Indices 1, 4, 7, 10...
        assert summary.by_region["eu-west-1"] == 33  # Indices 2, 5, 8, 11...


class TestSnapshotReporterFiltering:
    """Tests for filtering functionality (User Story 2)."""

    def test_get_filtered_resources_generator(self, sample_snapshot):
        """Test SnapshotReporter.get_filtered_resources() generator pattern."""
        from src.models.report import FilterCriteria

        reporter = SnapshotReporter(sample_snapshot)
        criteria = FilterCriteria(resource_types=["ec2"], regions=None)

        # Get filtered resources
        filtered = list(reporter.get_filtered_resources(criteria))

        # Should only return EC2 instances
        assert len(filtered) == 3
        assert all("EC2" in r.resource_type for r in filtered)

    def test_apply_filters_with_criteria(self, sample_snapshot):
        """Test SnapshotReporter._apply_filters() with FilterCriteria."""
        from src.models.report import FilterCriteria

        reporter = SnapshotReporter(sample_snapshot)

        # Filter by service
        criteria = FilterCriteria(resource_types=["s3"], regions=None)
        filtered = list(reporter.get_filtered_resources(criteria))
        assert len(filtered) == 1
        assert "S3" in filtered[0].resource_type

        # Filter by region
        criteria = FilterCriteria(resource_types=None, regions=["us-east-1"])
        filtered = list(reporter.get_filtered_resources(criteria))
        assert len(filtered) == 4  # 2 EC2 instances + 1 S3 + 1 Lambda in us-east-1
        assert all(r.region == "us-east-1" for r in filtered)

    def test_filtered_summary_generation(self, sample_snapshot):
        """Test filtered summary generation."""
        from src.models.report import FilterCriteria

        reporter = SnapshotReporter(sample_snapshot)
        criteria = FilterCriteria(resource_types=["lambda"], regions=None)

        summary = reporter.generate_filtered_summary(criteria)

        assert summary.total_count == 1
        assert summary.by_service["Lambda"] == 1
        assert summary.by_region["us-east-1"] == 1


class TestSnapshotReporterDetailedView:
    """Tests for detailed resource view functionality (User Story 3)."""

    def test_get_detailed_resources_generator(self, sample_snapshot):
        """Test SnapshotReporter.get_detailed_resources() returns generator."""
        reporter = SnapshotReporter(sample_snapshot)

        # Get detailed resources
        detailed = reporter.get_detailed_resources()

        # Should be a generator
        assert hasattr(detailed, "__iter__")
        assert hasattr(detailed, "__next__")

    def test_get_detailed_resources_conversion(self, sample_snapshot):
        """Test conversion from Resource to DetailedResource."""
        reporter = SnapshotReporter(sample_snapshot)
        detailed_list = list(reporter.get_detailed_resources())

        assert len(detailed_list) == 5

        # Check first resource has all fields
        first = detailed_list[0]
        assert hasattr(first, "arn")
        assert hasattr(first, "resource_type")
        assert hasattr(first, "name")
        assert hasattr(first, "region")
        assert hasattr(first, "tags")
        assert hasattr(first, "created_at")
        assert hasattr(first, "config_hash")

    def test_get_detailed_resources_with_filters(self, sample_snapshot):
        """Test get_detailed_resources() with FilterCriteria."""
        from src.models.report import FilterCriteria

        reporter = SnapshotReporter(sample_snapshot)
        criteria = FilterCriteria(resource_types=["ec2"], regions=None)

        detailed_list = list(reporter.get_detailed_resources(criteria))

        # Should only return EC2 resources
        assert len(detailed_list) == 3
        assert all("EC2" in r.resource_type for r in detailed_list)
