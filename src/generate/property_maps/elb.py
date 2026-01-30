"""AWS ELB to Terraform property mappings.

Maps AWS ELB API response properties to Terraform resource properties
for Application Load Balancers (ALB), Network Load Balancers (NLB),
target groups, and listeners.
"""

from typing import Any, Dict, Optional

# ALB/NLB Load Balancer configurable properties
# Maps AWS API field names to Terraform aws_lb argument names
ALB_NLB_CONFIGURABLE: Dict[str, str] = {
    "Name": "name",
    "Subnets": "subnets",
    "SecurityGroups": "security_groups",
    "Scheme": "internal",  # Maps to internal boolean (true if Scheme == "internal")
    "Type": "load_balancer_type",
    "IpAddressType": "ip_address_type",
    "Tags": "tags",
    "LoadBalancerAttributes": "enable_deletion_protection",  # Complex object
    "AvailabilityZones": "availability_zones",
}

# ALB/NLB Load Balancer computed/read-only properties
ALB_NLB_COMPUTED: set = {
    "LoadBalancerArn",
    "LoadBalancerName",
    "VpcId",
    "State",
    "CreatedTime",
    "CanonicalHostedZoneId",
    "DNSName",
}

# Target Group configurable properties
# Maps AWS API field names to Terraform aws_lb_target_group argument names
TARGET_GROUP_CONFIGURABLE: Dict[str, str] = {
    "Name": "name",
    "Port": "port",
    "Protocol": "protocol",
    "VpcId": "vpc_id",
    "TargetType": "target_type",
    "HealthCheckPath": "health_check",  # Complex nested block
    "HealthCheckProtocol": "health_check",
    "HealthCheckIntervalSeconds": "health_check",
    "HealthCheckTimeoutSeconds": "health_check",
    "HealthyThresholdCount": "health_check",
    "UnhealthyThresholdCount": "health_check",
    "Matcher": "health_check",
    "TargetGroupAttributes": "stickiness",  # Complex nested block
    "Tags": "tags",
}

# Target Group computed/read-only properties
TARGET_GROUP_COMPUTED: set = {
    "TargetGroupArn",
    "TargetGroupName",
    "CreatedTime",
    "LoadBalancerArns",
}

# Listener configurable properties
# Maps AWS API field names to Terraform aws_lb_listener argument names
LISTENER_CONFIGURABLE: Dict[str, str] = {
    "LoadBalancerArn": "load_balancer_arn",
    "Port": "port",
    "Protocol": "protocol",
    "DefaultActions": "default_action",  # Complex nested block
    "SslPolicy": "ssl_policy",
    "CertificateArn": "certificate_arn",
    "AlpnPolicy": "alpn_policy",
    "Tags": "tags",
}

# Listener computed/read-only properties
LISTENER_COMPUTED: set = {
    "ListenerArn",
}


def _parse_scheme_to_internal(scheme: Optional[str]) -> bool:
    """Convert AWS Scheme to Terraform internal boolean.

    Args:
        scheme: AWS scheme value ("internet-facing" or "internal")

    Returns:
        Boolean where True means internal (private) load balancer
    """
    if not scheme:
        return False
    return scheme.lower() == "internal"


def _extract_health_check_block(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract health check configuration into Terraform block format.

    Args:
        raw_config: Raw target group configuration from AWS API

    Returns:
        Dictionary with health_check block properties, or None if not configured
    """
    health_check = {}

    if "HealthCheckPath" in raw_config:
        health_check["path"] = raw_config["HealthCheckPath"]

    if "HealthCheckProtocol" in raw_config:
        health_check["protocol"] = raw_config["HealthCheckProtocol"]

    if "HealthCheckIntervalSeconds" in raw_config:
        health_check["interval"] = raw_config["HealthCheckIntervalSeconds"]

    if "HealthCheckTimeoutSeconds" in raw_config:
        health_check["timeout"] = raw_config["HealthCheckTimeoutSeconds"]

    if "HealthyThresholdCount" in raw_config:
        health_check["healthy_threshold"] = raw_config["HealthyThresholdCount"]

    if "UnhealthyThresholdCount" in raw_config:
        health_check["unhealthy_threshold"] = raw_config["UnhealthyThresholdCount"]

    if "Matcher" in raw_config:
        matcher = raw_config["Matcher"]
        if isinstance(matcher, dict):
            if "HttpCode" in matcher:
                health_check["matcher"] = matcher["HttpCode"]
        elif isinstance(matcher, str):
            health_check["matcher"] = matcher

    return health_check if health_check else None


def _extract_stickiness_block(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract stickiness configuration from target group attributes.

    Args:
        raw_config: Raw target group configuration from AWS API

    Returns:
        Dictionary with stickiness block properties, or None if not configured
    """
    attributes = raw_config.get("TargetGroupAttributes", [])
    if not attributes:
        return None

    stickiness_config = {}

    for attr in attributes:
        if isinstance(attr, dict):
            key = attr.get("Key", "")
            value = attr.get("Value")

            if key == "stickiness.enabled":
                stickiness_config["enabled"] = value.lower() == "true" if value else False
            elif key == "stickiness.type":
                stickiness_config["type"] = value
            elif key == "stickiness.lb_cookie.duration_seconds":
                stickiness_config["cookie_duration"] = int(value) if value else 86400
            elif key == "stickiness.app_cookie.cookie_name":
                stickiness_config["cookie_name"] = value

    return stickiness_config if stickiness_config else None


def _extract_default_actions_block(
    raw_config: Dict[str, Any],
) -> Optional[list[Dict[str, Any]]]:
    """Extract default actions configuration into Terraform block format.

    Args:
        raw_config: Raw listener configuration from AWS API

    Returns:
        List of default_action blocks, or None if not configured
    """
    actions = raw_config.get("DefaultActions", [])
    if not actions:
        return None

    default_actions = []

    for action in actions:
        if isinstance(action, dict):
            action_block = {}

            if "Type" in action:
                action_block["type"] = action["Type"]

            if "TargetGroupArn" in action:
                action_block["target_group_arn"] = action["TargetGroupArn"]

            if "RedirectConfig" in action:
                redirect = action["RedirectConfig"]
                action_block["redirect"] = {
                    "status_code": redirect.get("StatusCode"),
                    "protocol": redirect.get("Protocol"),
                    "host": redirect.get("Host"),
                    "path": redirect.get("Path"),
                    "query": redirect.get("Query"),
                }

            if "FixedResponseConfig" in action:
                fixed_response = action["FixedResponseConfig"]
                action_block["fixed_response"] = {
                    "status_code": fixed_response.get("StatusCode"),
                    "content_type": fixed_response.get("ContentType"),
                    "message_body": fixed_response.get("MessageBody"),
                }

            if action_block:
                default_actions.append(action_block)

    return default_actions if default_actions else None


def get_alb_nlb_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ALB/NLB load balancer properties from raw AWS config.

    Converts AWS API properties to Terraform argument names (snake_case)
    and handles special transformations (e.g., Scheme to internal boolean).

    Args:
        raw_config: Raw load balancer configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in ALB_NLB_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in ALB_NLB_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                # Special transformation for Scheme -> internal
                if aws_key == "Scheme":
                    terraform_config[tf_key] = _parse_scheme_to_internal(value)
                else:
                    terraform_config[tf_key] = value

    return terraform_config


def get_target_group_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract target group properties from raw AWS config.

    Converts AWS API properties to Terraform argument names (snake_case)
    and handles nested block conversions (health_check, stickiness).

    Args:
        raw_config: Raw target group configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in TARGET_GROUP_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in TARGET_GROUP_COMPUTED:
            value = raw_config[aws_key]
            if value is not None and tf_key not in ["health_check", "stickiness"]:
                terraform_config[tf_key] = value

    # Extract health_check as a nested block
    health_check = _extract_health_check_block(raw_config)
    if health_check:
        terraform_config["health_check"] = health_check

    # Extract stickiness as a nested block
    stickiness = _extract_stickiness_block(raw_config)
    if stickiness:
        terraform_config["stickiness"] = stickiness

    return terraform_config


def get_listener_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract listener properties from raw AWS config.

    Converts AWS API properties to Terraform argument names (snake_case)
    and handles nested default_action blocks.

    Args:
        raw_config: Raw listener configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in LISTENER_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in LISTENER_COMPUTED:
            value = raw_config[aws_key]
            if value is not None and tf_key != "default_action":
                terraform_config[tf_key] = value

    # Extract default_actions as nested blocks
    default_actions = _extract_default_actions_block(raw_config)
    if default_actions:
        terraform_config["default_action"] = default_actions

    return terraform_config


def _register_maps() -> None:
    """Register ELB property maps with the registry."""
    try:
        from . import register_property_map

        register_property_map(
            "elb:alb",
            {
                "configurable": ALB_NLB_CONFIGURABLE,
                "computed": ALB_NLB_COMPUTED,
                "get_properties": get_alb_nlb_properties,
            },
        )
        register_property_map(
            "elb:nlb",
            {
                "configurable": ALB_NLB_CONFIGURABLE,
                "computed": ALB_NLB_COMPUTED,
                "get_properties": get_alb_nlb_properties,
            },
        )
        register_property_map(
            "elb:target_group",
            {
                "configurable": TARGET_GROUP_CONFIGURABLE,
                "computed": TARGET_GROUP_COMPUTED,
                "get_properties": get_target_group_properties,
            },
        )
        register_property_map(
            "elb:listener",
            {
                "configurable": LISTENER_CONFIGURABLE,
                "computed": LISTENER_COMPUTED,
                "get_properties": get_listener_properties,
            },
        )
        register_property_map(
            "aws:lb",
            {
                "configurable": ALB_NLB_CONFIGURABLE,
                "computed": ALB_NLB_COMPUTED,
                "get_properties": get_alb_nlb_properties,
            },
        )
        register_property_map(
            "aws:lb_target_group",
            {
                "configurable": TARGET_GROUP_CONFIGURABLE,
                "computed": TARGET_GROUP_COMPUTED,
                "get_properties": get_target_group_properties,
            },
        )
        register_property_map(
            "aws:lb_listener",
            {
                "configurable": LISTENER_CONFIGURABLE,
                "computed": LISTENER_COMPUTED,
                "get_properties": get_listener_properties,
            },
        )
    except ImportError:
        # Registry not available yet, will be registered on import
        pass


# Auto-register on module import
_register_maps()

__all__ = [
    "ALB_NLB_CONFIGURABLE",
    "ALB_NLB_COMPUTED",
    "TARGET_GROUP_CONFIGURABLE",
    "TARGET_GROUP_COMPUTED",
    "LISTENER_CONFIGURABLE",
    "LISTENER_COMPUTED",
    "get_alb_nlb_properties",
    "get_target_group_properties",
    "get_listener_properties",
]
