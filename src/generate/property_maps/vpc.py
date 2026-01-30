"""AWS VPC to Terraform property mappings."""

from typing import Any, Dict

from . import register_property_map

# VPC properties that can be configured in Terraform
VPC_CONFIGURABLE: Dict[str, str] = {
    "CidrBlock": "cidr_block",
    "EnableDnsHostnames": "enable_dns_hostnames",
    "EnableDnsSupport": "enable_dns_support",
    "InstanceTenancy": "instance_tenancy",
    "Ipv6CidrBlockNetworkBorderGroup": "ipv6_cidr_block_network_border_group",
    "AmazonProvidedIpv6CidrBlock": "assign_generated_ipv6_cidr_block",
    "Ipv6CidrBlock": "ipv6_cidr_block",
    "Tags": "tags",
}

# VPC properties that are read-only (computed) and should be omitted
VPC_COMPUTED: set = {
    "VpcId",
    "State",
    "OwnerId",
    "IsDefault",
    "Ipv6AssociationSet",
    "CidrBlockAssociationSet",
    "DhcpOptionsId",
    "DefaultNetworkAcl",
    "DefaultSecurityGroup",
}

# Subnet properties that can be configured in Terraform
SUBNET_CONFIGURABLE: Dict[str, str] = {
    "VpcId": "vpc_id",
    "CidrBlock": "cidr_block",
    "AvailabilityZone": "availability_zone",
    "AvailabilityZoneId": "availability_zone_id",
    "AssignIpv6AddressOnCreation": "assign_ipv6_address_on_creation",
    "Ipv6CidrBlockAssociationSet": "ipv6_cidr_block_association_id",
    "MapPublicIpOnLaunch": "map_public_ip_on_launch",
    "OutpostArn": "outpost_arn",
    "CustomerOwnedIpv4Pool": "customer_owned_ipv4_pool",
    "MapCustomerOwnedIpOnLaunch": "map_customer_owned_ip_on_launch",
    "Tags": "tags",
    "EnableDns64": "enable_dns64",
    "PrivateDnsNameOptionsOnLaunch": "private_dns_name_options_on_launch",
}

# Subnet properties that are read-only (computed) and should be omitted
SUBNET_COMPUTED: set = {
    "SubnetId",
    "State",
    "AvailableIpAddressCount",
    "AvailabilityZone",
    "AvailabilityZoneId",
    "Ipv6CidrBlockAssociationSet",
    "CustomerOwnedIpv4Pool",
    "DefaultForAz",
    "MapPublicIpOnLaunch",
    "OwnerId",
    "CidrBlock",
    "Ipv6Native",
}


def get_vpc_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and transform VPC properties for Terraform.

    Converts AWS API properties to Terraform argument names (snake_case)
    and omits computed/read-only properties.

    Args:
        raw_config: Raw VPC configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in VPC_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in VPC_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    return terraform_config


def get_subnet_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and transform Subnet properties for Terraform.

    Converts AWS API properties to Terraform argument names (snake_case)
    and omits computed/read-only properties.

    Args:
        raw_config: Raw Subnet configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in SUBNET_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in SUBNET_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    return terraform_config


# Register this property map for EC2 VPC and Subnet resources
register_property_map(
    "ec2:vpc",
    {
        "vpc": {
            "configurable": VPC_CONFIGURABLE,
            "computed": VPC_COMPUTED,
            "get_properties": get_vpc_properties,
        },
        "subnet": {
            "configurable": SUBNET_CONFIGURABLE,
            "computed": SUBNET_COMPUTED,
            "get_properties": get_subnet_properties,
        },
    },
)

__all__ = [
    "VPC_CONFIGURABLE",
    "VPC_COMPUTED",
    "SUBNET_CONFIGURABLE",
    "SUBNET_COMPUTED",
    "get_vpc_properties",
    "get_subnet_properties",
]
