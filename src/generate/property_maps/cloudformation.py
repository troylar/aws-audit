"""AWS CloudFormation to Terraform property mappings."""

from typing import Any, Dict, List, Optional

from . import register_property_map

# CloudFormation Stack configurable properties
CLOUDFORMATION_STACK_CONFIGURABLE = {
    "StackName": "name",
    "TemplateBody": "template_body",
    "TemplateURL": "template_url",
    "Parameters": "parameter",
    "Capabilities": "capabilities",
    "DisableRollback": "disable_rollback",
    "TimeoutInMinutes": "timeout_in_minutes",
    "Tags": "tags",
}

# CloudFormation Stack computed/read-only properties
CLOUDFORMATION_STACK_COMPUTED = {
    "StackId": "id",
    "StackStatus": "status",
    "CreationTime": "creation_time",
    "Outputs": "outputs",
}


def _transform_parameters(
    parameters: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """Transform stack parameters to Terraform format.

    Args:
        parameters: List of AWS parameter dicts with ParameterKey and ParameterValue

    Returns:
        List of Terraform-formatted parameter dicts or None if empty
    """
    if not parameters:
        return None

    result = []
    for param in parameters:
        tf_param = {}

        if "ParameterKey" in param:
            tf_param["key"] = param["ParameterKey"]

        if "ParameterValue" in param:
            tf_param["value"] = param["ParameterValue"]

        if "UsePreviousValue" in param:
            tf_param["use_previous_value"] = param["UsePreviousValue"]

        if tf_param:
            result.append(tf_param)

    return result if result else None


def _transform_outputs(
    outputs: Optional[List[Dict[str, Any]]],
) -> Optional[List[Dict[str, Any]]]:
    """Transform stack outputs to Terraform format.

    Args:
        outputs: List of AWS output dicts with OutputKey, OutputValue, etc.

    Returns:
        List of Terraform-formatted output dicts or None if empty
    """
    if not outputs:
        return None

    result = []
    for output in outputs:
        tf_output = {}

        if "OutputKey" in output:
            tf_output["key"] = output["OutputKey"]

        if "OutputValue" in output:
            tf_output["value"] = output["OutputValue"]

        if "Description" in output:
            tf_output["description"] = output["Description"]

        if "ExportName" in output:
            tf_output["export_name"] = output["ExportName"]

        if tf_output:
            result.append(tf_output)

    return result if result else None


def get_cloudformation_stack_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform CloudFormation stack properties for Terraform.

    Args:
        raw_config: Raw CloudFormation stack configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_cloudformation_stack resource
    """
    properties = {}

    for aws_field, tf_field in CLOUDFORMATION_STACK_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "Parameters":
            transformed = _transform_parameters(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in CLOUDFORMATION_STACK_COMPUTED.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations for computed fields
        if aws_field == "Outputs":
            transformed = _transform_outputs(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for computed properties
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for CloudFormation stacks
register_property_map("cloudformation:stack", __name__)
register_property_map("cloudformation", __name__)

__all__ = [
    "CLOUDFORMATION_STACK_CONFIGURABLE",
    "CLOUDFORMATION_STACK_COMPUTED",
    "get_cloudformation_stack_properties",
]
