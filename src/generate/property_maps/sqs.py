"""AWS SQS to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
SQS_CONFIGURABLE = {
    "QueueName": "name",
    "DelaySeconds": "delay_seconds",
    "MaximumMessageSize": "max_message_size",
    "MessageRetentionPeriod": "message_retention_seconds",
    "ReceiveMessageWaitTimeSeconds": "receive_wait_time_seconds",
    "VisibilityTimeout": "visibility_timeout_seconds",
    "FifoQueue": "fifo_queue",
    "ContentBasedDeduplication": "content_based_deduplication",
    "KmsMasterKeyId": "kms_master_key_id",
    "Policy": "policy",
    "RedrivePolicy": "redrive_policy",
    "Tags": "tags",
}

# Properties computed by AWS that are read-only
SQS_COMPUTED = {
    "QueueArn": "arn",
    "QueueUrl": "url",
    "ApproximateNumberOfMessages": "approximate_number_of_messages",
    "ApproximateNumberOfMessagesDelayed": "approximate_number_of_messages_delayed",
    "ApproximateNumberOfMessagesNotVisible": "approximate_number_of_messages_not_visible",
    "CreatedTimestamp": "created_timestamp",
    "LastModifiedTimestamp": "last_modified_timestamp",
}


def _transform_redrive_policy(redrive_policy: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Transform redrive policy to Terraform format.

    Args:
        redrive_policy: AWS redrive policy dict with deadLetterTargetArn and maxReceiveCount

    Returns:
        Terraform-formatted redrive policy dict or None if empty
    """
    if not redrive_policy:
        return None

    result = {}

    if "deadLetterTargetArn" in redrive_policy:
        result["dead_letter_target_arn"] = redrive_policy["deadLetterTargetArn"]

    if "maxReceiveCount" in redrive_policy:
        result["max_receive_count"] = redrive_policy["maxReceiveCount"]

    return result if result else None


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


def get_sqs_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform SQS queue properties for Terraform.

    This helper transforms AWS SQS configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw SQS configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_sqs_queue resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in SQS_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "RedrivePolicy":
            transformed = _transform_redrive_policy(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "Policy":
            transformed = _transform_policy(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in SQS_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for SQS queues
register_property_map("sqs:queue", __name__)
register_property_map("sqs", __name__)
