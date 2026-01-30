"""AWS EC2 to Terraform property mappings."""

from typing import Any, Dict

from . import register_property_map

# EC2 Instance properties that can be configured in Terraform
EC2_INSTANCE_CONFIGURABLE: Dict[str, str] = {
    "InstanceType": "instance_type",
    "SubnetId": "subnet_id",
    "KeyName": "key_name",
    "SecurityGroupIds": "vpc_security_group_ids",
    "SecurityGroups": "security_groups",
    "DisableApiTermination": "disable_api_termination",
    "EbsOptimized": "ebs_optimized",
    "Monitoring": "monitoring",
    "IamInstanceProfile": "iam_instance_profile",
    "UserData": "user_data",
    "SourceDestCheck": "source_dest_check",
    "Tenancy": "tenancy",
    "HostId": "host_id",
    "Affinity": "affinity",
    "SpreadDomain": "spread_domain",
    "HostResourceGroupArn": "host_resource_group_arn",
    "CpuOptions": "cpu_options",
    "EnclaveOptions": "enclave_options",
    "MetadataOptions": "metadata_options",
    "Tags": "tags",
    "RootBlockDevice": "root_block_device",
    "EbsBlockDevice": "ebs_block_device",
    "EphemeralBlockDevice": "ephemeral_block_device",
    "VpcSecurityGroupIds": "vpc_security_group_ids",
    "PrivateIpAddress": "private_ip",
    "SecondaryPrivateIpAddresses": "secondary_private_ips",
    "AssociatePublicIpAddress": "associate_public_ip_address",
    "NetworkInterface": "network_interface",
    "CreditSpecification": "credit_specification",
    "HibernationOptions": "hibernation_options",
    "MaintenanceOptions": "maintenance_options",
    "PrivateDnsNameOptions": "private_dns_name_options",
}

# EC2 Instance properties that are read-only (computed) and should be omitted
EC2_INSTANCE_COMPUTED: set = {
    "InstanceId",
    "State",
    "PublicIpAddress",
    "PrivateIpAddress",
    "Ipv6Addresses",
    "PublicDnsName",
    "PrivateDnsName",
    "LaunchTime",
    "Placement",
    "KernelId",
    "RamdiskId",
    "Platform",
    "Monitoring",
    "SubnetId",
    "VpcId",
    "PrivateIpAddress",
    "SecurityGroups",
    "SourceDestCheck",
    "GroupSet",
    "Architecture",
    "RootDeviceName",
    "RootDeviceType",
    "BlockDeviceMappings",
    "VirtualizationType",
    "ClientToken",
    "TagSet",
    "AmiLaunchIndex",
    "ReservationId",
    "OwnerId",
    "Requester",
    "SpotInstanceRequestId",
    "License",
    "EnaSupport",
    "SriovNetSupport",
    "PrimaryNetworkInterface",
    "NetworkInterfaces",
    "IamInstanceProfile",
    "EbsOptimized",
    "StateReason",
    "StateTransitionReason",
    "CapacityReservationId",
    "CapacityReservationSpecification",
    "HibernationOptions",
    "MetadataOptions",
    "EnclaveOptions",
    "BootMode",
    "PlatformDetails",
    "UsageOperation",
    "UsageOperationUpdateTime",
    "PrivateDnsNameOptions",
    "Ipv6Native",
    "CurrentInstanceBootMode",
    "SecurityGroupIds",
    "VirtualizationType",
}


def get_ec2_instance_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and transform EC2 instance properties for Terraform.

    Converts AWS API properties to Terraform argument names (snake_case)
    and omits computed/read-only properties.

    Args:
        raw_config: Raw EC2 instance configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in EC2_INSTANCE_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in EC2_INSTANCE_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    return terraform_config


# Register this property map for EC2 resources
register_property_map(
    "ec2",
    {
        "instance": {
            "configurable": EC2_INSTANCE_CONFIGURABLE,
            "computed": EC2_INSTANCE_COMPUTED,
            "get_properties": get_ec2_instance_properties,
        },
    },
)

__all__ = [
    "EC2_INSTANCE_CONFIGURABLE",
    "EC2_INSTANCE_COMPUTED",
    "get_ec2_instance_properties",
]
