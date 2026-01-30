"""AWS EFS to Terraform property mappings.

Maps AWS EFS API response properties to Terraform resource properties
for EFS file systems.
"""

from typing import Any, Dict, List

# EFS File System configurable properties
# Maps AWS API field names to Terraform aws_efs_file_system argument names
EFS_FILESYSTEM_CONFIGURABLE: Dict[str, str] = {
    "CreationToken": "creation_token",
    "PerformanceMode": "performance_mode",
    "ThroughputMode": "throughput_mode",
    "ProvisionedThroughputInMibps": "provisioned_throughput_in_mibps",
    "Encrypted": "encrypted",
    "KmsKeyId": "kms_key_id",
    "Tags": "tags",
}

# EFS File System computed/read-only properties
EFS_FILESYSTEM_COMPUTED: Dict[str, str] = {
    "FileSystemId": "id",
    "OwnerId": "owner_id",
    "CreationTime": "creation_time",
    "FileSystemArn": "arn",
    "SizeInBytes": "size_in_bytes",
    "NumberOfMountTargets": "number_of_mount_targets",
    "LifeCycleState": "lifecycle_state",
    "PerformanceMode": "performance_mode",
    "ThroughputMode": "throughput_mode",
    "ProvisionedThroughputInMibps": "provisioned_throughput_in_mibps",
    "Encrypted": "encrypted",
    "KmsKeyId": "kms_key_id",
}


def process_lifecycle_policies(raw_policies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform AWS lifecycle policies to Terraform format.

    AWS LifecyclePolicies format:
    [
        {
            "TransitionToIA": "AFTER_30_DAYS",
            "TransitionToPrimaryStorageClass": "AFTER_1_DAY"
        }
    ]

    Terraform format expects lifecycle_policy blocks with:
    - transition_to_ia
    - transition_to_primary_storage_class

    Args:
        raw_policies: List of lifecycle policies from AWS API

    Returns:
        List of transformed lifecycle policy configurations
    """
    if not raw_policies:
        return []

    terraform_policies = []
    for policy in raw_policies:
        tf_policy = {}

        if "TransitionToIA" in policy:
            tf_policy["transition_to_ia"] = policy["TransitionToIA"]

        if "TransitionToPrimaryStorageClass" in policy:
            tf_policy["transition_to_primary_storage_class"] = policy["TransitionToPrimaryStorageClass"]

        if tf_policy:
            terraform_policies.append(tf_policy)

    return terraform_policies


def get_efs_filesystem_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract EFS file system properties from raw AWS config.

    Args:
        raw_config: Raw AWS EFS file system configuration from describe_file_systems

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    properties = {}

    # Extract configurable properties
    for aws_field, tf_field in EFS_FILESYSTEM_CONFIGURABLE.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                if aws_field == "Tags" and isinstance(value, list):
                    # Convert list of tag objects to dict
                    tags_dict = {}
                    for tag in value:
                        tags_dict[tag.get("Key")] = tag.get("Value")
                    properties[tf_field] = tags_dict
                else:
                    properties[tf_field] = value

    # Handle lifecycle policies if present
    if "LifecyclePolicies" in raw_config:
        lifecycle_policies = process_lifecycle_policies(raw_config.get("LifecyclePolicies", []))
        if lifecycle_policies:
            properties["lifecycle_policy"] = lifecycle_policies

    return properties


def get_efs_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed/read-only EFS properties from raw AWS config.

    Args:
        raw_config: Raw AWS EFS file system configuration

    Returns:
        Dictionary of read-only properties
    """
    computed = {}

    for aws_field, tf_field in EFS_FILESYSTEM_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                # Handle SizeInBytes which is a complex object
                if aws_field == "SizeInBytes" and isinstance(value, dict):
                    computed[tf_field] = {
                        "value": value.get("Value"),
                        "timestamp": value.get("Timestamp"),
                    }
                else:
                    computed[tf_field] = value

    return computed


# Register this property map for EFS resources
from . import register_property_map

register_property_map(
    "efs",
    {
        "file_system": {
            "configurable": EFS_FILESYSTEM_CONFIGURABLE,
            "computed": EFS_FILESYSTEM_COMPUTED,
            "get_properties": get_efs_filesystem_properties,
            "get_computed": get_efs_computed_properties,
        },
    },
)

__all__ = [
    "EFS_FILESYSTEM_CONFIGURABLE",
    "EFS_FILESYSTEM_COMPUTED",
    "get_efs_filesystem_properties",
    "get_efs_computed_properties",
    "process_lifecycle_policies",
]
