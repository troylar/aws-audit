"""AWS CloudWatch to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# CloudWatch Alarm configurable properties that map to aws_cloudwatch_metric_alarm
ALARM_CONFIGURABLE = {
    "AlarmName": "alarm_name",
    "ComparisonOperator": "comparison_operator",
    "EvaluationPeriods": "evaluation_periods",
    "MetricName": "metric_name",
    "Namespace": "namespace",
    "Period": "period",
    "Statistic": "statistic",
    "Threshold": "threshold",
    "AlarmActions": "alarm_actions",
    "Dimensions": "dimensions",
    "Tags": "tags",
}

# CloudWatch Alarm computed/read-only properties
ALARM_COMPUTED = {
    "AlarmArn": "arn",
    "StateUpdatedTimestamp": "state_updated_timestamp",
}

# Log Group configurable properties that map to aws_cloudwatch_log_group
LOG_GROUP_CONFIGURABLE = {
    "LogGroupName": "name",
    "RetentionInDays": "retention_in_days",
    "KmsKeyId": "kms_key_id",
    "Tags": "tags",
}

# Log Group computed/read-only properties
LOG_GROUP_COMPUTED = {
    "Arn": "arn",
    "CreationTime": "creation_time",
}


def _transform_dimensions(
    dimensions: Optional[list],
) -> Optional[list]:
    """Transform dimensions to Terraform format.

    Args:
        dimensions: List of AWS dimension dicts with Name and Value keys

    Returns:
        List of Terraform-formatted dimension dicts or None if empty
    """
    if not dimensions:
        return None

    result = []
    for dimension in dimensions:
        if isinstance(dimension, dict):
            tf_dim = {}
            if "Name" in dimension:
                tf_dim["name"] = dimension["Name"]
            if "Value" in dimension:
                tf_dim["value"] = dimension["Value"]
            if tf_dim:
                result.append(tf_dim)

    return result if result else None


def get_alarm_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform CloudWatch Alarm properties for Terraform.

    This helper transforms AWS CloudWatch Alarm configuration into
    Terraform-compatible format, handling special cases for nested structures.

    Args:
        raw_config: Raw CloudWatch Alarm configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_cloudwatch_metric_alarm resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in ALARM_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "Dimensions":
            transformed = _transform_dimensions(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in ALARM_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


def get_log_group_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform Log Group properties for Terraform.

    This helper transforms AWS CloudWatch Log Group configuration into
    Terraform-compatible format.

    Args:
        raw_config: Raw Log Group configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_cloudwatch_log_group resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in LOG_GROUP_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Simple pass-through for all properties
        if value is not None:
            properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in LOG_GROUP_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property maps for CloudWatch resources
register_property_map("cloudwatch:alarm", __name__)
register_property_map("cloudwatch:log_group", __name__)
register_property_map("cloudwatch", __name__)
