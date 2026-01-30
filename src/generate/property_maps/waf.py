"""AWS WAFv2 to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
WAF_WEBACL_CONFIGURABLE = {
    "Name": "name",
    "Scope": "scope",
    "DefaultAction": "default_action",
    "Description": "description",
    "Rules": "rules",
    "VisibilityConfig": "visibility_config",
    "Tags": "tags",
}

# Properties computed by AWS that are read-only
WAF_WEBACL_COMPUTED = {
    "ARN": "arn",
    "Id": "id",
    "Capacity": "capacity",
}


def _transform_default_action(default_action: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform WAF default action to Terraform format.

    Args:
        default_action: AWS default action dict with Allow or Block key

    Returns:
        Terraform-formatted default action or None if empty
    """
    if not default_action:
        return None

    result = {}

    if "Allow" in default_action:
        result["allow"] = {}
        allow_config = default_action["Allow"]
        if allow_config and isinstance(allow_config, dict):
            if "CustomResponse" in allow_config:
                result["allow"]["custom_response"] = _transform_custom_response(allow_config["CustomResponse"])

    elif "Block" in default_action:
        result["block"] = {}
        block_config = default_action["Block"]
        if block_config and isinstance(block_config, dict):
            if "CustomResponse" in block_config:
                result["block"]["custom_response"] = _transform_custom_response(block_config["CustomResponse"])

    return result if result else None


def _transform_custom_response(custom_response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform WAF custom response to Terraform format.

    Args:
        custom_response: AWS custom response dict with ResponseCode and CustomResponseBodyKey

    Returns:
        Terraform-formatted custom response or None if empty
    """
    if not custom_response:
        return None

    result = {}

    if "ResponseCode" in custom_response:
        result["response_code"] = custom_response["ResponseCode"]

    if "CustomResponseBodyKey" in custom_response:
        result["custom_response_body_key"] = custom_response["CustomResponseBodyKey"]

    return result if result else None


def _transform_visibility_config(visibility_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform WAF visibility config to Terraform format.

    Args:
        visibility_config: AWS visibility config dict with SampledRequestsEnabled, CloudWatchLogsEnabled, MetricName

    Returns:
        Terraform-formatted visibility config or None if empty
    """
    if not visibility_config:
        return None

    result = {}

    if "SampledRequestsEnabled" in visibility_config:
        result["sampled_requests_enabled"] = visibility_config["SampledRequestsEnabled"]

    if "CloudWatchLogsEnabled" in visibility_config:
        result["cloudwatch_logs_enabled"] = visibility_config["CloudWatchLogsEnabled"]

    if "MetricName" in visibility_config:
        result["metric_name"] = visibility_config["MetricName"]

    return result if result else None


def _transform_rules(rules: Optional[list]) -> Optional[list]:
    """Transform WAF rules to Terraform format.

    Args:
        rules: AWS rules list with Name, Priority, Statement, Action, VisibilityConfig

    Returns:
        Terraform-formatted rules list or None if empty
    """
    if not rules:
        return None

    tf_rules = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue

        tf_rule = {}

        if "Name" in rule:
            tf_rule["name"] = rule["Name"]

        if "Priority" in rule:
            tf_rule["priority"] = rule["Priority"]

        if "Statement" in rule:
            tf_rule["statement"] = rule["Statement"]

        if "Action" in rule:
            action = rule["Action"]
            if isinstance(action, dict):
                tf_action = {}
                if "Block" in action:
                    tf_action["block"] = action["Block"]
                elif "Allow" in action:
                    tf_action["allow"] = action["Allow"]
                elif "Count" in action:
                    tf_action["count"] = action["Count"]
                if tf_action:
                    tf_rule["action"] = tf_action

        if "VisibilityConfig" in rule:
            visibility = _transform_visibility_config(rule["VisibilityConfig"])
            if visibility:
                tf_rule["visibility_config"] = visibility

        if tf_rule:
            tf_rules.append(tf_rule)

    return tf_rules if tf_rules else None


def _transform_tags(tags: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Transform WAF tags to Terraform format.

    Args:
        tags: AWS tags dict or list with key-value pairs

    Returns:
        Terraform-formatted tags dict or None if empty
    """
    if not tags:
        return None

    # Tags may be a direct key-value pairs dict
    if isinstance(tags, dict):
        # Check if it's already in the right format (string keys and values)
        is_simple_tags = all(isinstance(k, str) and isinstance(v, str) for k, v in tags.items())
        if is_simple_tags:
            return tags

    return None


def get_waf_webacl_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform WAFv2 WebACL properties for Terraform.

    This helper transforms AWS WAFv2 configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw WAFv2 WebACL configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_wafv2_web_acl resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in WAF_WEBACL_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special transformations
        if aws_field == "DefaultAction":
            transformed = _transform_default_action(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "VisibilityConfig":
            transformed = _transform_visibility_config(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "Rules":
            transformed = _transform_rules(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "Tags":
            transformed = _transform_tags(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in WAF_WEBACL_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for WAFv2 WebACLs
register_property_map("wafv2:web_acl", __name__)
register_property_map("wafv2", __name__)
register_property_map("waf", __name__)
