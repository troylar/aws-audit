"""Boto3 client wrapper with retry configuration and error handling."""

import logging
from typing import Any, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


# Aggressive retry configuration for batch operations
DEFAULT_RETRY_CONFIG = Config(
    retries={"max_attempts": 10, "mode": "adaptive"},  # Adaptive retry mode (boto3 1.16+)
    max_pool_connections=50,
    connect_timeout=60,
    read_timeout=60,
)


def create_boto_client(
    service_name: str,
    region_name: str = "us-east-1",
    profile_name: Optional[str] = None,
    retry_config: Optional[Config] = None,
) -> Any:
    """Create boto3 client with retry configuration and error handling.

    Args:
        service_name: AWS service name (e.g., 'ec2', 'iam', 'lambda')
        region_name: AWS region (default: 'us-east-1')
        profile_name: AWS profile name from ~/.aws/config (optional)
        retry_config: Custom botocore Config object (optional)

    Returns:
        Configured boto3 client

    Raises:
        NoCredentialsError: If AWS credentials are not found
        ClientError: If client creation fails
    """
    if retry_config is None:
        retry_config = DEFAULT_RETRY_CONFIG

    try:
        # Create session (with or without profile)
        if profile_name:
            session = boto3.Session(profile_name=profile_name)
            client = session.client(service_name, region_name=region_name, config=retry_config)
        else:
            client = boto3.client(service_name, region_name=region_name, config=retry_config)

        logger.debug(f"Created {service_name} client for region {region_name}")
        return client

    except NoCredentialsError:
        logger.error("AWS credentials not found")
        raise
    except ClientError as e:
        logger.error(f"Failed to create {service_name} client: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating {service_name} client: {e}")
        raise


def get_enabled_regions(profile_name: Optional[str] = None) -> List[str]:  # type: ignore
    """Get list of enabled AWS regions for the account.

    Args:
        profile_name: AWS profile name (optional)

    Returns:
        List of enabled region names
    """
    try:
        ec2_client = create_boto_client("ec2", region_name="us-east-1", profile_name=profile_name)
        response = ec2_client.describe_regions(AllRegions=False)  # Only enabled regions
        regions = [region["RegionName"] for region in response["Regions"]]
        logger.info(f"Found {len(regions)} enabled regions")
        return regions
    except Exception as e:
        logger.warning(f"Could not retrieve enabled regions: {e}")
        # Return default set of common regions
        return [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
        ]


def check_client_connection(client: Any) -> bool:
    """Test if a boto3 client can connect to AWS.

    Args:
        client: Boto3 client instance

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Different services have different test methods
        service_name = client._service_model.service_name

        if service_name == "sts":
            client.get_caller_identity()
        elif service_name == "ec2":
            client.describe_regions(MaxResults=1)
        elif service_name == "iam":
            client.list_users(MaxItems=1)
        elif service_name == "lambda":
            client.list_functions(MaxItems=1)
        elif service_name == "s3":
            client.list_buckets()
        else:
            # Generic test - just try to get service metadata
            client._make_api_call("ListObjects", {})

        return True
    except Exception as e:
        logger.debug(f"Client connection test failed: {e}")
        return False
