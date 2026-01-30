"""AWS ECS to Terraform property mappings.

Maps AWS ECS API response properties to Terraform resource properties
for ECS Clusters, Services, and Task Definitions.
"""

from typing import Any, Dict

from . import register_property_map

# ECS Cluster configurable properties
ECS_CLUSTER_CONFIGURABLE: Dict[str, str] = {
    "ClusterName": "name",
    "Configuration": "configuration",
    "Settings": "setting",
    "Tags": "tags",
}

# ECS Cluster computed/read-only properties
ECS_CLUSTER_COMPUTED: Dict[str, str] = {
    "ClusterArn": "arn",
    "ClusterName": "name",
    "Status": "status",
    "RegisteredContainerInstancesCount": "registered_container_instances_count",
    "RunningTasksCount": "running_tasks_count",
    "PendingTasksCount": "pending_tasks_count",
    "ActiveServicesCount": "active_services_count",
    "Statistics": "statistics",
    "Tags": "tags",
    "CreatedAt": "created_at",
}

# ECS Service configurable properties
ECS_SERVICE_CONFIGURABLE: Dict[str, str] = {
    "ServiceName": "name",
    "TaskDefinition": "task_definition",
    "DesiredCount": "desired_count",
    "LaunchType": "launch_type",
    "PlatformVersion": "platform_version",
    "SchedulingStrategy": "scheduling_strategy",
    "DeploymentConfiguration": "deployment_configuration",
    "NetworkConfiguration": "network_configuration",
    "LoadBalancers": "load_balancers",
    "Role": "role",
    "PropagateTags": "propagate_tags",
    "EnableEcsManagedTags": "enable_ecs_managed_tags",
    "ServiceRegistries": "service_registries",
    "PlacementConstraints": "placement_constraints",
    "PlacementStrategy": "placement_strategy",
    "Tags": "tags",
}

# ECS Service computed/read-only properties
ECS_SERVICE_COMPUTED: Dict[str, str] = {
    "ServiceArn": "arn",
    "ServiceName": "name",
    "ClusterArn": "cluster_arn",
    "Status": "status",
    "TaskDefinition": "task_definition",
    "DesiredCount": "desired_count",
    "RunningCount": "running_count",
    "PendingCount": "pending_count",
    "LaunchType": "launch_type",
    "PlatformVersion": "platform_version",
    "SchedulingStrategy": "scheduling_strategy",
    "DeploymentConfiguration": "deployment_configuration",
    "DeploymentController": "deployment_controller",
    "NetworkConfiguration": "network_configuration",
    "LoadBalancers": "load_balancers",
    "ServiceRegistries": "service_registries",
    "Role": "role",
    "Events": "events",
    "Deployments": "deployments",
    "PropagateTags": "propagate_tags",
    "EnableEcsManagedTags": "enable_ecs_managed_tags",
    "CreatedAt": "created_at",
    "CreatedBy": "created_by",
    "UpdatedAt": "updated_at",
    "UpdatedBy": "updated_by",
    "Tags": "tags",
}

# ECS Task Definition configurable properties
ECS_TASK_DEFINITION_CONFIGURABLE: Dict[str, str] = {
    "Family": "family",
    "ContainerDefinitions": "container_definitions",
    "Cpu": "cpu",
    "Memory": "memory",
    "NetworkMode": "network_mode",
    "RequiresCompatibilities": "requires_compatibilities",
    "ExecutionRoleArn": "execution_role_arn",
    "TaskRoleArn": "task_role_arn",
    "Tags": "tags",
    "Volumes": "volume",
    "InferenceAccelerators": "inference_accelerator",
    "Ipc": "ipc",
    "Pid": "pid_mode",
    "ProxyConfiguration": "proxy_configuration",
    "RuntimePlatform": "runtime_platform",
    "EphemeralStorage": "ephemeral_storage",
}

# ECS Task Definition computed/read-only properties
ECS_TASK_DEFINITION_COMPUTED: Dict[str, str] = {
    "TaskDefinitionArn": "arn",
    "Family": "family",
    "Revision": "revision",
    "Status": "status",
    "ContainerDefinitions": "container_definitions",
    "Cpu": "cpu",
    "Memory": "memory",
    "NetworkMode": "network_mode",
    "RequiresCompatibilities": "requires_compatibilities",
    "Volumes": "volumes",
    "ExecutionRoleArn": "execution_role_arn",
    "TaskRoleArn": "task_role_arn",
    "RequiresAttributes": "requires_attributes",
    "Compatibilities": "compatibilities",
    "RegisteredAt": "registered_at",
    "RegisteredBy": "registered_by",
    "DeregistrationDate": "deregistration_date",
    "InferenceAccelerators": "inference_accelerators",
    "Ipc": "ipc",
    "Pid": "pid_mode",
    "ProxyConfiguration": "proxy_configuration",
    "RuntimePlatform": "runtime_platform",
    "EphemeralStorage": "ephemeral_storage",
    "Tags": "tags",
}


def get_ecs_cluster_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ECS Cluster properties from raw AWS config.

    Args:
        raw_config: Raw AWS ECS Cluster configuration from describe_clusters

    Returns:
        Dictionary with configurable Terraform properties
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in ECS_CLUSTER_CONFIGURABLE.items():
        if aws_key in raw_config:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    return terraform_config


def get_ecs_service_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ECS Service properties from raw AWS config.

    Args:
        raw_config: Raw AWS ECS Service configuration from describe_services

    Returns:
        Dictionary with configurable Terraform properties
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in ECS_SERVICE_CONFIGURABLE.items():
        if aws_key in raw_config:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    return terraform_config


def get_ecs_task_definition_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ECS Task Definition properties from raw AWS config.

    Args:
        raw_config: Raw AWS ECS Task Definition configuration from describe_task_definition

    Returns:
        Dictionary with configurable Terraform properties
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in ECS_TASK_DEFINITION_CONFIGURABLE.items():
        if aws_key in raw_config:
            value = raw_config[aws_key]
            if value is not None:
                terraform_config[tf_key] = value

    return terraform_config


# Register ECS property maps with the registry
register_property_map(
    "ecs:cluster",
    {
        "configurable": ECS_CLUSTER_CONFIGURABLE,
        "computed": ECS_CLUSTER_COMPUTED,
        "get_properties": get_ecs_cluster_properties,
    },
)

register_property_map(
    "ecs:service",
    {
        "configurable": ECS_SERVICE_CONFIGURABLE,
        "computed": ECS_SERVICE_COMPUTED,
        "get_properties": get_ecs_service_properties,
    },
)

register_property_map(
    "ecs:task_definition",
    {
        "configurable": ECS_TASK_DEFINITION_CONFIGURABLE,
        "computed": ECS_TASK_DEFINITION_COMPUTED,
        "get_properties": get_ecs_task_definition_properties,
    },
)

# Also register with AWS CloudFormation resource type names
register_property_map(
    "AWS::ECS::Cluster",
    {
        "configurable": ECS_CLUSTER_CONFIGURABLE,
        "computed": ECS_CLUSTER_COMPUTED,
    },
)

register_property_map(
    "AWS::ECS::Service",
    {
        "configurable": ECS_SERVICE_CONFIGURABLE,
        "computed": ECS_SERVICE_COMPUTED,
    },
)

register_property_map(
    "AWS::ECS::TaskDefinition",
    {
        "configurable": ECS_TASK_DEFINITION_CONFIGURABLE,
        "computed": ECS_TASK_DEFINITION_COMPUTED,
    },
)

__all__ = [
    "ECS_CLUSTER_CONFIGURABLE",
    "ECS_CLUSTER_COMPUTED",
    "ECS_SERVICE_CONFIGURABLE",
    "ECS_SERVICE_COMPUTED",
    "ECS_TASK_DEFINITION_CONFIGURABLE",
    "ECS_TASK_DEFINITION_COMPUTED",
    "get_ecs_cluster_properties",
    "get_ecs_service_properties",
    "get_ecs_task_definition_properties",
]
