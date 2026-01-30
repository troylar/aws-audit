"""AWS Config-based resource collector.

Collects resources using AWS Config APIs instead of direct service API calls.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    import boto3

from ..aws.client import create_boto_client
from ..models.resource import Resource
from ..utils.hash import compute_config_hash
from .detector import ConfigAvailability

logger = logging.getLogger(__name__)

# Maximum resources per batch_get_resource_config call
MAX_BATCH_SIZE = 100


class ConfigResourceCollector:
    """Collect AWS resources using AWS Config APIs.

    Uses list_discovered_resources to find resources and
    batch_get_resource_config to get their configurations.
    """

    def __init__(
        self,
        session: "boto3.Session",
        region: str,
        profile_name: Optional[str] = None,
        config_availability: Optional[ConfigAvailability] = None,
    ):
        """Initialize the Config resource collector.

        Args:
            session: Boto3 session
            region: AWS region to collect from
            profile_name: Optional AWS profile name
            config_availability: Pre-computed Config availability (optional)
        """
        self.session = session
        self.region = region
        self.profile_name = profile_name or (session.profile_name if hasattr(session, "profile_name") else None)
        self.config_availability = config_availability
        self._client = None
        self._account_id = None

    @property
    def client(self):
        """Get or create the Config client."""
        if self._client is None:
            self._client = create_boto_client(
                service_name="config",
                region_name=self.region,
                profile_name=self.profile_name,
            )
        return self._client

    @property
    def account_id(self) -> str:
        """Get the AWS account ID."""
        if self._account_id is None:
            sts_client = create_boto_client(
                service_name="sts",
                region_name=self.region,
                profile_name=self.profile_name,
            )
            self._account_id = sts_client.get_caller_identity()["Account"]
        return self._account_id

    def collect_by_type(self, resource_type: str) -> List[Resource]:
        """Collect all resources of a specific type using AWS Config.

        Args:
            resource_type: AWS resource type (e.g., "AWS::EC2::Instance")

        Returns:
            List of Resource objects
        """
        resources = []

        try:
            # Step 1: List all discovered resources of this type
            resource_ids = self._list_discovered_resources(resource_type)

            if not resource_ids:
                logger.debug(f"No {resource_type} resources found via Config in {self.region}")
                return resources

            logger.debug(f"Found {len(resource_ids)} {resource_type} resources via Config in {self.region}")

            # Step 2: Batch get configurations
            config_items = self._batch_get_resource_configs(resource_type, resource_ids)

            # Step 3: Convert to Resource model
            for config_item in config_items:
                try:
                    resource = self._normalize_config_item(config_item)
                    if resource:
                        resources.append(resource)
                except Exception as e:
                    logger.warning(f"Failed to normalize Config item for {resource_type}: {e}")

        except Exception as e:
            logger.error(f"Error collecting {resource_type} via Config in {self.region}: {e}")
            raise

        return resources

    def _list_discovered_resources(self, resource_type: str) -> List[str]:
        """List all discovered resources of a type.

        Args:
            resource_type: AWS resource type

        Returns:
            List of resource IDs
        """
        resource_ids = []

        try:
            paginator = self.client.get_paginator("list_discovered_resources")

            for page in paginator.paginate(resourceType=resource_type):
                for resource_id_info in page.get("resourceIdentifiers", []):
                    resource_id = resource_id_info.get("resourceId")
                    if resource_id:
                        resource_ids.append(resource_id)

        except Exception as e:
            logger.error(f"Error listing {resource_type} resources in {self.region}: {e}")
            raise

        return resource_ids

    def _batch_get_resource_configs(self, resource_type: str, resource_ids: List[str]) -> List[Dict[str, Any]]:
        """Batch get resource configurations.

        Args:
            resource_type: AWS resource type
            resource_ids: List of resource IDs to fetch

        Returns:
            List of configuration items from Config
        """
        config_items = []

        # Process in batches of MAX_BATCH_SIZE
        for i in range(0, len(resource_ids), MAX_BATCH_SIZE):
            batch_ids = resource_ids[i : i + MAX_BATCH_SIZE]

            resource_keys = [{"resourceType": resource_type, "resourceId": rid} for rid in batch_ids]

            try:
                response = self.client.batch_get_resource_config(resourceKeys=resource_keys)

                # Get base configuration items
                base_items = response.get("baseConfigurationItems", [])
                config_items.extend(base_items)

                # Log any unprocessed keys
                unprocessed = response.get("unprocessedResourceKeys", [])
                if unprocessed:
                    logger.warning(f"Config could not process {len(unprocessed)} {resource_type} resources")

            except Exception as e:
                logger.error(f"Error batch getting {resource_type} configs in {self.region}: {e}")
                # Continue with other batches
                continue

        return config_items

    def _normalize_config_item(self, config_item: Dict[str, Any]) -> Optional[Resource]:
        """Convert an AWS Config item to our Resource model.

        Args:
            config_item: Config item from batch_get_resource_config

        Returns:
            Resource object or None if conversion fails
        """
        try:
            # Extract basic fields
            resource_type = config_item.get("resourceType", "")
            resource_id = config_item.get("resourceId", "")
            arn = config_item.get("arn", "")
            resource_name = config_item.get("resourceName", resource_id)

            # If no ARN provided, try to construct one
            if not arn:
                arn = self._construct_arn(resource_type, resource_id)

            # Get the configuration data
            # Config stores this as a JSON string in 'configuration'
            import json

            configuration_str = config_item.get("configuration", "{}")
            if isinstance(configuration_str, str):
                raw_config = json.loads(configuration_str)
            else:
                raw_config = configuration_str

            # Add Config-specific metadata to raw_config
            raw_config["_config_metadata"] = {
                "configurationItemCaptureTime": config_item.get("configurationItemCaptureTime"),
                "configurationStateId": config_item.get("configurationStateId"),
                "awsAccountId": config_item.get("accountId"),
                "configurationItemStatus": config_item.get("configurationItemStatus"),
            }

            # Extract tags (Config stores supplementary configuration)
            tags = {}
            supplementary_config = config_item.get("supplementaryConfiguration", {})
            if "Tags" in supplementary_config:
                tags_data = supplementary_config["Tags"]
                if isinstance(tags_data, str):
                    tags_list = json.loads(tags_data)
                else:
                    tags_list = tags_data
                if isinstance(tags_list, list):
                    for tag in tags_list:
                        if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                            tags[tag["Key"]] = tag["Value"]
                elif isinstance(tags_list, dict):
                    tags = tags_list

            # Parse creation time if available
            created_at = None
            capture_time = config_item.get("configurationItemCaptureTime")
            if capture_time:
                if isinstance(capture_time, datetime):
                    created_at = capture_time
                elif isinstance(capture_time, str):
                    try:
                        created_at = datetime.fromisoformat(capture_time.replace("Z", "+00:00"))
                    except ValueError:
                        pass

            # Determine region
            region = config_item.get("awsRegion", self.region)
            if resource_type.startswith("AWS::IAM::"):
                region = "global"

            # Create Resource
            resource = Resource(
                arn=arn,
                resource_type=resource_type,
                name=resource_name,
                region=region,
                tags=tags,
                config_hash=compute_config_hash(raw_config),
                created_at=created_at,
                raw_config=raw_config,
                source="config",
            )

            return resource

        except Exception as e:
            logger.warning(f"Failed to normalize Config item: {e}")
            return None

    def _construct_arn(self, resource_type: str, resource_id: str) -> str:
        """Construct an ARN for a resource.

        Args:
            resource_type: AWS resource type
            resource_id: Resource ID

        Returns:
            Constructed ARN string
        """
        # Parse resource type: AWS::Service::Type
        parts = resource_type.split("::")
        if len(parts) != 3:
            return f"arn:aws:unknown:{self.region}:{self.account_id}:{resource_id}"

        service = parts[1].lower()
        type_name = parts[2].lower()

        # Service-specific ARN formats
        if service == "s3":
            return f"arn:aws:s3:::{resource_id}"
        elif service == "iam":
            return f"arn:aws:iam::{self.account_id}:{type_name}/{resource_id}"
        elif service == "lambda":
            return f"arn:aws:lambda:{self.region}:{self.account_id}:function:{resource_id}"
        elif service == "dynamodb":
            return f"arn:aws:dynamodb:{self.region}:{self.account_id}:table/{resource_id}"
        elif service == "sns":
            return f"arn:aws:sns:{self.region}:{self.account_id}:{resource_id}"
        elif service == "sqs":
            return f"arn:aws:sqs:{self.region}:{self.account_id}:{resource_id}"
        elif service == "logs":
            return f"arn:aws:logs:{self.region}:{self.account_id}:log-group:{resource_id}"
        else:
            # Generic format
            return f"arn:aws:{service}:{self.region}:{self.account_id}:{type_name}/{resource_id}"

    def collect_multiple_types(self, resource_types: List[str]) -> List[Resource]:
        """Collect resources of multiple types.

        Args:
            resource_types: List of AWS resource types

        Returns:
            List of all collected resources
        """
        all_resources = []

        for resource_type in resource_types:
            try:
                resources = self.collect_by_type(resource_type)
                all_resources.extend(resources)
            except Exception as e:
                logger.error(f"Failed to collect {resource_type}: {e}")
                # Continue with other types

        return all_resources
