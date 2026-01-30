"""Tests for Cost Explorer client."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.cost.explorer import CostExplorerClient, CostExplorerError


class TestCostExplorerClientInit:
    """Tests for CostExplorerClient initialization."""

    @patch("src.cost.explorer.boto3")
    def test_init_without_profile(self, mock_boto3):
        """Test initialization without a profile uses default client."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        client = CostExplorerClient()

        mock_boto3.client.assert_called_once_with("ce", region_name="us-east-1")
        assert client.client == mock_client

    @patch("src.cost.explorer.boto3")
    def test_init_with_profile(self, mock_boto3):
        """Test initialization with profile uses session."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_boto3.Session.return_value = mock_session

        client = CostExplorerClient(profile_name="test-profile")

        mock_boto3.Session.assert_called_once_with(profile_name="test-profile")
        mock_session.client.assert_called_once_with("ce", region_name="us-east-1")
        assert client.client == mock_client


class TestCostExplorerClientGetCostAndUsage:
    """Tests for CostExplorerClient.get_cost_and_usage method."""

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_basic(self, mock_boto3):
        """Test basic cost and usage retrieval."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [{"TimePeriod": {"Start": "2025-01-01", "End": "2025-02-01"}}]
        }

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        result = client.get_cost_and_usage(start, end)

        assert "ResultsByTime" in result
        mock_client.get_cost_and_usage.assert_called_once()

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_with_group_by(self, mock_boto3):
        """Test cost retrieval with group_by parameter."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)
        group_by = [{"Type": "DIMENSION", "Key": "SERVICE"}]

        client.get_cost_and_usage(start, end, group_by=group_by)

        call_kwargs = mock_client.get_cost_and_usage.call_args.kwargs
        assert call_kwargs["GroupBy"] == group_by

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_with_filter(self, mock_boto3):
        """Test cost retrieval with filter expression."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)
        filter_expr = {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon EC2"]}}

        client.get_cost_and_usage(start, end, filter_expression=filter_expr)

        call_kwargs = mock_client.get_cost_and_usage.call_args.kwargs
        assert call_kwargs["Filter"] == filter_expr

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_with_daily_granularity(self, mock_boto3):
        """Test cost retrieval with daily granularity."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 10)

        client.get_cost_and_usage(start, end, granularity="DAILY")

        call_kwargs = mock_client.get_cost_and_usage.call_args.kwargs
        assert call_kwargs["Granularity"] == "DAILY"

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_access_denied(self, mock_boto3):
        """Test handling of AccessDeniedException."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}, "GetCostAndUsage"
        )

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        with pytest.raises(CostExplorerError) as exc_info:
            client.get_cost_and_usage(start, end)

        assert "Access denied" in str(exc_info.value)

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_data_unavailable(self, mock_boto3):
        """Test handling of DataUnavailableException."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "DataUnavailableException", "Message": "Data not available"}}, "GetCostAndUsage"
        )

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        with pytest.raises(CostExplorerError) as exc_info:
            client.get_cost_and_usage(start, end)

        assert "not yet available" in str(exc_info.value)

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_other_client_error(self, mock_boto3):
        """Test handling of other ClientError types."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.side_effect = ClientError(
            {"Error": {"Code": "UnknownError", "Message": "Something went wrong"}}, "GetCostAndUsage"
        )

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        with pytest.raises(CostExplorerError) as exc_info:
            client.get_cost_and_usage(start, end)

        assert "Cost Explorer API error" in str(exc_info.value)

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_unexpected_error(self, mock_boto3):
        """Test handling of unexpected exceptions."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.side_effect = ValueError("Unexpected error")

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        with pytest.raises(CostExplorerError) as exc_info:
            client.get_cost_and_usage(start, end)

        assert "Failed to retrieve cost data" in str(exc_info.value)

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_default_metrics(self, mock_boto3):
        """Test that default metrics is UnblendedCost."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        client.get_cost_and_usage(start, end)

        call_kwargs = mock_client.get_cost_and_usage.call_args.kwargs
        assert call_kwargs["Metrics"] == ["UnblendedCost"]

    @patch("src.cost.explorer.boto3")
    def test_get_cost_and_usage_custom_metrics(self, mock_boto3):
        """Test cost retrieval with custom metrics."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        client.get_cost_and_usage(start, end, metrics=["BlendedCost", "UsageQuantity"])

        call_kwargs = mock_client.get_cost_and_usage.call_args.kwargs
        assert call_kwargs["Metrics"] == ["BlendedCost", "UsageQuantity"]


class TestCostExplorerClientGetCostsByService:
    """Tests for CostExplorerClient.get_costs_by_service method."""

    @patch("src.cost.explorer.boto3")
    def test_get_costs_by_service_single_period(self, mock_boto3):
        """Test getting costs by service for a single period."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "TimePeriod": {"Start": "2025-01-01", "End": "2025-02-01"},
                    "Groups": [
                        {"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": "100.50"}}},
                        {"Keys": ["Amazon S3"], "Metrics": {"UnblendedCost": {"Amount": "25.75"}}},
                    ],
                }
            ]
        }

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        result = client.get_costs_by_service(start, end)

        assert result["Amazon EC2"] == 100.50
        assert result["Amazon S3"] == 25.75

    @patch("src.cost.explorer.boto3")
    def test_get_costs_by_service_multiple_periods(self, mock_boto3):
        """Test getting costs by service aggregated across multiple periods."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": "50.00"}}},
                    ]
                },
                {
                    "Groups": [
                        {"Keys": ["Amazon EC2"], "Metrics": {"UnblendedCost": {"Amount": "75.00"}}},
                    ]
                },
            ]
        }

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 3, 1)

        result = client.get_costs_by_service(start, end)

        # Should aggregate costs across periods
        assert result["Amazon EC2"] == 125.00

    @patch("src.cost.explorer.boto3")
    def test_get_costs_by_service_empty(self, mock_boto3):
        """Test getting costs by service when no data."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        result = client.get_costs_by_service(start, end)

        assert result == {}


class TestCostExplorerClientGetTotalCost:
    """Tests for CostExplorerClient.get_total_cost method."""

    @patch("src.cost.explorer.boto3")
    def test_get_total_cost_single_period(self, mock_boto3):
        """Test getting total cost for single period."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [{"Total": {"UnblendedCost": {"Amount": "250.00"}}}]
        }

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        result = client.get_total_cost(start, end)

        assert result == 250.00

    @patch("src.cost.explorer.boto3")
    def test_get_total_cost_multiple_periods(self, mock_boto3):
        """Test getting total cost aggregated across periods."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {"Total": {"UnblendedCost": {"Amount": "100.00"}}},
                {"Total": {"UnblendedCost": {"Amount": "150.00"}}},
            ]
        }

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 3, 1)

        result = client.get_total_cost(start, end)

        assert result == 250.00

    @patch("src.cost.explorer.boto3")
    def test_get_total_cost_no_data(self, mock_boto3):
        """Test getting total cost when no data available."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.get_cost_and_usage.return_value = {"ResultsByTime": []}

        client = CostExplorerClient()
        start = datetime(2025, 1, 1)
        end = datetime(2025, 2, 1)

        result = client.get_total_cost(start, end)

        assert result == 0.0


class TestCostExplorerClientCheckDataCompleteness:
    """Tests for CostExplorerClient.check_data_completeness method."""

    @patch("src.cost.explorer.boto3")
    def test_check_data_completeness_complete(self, mock_boto3):
        """Test data completeness when data is complete (>= 2 days old)."""
        mock_boto3.client.return_value = MagicMock()

        client = CostExplorerClient()
        # Use a date that is definitely more than 2 days ago
        end_date = datetime.now() - timedelta(days=5)

        is_complete, data_through, lag_days = client.check_data_completeness(end_date)

        assert is_complete is True
        assert lag_days >= 2

    @patch("src.cost.explorer.boto3")
    def test_check_data_completeness_incomplete(self, mock_boto3):
        """Test data completeness when data is incomplete (< 2 days old)."""
        mock_boto3.client.return_value = MagicMock()

        client = CostExplorerClient()
        # Use today's date
        end_date = datetime.now()

        is_complete, data_through, lag_days = client.check_data_completeness(end_date)

        assert is_complete is False
        assert lag_days <= 1

    @patch("src.cost.explorer.boto3")
    def test_check_data_completeness_returns_tuple(self, mock_boto3):
        """Test that check_data_completeness returns correct tuple format."""
        mock_boto3.client.return_value = MagicMock()

        client = CostExplorerClient()
        end_date = datetime.now() - timedelta(days=3)

        result = client.check_data_completeness(end_date)

        assert isinstance(result, tuple)
        assert len(result) == 3
        is_complete, data_through, lag_days = result
        assert isinstance(is_complete, bool)
        assert isinstance(lag_days, int)

    @patch("src.cost.explorer.boto3")
    def test_check_data_completeness_boundary(self, mock_boto3):
        """Test data completeness at exactly 2 day boundary."""
        mock_boto3.client.return_value = MagicMock()

        client = CostExplorerClient()
        # Exactly 2 days ago
        end_date = datetime.now() - timedelta(days=2)

        is_complete, data_through, lag_days = client.check_data_completeness(end_date)

        assert is_complete is True
        assert lag_days >= 2


class TestCostExplorerError:
    """Tests for CostExplorerError exception."""

    def test_cost_explorer_error_message(self):
        """Test CostExplorerError can be raised with message."""
        error = CostExplorerError("Test error message")
        assert str(error) == "Test error message"

    def test_cost_explorer_error_is_exception(self):
        """Test CostExplorerError is an Exception subclass."""
        assert issubclass(CostExplorerError, Exception)

    def test_cost_explorer_error_can_be_caught(self):
        """Test CostExplorerError can be caught."""
        with pytest.raises(CostExplorerError):
            raise CostExplorerError("Test")
