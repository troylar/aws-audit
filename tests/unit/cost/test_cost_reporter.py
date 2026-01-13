"""Tests for cost reporter."""

from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from src.cost.reporter import CostReporter
from src.models.cost_report import CostBreakdown, CostReport


def make_cost_report(
    baseline_total=100.0,
    non_baseline_total=0.0,
    baseline_services=None,
    non_baseline_services=None,
    data_complete=True,
    data_through=None,
    lag_days=0,
):
    """Helper to create CostReport with proper field ordering."""
    if baseline_services is None:
        baseline_services = {}
    if non_baseline_services is None:
        non_baseline_services = {}

    total = baseline_total + non_baseline_total
    baseline_pct = (baseline_total / total * 100) if total > 0 else 0
    non_baseline_pct = (non_baseline_total / total * 100) if total > 0 else 0

    return CostReport(
        generated_at=datetime(2025, 1, 31, 12, 0, 0, tzinfo=timezone.utc),
        baseline_snapshot_name="test-snapshot",
        period_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2025, 1, 31, tzinfo=timezone.utc),
        baseline_costs=CostBreakdown(
            total=baseline_total,
            by_service=baseline_services,
            percentage=baseline_pct,
        ),
        non_baseline_costs=CostBreakdown(
            total=non_baseline_total,
            by_service=non_baseline_services,
            percentage=non_baseline_pct,
        ),
        total_cost=total,
        data_complete=data_complete,
        data_through=data_through,
        lag_days=lag_days,
    )


class TestCostReporterInit:
    """Tests for CostReporter initialization."""

    def test_default_console(self):
        """Test reporter creates default console."""
        reporter = CostReporter()
        assert reporter.console is not None
        assert isinstance(reporter.console, Console)

    def test_custom_console(self):
        """Test reporter uses provided console."""
        console = Console()
        reporter = CostReporter(console=console)
        assert reporter.console is console


class TestCostReporterDisplay:
    """Tests for CostReporter.display method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return CostReporter(console=console)

    def test_display_basic_report(self, reporter, console):
        """Test displaying a basic cost report."""
        report = make_cost_report(
            baseline_total=100.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
        )
        reporter.display(report, has_deltas=False)
        output = console.file.getvalue()
        assert "Cost Analysis Report" in output
        assert "test-snapshot" in output
        assert "No resource changes detected" in output

    def test_display_report_with_deltas(self, reporter, console):
        """Test displaying a report with changes."""
        report = make_cost_report(
            baseline_total=100.0,
            non_baseline_total=50.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
            non_baseline_services={"AWS Lambda": 30.0, "Amazon DynamoDB": 20.0},
        )
        reporter.display(report, has_deltas=True)
        output = console.file.getvalue()
        assert "Cost Summary" in output
        assert "Baseline" in output
        assert "Non-Baseline" in output

    def test_display_with_services(self, reporter, console):
        """Test displaying service breakdown."""
        report = make_cost_report(
            baseline_total=100.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
        )
        reporter.display(report, show_services=True, has_deltas=False)
        output = console.file.getvalue()
        assert "Costs by Service" in output

    def test_display_without_services(self, reporter, console):
        """Test display without service breakdown."""
        report = make_cost_report(baseline_total=100.0)
        reporter.display(report, show_services=False, has_deltas=False)
        output = console.file.getvalue()
        # Should not show service details when no services
        assert "Top Baseline Services" not in output

    def test_display_data_lag_warning(self, reporter, console):
        """Test that data lag warning is shown."""
        report = make_cost_report(
            baseline_total=100.0,
            data_complete=False,
            data_through=datetime(2025, 1, 29, tzinfo=timezone.utc),
            lag_days=2,
        )
        reporter.display(report, has_deltas=False)
        output = console.file.getvalue()
        assert "lag" in output.lower() or "Note" in output


class TestCostReporterDisplaySnapshotCosts:
    """Tests for CostReporter._display_snapshot_costs method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return CostReporter(console=console)

    def test_display_snapshot_costs(self, reporter, console):
        """Test displaying snapshot costs."""
        report = make_cost_report(baseline_total=150.75)
        reporter._display_snapshot_costs(report)
        output = console.file.getvalue()
        assert "150.75" in output
        assert "Snapshot Costs" in output


class TestCostReporterDisplaySummary:
    """Tests for CostReporter._display_summary method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return CostReporter(console=console)

    def test_display_summary(self, reporter, console):
        """Test displaying cost summary."""
        report = make_cost_report(
            baseline_total=100.0,
            non_baseline_total=50.0,
        )
        reporter._display_summary(report)
        output = console.file.getvalue()
        assert "Cost Summary" in output
        assert "Baseline" in output
        assert "Non-Baseline" in output
        assert "Total" in output


class TestCostReporterDisplayServiceBreakdown:
    """Tests for CostReporter._display_service_breakdown method."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return CostReporter(console=console)

    def test_display_service_breakdown_without_deltas(self, reporter, console):
        """Test service breakdown without deltas."""
        report = make_cost_report(
            baseline_total=100.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
        )
        reporter._display_service_breakdown(report, has_deltas=False)
        output = console.file.getvalue()
        assert "Costs by Service" in output

    def test_display_service_breakdown_with_deltas(self, reporter, console):
        """Test service breakdown with deltas shows both sections."""
        report = make_cost_report(
            baseline_total=100.0,
            non_baseline_total=50.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
            non_baseline_services={"AWS Lambda": 50.0},
        )
        reporter._display_service_breakdown(report, has_deltas=True)
        output = console.file.getvalue()
        assert "Top Baseline Services" in output
        assert "Top Non-Baseline Services" in output

    def test_display_service_breakdown_empty_baseline(self, reporter, console):
        """Test service breakdown with empty baseline services."""
        report = make_cost_report(baseline_total=0.0)
        reporter._display_service_breakdown(report, has_deltas=False)
        output = console.file.getvalue()
        # Should not crash with empty services
        assert output is not None


class TestCostReporterProgressBar:
    """Tests for CostReporter._create_progress_bar method."""

    @pytest.fixture
    def reporter(self):
        """Create a reporter."""
        return CostReporter()

    def test_progress_bar_zero(self, reporter):
        """Test progress bar at 0%."""
        result = reporter._create_progress_bar(0)
        assert "░" in result

    def test_progress_bar_full(self, reporter):
        """Test progress bar at 100%."""
        result = reporter._create_progress_bar(100)
        assert "█" in result
        assert "░" not in result

    def test_progress_bar_half(self, reporter):
        """Test progress bar at 50%."""
        result = reporter._create_progress_bar(50)
        assert "█" in result
        assert "░" in result

    def test_progress_bar_color(self, reporter):
        """Test progress bar with custom color."""
        result = reporter._create_progress_bar(50, color="blue")
        assert "[blue]" in result


class TestCostReporterShortenServiceName:
    """Tests for CostReporter._shorten_service_name method."""

    @pytest.fixture
    def reporter(self):
        """Create a reporter."""
        return CostReporter()

    def test_shorten_ec2(self, reporter):
        """Test shortening EC2 service name."""
        result = reporter._shorten_service_name("Amazon Elastic Compute Cloud - Compute")
        assert result == "EC2"

    def test_shorten_s3(self, reporter):
        """Test shortening S3 service name."""
        result = reporter._shorten_service_name("Amazon Simple Storage Service")
        assert result == "S3"

    def test_shorten_lambda(self, reporter):
        """Test shortening Lambda service name."""
        result = reporter._shorten_service_name("AWS Lambda")
        assert result == "Lambda"

    def test_shorten_rds(self, reporter):
        """Test shortening RDS service name."""
        result = reporter._shorten_service_name("Amazon Relational Database Service")
        assert result == "RDS"

    def test_unknown_service(self, reporter):
        """Test unknown service name is returned as-is."""
        result = reporter._shorten_service_name("Some Unknown Service")
        assert result == "Some Unknown Service"


class TestCostReporterExport:
    """Tests for CostReporter export methods."""

    @pytest.fixture
    def console(self):
        """Create a console that captures output."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def reporter(self, console):
        """Create a reporter with captured console."""
        return CostReporter(console=console)

    @patch("src.utils.export.export_to_json")
    def test_export_json(self, mock_export, reporter, console):
        """Test JSON export."""
        report = make_cost_report(
            baseline_total=100.0,
            non_baseline_total=50.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
            non_baseline_services={"AWS Lambda": 50.0},
        )
        reporter.export_json(report, "/tmp/test.json")
        mock_export.assert_called_once()
        output = console.file.getvalue()
        assert "exported" in output

    @patch("src.utils.export.export_to_csv")
    def test_export_csv(self, mock_export, reporter, console):
        """Test CSV export."""
        report = make_cost_report(
            baseline_total=100.0,
            non_baseline_total=50.0,
            baseline_services={"Amazon EC2": 60.0, "Amazon S3": 40.0},
            non_baseline_services={"AWS Lambda": 50.0},
        )
        reporter.export_csv(report, "/tmp/test.csv")
        mock_export.assert_called_once()
        output = console.file.getvalue()
        assert "exported" in output
        # Check that the rows contain expected data
        call_args = mock_export.call_args[0][0]
        assert len(call_args) == 3  # 2 baseline + 1 non-baseline
        assert call_args[0]["category"] == "baseline"

    @patch("src.utils.export.export_to_csv")
    def test_export_csv_empty(self, mock_export, reporter, console):
        """Test CSV export with no data."""
        report = make_cost_report(baseline_total=0.0)
        reporter.export_csv(report, "/tmp/test.csv")
        # Should not call export_to_csv with empty data
        mock_export.assert_not_called()
        output = console.file.getvalue()
        assert "No cost data" in output
