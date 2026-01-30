"""AWS SNS to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
SNS_CONFIGURABLE = {
    "TopicName": "name",
    "DisplayName": "display_name",
    "KmsMasterKeyId": "kms_master_key_id",
    "Policy": "policy",
    "DeliveryPolicy": "delivery_policy",
    "FifoTopic": "fifo_topic",
    "ContentBasedDeduplication": "content_based_deduplication",
    "Tags": "tags",
}

# Properties computed by AWS that are read-only
SNS_COMPUTED = {
    "TopicArn": "arn",
    "Owner": "owner",
}


def _transform_policy(policy: Optional[str]) -> Optional[Dict[str, str]]:
    """Transform policy to Terraform format.

    Args:
        policy: AWS policy JSON string

    Returns:
        Terraform-formatted policy dict or None if empty
    """
    if not policy:
        return None

    return {"policy": policy}


def _transform_delivery_policy(delivery_policy: Optional[str]) -> Optional[Dict[str, str]]:
    """Transform delivery policy to Terraform format.

    Args:
        delivery_policy: AWS delivery policy JSON string

    Returns:
        Terraform-formatted delivery policy dict or None if empty
    """
    if not delivery_policy:
        return None

    return {"delivery_policy": delivery_policy}


def get_sns_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform SNS topic properties for Terraform.

    This helper transforms AWS SNS configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw SNS configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_sns_topic resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in SNS_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "Policy":
            transformed = _transform_policy(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "DeliveryPolicy":
            transformed = _transform_delivery_policy(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in SNS_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for SNS topics
register_property_map("sns:topic", __name__)
register_property_map("sns", __name__)
