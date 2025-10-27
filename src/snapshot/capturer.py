"""Snapshot capture coordinator for AWS resources."""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Type
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ..models.snapshot import Snapshot
from ..models.resource import Resource
from .resource_collectors.base import BaseResourceCollector
from .resource_collectors.iam import IAMCollector
from .resource_collectors.lambda_func import LambdaCollector
from .resource_collectors.s3 import S3Collector
from .resource_collectors.ec2 import EC2Collector
from .resource_collectors.rds import RDSCollector
from .resource_collectors.cloudwatch import CloudWatchCollector
from .resource_collectors.sns import SNSCollector
from .resource_collectors.sqs import SQSCollector
from .resource_collectors.dynamodb import DynamoDBCollector
from .resource_collectors.elb import ELBCollector
from .resource_collectors.cloudformation import CloudFormationCollector
from .resource_collectors.apigateway import APIGatewayCollector
from .resource_collectors.eventbridge import EventBridgeCollector
from .resource_collectors.secretsmanager import SecretsManagerCollector
from .resource_collectors.kms import KMSCollector
from .resource_collectors.ssm import SSMCollector
from .resource_collectors.route53 import Route53Collector
from .resource_collectors.ecs import ECSCollector
from .resource_collectors.stepfunctions import StepFunctionsCollector
from .resource_collectors.vpcendpoints import VPCEndpointsCollector
from .resource_collectors.waf import WAFCollector
from .resource_collectors.eks import EKSCollector
from .resource_collectors.codepipeline import CodePipelineCollector
from .resource_collectors.codebuild import CodeBuildCollector
from .resource_collectors.backup import BackupCollector

logger = logging.getLogger(__name__)


# Registry of all available collectors
COLLECTOR_REGISTRY: List[Type[BaseResourceCollector]] = [
    IAMCollector,
    LambdaCollector,
    S3Collector,
    EC2Collector,
    RDSCollector,
    CloudWatchCollector,
    SNSCollector,
    SQSCollector,
    DynamoDBCollector,
    ELBCollector,
    CloudFormationCollector,
    APIGatewayCollector,
    EventBridgeCollector,
    SecretsManagerCollector,
    KMSCollector,
    SSMCollector,
    Route53Collector,
    ECSCollector,
    StepFunctionsCollector,
    VPCEndpointsCollector,
    WAFCollector,
    EKSCollector,
    CodePipelineCollector,
    CodeBuildCollector,
    BackupCollector,
]


def create_snapshot(
    name: str,
    regions: List[str],
    account_id: str,
    profile_name: Optional[str] = None,
    set_active: bool = True,
    resource_types: Optional[List[str]] = None,
    parallel_workers: int = 10,
    resource_filter: Optional['ResourceFilter'] = None,
) -> Snapshot:
    """Create a comprehensive snapshot of AWS resources.

    Args:
        name: Snapshot name
        regions: List of AWS regions to scan
        account_id: AWS account ID
        profile_name: AWS profile name (optional)
        set_active: Whether to set as active baseline
        resource_types: Optional list of resource types to collect (e.g., ['iam', 'lambda'])
        parallel_workers: Number of parallel collection tasks
        resource_filter: Optional ResourceFilter for date/tag-based filtering

    Returns:
        Snapshot instance with captured resources
    """
    logger.info(f"Creating snapshot '{name}' for regions: {regions}")

    # Create session with optional profile
    session_kwargs = {}
    if profile_name:
        session_kwargs['profile_name'] = profile_name

    session = boto3.Session(**session_kwargs)

    # Collect resources
    all_resources = []
    resource_counts = {}  # Track counts per service for progress
    collection_errors = []  # Track errors for summary

    # Expected errors that we'll suppress (service not enabled, pagination issues, etc.)
    EXPECTED_ERROR_PATTERNS = [
        "Operation cannot be paginated",
        "is not subscribed",
        "AccessDenied",
        "not authorized",
        "InvalidAction",
        "OptInRequired",
    ]

    def is_expected_error(error_msg: str) -> bool:
        """Check if error is expected and can be safely ignored."""
        return any(pattern in error_msg for pattern in EXPECTED_ERROR_PATTERNS)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        # Determine which collectors to use
        collectors_to_use = _get_collectors(resource_types)

        # Separate global and regional collectors
        # Create temporary instances to check is_global_service property
        global_collectors = []
        regional_collectors = []
        for c in collectors_to_use:
            temp_instance = c(session, 'us-east-1')
            if temp_instance.is_global_service:
                global_collectors.append(c)
            else:
                regional_collectors.append(c)

        total_tasks = len(global_collectors) + (len(regional_collectors) * len(regions))
        main_task = progress.add_task(
            f"[bold]Collecting AWS resources from {len(regions)} region(s)...",
            total=total_tasks
        )

        # Collect global services first (only once)
        for idx, collector_class in enumerate(global_collectors, 1):
            collector = collector_class(session, 'us-east-1')
            service_name = collector.service_name.upper()

            progress.update(main_task, description=f"📦 {service_name} (global)")

            try:
                resources = collector.collect()
                all_resources.extend(resources)
                resource_counts[service_name] = len(resources)
                logger.debug(f"Collected {len(resources)} {service_name} resources")
            except Exception as e:
                error_msg = str(e)
                if not is_expected_error(error_msg):
                    collection_errors.append({
                        'service': service_name,
                        'region': 'global',
                        'error': error_msg[:100]
                    })
                    logger.warning(f"⚠️  {service_name}: {error_msg[:80]}")
                else:
                    logger.debug(f"Skipping {service_name} (not available): {error_msg[:80]}")

            progress.advance(main_task)

        # Collect regional services (for each region)
        for region in regions:
            for collector_class in regional_collectors:
                collector = collector_class(session, region)
                service_name = collector.service_name.upper()

                progress.update(main_task, description=f"📦 {service_name} • {region}")

                try:
                    resources = collector.collect()
                    all_resources.extend(resources)
                    key = f"{service_name}_{region}"
                    resource_counts[key] = len(resources)
                    logger.debug(f"Collected {len(resources)} {service_name} resources from {region}")
                except Exception as e:
                    error_msg = str(e)
                    if not is_expected_error(error_msg):
                        collection_errors.append({
                            'service': service_name,
                            'region': region,
                            'error': error_msg[:100]
                        })
                        logger.warning(f"⚠️  {service_name} ({region}): {error_msg[:80]}")
                    else:
                        logger.debug(f"Skipping {service_name} in {region} (not available): {error_msg[:80]}")

                progress.advance(main_task)

        progress.update(main_task, description=f"[bold green]✓ Successfully collected {len(all_resources)} resources")

    # Log summary of collection errors if any (but not expected ones)
    if collection_errors:
        logger.info(f"\nCollection completed with {len(collection_errors)} service(s) unavailable")
        logger.debug("Services that failed:")
        for error in collection_errors:
            logger.debug(f"  - {error['service']} ({error['region']}): {error['error']}")

    # Apply filters if specified
    total_before_filter = len(all_resources)
    filters_applied = None

    if resource_filter:
        logger.info(f"Applying filters: {resource_filter.get_filter_summary()}")
        all_resources = resource_filter.apply(all_resources)
        filter_stats = resource_filter.get_statistics_summary()

        filters_applied = {
            'date_filters': {
                'before_date': resource_filter.before_date.isoformat() if resource_filter.before_date else None,
                'after_date': resource_filter.after_date.isoformat() if resource_filter.after_date else None,
            },
            'tag_filters': resource_filter.required_tags,
            'statistics': filter_stats,
        }

        logger.info(
            f"Filtering complete: {filter_stats['total_collected']} collected, "
            f"{filter_stats['final_count']} matched filters"
        )

    # Calculate service counts
    service_counts: Dict[str, int] = {}
    for resource in all_resources:
        service_counts[resource.resource_type] = service_counts.get(resource.resource_type, 0) + 1

    # Create snapshot
    snapshot = Snapshot(
        name=name,
        created_at=datetime.now(timezone.utc),
        account_id=account_id,
        regions=regions,
        resources=all_resources,
        metadata={
            'tool': 'aws-baseline-snapshot',
            'version': '1.0.0',
            'collectors_used': [c(session, 'us-east-1').service_name for c in collectors_to_use],
            'collection_errors': collection_errors if collection_errors else None,
        },
        is_active=set_active,
        service_counts=service_counts,
        filters_applied=filters_applied,
        total_resources_before_filter=total_before_filter if resource_filter else None,
    )

    logger.info(f"Snapshot '{name}' created with {len(all_resources)} resources")

    return snapshot


def create_snapshot_mvp(
    name: str,
    regions: List[str],
    account_id: str,
    profile_name: Optional[str] = None,
    set_active: bool = True,
) -> Snapshot:
    """Create snapshot using the full implementation.

    This is a wrapper for backward compatibility with the MVP CLI code.

    Args:
        name: Snapshot name
        regions: List of AWS regions to scan
        account_id: AWS account ID
        profile_name: AWS profile name (optional)
        set_active: Whether to set as active baseline

    Returns:
        Snapshot instance with captured resources
    """
    return create_snapshot(
        name=name,
        regions=regions,
        account_id=account_id,
        profile_name=profile_name,
        set_active=set_active,
    )


def _get_collectors(resource_types: Optional[List[str]] = None) -> List[Type[BaseResourceCollector]]:
    """Get list of collectors to use based on resource type filter.

    Args:
        resource_types: Optional list of service names to filter (e.g., ['iam', 'lambda'])

    Returns:
        List of collector classes to use
    """
    if not resource_types:
        return COLLECTOR_REGISTRY

    # Filter collectors based on service name
    filtered = []
    for collector_class in COLLECTOR_REGISTRY:
        # Create temporary instance to check service name
        temp_collector = collector_class(boto3.Session(), 'us-east-1')
        if temp_collector.service_name in resource_types:
            filtered.append(collector_class)

    return filtered if filtered else COLLECTOR_REGISTRY
