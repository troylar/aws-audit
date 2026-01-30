"""Lambda resource collector."""

import base64
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from ..lambda_code_storage import LambdaCodeStorage
from .base import BaseResourceCollector

# Default maximum code size to store inline (10MB)
DEFAULT_MAX_INLINE_CODE_SIZE = 10 * 1024 * 1024

# Maximum code size to download at all (250MB - Lambda's max)
MAX_DOWNLOAD_SIZE = 250 * 1024 * 1024


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

    def __init__(
        self,
        session: Any,
        region: str,
        max_inline_code_size: int = DEFAULT_MAX_INLINE_CODE_SIZE,
        snapshot_name: Optional[str] = None,
        external_storage_path: Optional[str] = None,
    ):
        """Initialize Lambda collector.

        Args:
            session: boto3 Session
            region: AWS region
            max_inline_code_size: Maximum code size (bytes) to store inline.
                                  Larger packages are stored externally.
                                  Set to 0 to disable inline storage.
                                  Set to -1 for unlimited inline storage.
            snapshot_name: Snapshot name (required for external storage)
            external_storage_path: Base path for external code storage
        """
        super().__init__(session, region)
        self.max_inline_code_size = max_inline_code_size
        self.snapshot_name = snapshot_name
        self.code_storage = LambdaCodeStorage(external_storage_path) if snapshot_name else None

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
        """Collect Lambda functions including deployment code."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_functions")
            for page in paginator.paginate():
                for function in page["Functions"]:
                    function_name = function["FunctionName"]
                    function_arn = function["FunctionArn"]

                    # Get full function configuration (includes tags and code location)
                    try:
                        full_config = client.get_function(FunctionName=function_name)
                        tags = full_config.get("Tags", {})
                        config_data = full_config.get("Configuration", function)
                        code_info = full_config.get("Code", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get full config for {function_name}: {e}")
                        tags = {}
                        config_data = function
                        code_info = {}

                    # Extract code metadata and download code
                    code_data = self._get_code_data(function_name, code_info)

                    # Merge code data into config
                    config_data_with_code = {
                        **config_data,
                        "_code": code_data,
                    }

                    # Parse LastModified timestamp (set on creation and updates)
                    last_modified = _parse_lambda_timestamp(config_data.get("LastModified"))

                    # Create resource
                    resource = Resource(
                        arn=function_arn,
                        resource_type="AWS::Lambda::Function",
                        name=function_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(config_data_with_code),
                        created_at=last_modified,
                        raw_config=config_data_with_code,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Lambda functions in {self.region}: {e}")

        return resources

    def _get_code_data(self, function_name: str, code_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract code metadata and download deployment package.

        Args:
            function_name: Name of the Lambda function
            code_info: Code info from get_function response

        Returns:
            Dictionary containing code metadata and optionally the code itself
        """
        code_data: Dict[str, Any] = {
            "repository_type": code_info.get("RepositoryType", "Unknown"),
            "image_uri": code_info.get("ImageUri"),  # For container images
            "resolved_image_uri": code_info.get("ResolvedImageUri"),
        }

        # Extract S3 source info if available (for functions deployed from S3)
        # Note: This is only available if you have GetFunctionCodeSigningConfig permission
        # and the function was deployed from S3 with those details preserved
        if "S3Bucket" in code_info:
            code_data["s3_bucket"] = code_info["S3Bucket"]
        if "S3Key" in code_info:
            code_data["s3_key"] = code_info["S3Key"]
        if "S3ObjectVersion" in code_info:
            code_data["s3_object_version"] = code_info["S3ObjectVersion"]

        # Download the code from the presigned URL
        code_location = code_info.get("Location")
        if code_location:
            try:
                self.logger.debug(f"Downloading code for {function_name}")
                response = requests.get(code_location, timeout=60)
                response.raise_for_status()

                code_bytes = response.content
                code_size = len(code_bytes)
                code_data["code_size_bytes"] = code_size

                # Compute SHA256 hash of the code
                code_hash = hashlib.sha256(code_bytes).hexdigest()
                code_data["code_sha256"] = code_hash

                # Determine storage strategy based on size and config
                # -1 means unlimited inline storage
                if self.max_inline_code_size == -1 or code_size <= self.max_inline_code_size:
                    # Store inline (base64 encoded)
                    code_data["code_base64"] = base64.b64encode(code_bytes).decode("utf-8")
                    code_data["code_stored"] = True
                    code_data["storage_type"] = "inline"
                elif self.code_storage and self.snapshot_name:
                    # Store externally to file
                    try:
                        file_path, _ = self.code_storage.store_code(self.snapshot_name, function_name, code_bytes)
                        code_data["code_stored"] = True
                        code_data["storage_type"] = "external"
                        code_data["code_file_path"] = file_path
                        self.logger.debug(
                            f"Code for {function_name} ({code_size / 1024 / 1024:.1f}MB) "
                            f"stored externally at {file_path}"
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to store code externally for {function_name}: {e}")
                        code_data["code_stored"] = False
                        code_data["code_too_large"] = True
                        code_data["storage_error"] = str(e)
                else:
                    # No external storage available, skip storing
                    code_data["code_stored"] = False
                    code_data["code_too_large"] = True
                    self.logger.debug(
                        f"Code for {function_name} is {code_size / 1024 / 1024:.1f}MB, "
                        "storing hash only (no external storage configured)"
                    )

            except requests.RequestException as e:
                self.logger.warning(f"Failed to download code for {function_name}: {e}")
                code_data["code_download_error"] = str(e)
            except Exception as e:
                self.logger.warning(f"Error processing code for {function_name}: {e}")
                code_data["code_error"] = str(e)

        return code_data

    def _collect_layers(self, account_id: str) -> List[Resource]:
        """Collect Lambda layers including deployment code."""
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
                        version_number = latest_version.get("Version", 1)

                        # Get full layer version details including code location
                        try:
                            layer_details = client.get_layer_version(LayerName=layer_name, VersionNumber=version_number)
                            code_info = layer_details.get("Content", {})
                        except Exception as e:
                            self.logger.debug(f"Could not get layer version details for {layer_name}: {e}")
                            code_info = {}

                        # Download layer code
                        code_data = self._get_layer_code_data(layer_name, code_info)

                        # Merge layer info with code data
                        layer_with_code = {
                            **layer,
                            "LatestMatchingVersion": latest_version,
                            "_code": code_data,
                        }

                        # Parse CreatedDate timestamp (same format as function LastModified)
                        created_at = _parse_lambda_timestamp(latest_version.get("CreatedDate"))

                        # Create resource
                        resource = Resource(
                            arn=layer_version_arn,
                            resource_type="AWS::Lambda::LayerVersion",
                            name=layer_name,
                            region=self.region,
                            tags={},  # Layers don't support tags
                            config_hash=compute_config_hash(layer_with_code),
                            created_at=created_at,
                            raw_config=layer_with_code,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Could not get layer version for {layer_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting Lambda layers in {self.region}: {e}")

        return resources

    def _get_layer_code_data(self, layer_name: str, code_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract layer code metadata and download deployment package.

        Args:
            layer_name: Name of the Lambda layer
            code_info: Content info from get_layer_version response

        Returns:
            Dictionary containing code metadata and optionally the code itself
        """
        code_data: Dict[str, Any] = {
            "code_sha256": code_info.get("CodeSha256"),
            "code_size": code_info.get("CodeSize"),
        }

        # Extract S3 source info if available
        if "S3Bucket" in code_info:
            code_data["s3_bucket"] = code_info["S3Bucket"]
        if "S3Key" in code_info:
            code_data["s3_key"] = code_info["S3Key"]

        # Download the code from the presigned URL
        code_location = code_info.get("Location")
        if code_location:
            try:
                self.logger.debug(f"Downloading code for layer {layer_name}")
                response = requests.get(code_location, timeout=60)
                response.raise_for_status()

                code_bytes = response.content
                code_size = len(code_bytes)
                code_data["code_size_bytes"] = code_size

                # Compute SHA256 hash of the code
                code_hash = hashlib.sha256(code_bytes).hexdigest()
                code_data["downloaded_code_sha256"] = code_hash

                # Determine storage strategy based on size and config
                # -1 means unlimited inline storage
                if self.max_inline_code_size == -1 or code_size <= self.max_inline_code_size:
                    # Store inline (base64 encoded)
                    code_data["code_base64"] = base64.b64encode(code_bytes).decode("utf-8")
                    code_data["code_stored"] = True
                    code_data["storage_type"] = "inline"
                elif self.code_storage and self.snapshot_name:
                    # Store externally to file (use layer_ prefix to distinguish)
                    try:
                        file_path, _ = self.code_storage.store_code(
                            self.snapshot_name, f"layer_{layer_name}", code_bytes
                        )
                        code_data["code_stored"] = True
                        code_data["storage_type"] = "external"
                        code_data["code_file_path"] = file_path
                        self.logger.debug(
                            f"Code for layer {layer_name} ({code_size / 1024 / 1024:.1f}MB) "
                            f"stored externally at {file_path}"
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to store code externally for layer {layer_name}: {e}")
                        code_data["code_stored"] = False
                        code_data["code_too_large"] = True
                        code_data["storage_error"] = str(e)
                else:
                    # No external storage available, skip storing
                    code_data["code_stored"] = False
                    code_data["code_too_large"] = True
                    self.logger.debug(
                        f"Code for layer {layer_name} is {code_size / 1024 / 1024:.1f}MB, "
                        "storing hash only (no external storage configured)"
                    )

            except requests.RequestException as e:
                self.logger.warning(f"Failed to download code for layer {layer_name}: {e}")
                code_data["code_download_error"] = str(e)
            except Exception as e:
                self.logger.warning(f"Error processing code for layer {layer_name}: {e}")
                code_data["code_error"] = str(e)

        return code_data
