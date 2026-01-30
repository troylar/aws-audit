"""Cost analyzer for inventory snapshots."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set

from ..models.cost_report import CostBreakdown, CostReport
from ..models.snapshot import Snapshot
from .explorer import CostExplorerClient

logger = logging.getLogger(__name__)


class CostAnalyzer:
    """Analyze costs for inventory snapshots."""

    def __init__(self, cost_explorer: CostExplorerClient):
        """Initialize cost analyzer.

        Args:
            cost_explorer: Cost Explorer client instance
        """
        self.cost_explorer = cost_explorer

    def analyze(
        self,
        snapshot: Snapshot,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: str = "MONTHLY",
        has_deltas: bool = False,
        delta_report: Optional[Any] = None,
    ) -> CostReport:
        """Analyze costs and separate snapshot resources.

        This implementation uses a simplified heuristic approach:
        1. Get total costs by service
        2. Estimate baseline portion based on resource counts in snapshot
        3. Remaining costs are attributed to non-baseline resources

        Note: For precise cost attribution, AWS would need to provide
        per-resource cost data, which Cost Explorer doesn't directly expose.
        This gives a good approximation based on service-level costs.

        Args:
            snapshot: The baseline snapshot
            start_date: Start date for cost analysis (default: snapshot date)
            end_date: End date for cost analysis (default: today)
            granularity: Cost granularity - DAILY or MONTHLY

        Returns:
            CostReport with baseline and non-baseline cost breakdown
        """
        # Default date range: from snapshot creation to today
        if not start_date:
            start_date = snapshot.created_at
            # Remove timezone for Cost Explorer API (uses dates only, no time)
            start_date = start_date.replace(tzinfo=None)

        if not end_date:
            end_date = datetime.now()

        # Ensure both dates are timezone-naive for comparison
        if hasattr(start_date, "tzinfo") and start_date.tzinfo is not None:
            start_date = start_date.replace(tzinfo=None)
        if hasattr(end_date, "tzinfo") and end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)

        # Ensure start_date is before end_date
        # AWS Cost Explorer requires at least 1 day difference
        if start_date >= end_date:
            # If dates are the same or inverted, set end_date to start_date + 1 day
            end_date = start_date + timedelta(days=1)

        logger.debug(f"Analyzing costs from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        # Execute data completeness check and cost retrieval in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit both tasks
            completeness_future = executor.submit(self.cost_explorer.check_data_completeness, end_date)
            costs_future = executor.submit(self.cost_explorer.get_costs_by_service, start_date, end_date, granularity)

            # Wait for both to complete
            is_complete, data_through, lag_days = completeness_future.result()
            service_costs = costs_future.result()

        # If no deltas (no resource changes), ALL costs are baseline
        if not has_deltas:
            logger.debug("No resource changes detected - all costs are from snapshot resources")
            baseline_costs = service_costs.copy()
            non_baseline_costs: Dict[str, float] = {}
            baseline_total = sum(baseline_costs.values())
            non_baseline_total = 0.0
            total_cost = baseline_total
            baseline_pct = 100.0
            non_baseline_pct = 0.0
        else:
            # There are deltas - we can't accurately split costs without per-resource pricing
            # Show total only with a note that we can't split accurately
            logger.debug("Resource changes detected - showing total costs only")
            baseline_costs = service_costs.copy()
            non_baseline_costs = {}
            baseline_total = sum(baseline_costs.values())
            non_baseline_total = 0.0
            total_cost = baseline_total
            baseline_pct = 100.0
            non_baseline_pct = 0.0
            # Note: We could enhance this in the future to track specific resource costs
            # For now, we show total and list the delta resources separately

        # Create cost breakdowns
        baseline_breakdown = CostBreakdown(
            total=baseline_total,
            by_service=baseline_costs,
            percentage=baseline_pct,
        )

        non_baseline_breakdown = CostBreakdown(
            total=non_baseline_total,
            by_service=non_baseline_costs,
            percentage=non_baseline_pct,
        )

        # Create cost report
        report = CostReport(
            generated_at=datetime.now(),
            baseline_snapshot_name=snapshot.name,
            period_start=start_date,
            period_end=end_date,
            baseline_costs=baseline_breakdown,
            non_baseline_costs=non_baseline_breakdown,
            total_cost=total_cost,
            data_complete=is_complete,
            data_through=data_through,
            lag_days=lag_days,
        )

        logger.info(
            f"Cost analysis complete: Baseline=${baseline_total:.2f}, "
            f"Non-baseline=${non_baseline_total:.2f}, Total=${total_cost:.2f}"
        )

        return report

    def _get_baseline_service_mapping(self, snapshot: Snapshot) -> Set[str]:
        """Get set of AWS service names that have baseline resources.

        Maps our resource types (e.g., 'AWS::EC2::Instance') to Cost Explorer
        service names (e.g., 'Amazon Elastic Compute Cloud - Compute').

        Args:
            snapshot: Baseline snapshot

        Returns:
            Set of AWS service names from Cost Explorer
        """
        # Mapping from our resource types to Cost Explorer service names
        service_name_map = {
            "AWS::EC2::Instance": "Amazon Elastic Compute Cloud - Compute",
            "AWS::EC2::Volume": "Amazon Elastic Compute Cloud - Compute",
            "AWS::EC2::VPC": "Amazon Elastic Compute Cloud - Compute",
            "AWS::EC2::SecurityGroup": "Amazon Elastic Compute Cloud - Compute",
            "AWS::EC2::Subnet": "Amazon Elastic Compute Cloud - Compute",
            "AWS::EC2::VPCEndpoint::Interface": "Amazon Elastic Compute Cloud - Compute",
            "AWS::EC2::VPCEndpoint::Gateway": "Amazon Elastic Compute Cloud - Compute",
            "AWS::Lambda::Function": "AWS Lambda",
            "AWS::Lambda::LayerVersion": "AWS Lambda",
            "AWS::S3::Bucket": "Amazon Simple Storage Service",
            "AWS::RDS::DBInstance": "Amazon Relational Database Service",
            "AWS::RDS::DBCluster": "Amazon Relational Database Service",
            "AWS::IAM::Role": "AWS Identity and Access Management",
            "AWS::IAM::User": "AWS Identity and Access Management",
            "AWS::IAM::Policy": "AWS Identity and Access Management",
            "AWS::IAM::Group": "AWS Identity and Access Management",
            "AWS::CloudWatch::Alarm": "Amazon CloudWatch",
            "AWS::CloudWatch::CompositeAlarm": "Amazon CloudWatch",
            "AWS::Logs::LogGroup": "Amazon CloudWatch",
            "AWS::SNS::Topic": "Amazon Simple Notification Service",
            "AWS::SQS::Queue": "Amazon Simple Queue Service",
            "AWS::DynamoDB::Table": "Amazon DynamoDB",
            "AWS::ElasticLoadBalancing::LoadBalancer": "Elastic Load Balancing",
            "AWS::ElasticLoadBalancingV2::LoadBalancer::Application": "Elastic Load Balancing",
            "AWS::ElasticLoadBalancingV2::LoadBalancer::Network": "Elastic Load Balancing",
            "AWS::ElasticLoadBalancingV2::LoadBalancer::Gateway": "Elastic Load Balancing",
            "AWS::CloudFormation::Stack": "AWS CloudFormation",
            "AWS::ApiGateway::RestApi": "Amazon API Gateway",
            "AWS::ApiGatewayV2::Api::HTTP": "Amazon API Gateway",
            "AWS::ApiGatewayV2::Api::WebSocket": "Amazon API Gateway",
            "AWS::Events::EventBus": "Amazon EventBridge",
            "AWS::Events::Rule": "Amazon EventBridge",
            "AWS::SecretsManager::Secret": "AWS Secrets Manager",
            "AWS::KMS::Key": "AWS Key Management Service",
            "AWS::SSM::Parameter": "AWS Systems Manager",
            "AWS::SSM::Document": "AWS Systems Manager",
            "AWS::Route53::HostedZone": "Amazon Route 53",
            "AWS::ECS::Cluster": "Amazon EC2 Container Service",
            "AWS::ECS::Service": "Amazon EC2 Container Service",
            "AWS::ECS::TaskDefinition": "Amazon EC2 Container Service",
            "AWS::StepFunctions::StateMachine": "AWS Step Functions",
            "AWS::WAFv2::WebACL::Regional": "AWS WAF",
            "AWS::WAFv2::WebACL::CloudFront": "AWS WAF",
            "AWS::EKS::Cluster": "Amazon Elastic Kubernetes Service",
            "AWS::EKS::Nodegroup": "Amazon Elastic Kubernetes Service",
            "AWS::EKS::FargateProfile": "Amazon Elastic Kubernetes Service",
            "AWS::CodePipeline::Pipeline": "AWS CodePipeline",
            "AWS::CodeBuild::Project": "AWS CodeBuild",
            "AWS::Backup::BackupPlan": "AWS Backup",
            "AWS::Backup::BackupVault": "AWS Backup",
        }

        baseline_services = set()

        # Get unique resource types from snapshot
        resource_types = set()
        for resource in snapshot.resources:
            resource_types.add(resource.resource_type)

        # Map to Cost Explorer service names
        for resource_type in resource_types:
            if resource_type in service_name_map:
                baseline_services.add(service_name_map[resource_type])

        logger.debug(f"Baseline services: {baseline_services}")

        return baseline_services
