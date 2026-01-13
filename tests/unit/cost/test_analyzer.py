"""Tests for cost analyzer."""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.cost.analyzer import CostAnalyzer
from src.models.resource import Resource
from src.models.snapshot import Snapshot


def make_snapshot(
    name="test-snapshot",
    resources=None,
    created_at=None,
):
    """Helper to create Snapshot objects."""
    return Snapshot(
        name=name,
        created_at=created_at or datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources or [],
    )


def make_resource(
    name="test-resource",
    resource_type="AWS::EC2::Instance",
    region="us-east-1",
):
    """Helper to create Resource objects."""
    return Resource(
        name=name,
        resource_type=resource_type,
        arn=f"arn:aws:ec2:{region}:123456789012:instance/{name}",
        region=region,
        config_hash="hash123",
        tags={},
    )


class TestCostAnalyzerInit:
    """Tests for CostAnalyzer initialization."""

    def test_init_stores_explorer(self):
        """Test that init stores cost explorer client."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)
        assert analyzer.cost_explorer == mock_explorer


class TestCostAnalyzerAnalyze:
    """Tests for CostAnalyzer.analyze method."""

    def test_analyze_with_default_dates(self):
        """Test analyze uses snapshot date as start and today as end."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {"Amazon EC2": 100.0}

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        report = analyzer.analyze(snapshot)

        assert report is not None
        assert report.baseline_snapshot_name == "test-snapshot"
        assert report.total_cost == 100.0

    def test_analyze_with_custom_dates(self):
        """Test analyze with custom start and end dates."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {"Amazon EC2": 150.0}

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 31)

        report = analyzer.analyze(snapshot, start_date=start, end_date=end)

        assert report.period_start == start
        assert report.period_end == end
        assert report.total_cost == 150.0

    def test_analyze_no_deltas_all_baseline(self):
        """Test that without deltas, all costs are baseline."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {
            "Amazon EC2": 100.0,
            "Amazon S3": 50.0,
        }

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        report = analyzer.analyze(snapshot, has_deltas=False)

        assert report.baseline_costs.total == 150.0
        assert report.non_baseline_costs.total == 0.0
        assert report.baseline_costs.percentage == 100.0

    def test_analyze_with_deltas_shows_total(self):
        """Test that with deltas, total costs are shown."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {
            "Amazon EC2": 100.0,
            "Amazon S3": 50.0,
        }

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        report = analyzer.analyze(snapshot, has_deltas=True)

        assert report.total_cost == 150.0
        assert report.baseline_costs.total == 150.0

    def test_analyze_handles_date_order(self):
        """Test that analyze handles start > end by adjusting dates."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {}

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        # Start date after end date
        start = datetime(2025, 1, 31)
        end = datetime(2025, 1, 1)

        report = analyzer.analyze(snapshot, start_date=start, end_date=end)

        # Should adjust end_date to start_date + 1 day
        assert report is not None

    def test_analyze_strips_timezone(self):
        """Test that analyze handles timezone-aware dates."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {}

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        # Timezone-aware dates
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 31, tzinfo=timezone.utc)

        report = analyzer.analyze(snapshot, start_date=start, end_date=end)

        # Dates should be stripped of timezone
        assert report.period_start.tzinfo is None
        assert report.period_end.tzinfo is None

    def test_analyze_includes_data_completeness(self):
        """Test that analyze includes data completeness info."""
        mock_explorer = MagicMock()
        data_through = datetime(2025, 1, 29)
        mock_explorer.check_data_completeness.return_value = (False, data_through, 2)
        mock_explorer.get_costs_by_service.return_value = {}

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        report = analyzer.analyze(snapshot)

        assert report.data_complete is False
        assert report.data_through == data_through
        assert report.lag_days == 2

    def test_analyze_cost_breakdown_by_service(self):
        """Test that cost breakdown includes service details."""
        mock_explorer = MagicMock()
        mock_explorer.check_data_completeness.return_value = (True, None, 0)
        mock_explorer.get_costs_by_service.return_value = {
            "Amazon EC2": 100.0,
            "Amazon S3": 50.0,
            "AWS Lambda": 25.0,
        }

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = make_snapshot()

        report = analyzer.analyze(snapshot)

        assert "Amazon EC2" in report.baseline_costs.by_service
        assert report.baseline_costs.by_service["Amazon EC2"] == 100.0
        assert "Amazon S3" in report.baseline_costs.by_service
        assert "AWS Lambda" in report.baseline_costs.by_service


class TestCostAnalyzerBaselineServiceMapping:
    """Tests for CostAnalyzer._get_baseline_service_mapping method."""

    def test_mapping_ec2_resources(self):
        """Test mapping EC2 resources to service names."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)

        resources = [
            make_resource(resource_type="AWS::EC2::Instance"),
            make_resource(resource_type="AWS::EC2::Volume"),
        ]
        snapshot = make_snapshot(resources=resources)

        services = analyzer._get_baseline_service_mapping(snapshot)

        assert "Amazon Elastic Compute Cloud - Compute" in services

    def test_mapping_lambda_resources(self):
        """Test mapping Lambda resources to service names."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)

        resources = [
            make_resource(resource_type="AWS::Lambda::Function"),
        ]
        snapshot = make_snapshot(resources=resources)

        services = analyzer._get_baseline_service_mapping(snapshot)

        assert "AWS Lambda" in services

    def test_mapping_multiple_services(self):
        """Test mapping resources to multiple services."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)

        resources = [
            make_resource(resource_type="AWS::EC2::Instance"),
            make_resource(resource_type="AWS::Lambda::Function"),
            make_resource(resource_type="AWS::S3::Bucket"),
        ]
        snapshot = make_snapshot(resources=resources)

        services = analyzer._get_baseline_service_mapping(snapshot)

        assert "Amazon Elastic Compute Cloud - Compute" in services
        assert "AWS Lambda" in services
        assert "Amazon Simple Storage Service" in services

    def test_mapping_empty_snapshot(self):
        """Test mapping with empty snapshot."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)

        snapshot = make_snapshot(resources=[])

        services = analyzer._get_baseline_service_mapping(snapshot)

        assert len(services) == 0

    def test_mapping_unknown_resource_type(self):
        """Test that unknown resource types are not mapped."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)

        resources = [
            make_resource(resource_type="AWS::Unknown::Resource"),
        ]
        snapshot = make_snapshot(resources=resources)

        services = analyzer._get_baseline_service_mapping(snapshot)

        assert len(services) == 0

    def test_mapping_deduplicated(self):
        """Test that services are deduplicated."""
        mock_explorer = MagicMock()
        analyzer = CostAnalyzer(mock_explorer)

        resources = [
            make_resource(name="inst-1", resource_type="AWS::EC2::Instance"),
            make_resource(name="inst-2", resource_type="AWS::EC2::Instance"),
            make_resource(name="vol-1", resource_type="AWS::EC2::Volume"),
        ]
        snapshot = make_snapshot(resources=resources)

        services = analyzer._get_baseline_service_mapping(snapshot)

        # All EC2 resources map to same service
        assert len(services) == 1
        assert "Amazon Elastic Compute Cloud - Compute" in services
