"""Utility for detecting unsupported AWS resources.

This module helps identify AWS resources that exist in an account but are not
covered by any of our collectors. This is important for:
- Ensuring complete inventory coverage
- Identifying when new AWS services need collectors
- Alerting users about resources that won't be included in snapshots
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


# Mapping of AWS resource type prefixes to our collector service names
# This maps from AWS Resource Groups Tagging API format to our collectors
SUPPORTED_RESOURCE_TYPE_PREFIXES: Dict[str, str] = {
    # IAM
    "iam:": "iam",
    # Compute
    "ec2:": "ec2",
    "lambda:": "lambda",
    "ecs:": "ecs",
    "eks:": "eks",
    # Storage
    "s3:": "s3",
    "dynamodb:": "dynamodb",
    "elasticache:": "elasticache",
    "rds:": "rds",
    "elasticfilesystem:": "efs",
    "backup:": "backup",
    # Networking
    "elasticloadbalancing:": "elb",
    "route53:": "route53",
    # Messaging
    "sns:": "sns",
    "sqs:": "sqs",
    # Security
    "secretsmanager:": "secretsmanager",
    "kms:": "kms",
    "wafv2:": "waf",
    # Monitoring & Logging
    "cloudwatch:": "cloudwatch",
    "logs:": "cloudwatch",  # CloudWatch Logs is part of CloudWatch collector
    # Integration & Orchestration
    "states:": "stepfunctions",
    "events:": "eventbridge",
    "apigateway:": "apigateway",
    "codepipeline:": "codepipeline",
    "codebuild:": "codebuild",
    # Management
    "cloudformation:": "cloudformation",
    "ssm:": "ssm",
    # VPC
    "ec2:vpc-endpoint": "vpcendpoints",
}


@dataclass
class UnsupportedResource:
    """Represents an AWS resource that is not covered by any collector."""

    resource_arn: str
    resource_type: str
    tags: Dict[str, str]
    region: str


@dataclass
class UnsupportedResourceReport:
    """Report of unsupported resources found in an AWS account."""

    unsupported_resources: List[UnsupportedResource]
    unsupported_types: Set[str]
    supported_types: Set[str]
    total_resources_scanned: int


def get_all_tagged_resources(
    session: Optional[boto3.Session] = None,
    regions: Optional[List[str]] = None,
) -> List[Tuple[str, str, Dict[str, str], str]]:
    """Get all tagged resources across all services using Resource Groups Tagging API.

    Args:
        session: Optional boto3 session (uses default if not provided)
        regions: Optional list of regions to scan (uses all regions if not provided)

    Returns:
        List of tuples (arn, resource_type, tags, region)
    """
    if session is None:
        session = boto3.Session()

    if regions is None:
        # Get all available regions
        ec2 = session.client("ec2", region_name="us-east-1")
        try:
            response = ec2.describe_regions(AllRegions=False)
            regions = [r["RegionName"] for r in response["Regions"]]
        except ClientError as e:
            logger.warning(f"Could not get regions, using default list: {e}")
            regions = ["us-east-1", "us-west-2", "eu-west-1"]

    all_resources: List[Tuple[str, str, Dict[str, str], str]] = []

    for region in regions:
        try:
            tagging = session.client("resourcegroupstaggingapi", region_name=region)
            paginator = tagging.get_paginator("get_resources")

            for page in paginator.paginate():
                for resource in page.get("ResourceTagMappingList", []):
                    arn = resource["ResourceARN"]
                    tags = {t["Key"]: t["Value"] for t in resource.get("Tags", [])}

                    # Extract resource type from ARN
                    # ARN format: arn:partition:service:region:account:resource-type/resource-id
                    parts = arn.split(":")
                    if len(parts) >= 6:
                        service = parts[2]
                        resource_part = parts[5] if len(parts) > 5 else ""

                        # Handle resource types like "bucket/name" or "function:name"
                        if "/" in resource_part:
                            resource_type = f"{service}:{resource_part.split('/')[0]}"
                        elif ":" in resource_part:
                            resource_type = f"{service}:{resource_part.split(':')[0]}"
                        else:
                            resource_type = f"{service}:{resource_part}"

                        all_resources.append((arn, resource_type, tags, region))

        except ClientError as e:
            logger.debug(f"Could not scan region {region}: {e}")
        except Exception as e:
            logger.warning(f"Error scanning region {region}: {e}")

    return all_resources


def is_resource_type_supported(resource_type: str) -> bool:
    """Check if a resource type is supported by any collector.

    Args:
        resource_type: The AWS resource type (e.g., "s3:bucket", "lambda:function")

    Returns:
        True if the resource type is supported
    """
    resource_type_lower = resource_type.lower()

    for prefix in SUPPORTED_RESOURCE_TYPE_PREFIXES:
        if resource_type_lower.startswith(prefix):
            return True

    return False


def detect_unsupported_resources(
    session: Optional[boto3.Session] = None,
    regions: Optional[List[str]] = None,
    include_untagged_warning: bool = True,
) -> UnsupportedResourceReport:
    """Detect AWS resources that are not supported by any collector.

    This function uses the Resource Groups Tagging API to find all tagged resources
    and compares them against our supported resource types.

    Note: This only detects TAGGED resources. Resources without tags will not be
    detected by this method. Use AWS Config for more comprehensive detection.

    Args:
        session: Optional boto3 session
        regions: Optional list of regions to scan
        include_untagged_warning: Whether to log a warning about untagged resources

    Returns:
        UnsupportedResourceReport with details about unsupported resources
    """
    if include_untagged_warning:
        logger.info(
            "Note: This detection only covers TAGGED resources. "
            "Untagged resources will not be detected. "
            "Consider enabling AWS Config for comprehensive resource tracking."
        )

    # Get all tagged resources
    all_resources = get_all_tagged_resources(session, regions)

    unsupported_resources: List[UnsupportedResource] = []
    unsupported_types: Set[str] = set()
    supported_types: Set[str] = set()

    for arn, resource_type, tags, region in all_resources:
        if is_resource_type_supported(resource_type):
            supported_types.add(resource_type)
        else:
            unsupported_types.add(resource_type)
            unsupported_resources.append(
                UnsupportedResource(
                    resource_arn=arn,
                    resource_type=resource_type,
                    tags=tags,
                    region=region,
                )
            )

    return UnsupportedResourceReport(
        unsupported_resources=unsupported_resources,
        unsupported_types=unsupported_types,
        supported_types=supported_types,
        total_resources_scanned=len(all_resources),
    )


def get_unsupported_resource_summary(report: UnsupportedResourceReport) -> str:
    """Generate a human-readable summary of unsupported resources.

    Args:
        report: The unsupported resource report

    Returns:
        Formatted string summary
    """
    lines = [
        "Unsupported Resource Detection Report",
        "=" * 40,
        f"Total resources scanned: {report.total_resources_scanned}",
        f"Supported resource types found: {len(report.supported_types)}",
        f"Unsupported resource types found: {len(report.unsupported_types)}",
        f"Total unsupported resources: {len(report.unsupported_resources)}",
        "",
    ]

    if report.unsupported_types:
        lines.append("Unsupported Resource Types:")
        lines.append("-" * 30)
        for resource_type in sorted(report.unsupported_types):
            count = sum(1 for r in report.unsupported_resources if r.resource_type == resource_type)
            lines.append(f"  {resource_type}: {count} resource(s)")

        lines.append("")
        lines.append("Consider adding collectors for these services to ensure")
        lines.append("complete inventory coverage and safe cleanup operations.")

    return "\n".join(lines)


def check_for_unsupported_resources_quick(
    session: Optional[boto3.Session] = None,
    region: str = "us-east-1",
    limit: int = 100,
) -> Tuple[bool, Set[str]]:
    """Quick check for unsupported resources in a single region.

    This is a faster alternative to full detection, useful for CLI warnings.

    Args:
        session: Optional boto3 session
        region: Region to check
        limit: Maximum number of resources to check

    Returns:
        Tuple of (has_unsupported, unsupported_types)
    """
    if session is None:
        session = boto3.Session()

    unsupported_types: Set[str] = set()

    try:
        tagging = session.client("resourcegroupstaggingapi", region_name=region)

        response = tagging.get_resources(ResourcesPerPage=limit)

        for resource in response.get("ResourceTagMappingList", []):
            arn = resource["ResourceARN"]
            parts = arn.split(":")
            if len(parts) >= 6:
                service = parts[2]
                resource_part = parts[5] if len(parts) > 5 else ""

                if "/" in resource_part:
                    resource_type = f"{service}:{resource_part.split('/')[0]}"
                elif ":" in resource_part:
                    resource_type = f"{service}:{resource_part.split(':')[0]}"
                else:
                    resource_type = f"{service}:{resource_part}"

                if not is_resource_type_supported(resource_type):
                    unsupported_types.add(resource_type)

    except Exception as e:
        logger.debug(f"Quick unsupported resource check failed: {e}")

    return bool(unsupported_types), unsupported_types
