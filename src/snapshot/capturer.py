"""Snapshot capture coordinator for AWS resources."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from threading import Lock
from typing import TYPE_CHECKING, Dict, List, Optional, Type

import boto3
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ..models.snapshot import Snapshot

if TYPE_CHECKING:
    from .filter import ResourceFilter

# Import Config service integration
from ..config_service.collector import ConfigResourceCollector
from ..config_service.detector import (
    ConfigAvailability,
    detect_config_availability,
)
from ..config_service.resource_type_mapping import (
    COLLECTOR_TO_CONFIG_TYPES,
)
from .resource_collectors.apigateway import APIGatewayCollector
from .resource_collectors.backup import BackupCollector
from .resource_collectors.base import BaseResourceCollector
from .resource_collectors.cloudformation import CloudFormationCollector
from .resource_collectors.cloudwatch import CloudWatchCollector
from .resource_collectors.codebuild import CodeBuildCollector
from .resource_collectors.codepipeline import CodePipelineCollector
from .resource_collectors.dynamodb import DynamoDBCollector
from .resource_collectors.ec2 import EC2Collector
from .resource_collectors.ecs import ECSCollector
from .resource_collectors.efs_collector import EFSCollector
from .resource_collectors.eks import EKSCollector
from .resource_collectors.elasticache_collector import ElastiCacheCollector
from .resource_collectors.elb import ELBCollector
from .resource_collectors.eventbridge import EventBridgeCollector
from .resource_collectors.glue import GlueCollector
from .resource_collectors.iam import IAMCollector
from .resource_collectors.kms import KMSCollector
from .resource_collectors.lambda_func import LambdaCollector
from .resource_collectors.rds import RDSCollector
from .resource_collectors.route53 import Route53Collector
from .resource_collectors.s3 import S3Collector
from .resource_collectors.secretsmanager import SecretsManagerCollector
from .resource_collectors.sns import SNSCollector
from .resource_collectors.sqs import SQSCollector
from .resource_collectors.ssm import SSMCollector
from .resource_collectors.stepfunctions import StepFunctionsCollector
from .resource_collectors.vpcendpoints import VPCEndpointsCollector
from .resource_collectors.waf import WAFCollector

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
    EFSCollector,
    ElastiCacheCollector,
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
    GlueCollector,
]


def create_snapshot(
    name: str,
    regions: List[str],
    account_id: str,
    profile_name: Optional[str] = None,
    set_active: bool = True,
    resource_types: Optional[List[str]] = None,
    parallel_workers: int = 10,
    resource_filter: Optional["ResourceFilter"] = None,
    inventory_name: str = "default",
    use_config: bool = True,
    config_aggregator: Optional[str] = None,
    lambda_code_max_size: Optional[int] = None,
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
        inventory_name: Name of inventory this snapshot belongs to (default: "default")
        use_config: Use AWS Config for collection when available (default: True)
        config_aggregator: Optional Config Aggregator name for multi-account collection

    Returns:
        Snapshot instance with captured resources
    """
    logger.debug(f"Creating snapshot '{name}' for regions: {regions}")
    if use_config:
        logger.debug("AWS Config collection enabled (will fall back to direct API if unavailable)")

    # Create session with optional profile
    session_kwargs = {}
    if profile_name:
        session_kwargs["profile_name"] = profile_name

    session = boto3.Session(**session_kwargs)

    # Detect AWS Config availability per region if Config collection is enabled
    config_availability: Dict[str, ConfigAvailability] = {}
    collection_sources: Dict[str, str] = {}  # Track source per resource type

    if use_config:
        logger.debug("Detecting AWS Config availability...")
        for region in regions:
            try:
                availability = detect_config_availability(session, region, profile_name)
                config_availability[region] = availability
                if availability.is_enabled:
                    logger.debug(
                        f"  {region}: Config enabled (all_supported={availability.recording_group_all_supported})"
                    )
                else:
                    logger.debug(f"  {region}: Config not available ({availability.error_message})")
            except Exception as e:
                logger.debug(f"  {region}: Config detection failed ({e})")
                config_availability[region] = ConfigAvailability(region=region, error_message=str(e))

    # Collect resources
    all_resources = []
    resource_counts = {}  # Track counts per service for progress
    collection_errors = []  # Track errors for summary

    # Expected errors that we'll suppress (service not enabled, pagination issues, etc.)
    expected_error_patterns = [
        "Operation cannot be paginated",
        "is not subscribed",
        "AccessDenied",
        "not authorized",
        "InvalidAction",
        "OptInRequired",
    ]

    def is_expected_error(error_msg: str) -> bool:
        """Check if error is expected and can be safely ignored."""
        return any(pattern in error_msg for pattern in expected_error_patterns)

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
            temp_instance = c(session, "us-east-1")
            if temp_instance.is_global_service:
                global_collectors.append(c)
            else:
                regional_collectors.append(c)

        total_tasks = len(global_collectors) + (len(regional_collectors) * len(regions))
        main_task = progress.add_task(
            f"[bold]Collecting AWS resources from {len(regions)} region(s)...", total=total_tasks
        )

        # Thread-safe lock for updating shared state
        lock = Lock()

        def collect_service(collector_class: Type[BaseResourceCollector], region: str, is_global: bool = False) -> Dict:
            """Collect resources for a single service in a region (thread-safe)."""
            try:
                # Special handling for LambdaCollector to pass code storage options
                if collector_class == LambdaCollector and lambda_code_max_size is not None:
                    collector = collector_class(
                        session,
                        region,
                        max_inline_code_size=lambda_code_max_size,
                        snapshot_name=name,
                    )
                else:
                    collector = collector_class(session, region)
                service_name = collector.service_name.upper()
                region_label = "global" if is_global else region

                # Update progress (thread-safe)
                with lock:
                    progress.update(main_task, description=f"📦 {service_name} • {region_label}")

                resources = []
                source = "direct_api"

                # Check if we should use AWS Config for this service/region
                config_region = "us-east-1" if is_global else region
                region_config = config_availability.get(config_region)
                service_config_types = COLLECTOR_TO_CONFIG_TYPES.get(collector.service_name, [])

                if use_config and region_config and region_config.is_enabled and service_config_types:
                    # Try to collect via AWS Config
                    try:
                        config_collector = ConfigResourceCollector(session, config_region, profile_name, region_config)

                        # Collect each resource type this service handles
                        for config_type in service_config_types:
                            if region_config.supports_resource_type(config_type):
                                type_resources = config_collector.collect_by_type(config_type)
                                resources.extend(type_resources)
                                with lock:
                                    collection_sources[config_type] = "config"

                        if resources:
                            source = "config"
                            logger.debug(
                                f"Collected {len(resources)} {service_name} resources via Config from {region_label}"
                            )

                    except Exception as config_error:
                        logger.debug(
                            f"Config collection failed for {service_name} in {region_label}, "
                            f"falling back to direct API: {config_error}"
                        )
                        resources = []  # Reset to trigger fallback

                # Fall back to direct API if Config didn't work or isn't available
                if not resources:
                    resources = collector.collect()
                    source = "direct_api"
                    # Track source for each resource type
                    for resource in resources:
                        with lock:
                            if resource.resource_type not in collection_sources:
                                collection_sources[resource.resource_type] = "direct_api"

                logger.debug(f"Collected {len(resources)} {service_name} resources from {region_label} via {source}")

                return {
                    "success": True,
                    "resources": resources,
                    "service": service_name,
                    "region": region_label,
                    "source": source,
                }

            except Exception as e:
                error_msg = str(e)
                service_name = collector_class.__name__.replace("Collector", "").upper()
                region_label = "global" if is_global else region

                if not is_expected_error(error_msg):
                    logger.debug(f"Collection error - {service_name} ({region_label}): {error_msg[:80]}")
                    return {
                        "success": False,
                        "error": {"service": service_name, "region": region_label, "error": error_msg[:100]},
                    }
                else:
                    logger.debug(f"Skipping {service_name} in {region_label} (not available): {error_msg[:80]}")
                    return {"success": False, "expected": True}

        # Create list of collection tasks
        collection_tasks = []

        # Add global service tasks
        for collector_class in global_collectors:
            collection_tasks.append((collector_class, "us-east-1", True))

        # Add regional service tasks
        for region in regions:
            for collector_class in regional_collectors:
                collection_tasks.append((collector_class, region, False))

        # Execute collections in parallel
        with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(collect_service, collector_class, region, is_global): (
                    collector_class,
                    region,
                    is_global,
                )
                for collector_class, region, is_global in collection_tasks
            }

            # Process completed tasks
            for future in as_completed(future_to_task):
                result = future.result()

                if result["success"]:
                    with lock:
                        all_resources.extend(result["resources"])
                        if result["region"] == "global":
                            resource_counts[result["service"]] = len(result["resources"])
                        else:
                            key = f"{result['service']}_{result['region']}"
                            resource_counts[key] = len(result["resources"])
                elif not result.get("expected", False):
                    with lock:
                        collection_errors.append(result["error"])

                # Advance progress (thread-safe)
                with lock:
                    progress.advance(main_task)

        progress.update(main_task, description=f"[bold green]✓ Successfully collected {len(all_resources)} resources")

    # Log summary of collection errors if any (but not expected ones)
    if collection_errors:
        logger.debug(f"\nCollection completed with {len(collection_errors)} service(s) unavailable")
        logger.debug("Services that failed:")
        for error in collection_errors:
            logger.debug(f"  - {error['service']} ({error['region']}): {error['error']}")

    # Apply filters if specified
    total_before_filter = len(all_resources)
    filters_applied = None

    if resource_filter:
        logger.debug(f"Applying filters: {resource_filter.get_filter_summary()}")
        all_resources = resource_filter.apply(all_resources)
        filter_stats = resource_filter.get_statistics_summary()

        filters_applied = {
            "date_filters": {
                "before_date": resource_filter.before_date.isoformat() if resource_filter.before_date else None,
                "after_date": resource_filter.after_date.isoformat() if resource_filter.after_date else None,
            },
            "tag_filters": resource_filter.required_tags,
            "statistics": filter_stats,
        }

        logger.debug(
            f"Filtering complete: {filter_stats['total_collected']} collected, "
            f"{filter_stats['final_count']} matched filters"
        )

    # Calculate service counts
    service_counts: Dict[str, int] = {}
    for resource in all_resources:
        service_counts[resource.resource_type] = service_counts.get(resource.resource_type, 0) + 1

    # Build Config-related metadata
    config_enabled_regions = (
        [region for region, avail in config_availability.items() if avail.is_enabled] if use_config else []
    )

    # Create snapshot
    snapshot = Snapshot(
        name=name,
        created_at=datetime.now(timezone.utc),
        account_id=account_id,
        regions=regions,
        resources=all_resources,
        metadata={
            "tool": "aws-inventory-manager",
            "version": "1.0.0",
            "collectors_used": [c(session, "us-east-1").service_name for c in collectors_to_use],
            "collection_errors": collection_errors if collection_errors else None,
            "use_config": use_config,
            "config_aggregator": config_aggregator,
            "config_enabled_regions": config_enabled_regions if config_enabled_regions else None,
            "collection_sources": collection_sources if collection_sources else None,
        },
        is_active=set_active,
        service_counts=service_counts,
        filters_applied=filters_applied,
        total_resources_before_filter=total_before_filter if resource_filter else None,
        inventory_name=inventory_name,
    )

    logger.debug(f"Snapshot '{name}' created with {len(all_resources)} resources")

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
        temp_collector = collector_class(boto3.Session(), "us-east-1")
        if temp_collector.service_name in resource_types:
            filtered.append(collector_class)

    return filtered if filtered else COLLECTOR_REGISTRY
