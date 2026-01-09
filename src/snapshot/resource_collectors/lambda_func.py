"""Lambda resource collector."""

from datetime import datetime
from typing import List, Optional

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


def _parse_lambda_timestamp(timestamp_str: Optional[str]) -> Optional[datetime]:
    """Parse Lambda's ISO-8601 timestamp format.

    Lambda returns timestamps like: 2024-01-15T10:30:00.000+0000

    Args:
        timestamp_str: ISO-8601 formatted timestamp string

    Returns:
        Parsed datetime or None if parsing fails
    """
    if not timestamp_str:
        return None
    try:
        # Lambda format: 2024-01-15T10:30:00.000+0000
        # Python's fromisoformat doesn't handle +0000 format, need to normalize
        normalized = timestamp_str.replace("+0000", "+00:00").replace("-0000", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        return None


class LambdaCollector(BaseResourceCollector):
    """Collector for AWS Lambda functions and layers."""

    @property
    def service_name(self) -> str:
        return "lambda"

    def collect(self) -> List[Resource]:
        """Collect Lambda resources.

        Returns:
            List of Lambda functions and layers
        """
        resources = []
        account_id = self._get_account_id()

        # Collect functions
        resources.extend(self._collect_functions(account_id))

        # Collect layers
        resources.extend(self._collect_layers(account_id))

        self.logger.debug(f"Collected {len(resources)} Lambda resources in {self.region}")
        return resources

    def _collect_functions(self, account_id: str) -> List[Resource]:
        """Collect Lambda functions."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_functions")
            for page in paginator.paginate():
                for function in page["Functions"]:
                    function_name = function["FunctionName"]
                    function_arn = function["FunctionArn"]

                    # Get full function configuration (includes tags)
                    try:
                        full_config = client.get_function(FunctionName=function_name)
                        tags = full_config.get("Tags", {})
                        config_data = full_config.get("Configuration", function)
                    except Exception as e:
                        self.logger.debug(f"Could not get full config for {function_name}: {e}")
                        tags = {}
                        config_data = function

                    # Parse LastModified timestamp (set on creation and updates)
                    last_modified = _parse_lambda_timestamp(config_data.get("LastModified"))

                    # Create resource
                    resource = Resource(
                        arn=function_arn,
                        resource_type="AWS::Lambda::Function",
                        name=function_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(config_data),
                        created_at=last_modified,
                        raw_config=config_data,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Lambda functions in {self.region}: {e}")

        return resources

    def _collect_layers(self, account_id: str) -> List[Resource]:
        """Collect Lambda layers."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_layers")
            for page in paginator.paginate():
                for layer in page["Layers"]:
                    layer_name = layer["LayerName"]
                    layer_arn = layer["LayerArn"]

                    # Get latest version info
                    try:
                        latest_version = layer.get("LatestMatchingVersion", {})
                        layer_version_arn = latest_version.get("LayerVersionArn", layer_arn)
                        # Parse CreatedDate timestamp (same format as function LastModified)
                        created_at = _parse_lambda_timestamp(latest_version.get("CreatedDate"))

                        # Create resource
                        resource = Resource(
                            arn=layer_version_arn,
                            resource_type="AWS::Lambda::LayerVersion",
                            name=layer_name,
                            region=self.region,
                            tags={},  # Layers don't support tags
                            config_hash=compute_config_hash(layer),
                            created_at=created_at,
                            raw_config=layer,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Could not get layer version for {layer_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting Lambda layers in {self.region}: {e}")

        return resources
