"""AWS VPC Endpoints to Terraform property mappings.

Maps AWS VPC Endpoints API response properties to Terraform resource properties
for VPC endpoints.
"""

from typing import Any, Dict, Optional, Union

# VPC Endpoint configurable properties
# Maps AWS API field names to Terraform aws_vpc_endpoint argument names
VPC_ENDPOINT_CONFIGURABLE: Dict[str, str] = {
    "ServiceName": "service_name",
    "VpcId": "vpc_id",
    "VpcEndpointType": "vpc_endpoint_type",
    "SubnetIds": "subnet_ids",
    "SecurityGroupIds": "security_group_ids",
    "PrivateDnsEnabled": "private_dns_enabled",
    "PolicyDocument": "policy",
    "RouteTableIds": "route_table_ids",
    "Tags": "tags",
}

# VPC Endpoint computed/read-only properties
VPC_ENDPOINT_COMPUTED: set = {
    "VpcEndpointId",
    "State",
    "CreationTimestamp",
    "DnsEntries",
    "DnsOptions",
    "NetworkInterfaceIds",
    "OwnerId",
    "VpcEndpointArn",
    "LastError",
    "TagSet",
    "PrivateDnsNameOptions",
}


def _parse_policy_document(policy_doc: Any) -> Optional[Union[Dict[str, Any], str]]:
    """Parse policy document from AWS API response.

    AWS returns the policy as either a string (JSON) or already parsed dict.
    Terraform expects it as a JSON string.

    Args:
        policy_doc: Policy document from AWS API (string or dict)

    Returns:
        Policy as string or dict suitable for Terraform, or None
    """
    if not policy_doc:
        return None

    if isinstance(policy_doc, str):
        return policy_doc
    elif isinstance(policy_doc, dict):
        return policy_doc

    return None


def _extract_security_group_ids(raw_config: Dict[str, Any]) -> Optional[list[str]]:
    """Extract security group IDs from raw config.

    AWS API returns security groups in different formats depending on endpoint type.
    Gateway endpoints don't have security groups, interface endpoints do.

    Args:
        raw_config: Raw VPC endpoint configuration from AWS API

    Returns:
        List of security group IDs, or None if not present
    """
    # Try direct SecurityGroupIds
    if "SecurityGroupIds" in raw_config:
        sg_ids = raw_config["SecurityGroupIds"]
        if isinstance(sg_ids, list):
            return sg_ids

    # Try Groups (alternative field name)
    if "Groups" in raw_config:
        groups = raw_config["Groups"]
        if isinstance(groups, list):
            sg_ids = []
            for group in groups:
                if isinstance(group, dict) and "GroupId" in group:
                    sg_ids.append(group["GroupId"])
                elif isinstance(group, str):
                    sg_ids.append(group)
            return sg_ids if sg_ids else None

    return None


def _extract_subnet_ids(raw_config: Dict[str, Any]) -> Optional[list[str]]:
    """Extract subnet IDs from raw config.

    Interface endpoints require subnet IDs; gateway endpoints don't use them.

    Args:
        raw_config: Raw VPC endpoint configuration from AWS API

    Returns:
        List of subnet IDs, or None if not present
    """
    if "SubnetIds" in raw_config:
        subnet_ids = raw_config["SubnetIds"]
        if isinstance(subnet_ids, list):
            return subnet_ids

    return None


def _extract_route_table_ids(raw_config: Dict[str, Any]) -> Optional[list[str]]:
    """Extract route table IDs from raw config.

    Gateway endpoints use route tables; interface endpoints don't.

    Args:
        raw_config: Raw VPC endpoint configuration from AWS API

    Returns:
        List of route table IDs, or None if not present
    """
    if "RouteTableIds" in raw_config:
        route_table_ids = raw_config["RouteTableIds"]
        if isinstance(route_table_ids, list):
            return route_table_ids

    return None


def _parse_private_dns_enabled(raw_config: Dict[str, Any]) -> Optional[bool]:
    """Extract private DNS enabled flag from raw config.

    Handles both direct PrivateDnsEnabled flag and nested PrivateDnsNameOptions.

    Args:
        raw_config: Raw VPC endpoint configuration from AWS API

    Returns:
        Boolean indicating if private DNS is enabled, or None
    """
    # Check direct flag
    if "PrivateDnsEnabled" in raw_config:
        value = raw_config["PrivateDnsEnabled"]
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() == "true"

    # Check nested options
    dns_options = raw_config.get("PrivateDnsNameOptions")
    if isinstance(dns_options, dict):
        if "PrivateDnsOnlyForInboundResolverEndpoint" in dns_options:
            value = dns_options["PrivateDnsOnlyForInboundResolverEndpoint"]
            if isinstance(value, bool):
                return value

    return None


def _get_endpoint_type(raw_config: Dict[str, Any]) -> Optional[str]:
    """Determine VPC endpoint type (Interface, Gateway, or GatewayLoadBalancer).

    Args:
        raw_config: Raw VPC endpoint configuration from AWS API

    Returns:
        Endpoint type string, or None if not determined
    """
    if "VpcEndpointType" in raw_config:
        return raw_config["VpcEndpointType"]

    # Infer type from presence of certain fields
    # Gateway endpoints have RouteTableIds, interface endpoints have SubnetIds
    if "RouteTableIds" in raw_config and raw_config.get("RouteTableIds"):
        return "Gateway"
    elif "SubnetIds" in raw_config and raw_config.get("SubnetIds"):
        return "Interface"

    return None


def get_vpc_endpoint_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract VPC endpoint properties from raw AWS config.

    Converts AWS API properties to Terraform argument names (snake_case)
    and handles type-specific properties (gateway vs interface endpoints).

    Args:
        raw_config: Raw VPC endpoint configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    # Extract basic configurable properties
    for aws_key, tf_key in VPC_ENDPOINT_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in VPC_ENDPOINT_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                # Handle special cases
                if aws_key == "PrivateDnsEnabled":
                    parsed_value = _parse_private_dns_enabled(raw_config)
                    if parsed_value is not None:
                        terraform_config[tf_key] = parsed_value
                elif aws_key == "PolicyDocument":
                    parsed_value = _parse_policy_document(value)
                    if parsed_value is not None:
                        terraform_config[tf_key] = parsed_value
                elif tf_key not in ["subnet_ids", "security_group_ids", "route_table_ids"]:
                    terraform_config[tf_key] = value

    # Extract security group IDs with special handling
    sg_ids = _extract_security_group_ids(raw_config)
    if sg_ids:
        terraform_config["security_group_ids"] = sg_ids

    # Extract subnet IDs with special handling
    subnet_ids = _extract_subnet_ids(raw_config)
    if subnet_ids:
        terraform_config["subnet_ids"] = subnet_ids

    # Extract route table IDs with special handling
    rt_ids = _extract_route_table_ids(raw_config)
    if rt_ids:
        terraform_config["route_table_ids"] = rt_ids

    # Ensure PrivateDnsEnabled is set correctly if not already set
    if "private_dns_enabled" not in terraform_config:
        dns_enabled = _parse_private_dns_enabled(raw_config)
        if dns_enabled is not None:
            terraform_config["private_dns_enabled"] = dns_enabled

    return terraform_config


def _register_maps() -> None:
    """Register VPC Endpoint property maps with the registry."""
    try:
        from . import register_property_map

        register_property_map(
            "ec2:vpc_endpoint",
            {
                "configurable": VPC_ENDPOINT_CONFIGURABLE,
                "computed": VPC_ENDPOINT_COMPUTED,
                "get_properties": get_vpc_endpoint_properties,
            },
        )
        register_property_map(
            "aws:vpc_endpoint",
            {
                "configurable": VPC_ENDPOINT_CONFIGURABLE,
                "computed": VPC_ENDPOINT_COMPUTED,
                "get_properties": get_vpc_endpoint_properties,
            },
        )
    except ImportError:
        # Registry not available yet, will be registered on import
        pass


# Auto-register on module import
_register_maps()

__all__ = [
    "VPC_ENDPOINT_CONFIGURABLE",
    "VPC_ENDPOINT_COMPUTED",
    "get_vpc_endpoint_properties",
]
