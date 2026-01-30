"""AWS EventBridge to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
EVENTBRIDGE_CONFIGURABLE = {
    "Name": "name",
    "ScheduleExpression": "schedule_expression",
    "EventPattern": "event_pattern",
    "State": "state",
    "Description": "description",
    "EventBusName": "event_bus_name",
    "Tags": "tags",
}

# Properties computed by AWS that are read-only
EVENTBRIDGE_COMPUTED = {
    "Arn": "arn",
    "RoleArn": "role_arn",
    "CreatedBy": "created_by",
    "CreationTime": "creation_time",
    "LastModifiedBy": "last_modified_by",
    "LastModifiedTime": "last_modified_time",
}


def _transform_event_pattern(event_pattern: Optional[Dict[str, Any]]) -> Optional[str]:
    """Transform event pattern to Terraform format.

    Args:
        event_pattern: AWS event pattern dict

    Returns:
        JSON string representation or None if empty
    """
    if not event_pattern:
        return None

    import json

    try:
        return json.dumps(event_pattern)
    except (TypeError, ValueError):
        return None


def get_eventbridge_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform EventBridge rule properties for Terraform.

    This helper transforms AWS EventBridge configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw EventBridge configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_cloudwatch_event_rule resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in EVENTBRIDGE_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "EventPattern":
            transformed = _transform_event_pattern(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in EVENTBRIDGE_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for EventBridge rules
register_property_map("events:rule", __name__)
register_property_map("events", __name__)
register_property_map("eventbridge:rule", __name__)
register_property_map("eventbridge", __name__)
