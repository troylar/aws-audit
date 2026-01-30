"""Cost Explorer integration for retrieving cost data."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CostExplorerClient:
    """Wrapper for AWS Cost Explorer API."""

    def __init__(self, profile_name: Optional[str] = None):
        """Initialize Cost Explorer client.

        Args:
            profile_name: AWS profile name (optional)
        """
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            self.client = session.client("ce", region_name="us-east-1")  # Cost Explorer is global
        else:
            self.client = boto3.client("ce", region_name="us-east-1")

    def get_cost_and_usage(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY",
        metrics: Optional[List[str]] = None,
        group_by: Optional[List[Dict[str, str]]] = None,
        filter_expression: Optional[Dict] = None,
    ) -> Dict:
        """Get cost and usage data from Cost Explorer.

        Args:
            start_date: Start date for cost data (inclusive)
            end_date: End date for cost data (exclusive)
            granularity: Time granularity - DAILY or MONTHLY
            metrics: Cost metrics to retrieve (default: UnblendedCost)
            group_by: Dimensions to group by (e.g., SERVICE, REGION)
            filter_expression: Filter to apply to cost data

        Returns:
            Cost and usage data from Cost Explorer API

        Raises:
            CostExplorerError: If Cost Explorer is not enabled or API call fails
        """
        if metrics is None:
            metrics = ["UnblendedCost"]

        try:
            params = {
                "TimePeriod": {
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                "Granularity": granularity,
                "Metrics": metrics,
            }

            if group_by:
                params["GroupBy"] = group_by  # type: ignore[assignment]

            if filter_expression:
                params["Filter"] = filter_expression

            logger.info(
                f"Retrieving cost data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )

            response = self.client.get_cost_and_usage(**params)

            logger.info(f"Retrieved {len(response.get('ResultsByTime', []))} time periods")

            return response  # type: ignore[return-value]

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")

            if error_code == "AccessDeniedException":
                raise CostExplorerError(
                    "Access denied to Cost Explorer. Ensure your IAM user/role has the 'ce:GetCostAndUsage' permission."
                )
            elif error_code == "DataUnavailableException":
                raise CostExplorerError(
                    "Cost data is not yet available for the specified time period. "
                    "Cost Explorer data typically has a 24-48 hour delay."
                )
            else:
                raise CostExplorerError(f"Cost Explorer API error: {e}")

        except Exception as e:
            logger.error(f"Unexpected error retrieving cost data: {e}")
            raise CostExplorerError(f"Failed to retrieve cost data: {e}")

    def get_costs_by_service(
        self,
        start_date: datetime,
        end_date: datetime,
        granularity: str = "MONTHLY",
    ) -> Dict[str, float]:
        """Get total costs grouped by AWS service.

        Args:
            start_date: Start date for cost data
            end_date: End date for cost data
            granularity: Time granularity

        Returns:
            Dictionary mapping service name to total cost
        """
        response = self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        service_costs: Dict[str, float] = {}

        for time_period in response.get("ResultsByTime", []):
            for group in time_period.get("Groups", []):
                service_name = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])

                if service_name in service_costs:
                    service_costs[service_name] += cost
                else:
                    service_costs[service_name] = cost

        return service_costs

    def get_total_cost(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        """Get total cost for the specified period.

        Args:
            start_date: Start date for cost data
            end_date: End date for cost data

        Returns:
            Total cost amount
        """
        response = self.get_cost_and_usage(
            start_date=start_date,
            end_date=end_date,
            granularity="MONTHLY",
        )

        total_cost = 0.0

        for time_period in response.get("ResultsByTime", []):
            cost = float(time_period["Total"]["UnblendedCost"]["Amount"])
            total_cost += cost

        return total_cost

    def check_data_completeness(
        self,
        end_date: datetime,
    ) -> Tuple[bool, Optional[datetime], int]:
        """Check if cost data is complete up to the specified date.

        Cost Explorer typically has a 24-48 hour delay in data availability.

        Args:
            end_date: The date to check data completeness for

        Returns:
            Tuple of (is_complete, data_available_through, lag_days)
        """
        # Cost Explorer data typically lags 1-2 days
        today = datetime.now().date()
        end_date_only = end_date.date()

        # Calculate lag
        lag_days = (today - end_date_only).days

        # Data is considered incomplete if less than 2 days old
        is_complete = lag_days >= 2

        # Estimate data available through date
        if lag_days < 2:
            data_available_through = datetime.combine(today - timedelta(days=2), datetime.min.time())
        else:
            data_available_through = end_date

        logger.info(
            f"Cost data completeness: {'Complete' if is_complete else 'Incomplete'}, "
            f"available through {data_available_through.strftime('%Y-%m-%d')}, "
            f"lag: {lag_days} days"
        )

        return is_complete, data_available_through, lag_days


class CostExplorerError(Exception):
    """Exception raised for Cost Explorer errors."""

    pass
