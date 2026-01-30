"""AWS Lambda to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
LAMBDA_CONFIGURABLE = {
    # Basic function settings
    "FunctionName": "function_name",
    "Runtime": "runtime",
    "Handler": "handler",
    "Role": "role",
    "Description": "description",
    "MemorySize": "memory_size",
    "Timeout": "timeout",
    "EphemeralStorage": "ephemeral_storage",  # dict with Size key
    # VPC configuration
    "VpcConfig": "vpc_config",  # Special nested handling required
    # Environment variables
    "Environment": "environment",  # Special nested handling required
    # Layers and code
    "Layers": "layers",
    "CodeSha256": "source_code_hash",
    # Dead letter queue
    "DeadLetterConfig": "dead_letter_config",
    # Tracing
    "TracingConfig": "tracing_config",
    # Architectures
    "Architectures": "architectures",
    # Image config (for container images)
    "ImageConfig": "image_config",
    # Reserved concurrent executions
    "ReservedConcurrentExecutions": "reserved_concurrent_executions",
    # Signing config
    "SigningProfileVersionArn": "signing_profile_version_arn",
    "CodeSigningConfigArn": "code_signing_config_arn",
    # KMS encryption
    "KMSKeyArn": "kms_key_arn",
    # Snap start
    "SnapStart": "snap_start",
    # Logging
    "LoggingConfig": "logging_config",
}

# Properties computed by AWS that are read-only
LAMBDA_COMPUTED = {
    "FunctionArn": "arn",
    "CodeSha256": "source_code_hash",
    "CodeSize": "code_size",
    "LastModified": "last_modified",
    "State": "state",
    "StateReason": "state_reason",
    "StateReasonCode": "state_reason_code",
    "Version": "version",
    "Revision": "revision",
    "PackageType": "package_type",
}


def _transform_vpc_config(vpc_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform VPC configuration to Terraform format.

    Args:
        vpc_config: AWS VPC config dict with SubnetIds, SecurityGroupIds, etc.

    Returns:
        Terraform-formatted VPC config dict or None if empty
    """
    if not vpc_config:
        return None

    result = {}

    if "SubnetIds" in vpc_config:
        result["subnet_ids"] = vpc_config["SubnetIds"]

    if "SecurityGroupIds" in vpc_config:
        result["security_group_ids"] = vpc_config["SecurityGroupIds"]

    if "Ipv6AllowedForDualStack" in vpc_config:
        result["ipv6_allowed_for_dual_stack"] = vpc_config["Ipv6AllowedForDualStack"]

    return result if result else None


def _transform_environment_variables(
    environment: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """Transform environment variables to Terraform format.

    Args:
        environment: AWS environment dict with Variables key

    Returns:
        Terraform-formatted variables dict or None if empty
    """
    if not environment:
        return None

    variables = environment.get("Variables", {})
    return variables if variables else None


def _transform_ephemeral_storage(
    ephemeral_storage: Optional[Dict[str, Any]],
) -> Optional[int]:
    """Transform ephemeral storage to Terraform format.

    Args:
        ephemeral_storage: AWS ephemeral storage dict with Size key (MB)

    Returns:
        Size in MB or None if not specified
    """
    if not ephemeral_storage:
        return None

    size = ephemeral_storage.get("Size")
    return size if size else None


def _transform_dead_letter_config(
    dlq_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """Transform dead letter queue config to Terraform format.

    Args:
        dlq_config: AWS DLQ config dict with TargetArn key

    Returns:
        Terraform-formatted DLQ config or None if empty
    """
    if not dlq_config:
        return None

    result = {}

    if "TargetArn" in dlq_config:
        result["target_arn"] = dlq_config["TargetArn"]

    return result if result else None


def _transform_tracing_config(
    tracing_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """Transform tracing config to Terraform format.

    Args:
        tracing_config: AWS tracing config dict with Mode key

    Returns:
        Terraform-formatted tracing config or None if empty
    """
    if not tracing_config:
        return None

    result = {}

    if "Mode" in tracing_config:
        result["mode"] = tracing_config["Mode"]

    return result if result else None


def _transform_image_config(
    image_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Transform image config to Terraform format.

    Args:
        image_config: AWS image config dict with EntryPoint, Command, etc.

    Returns:
        Terraform-formatted image config or None if empty
    """
    if not image_config:
        return None

    result = {}

    if "EntryPoint" in image_config:
        result["entry_point"] = image_config["EntryPoint"]

    if "Command" in image_config:
        result["command"] = image_config["Command"]

    if "WorkingDirectory" in image_config:
        result["working_directory"] = image_config["WorkingDirectory"]

    return result if result else None


def _transform_snap_start(
    snap_start: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """Transform SnapStart config to Terraform format.

    Args:
        snap_start: AWS SnapStart config dict with ApplyOn key

    Returns:
        Terraform-formatted SnapStart config or None if empty
    """
    if not snap_start:
        return None

    result = {}

    if "ApplyOn" in snap_start:
        result["apply_on"] = snap_start["ApplyOn"]

    return result if result else None


def _transform_logging_config(
    logging_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """Transform logging config to Terraform format.

    Args:
        logging_config: AWS logging config dict with LogFormat, LogGroup, etc.

    Returns:
        Terraform-formatted logging config or None if empty
    """
    if not logging_config:
        return None

    result = {}

    if "LogFormat" in logging_config:
        result["log_format"] = logging_config["LogFormat"]

    if "LogGroup" in logging_config:
        result["log_group"] = logging_config["LogGroup"]

    return result if result else None


def get_lambda_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform Lambda function properties for Terraform.

    This helper transforms AWS Lambda configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw Lambda configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_lambda_function resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in LAMBDA_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "VpcConfig":
            transformed = _transform_vpc_config(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "Environment":
            transformed = _transform_environment_variables(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "EphemeralStorage":
            transformed = _transform_ephemeral_storage(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "DeadLetterConfig":
            transformed = _transform_dead_letter_config(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "TracingConfig":
            transformed = _transform_tracing_config(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "ImageConfig":
            transformed = _transform_image_config(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "SnapStart":
            transformed = _transform_snap_start(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "LoggingConfig":
            transformed = _transform_logging_config(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in LAMBDA_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for Lambda functions
register_property_map("lambda:function", __name__)
register_property_map("lambda", __name__)
