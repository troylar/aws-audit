"""Unit tests for cost analyzer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from src.cost.analyzer import CostAnalyzer
from src.cost.explorer import CostExplorerClient
from src.models.snapshot import Snapshot


@pytest.fixture
def mock_cost_explorer():
    """Create mock Cost Explorer client."""
    mock = Mock(spec=CostExplorerClient)

    # Mock check_data_completeness to return complete data
    mock.check_data_completeness.return_value = (True, datetime(2024, 1, 15), 0)

    # Mock get_costs_by_service to return sample costs
    mock.get_costs_by_service.return_value = {
        "Amazon Elastic Compute Cloud - Compute": 100.50,
        "Amazon Simple Storage Service": 25.75,
        "AWS Lambda": 10.25,
    }

    return mock


@pytest.fixture
def sample_snapshot():
    """Create sample snapshot."""
    return Snapshot(
        name="test-snapshot",
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=[],
    )


class TestCostAnalyzer:
    """Tests for CostAnalyzer class."""

    def test_init(self, mock_cost_explorer):
        """Test analyzer initialization."""
        analyzer = CostAnalyzer(mock_cost_explorer)
        assert analyzer.cost_explorer is mock_cost_explorer

    def test_analyze_default_dates(self, mock_cost_explorer, sample_snapshot):
        """Test analyze with default date range."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        report = analyzer.analyze(sample_snapshot)

        # Should use snapshot date as start
        assert report.period_start.date() == sample_snapshot.created_at.date()

        # Should call cost explorer
        mock_cost_explorer.get_costs_by_service.assert_called_once()
        mock_cost_explorer.check_data_completeness.assert_called_once()

    def test_analyze_custom_dates(self, mock_cost_explorer, sample_snapshot):
        """Test analyze with custom date range."""

        analyzer = CostAnalyzer(mock_cost_explorer)

        start = datetime(2024, 1, 5, tzinfo=timezone.utc)
        end = datetime(2024, 1, 10, tzinfo=timezone.utc)

        report = analyzer.analyze(snapshot=sample_snapshot, start_date=start, end_date=end)

        # Start and end should match the provided dates
        assert report.period_start == start.replace(tzinfo=None)
        assert report.period_end == end.replace(tzinfo=None)

    def test_analyze_no_deltas(self, mock_cost_explorer, sample_snapshot):
        """Test analyze when has_deltas=False (all costs are from snapshot)."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        report = analyzer.analyze(sample_snapshot, has_deltas=False)

        # All costs should be baseline
        assert report.baseline_costs.total == 136.50  # Sum of all service costs
        assert report.non_baseline_costs.total == 0.0
        assert report.baseline_costs.percentage == 100.0
        assert report.non_baseline_costs.percentage == 0.0

    def test_analyze_with_deltas(self, mock_cost_explorer, sample_snapshot):
        """Test analyze when has_deltas=True."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        report = analyzer.analyze(sample_snapshot, has_deltas=True)

        # Currently implementation shows total only when has_deltas=True
        assert report.total_cost == 136.50
        assert report.baseline_costs.total > 0

    def test_analyze_granularity_daily(self, mock_cost_explorer, sample_snapshot):
        """Test analyze with daily granularity."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        analyzer.analyze(sample_snapshot, granularity="DAILY")

        # Verify granularity was passed to cost explorer (as positional arg)
        call_args = mock_cost_explorer.get_costs_by_service.call_args
        assert call_args[0][2] == "DAILY"  # Third positional argument

    def test_analyze_granularity_monthly(self, mock_cost_explorer, sample_snapshot):
        """Test analyze with monthly granularity (default)."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        analyzer.analyze(sample_snapshot)

        # Verify default monthly granularity (as positional arg)
        call_args = mock_cost_explorer.get_costs_by_service.call_args
        assert call_args[0][2] == "MONTHLY"  # Third positional argument

    def test_analyze_data_completeness_incomplete(self, mock_cost_explorer, sample_snapshot):
        """Test analyze when cost data is incomplete."""
        # Mock incomplete data
        mock_cost_explorer.check_data_completeness.return_value = (False, datetime(2024, 1, 12), 3)

        analyzer = CostAnalyzer(mock_cost_explorer)
        report = analyzer.analyze(sample_snapshot)

        assert report.data_complete is False
        assert report.data_through == datetime(2024, 1, 12)
        assert report.lag_days == 3

    def test_analyze_data_completeness_complete(self, mock_cost_explorer, sample_snapshot):
        """Test analyze when cost data is complete."""
        mock_cost_explorer.check_data_completeness.return_value = (True, datetime(2024, 1, 15), 0)

        analyzer = CostAnalyzer(mock_cost_explorer)
        report = analyzer.analyze(sample_snapshot)

        assert report.data_complete is True
        assert report.lag_days == 0

    def test_analyze_service_costs_breakdown(self, mock_cost_explorer, sample_snapshot):
        """Test that service costs are properly broken down."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        report = analyzer.analyze(sample_snapshot)

        # Check service breakdown
        assert "Amazon Elastic Compute Cloud - Compute" in report.baseline_costs.by_service
        assert "Amazon Simple Storage Service" in report.baseline_costs.by_service
        assert "AWS Lambda" in report.baseline_costs.by_service

        assert report.baseline_costs.by_service["Amazon Elastic Compute Cloud - Compute"] == 100.50
        assert report.baseline_costs.by_service["Amazon Simple Storage Service"] == 25.75
        assert report.baseline_costs.by_service["AWS Lambda"] == 10.25

    def test_analyze_report_metadata(self, mock_cost_explorer, sample_snapshot):
        """Test that report contains correct metadata."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        report = analyzer.analyze(sample_snapshot)

        assert report.baseline_snapshot_name == "test-snapshot"
        assert isinstance(report.generated_at, datetime)

    def test_analyze_timezone_handling(self, mock_cost_explorer, sample_snapshot):
        """Test that timezones are properly handled."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        # Use timezone-aware dates
        start = datetime(2024, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 10, 12, 0, 0, tzinfo=timezone.utc)

        report = analyzer.analyze(sample_snapshot, start_date=start, end_date=end)

        # Report dates should be timezone-naive
        assert report.period_start.tzinfo is None
        assert report.period_end.tzinfo is None

    def test_analyze_date_range_same_day(self, mock_cost_explorer, sample_snapshot):
        """Test analyze when start and end dates are the same."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        same_date = datetime(2024, 1, 5)

        report = analyzer.analyze(sample_snapshot, start_date=same_date, end_date=same_date)

        # Should adjust end_date to be start_date + 1 day (minimum range requirement)
        assert report.period_end == same_date + timedelta(days=1)

    def test_analyze_date_range_inverted(self, mock_cost_explorer, sample_snapshot):
        """Test analyze when end_date is before start_date."""
        analyzer = CostAnalyzer(mock_cost_explorer)

        start = datetime(2024, 1, 10)
        end = datetime(2024, 1, 5)

        report = analyzer.analyze(sample_snapshot, start_date=start, end_date=end)

        # Should adjust end_date to be start_date + 1 day (minimum range requirement)
        assert report.period_end == start + timedelta(days=1)

    def test_get_baseline_service_mapping(self, mock_cost_explorer):
        """Test _get_baseline_service_mapping helper method."""
        from src.models.resource import Resource

        # Create snapshot with various resource types
        resources = [
            Resource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-1",
                resource_type="AWS::EC2::Instance",
                name="test-instance",
                region="us-east-1",
                config_hash="a" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:lambda:us-east-1:123:function:test",
                resource_type="AWS::Lambda::Function",
                name="test-func",
                region="us-east-1",
                config_hash="b" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:s3:::test-bucket",
                resource_type="AWS::S3::Bucket",
                name="test-bucket",
                region="us-east-1",
                config_hash="c" * 64,
                raw_config={},
            ),
        ]

        snapshot = Snapshot(
            name="test",
            created_at=datetime.now(timezone.utc),
            account_id="123",
            regions=["us-east-1"],
            resources=resources,
        )

        analyzer = CostAnalyzer(mock_cost_explorer)
        service_names = analyzer._get_baseline_service_mapping(snapshot)

        # Should map to Cost Explorer service names
        assert "Amazon Elastic Compute Cloud - Compute" in service_names
        assert "AWS Lambda" in service_names
        assert "Amazon Simple Storage Service" in service_names
