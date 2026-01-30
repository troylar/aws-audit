"""AWS ElastiCache to Terraform property mappings.

Maps AWS ElastiCache API response properties to Terraform resource properties
for both cache clusters and replication groups (Redis).
"""

from typing import Any, Dict, List

# ElastiCache Cluster configurable properties
# Maps AWS API field names to Terraform aws_elasticache_cluster argument names
ELASTICACHE_CLUSTER_CONFIGURABLE: Dict[str, str] = {
    "CacheClusterId": "cluster_id",
    "CacheNodeType": "node_type",
    "Engine": "engine",
    "EngineVersion": "engine_version",
    "NumCacheNodes": "num_cache_nodes",
    "CacheParameterGroupName": "parameter_group_name",
    "CacheSubnetGroupName": "subnet_group_name",
    "SecurityGroupIds": "security_group_ids",
    "Tags": "tags",
}

# ElastiCache Cluster computed/read-only properties
ELASTICACHE_CLUSTER_COMPUTED: Dict[str, str] = {
    "CacheClusterStatus": "cluster_status",
    "Address": "cluster_address",
    "Port": "port",
    "CacheClusterCreateTime": "create_time",
    "PreferredAvailabilityZone": "preferred_availability_zone",
    "NotificationConfiguration": "notification_configuration",
    "CacheSecurityGroups": "security_groups",
    "CacheParameterGroup": "parameter_group",
    "CacheSubnetGroup": "subnet_group",
    "CacheNodes": "cache_nodes",
    "AutomaticFailover": "automatic_failover",
    "MultiAZ": "multi_az",
    "ReplicationGroupId": "replication_group_id",
    "EngineVersion": "engine_version",
    "Engine": "engine",
}

# ElastiCache Replication Group configurable properties (for Redis)
# Maps AWS API field names to Terraform aws_elasticache_replication_group argument names
ELASTICACHE_REPLICATION_GROUP_CONFIGURABLE: Dict[str, str] = {
    "ReplicationGroupId": "replication_group_id",
    "ReplicationGroupDescription": "replication_group_description",
    "Engine": "engine",
    "EngineVersion": "engine_version",
    "CacheNodeType": "node_type",
    "AutomaticFailoverEnabled": "automatic_failover_enabled",
    "MultiAZEnabled": "multi_az_enabled",
    "NumCacheClusters": "num_cache_clusters",
    "PreferredCacheClusterAZs": "preferred_cache_cluster_azs",
    "CacheParameterGroupName": "parameter_group_name",
    "CacheSubnetGroupName": "subnet_group_name",
    "SecurityGroupIds": "security_group_ids",
    "NotificationTopicArn": "notification_topic_arn",
    "Tags": "tags",
    "Port": "port",
    "SnapShotRetentionLimit": "snapshot_retention_limit",
    "SnapShotWindow": "snapshot_window",
    "MaintenanceWindow": "maintenance_window",
    "AuthToken": "auth_token",
    "AtRestEncryptionEnabled": "at_rest_encryption_enabled",
    "TransitEncryptionEnabled": "transit_encryption_enabled",
    "KmsKeyId": "kms_key_id",
    "LogDeliveryConfigurations": "log_delivery_configuration",
}

# ElastiCache Replication Group computed/read-only properties
ELASTICACHE_REPLICATION_GROUP_COMPUTED: Dict[str, str] = {
    "ReplicationGroupArn": "arn",
    "Status": "status",
    "PendingModifiedValues": "pending_modified_values",
    "ConfigEndpoint": "configuration_endpoint_address",
    "PrimaryEndpoint": "primary_endpoint_address",
    "ReaderEndpoint": "reader_endpoint_address",
    "MemberClusters": "member_clusters",
    "NodeGroups": "node_groups",
    "SnapShotting": "snapshotting_enabled",
    "ReplicationGroupCreateTime": "create_time",
    "ClusterEnabled": "cluster_enabled",
}


def process_cache_nodes(raw_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform AWS cache nodes to Terraform format.

    AWS format:
    [
        {
            "CacheNodeId": "0001",
            "CacheNodeStatus": "available",
            "CacheNodeCreateTime": "2024-01-30T...",
            "Address": "node.abc123.ng.0001.use1.cache.amazonaws.com",
            "Port": 6379,
            "ParameterGroupStatus": "in-sync"
        }
    ]

    Args:
        raw_nodes: List of cache nodes from AWS

    Returns:
        List of transformed cache node configurations
    """
    if not raw_nodes:
        return []

    terraform_nodes = []
    for node in raw_nodes:
        tf_node = {
            "id": node.get("CacheNodeId"),
            "status": node.get("CacheNodeStatus"),
            "address": node.get("Address"),
            "port": node.get("Port"),
            "parameter_group_status": node.get("ParameterGroupStatus"),
        }
        terraform_nodes.append(tf_node)

    return terraform_nodes


def process_log_delivery_configurations(raw_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform AWS log delivery configurations to Terraform format.

    AWS format:
    [
        {
            "LogType": "slow-log",
            "DestinationType": "cloudwatch-logs",
            "DestinationDetails": {
                "CloudWatchLogsDetails": {
                    "LogGroup": "/aws/elasticache/redis/slow-log"
                }
            },
            "LogFormat": "json",
            "Enabled": true,
            "Status": "enabled"
        }
    ]

    Args:
        raw_configs: List of log delivery configurations from AWS

    Returns:
        List of transformed log delivery configurations
    """
    if not raw_configs:
        return []

    terraform_configs = []
    for config in raw_configs:
        tf_config = {
            "log_type": config.get("LogType"),
            "destination_type": config.get("DestinationType"),
            "log_format": config.get("LogFormat"),
            "enabled": config.get("Enabled", False),
        }

        # Handle destination details
        dest_details = config.get("DestinationDetails", {})
        if "CloudWatchLogsDetails" in dest_details:
            tf_config["destination"] = dest_details["CloudWatchLogsDetails"].get("LogGroup")
        elif "KinesisFirehoseDetails" in dest_details:
            tf_config["destination"] = dest_details["KinesisFirehoseDetails"].get("DeliveryStream")

        terraform_configs.append(tf_config)

    return terraform_configs


def process_node_groups(raw_node_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform AWS node groups to Terraform format.

    Args:
        raw_node_groups: List of node groups from AWS

    Returns:
        List of transformed node group configurations
    """
    if not raw_node_groups:
        return []

    terraform_groups = []
    for group in raw_node_groups:
        tf_group = {
            "node_group_id": group.get("NodeGroupId"),
            "node_group_status": group.get("Status"),
            "num_cache_nodes": len(group.get("NodeGroupMembers", [])),
            "slots": group.get("Slots"),
        }

        # Process member nodes
        if "NodeGroupMembers" in group:
            members = []
            for member in group["NodeGroupMembers"]:
                members.append(
                    {
                        "cache_node_id": member.get("CacheNodeId"),
                        "read_endpoint": member.get("ReadEndpoint", {}).get("Address"),
                        "read_endpoint_port": member.get("ReadEndpoint", {}).get("Port"),
                        "write_endpoint": member.get("WriteEndpoint", {}).get("Address"),
                        "write_endpoint_port": member.get("WriteEndpoint", {}).get("Port"),
                    }
                )
            tf_group["node_group_members"] = members

        terraform_groups.append(tf_group)

    return terraform_groups


def get_elasticache_cluster_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ElastiCache cluster properties from raw AWS config.

    Args:
        raw_config: Raw AWS ElastiCache cluster configuration from describe_cache_clusters

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    properties = {}

    # Extract configurable properties
    for aws_field, tf_field in ELASTICACHE_CLUSTER_CONFIGURABLE.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                if aws_field == "Tags" and isinstance(value, list):
                    # Convert list of tag objects to dict
                    tags_dict = {}
                    for tag in value:
                        tags_dict[tag.get("Key")] = tag.get("Value")
                    properties[tf_field] = tags_dict
                elif aws_field == "SecurityGroupIds" and isinstance(value, list):
                    # Extract IDs from security group objects or use directly
                    sg_ids = []
                    for sg in value:
                        if isinstance(sg, dict):
                            sg_ids.append(sg.get("GroupId"))
                        else:
                            sg_ids.append(sg)
                    properties[tf_field] = sg_ids
                else:
                    properties[tf_field] = value

    return properties


def get_elasticache_replication_group_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ElastiCache replication group properties from raw AWS config.

    Args:
        raw_config: Raw AWS ElastiCache replication group configuration from describe_replication_groups

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    properties = {}

    # Extract configurable properties
    for aws_field, tf_field in ELASTICACHE_REPLICATION_GROUP_CONFIGURABLE.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                if aws_field == "Tags" and isinstance(value, list):
                    # Convert list of tag objects to dict
                    tags_dict = {}
                    for tag in value:
                        tags_dict[tag.get("Key")] = tag.get("Value")
                    properties[tf_field] = tags_dict
                elif aws_field == "SecurityGroupIds" and isinstance(value, list):
                    # Extract IDs from security group objects or use directly
                    sg_ids = []
                    for sg in value:
                        if isinstance(sg, dict):
                            sg_ids.append(sg.get("GroupId"))
                        else:
                            sg_ids.append(sg)
                    properties[tf_field] = sg_ids
                elif aws_field == "LogDeliveryConfigurations" and isinstance(value, list):
                    log_configs = process_log_delivery_configurations(value)
                    if log_configs:
                        properties[tf_field] = log_configs
                else:
                    properties[tf_field] = value

    return properties


def get_elasticache_cluster_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed/read-only ElastiCache cluster properties from raw AWS config.

    Args:
        raw_config: Raw AWS ElastiCache cluster configuration

    Returns:
        Dictionary of read-only properties
    """
    computed = {}

    for aws_field, tf_field in ELASTICACHE_CLUSTER_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                # Handle cache nodes
                if aws_field == "CacheNodes" and isinstance(value, list):
                    computed[tf_field] = process_cache_nodes(value)
                else:
                    computed[tf_field] = value

    return computed


def get_elasticache_replication_group_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed/read-only ElastiCache replication group properties from raw AWS config.

    Args:
        raw_config: Raw AWS ElastiCache replication group configuration

    Returns:
        Dictionary of read-only properties
    """
    computed = {}

    for aws_field, tf_field in ELASTICACHE_REPLICATION_GROUP_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                # Handle node groups
                if aws_field == "NodeGroups" and isinstance(value, list):
                    computed[tf_field] = process_node_groups(value)
                else:
                    computed[tf_field] = value

    return computed


# Register this property map for ElastiCache resources
from . import register_property_map

register_property_map(
    "elasticache",
    {
        "cluster": {
            "configurable": ELASTICACHE_CLUSTER_CONFIGURABLE,
            "computed": ELASTICACHE_CLUSTER_COMPUTED,
            "get_properties": get_elasticache_cluster_properties,
            "get_computed": get_elasticache_cluster_computed_properties,
        },
        "replication_group": {
            "configurable": ELASTICACHE_REPLICATION_GROUP_CONFIGURABLE,
            "computed": ELASTICACHE_REPLICATION_GROUP_COMPUTED,
            "get_properties": get_elasticache_replication_group_properties,
            "get_computed": get_elasticache_replication_group_computed_properties,
        },
    },
)

__all__ = [
    "ELASTICACHE_CLUSTER_CONFIGURABLE",
    "ELASTICACHE_CLUSTER_COMPUTED",
    "ELASTICACHE_REPLICATION_GROUP_CONFIGURABLE",
    "ELASTICACHE_REPLICATION_GROUP_COMPUTED",
    "get_elasticache_cluster_properties",
    "get_elasticache_replication_group_properties",
    "get_elasticache_cluster_computed_properties",
    "get_elasticache_replication_group_computed_properties",
    "process_cache_nodes",
    "process_log_delivery_configurations",
    "process_node_groups",
]
