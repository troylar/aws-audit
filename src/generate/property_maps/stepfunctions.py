"""AWS Step Functions to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
STEPFUNCTIONS_CONFIGURABLE = {
    "Name": "name",
    "Definition": "definition",
    "RoleArn": "role_arn",
    "Type": "type",
    "LoggingConfiguration": "logging_configuration",
    "TracingConfiguration": "tracing_configuration",
    "Tags": "tags",
}

# Properties computed by AWS that are read-only
STEPFUNCTIONS_COMPUTED = {
    "StateMachineArn": "arn",
    "CreationDate": "creation_date",
    "Status": "status",
}


def _transform_definition(definition: Optional[str]) -> Optional[str]:
    """Transform definition to Terraform format.

    Args:
        definition: AWS state machine definition JSON string

    Returns:
        JSON string representation or None if empty
    """
    if not definition:
        return None

    return definition


def _transform_logging_configuration(
    logging_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Transform logging configuration to Terraform format.

    Args:
        logging_config: AWS logging configuration dict with Destinations and LoggingLevelConfig

    Returns:
        Terraform-formatted logging config dict or None if empty
    """
    if not logging_config:
        return None

    result = {}

    # Handle Destinations (list of log destinations)
    if "Destinations" in logging_config:
        destinations = logging_config["Destinations"]
        if destinations:
            transformed_destinations = []
            for dest in destinations:
                tf_dest = {}
                if "CloudWatchLogsLogGroup" in dest:
                    tf_dest["cloudwatch_logs_log_group"] = {
                        "log_group_arn": dest["CloudWatchLogsLogGroup"].get("LogGroupArn")
                    }
                transformed_destinations.append(tf_dest)
            if transformed_destinations:
                result["log_destinations"] = transformed_destinations

    # Handle LoggingLevelConfig
    if "LoggingLevelConfig" in logging_config:
        level_config = logging_config["LoggingLevelConfig"]
        if level_config:
            result["log_level"] = level_config.get("Level", "ERROR")
            if level_config.get("IncludeExecutionData"):
                result["include_execution_data"] = True

    return result if result else None


def _transform_tracing_configuration(
    tracing_config: Optional[Dict[str, Any]],
) -> Optional[Dict[str, bool]]:
    """Transform tracing configuration to Terraform format.

    Args:
        tracing_config: AWS tracing configuration dict with Enabled key

    Returns:
        Terraform-formatted tracing config dict or None if empty
    """
    if not tracing_config:
        return None

    result = {}

    if "Enabled" in tracing_config:
        result["enabled"] = tracing_config["Enabled"]

    return result if result else None


def get_stepfunctions_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform Step Functions state machine properties for Terraform.

    This helper transforms AWS Step Functions configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw Step Functions configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_sfn_state_machine resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in STEPFUNCTIONS_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "Definition":
            transformed = _transform_definition(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "LoggingConfiguration":
            transformed = _transform_logging_configuration(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "TracingConfiguration":
            transformed = _transform_tracing_configuration(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in STEPFUNCTIONS_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for Step Functions state machines
register_property_map("stepfunctions:statemachine", __name__)
register_property_map("stepfunctions", __name__)
register_property_map("sfn:statemachine", __name__)
register_property_map("sfn", __name__)
