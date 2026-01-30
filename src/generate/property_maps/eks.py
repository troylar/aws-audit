"""AWS EKS to Terraform property mappings.

Maps AWS EKS API response properties to Terraform resource properties
for EKS Clusters and Node Groups.
"""

from typing import Any, Dict

from . import register_property_map

# EKS Cluster configurable properties
EKS_CLUSTER_CONFIGURABLE: Dict[str, str] = {
    "Name": "name",
    "Version": "kubernetes_network_config",
    "RoleArn": "role_arn",
    "VpcConfig": "vpc_config",
    "Tags": "tags",
    "Logging": "enabled_cluster_log_types",
    "EncryptionConfig": "encryption_config",
    "EnabledClusterLogging": "enabled_cluster_log_types",
    "ResourcesVpcConfig": "vpc_config",
}

# EKS Cluster computed/read-only properties
EKS_CLUSTER_COMPUTED: Dict[str, str] = {
    "Name": "name",
    "Arn": "arn",
    "CreatedAt": "created_at",
    "Version": "version",
    "Endpoint": "endpoint",
    "RoleArn": "role_arn",
    "ResourcesVpcConfig": "vpc_config",
    "Logging": "logging",
    "Identity": "identity",
    "Status": "status",
    "CertificateAuthority": "certificate_authority",
    "PlatformVersion": "platform_version",
    "Tags": "tags",
    "EncryptionConfig": "encryption_config",
    "Connectors": "connectors",
}

# EKS Node Group configurable properties
EKS_NODE_GROUP_CONFIGURABLE: Dict[str, str] = {
    "NodegroupName": "name",
    "NodeRole": "node_role_arn",
    "Subnets": "subnet_ids",
    "InstanceTypes": "instance_types",
    "ScalingConfig": "scaling_config",
    "Labels": "labels",
    "Tags": "tags",
    "DiskSize": "disk_size",
    "RemoteAccess": "remote_access",
    "AmiType": "ami_type",
    "CapacityType": "capacity_type",
    "UpdateConfig": "update_config",
    "LaunchTemplate": "launch_template",
    "Taints": "taints",
}

# EKS Node Group computed/read-only properties
EKS_NODE_GROUP_COMPUTED: Dict[str, str] = {
    "NodegroupName": "name",
    "NodegroupArn": "arn",
    "ClusterName": "cluster_name",
    "Version": "version",
    "ReleaseVersion": "release_version",
    "CreatedAt": "created_at",
    "ModifiedAt": "modified_at",
    "Status": "status",
    "Resources": "resources",
    "NodeRole": "node_role_arn",
    "Labels": "labels",
    "DiskSize": "disk_size",
    "Health": "health",
    "InstanceTypes": "instance_types",
    "Subnets": "subnet_ids",
    "RemoteAccess": "remote_access",
    "AmiType": "ami_type",
    "NodeClass": "node_class",
    "Tags": "tags",
    "ScalingConfig": "scaling_config",
    "CapacityType": "capacity_type",
    "UpdateConfig": "update_config",
    "LaunchTemplate": "launch_template",
    "Taints": "taints",
    "PlatformVersion": "platform_version",
}


def get_eks_cluster_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract EKS Cluster properties from raw AWS config.

    Args:
        raw_config: Raw AWS EKS Cluster configuration from describe_cluster

    Returns:
        Dictionary with configurable Terraform properties
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in EKS_CLUSTER_CONFIGURABLE.items():
        if aws_key in raw_config:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    # Handle VpcConfig extraction (complex nested object)
    if "ResourcesVpcConfig" in raw_config:
        vpc_config = raw_config["ResourcesVpcConfig"]
        if isinstance(vpc_config, dict):
            terraform_config["vpc_config"] = {
                "subnet_ids": vpc_config.get("SubnetIds"),
                "security_group_ids": vpc_config.get("SecurityGroupIds"),
                "endpoint_private_access": vpc_config.get("EndpointPrivateAccess"),
                "endpoint_public_access": vpc_config.get("EndpointPublicAccess"),
            }

    return terraform_config


def get_eks_node_group_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract EKS Node Group properties from raw AWS config.

    Args:
        raw_config: Raw AWS EKS Node Group configuration from describe_nodegroup

    Returns:
        Dictionary with configurable Terraform properties
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in EKS_NODE_GROUP_CONFIGURABLE.items():
        if aws_key in raw_config:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    # Handle ScalingConfig extraction (complex nested object)
    if "ScalingConfig" in raw_config:
        scaling_config = raw_config["ScalingConfig"]
        if isinstance(scaling_config, dict):
            terraform_config["scaling_config"] = {
                "desired_size": scaling_config.get("DesiredSize"),
                "max_size": scaling_config.get("MaxSize"),
                "min_size": scaling_config.get("MinSize"),
            }

    return terraform_config


# Register EKS property maps with the registry
register_property_map(
    "eks:cluster",
    {
        "configurable": EKS_CLUSTER_CONFIGURABLE,
        "computed": EKS_CLUSTER_COMPUTED,
        "get_properties": get_eks_cluster_properties,
    },
)

register_property_map(
    "eks:node_group",
    {
        "configurable": EKS_NODE_GROUP_CONFIGURABLE,
        "computed": EKS_NODE_GROUP_COMPUTED,
        "get_properties": get_eks_node_group_properties,
    },
)

# Also register with AWS CloudFormation resource type names
register_property_map(
    "AWS::EKS::Cluster",
    {
        "configurable": EKS_CLUSTER_CONFIGURABLE,
        "computed": EKS_CLUSTER_COMPUTED,
    },
)

register_property_map(
    "AWS::EKS::NodeGroup",
    {
        "configurable": EKS_NODE_GROUP_CONFIGURABLE,
        "computed": EKS_NODE_GROUP_COMPUTED,
    },
)

__all__ = [
    "EKS_CLUSTER_CONFIGURABLE",
    "EKS_CLUSTER_COMPUTED",
    "EKS_NODE_GROUP_CONFIGURABLE",
    "EKS_NODE_GROUP_COMPUTED",
    "get_eks_cluster_properties",
    "get_eks_node_group_properties",
]
