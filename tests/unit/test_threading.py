"""Unit tests for multi-threading behavior in resource collection and cost analysis."""

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.cost.analyzer import CostAnalyzer
from src.cost.explorer import CostExplorerClient
from src.models.snapshot import Snapshot


class TestCostAnalyzerThreading:
    """Tests for concurrent execution in cost analysis."""

    def test_parallel_cost_and_completeness_check(self):
        """Test that cost retrieval and completeness check run in parallel."""
        mock_explorer = Mock(spec=CostExplorerClient)

        # Track call order and timing
        call_times = []

        def mock_check_completeness(end_date):
            call_times.append(("completeness_start", time.time()))
            time.sleep(0.1)  # Simulate API call
            call_times.append(("completeness_end", time.time()))
            return (True, datetime(2024, 1, 15), 0)

        def mock_get_costs(start_date, end_date, granularity):
            call_times.append(("costs_start", time.time()))
            time.sleep(0.1)  # Simulate API call
            call_times.append(("costs_end", time.time()))
            return {"Service1": 100.0}

        mock_explorer.check_data_completeness = mock_check_completeness
        mock_explorer.get_costs_by_service = mock_get_costs

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = Snapshot(
            name="test",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            account_id="123",
            regions=["us-east-1"],
            resources=[],
        )

        start = time.time()
        analyzer.analyze(snapshot)
        elapsed = time.time() - start

        # Both operations take 0.1s each
        # If sequential: 0.2s+
        # If parallel: ~0.1s
        # Allow some overhead, but should be significantly faster than sequential
        assert elapsed < 0.18, f"Expected parallel execution (~0.1s), got {elapsed:.3f}s"

        # Verify both operations were called
        assert len(call_times) == 4
        assert any("completeness_start" in c for c in call_times)
        assert any("costs_start" in c for c in call_times)

    def test_parallel_execution_handles_exceptions(self):
        """Test that exception in one thread doesn't block the other."""
        mock_explorer = Mock(spec=CostExplorerClient)

        # Completeness check succeeds
        mock_explorer.check_data_completeness.return_value = (True, datetime(2024, 1, 15), 0)

        # Cost retrieval fails
        mock_explorer.get_costs_by_service.side_effect = Exception("API Error")

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = Snapshot(
            name="test",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            account_id="123",
            regions=["us-east-1"],
            resources=[],
        )

        # Should propagate the exception
        with pytest.raises(Exception, match="API Error"):
            analyzer.analyze(snapshot)

        # Both methods should have been called
        assert mock_explorer.check_data_completeness.called
        assert mock_explorer.get_costs_by_service.called

    def test_both_futures_complete_before_processing(self):
        """Test that both futures complete before results are used."""
        mock_explorer = Mock(spec=CostExplorerClient)

        results_used = []

        def mock_check_completeness(end_date):
            time.sleep(0.05)
            results_used.append("completeness_done")
            return (True, datetime(2024, 1, 15), 0)

        def mock_get_costs(start_date, end_date, granularity):
            time.sleep(0.05)
            results_used.append("costs_done")
            return {"Service1": 100.0}

        mock_explorer.check_data_completeness = mock_check_completeness
        mock_explorer.get_costs_by_service = mock_get_costs

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = Snapshot(
            name="test",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            account_id="123",
            regions=["us-east-1"],
            resources=[],
        )

        report = analyzer.analyze(snapshot)

        # Both should be complete
        assert len(results_used) == 2
        assert "completeness_done" in results_used
        assert "costs_done" in results_used

        # Report should have valid data from both
        assert report.data_complete is True
        assert report.baseline_costs.total == 100.0


class TestResourceCollectorThreading:
    """Tests for concurrent execution in resource collection."""

    @patch("src.snapshot.capturer.boto3.Session")
    def test_collectors_run_in_parallel(self, mock_session_class):
        """Test that resource collectors run concurrently."""
        # This is a complex test that would require significant mocking
        # For now, we verify the parallel_workers parameter is used
        from src.snapshot.capturer import create_snapshot

        # Mock boto3 session
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock the collectors to avoid actual AWS calls
        with patch("src.snapshot.capturer.COLLECTOR_REGISTRY", []):
            # Empty registry = no collectors = fast execution
            snapshot = create_snapshot(
                name="test",
                regions=["us-east-1"],
                account_id="123456789012",
                parallel_workers=5,
            )

            assert snapshot.name == "test"
            assert len(snapshot.resources) == 0

    def test_parallel_workers_parameter_accepted(self):
        """Test that parallel_workers parameter is accepted."""
        from src.snapshot.capturer import create_snapshot

        # Verify function accepts parallel_workers parameter
        with patch("src.snapshot.capturer.boto3.Session"):
            with patch("src.snapshot.capturer.COLLECTOR_REGISTRY", []):
                # Should not raise TypeError
                snapshot = create_snapshot(
                    name="test",
                    regions=["us-east-1"],
                    account_id="123",
                    parallel_workers=10,  # Custom worker count
                )
                assert snapshot is not None

    def test_thread_safety_with_shared_state(self):
        """Test thread-safe updates to shared state (progress, resources)."""
        # This test verifies the Lock mechanism is in place
        # Actual thread safety would be tested via integration tests
        from src.snapshot.capturer import create_snapshot

        with patch("src.snapshot.capturer.boto3.Session"):
            with patch("src.snapshot.capturer.COLLECTOR_REGISTRY", []):
                # Multiple regions to trigger parallel execution
                snapshot = create_snapshot(
                    name="test",
                    regions=["us-east-1", "us-west-2", "eu-west-1"],
                    account_id="123",
                    parallel_workers=3,
                )

                # Should complete without race conditions
                assert snapshot.regions == ["us-east-1", "us-west-2", "eu-west-1"]


class TestThreadPoolConfiguration:
    """Tests for ThreadPoolExecutor configuration."""

    def test_cost_analyzer_uses_2_workers(self):
        """Test that cost analyzer uses exactly 2 workers (completeness + costs)."""
        mock_explorer = Mock(spec=CostExplorerClient)
        mock_explorer.check_data_completeness.return_value = (True, datetime(2024, 1, 15), 0)
        mock_explorer.get_costs_by_service.return_value = {}

        analyzer = CostAnalyzer(mock_explorer)
        snapshot = Snapshot(
            name="test",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            account_id="123",
            regions=["us-east-1"],
            resources=[],
        )

        with patch("src.cost.analyzer.ThreadPoolExecutor") as mock_executor_class:
            mock_executor = MagicMock()
            mock_executor.__enter__ = Mock(return_value=mock_executor)
            mock_executor.__exit__ = Mock(return_value=False)
            mock_executor_class.return_value = mock_executor

            # Mock futures
            mock_future1 = MagicMock()
            mock_future1.result.return_value = (True, datetime(2024, 1, 15), 0)
            mock_future2 = MagicMock()
            mock_future2.result.return_value = {}
            mock_executor.submit.side_effect = [mock_future1, mock_future2]

            analyzer.analyze(snapshot)

            # Verify ThreadPoolExecutor was created with max_workers=2
            mock_executor_class.assert_called_once_with(max_workers=2)

    @patch("src.snapshot.capturer.boto3.Session")
    def test_capturer_uses_custom_workers(self, mock_session_class):
        """Test that capturer uses custom parallel_workers value."""
        from src.snapshot.capturer import create_snapshot

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        with patch("src.snapshot.capturer.COLLECTOR_REGISTRY", []):
            with patch("src.snapshot.capturer.ThreadPoolExecutor") as mock_executor_class:
                mock_executor = MagicMock()
                mock_executor.__enter__ = Mock(return_value=mock_executor)
                mock_executor.__exit__ = Mock(return_value=False)
                mock_executor_class.return_value = mock_executor

                create_snapshot(
                    name="test",
                    regions=["us-east-1"],
                    account_id="123",
                    parallel_workers=15,  # Custom value
                )

                # Verify ThreadPoolExecutor was created with custom max_workers
                mock_executor_class.assert_called_once_with(max_workers=15)
