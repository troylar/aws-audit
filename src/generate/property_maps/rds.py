"""AWS RDS to Terraform property mappings.

Maps AWS RDS API response properties to Terraform resource properties
for both DB instances and Aurora clusters.
"""

from __future__ import annotations

from typing import Any, Dict, List

# RDS DB Instance configurable properties
# Maps AWS API field names to Terraform aws_db_instance argument names
RDS_INSTANCE_CONFIGURABLE: Dict[str, str] = {
    "DBInstanceClass": "instance_class",
    "Engine": "engine",
    "EngineVersion": "engine_version",
    "AllocatedStorage": "allocated_storage",
    "DBName": "db_name",
    "MasterUsername": "username",
    "MasterUserPassword": "password",  # Handled as sensitive variable
    "DBInstanceIdentifier": "identifier",
    "DBSubnetGroupName": "db_subnet_group_name",
    "VpcSecurityGroupIds": "vpc_security_group_ids",
    "SecurityGroupIds": "vpc_security_group_ids",
    "PubliclyAccessible": "publicly_accessible",
    "StorageEncrypted": "storage_encrypted",
    "Iops": "iops",
    "StorageType": "storage_type",
    "Port": "port",
    "BackupRetentionPeriod": "backup_retention_period",
    "PreferredBackupWindow": "backup_window",
    "PreferredMaintenanceWindow": "maintenance_window",
    "MultiAZ": "multi_az",
    "EnableCloudwatchLogsExports": "enabled_cloudwatch_logs_exports",
    "EnableIAMDatabaseAuthentication": "iam_database_authentication_enabled",
    "KmsKeyId": "kms_key_id",
    "DeletionProtection": "deletion_protection",
    "LicenseModel": "license_model",
    "DBParameterGroupName": "parameter_group_name",
    "CharacterSetName": "character_set_name",
    "EnableEnhancedMonitoring": "enable_monitoring",
    "MonitoringInterval": "monitoring_interval",
    "MonitoringRoleArn": "monitoring_role_arn",
    "OptionGroupName": "option_group_name",
    "EnableAutomaticFailover": "auto_failover",
    "CopyTagsToSnapshot": "copy_tags_to_snapshot",
    "TdeCredentialArn": "tde_credential_arn",
    "TdeCredentialPassword": "tde_credential_password",
}

# RDS DB Instance computed/read-only properties
# These are populated by AWS and typically not set by Terraform
RDS_INSTANCE_COMPUTED: Dict[str, str] = {
    "DBInstanceArn": "arn",
    "DBInstanceStatus": "status",
    "DBInstanceIdentifier": "identifier",
    "Engine": "engine",
    "DBInstanceClass": "instance_class",
    "Endpoint": "endpoint",  # Complex object with Address, Port, HostedZoneId
    "AllocatedStorage": "allocated_storage",
    "InstanceCreateTime": "instance_create_time",
    "PreferredBackupWindow": "backup_window",
    "PreferredMaintenanceWindow": "maintenance_window",
    "PendingModifiedValues": "pending_modified_values",
    "LatestRestorableTime": "latest_restorable_time",
    "BackupRetentionPeriod": "backup_retention_period",
    "DBSecurityGroups": "security_groups",
    "VpcSecurityGroupMemberships": "vpc_security_groups",
    "DBParameterGroups": "db_parameter_groups",
    "AvailabilityZone": "availability_zone",
    "DBSubnetGroup": "db_subnet_group",
    "SecondaryAvailabilityZone": "secondary_availability_zone",
    "PubliclyAccessible": "publicly_accessible",
    "StorageType": "storage_type",
    "Iops": "iops",
    "PendingCloudwatchLogsExports": "pending_cloudwatch_logs_exports",
    "MultiAZ": "multi_az",
    "EngineVersion": "engine_version",
    "AutoMinorVersionUpgrade": "auto_minor_version_upgrade",
    "LicenseModel": "license_model",
    "OptionGroupMemberships": "option_group_memberships",
    "CharacterSetName": "character_set_name",
    "StorageEncrypted": "storage_encrypted",
    "KmsKeyId": "kms_key_id",
    "DbiResourceId": "resource_id",
    "CACertificateIdentifier": "ca_certificate_identifier",
    "DomainMemberships": "domain_memberships",
    "CopyTagsToSnapshot": "copy_tags_to_snapshot",
    "MonitoringInterval": "monitoring_interval",
    "DBInstancePort": "db_instance_port",
    "DBClusterIdentifier": "db_cluster_identifier",
    "StorageTypeUpgradeable": "storage_type_upgradeable",
    "DBInstanceAutomatedBackupsReplications": "automated_backups_replications",
    "DeletionProtection": "deletion_protection",
    "AssociatedRoles": "associated_roles",
    "Timezone": "timezone",
    "IAMDatabaseAuthenticationEnabled": "iam_database_authentication_enabled",
    "PerformanceInsightsEnabled": "performance_insights_enabled",
    "PerformanceInsightsKMSKeyId": "performance_insights_kms_key_id",
    "PerformanceInsightsRetentionPeriod": "performance_insights_retention_period",
    "EnabledCloudwatchLogsExports": "enabled_cloudwatch_logs_exports",
    "ProcessorFeatures": "processor_features",
    "DeletionProtectionEnabled": "deletion_protection",
    "ListenerEndpoint": "listener_endpoint",
    "MaxAllocatedStorage": "max_allocated_storage",
    "DBSystemId": "db_system_id",
    "CustomIamInstanceProfile": "custom_iam_instance_profile",
}

# RDS DB Cluster configurable properties
# Maps AWS API field names to Terraform aws_rds_cluster argument names
RDS_CLUSTER_CONFIGURABLE: Dict[str, str] = {
    "Engine": "engine",
    "EngineVersion": "engine_version",
    "DBClusterIdentifier": "cluster_identifier",
    "MasterUsername": "master_username",
    "MasterUserPassword": "master_password",  # Handled as sensitive variable
    "Port": "port",
    "DBSubnetGroupName": "db_subnet_group_name",
    "VpcSecurityGroupIds": "vpc_security_group_ids",
    "AvailabilityZones": "availability_zones",
    "BackupRetentionPeriod": "backup_retention_period",
    "PreferredBackupWindow": "preferred_backup_window",
    "PreferredMaintenanceWindow": "preferred_maintenance_window",
    "EnableCloudwatchLogsExports": "enabled_cloudwatch_logs_exports",
    "EnableIAMDatabaseAuthentication": "iam_database_authentication_enabled",
    "KmsKeyId": "kms_key_id",
    "StorageEncrypted": "storage_encrypted",
    "DeletionProtection": "deletion_protection",
    "EnableHttpEndpoint": "enable_http_endpoint",
    "CopyTagsToSnapshot": "copy_tags_to_snapshot",
    "DatabaseName": "database_name",
    "DBClusterParameterGroupName": "db_cluster_parameter_group_name",
    "OptionGroupName": "db_option_group_name",
    "ReplicationSourceIdentifier": "replication_source_identifier",
    "EnableGlobalWriteForwarding": "enable_global_write_forwarding",
    "GlobalWriteForwardingRequested": "enable_global_write_forwarding",
    "EnableLocalWriteForwarding": "enable_local_write_forwarding",
    "EngineMode": "engine_mode",
    "BacktrackWindow": "backtrack_window",
    "EnableRdsCustom": "enable_rds_custom",
}

# RDS DB Cluster computed/read-only properties
RDS_CLUSTER_COMPUTED: Dict[str, str] = {
    "DBClusterArn": "arn",
    "DBClusterIdentifier": "cluster_identifier",
    "ClusterCreateTime": "cluster_create_time",
    "Engine": "engine",
    "EngineVersion": "engine_version",
    "Status": "status",
    "Endpoint": "endpoint",
    "ReaderEndpoint": "reader_endpoint",
    "Port": "port",
    "DBClusterMembers": "cluster_members",
    "VpcSecurityGroupMemberships": "vpc_security_groups",
    "AvailabilityZones": "availability_zones",
    "DBSubnetGroup": "db_subnet_group",
    "PreferredBackupWindow": "preferred_backup_window",
    "PreferredMaintenanceWindow": "preferred_maintenance_window",
    "BackupRetentionPeriod": "backup_retention_period",
    "EnabledCloudwatchLogsExports": "enabled_cloudwatch_logs_exports",
    "PendingCloudwatchLogsExports": "pending_cloudwatch_logs_exports",
    "StorageEncrypted": "storage_encrypted",
    "KmsKeyId": "kms_key_id",
    "DbiResourceId": "resource_id",
    "DBClusterResourceId": "cluster_resource_id",
    "DBClusterOptionGroupMemberships": "option_group_memberships",
    "IAMDatabaseAuthenticationEnabled": "iam_database_authentication_enabled",
    "EarliestRestorableTime": "earliest_restorable_time",
    "LatestRestorableTime": "latest_restorable_time",
    "DeletionProtection": "deletion_protection",
    "HttpEndpointEnabled": "http_endpoint_enabled",
    "ActivityStreamStatus": "activity_stream_status",
    "CopyTagsToSnapshot": "copy_tags_to_snapshot",
    "EngineMode": "engine_mode",
    "GlobalWriteForwardingStatus": "global_write_forwarding_status",
    "GlobalWriteForwardingRequested": "enable_global_write_forwarding",
    "DBClusterParameterGroup": "db_cluster_parameter_group",
    "ReplicationSourceIdentifier": "replication_source_identifier",
    "BacktrackWindow": "backtrack_window",
    "BacktrackConsumedChangeRecords": "backtrack_consumed_change_records",
    "AssociatedRoles": "associated_roles",
    "DatabaseName": "database_name",
    "DomainMemberships": "domain_memberships",
    "HostedZoneId": "hosted_zone_id",
    "StorageType": "storage_type",
    "Iops": "iops",
    "PendingModifiedValues": "pending_modified_values",
    "AvailabilityZoneCount": "availability_zone_count",
    "CACertificateIdentifier": "ca_certificate_identifier",
    "PerformanceInsightsEnabled": "performance_insights_enabled",
    "PerformanceInsightsKMSKeyId": "performance_insights_kms_key_id",
    "PerformanceInsightsRetentionPeriod": "performance_insights_retention_period",
    "ServerlessV2ScalingConfigurationInfo": "serverlessv2_scaling_configuration",
    "GlobalWriteForwarding": "global_write_forwarding",
    "LocalWriteForwarding": "local_write_forwarding",
    "CrossAccountClone": "cross_account_clone",
}

# Sensitive fields that should be handled as variables
SENSITIVE_FIELDS: List[str] = [
    "MasterUserPassword",
    "master_password",
    "MasterUserPassword",
    "password",
    "TdeCredentialPassword",
    "tde_credential_password",
]


def get_rds_instance_properties(
    raw_config: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    """Extract RDS DB Instance properties from raw AWS config.

    Args:
        raw_config: Raw AWS RDS DB Instance configuration from describe_db_instances

    Returns:
        Tuple of:
        - configurable_properties: Properties that can be set in Terraform
        - computed_properties: Read-only properties from AWS
        - sensitive_variables: Password and other sensitive fields to handle separately
    """
    configurable = {}
    computed = {}
    sensitive = {}

    # Extract configurable properties
    for aws_field, tf_field in RDS_INSTANCE_CONFIGURABLE.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if aws_field in SENSITIVE_FIELDS:
                sensitive[tf_field] = value
            else:
                configurable[tf_field] = value

    # Extract computed properties
    for aws_field, tf_field in RDS_INSTANCE_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if aws_field not in SENSITIVE_FIELDS:
                computed[tf_field] = value

    # Handle endpoint extraction (complex nested object)
    if "Endpoint" in raw_config and "Endpoint" in raw_config:
        endpoint = raw_config["Endpoint"]
        if isinstance(endpoint, dict):
            computed["endpoint"] = {
                "address": endpoint.get("Address"),
                "port": endpoint.get("Port"),
                "hosted_zone_id": endpoint.get("HostedZoneId"),
            }

    return configurable, computed, sensitive


def get_rds_cluster_properties(
    raw_config: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, str]]:
    """Extract RDS DB Cluster properties from raw AWS config.

    Args:
        raw_config: Raw AWS RDS DB Cluster configuration from describe_db_clusters

    Returns:
        Tuple of:
        - configurable_properties: Properties that can be set in Terraform
        - computed_properties: Read-only properties from AWS
        - sensitive_variables: Password and other sensitive fields to handle separately
    """
    configurable = {}
    computed = {}
    sensitive = {}

    # Extract configurable properties
    for aws_field, tf_field in RDS_CLUSTER_CONFIGURABLE.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if aws_field in SENSITIVE_FIELDS:
                sensitive[tf_field] = value
            else:
                configurable[tf_field] = value

    # Extract computed properties
    for aws_field, tf_field in RDS_CLUSTER_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if aws_field not in SENSITIVE_FIELDS:
                computed[tf_field] = value

    # Handle endpoint extraction (complex nested object)
    if "Endpoint" in raw_config:
        endpoint = raw_config["Endpoint"]
        if isinstance(endpoint, str):
            computed["endpoint"] = endpoint
        elif isinstance(endpoint, dict):
            computed["endpoint"] = endpoint.get("Address")

    # Handle reader endpoint
    if "ReaderEndpoint" in raw_config:
        reader_endpoint = raw_config["ReaderEndpoint"]
        if isinstance(reader_endpoint, str):
            computed["reader_endpoint"] = reader_endpoint
        elif isinstance(reader_endpoint, dict):
            computed["reader_endpoint"] = reader_endpoint.get("Address")

    return configurable, computed, sensitive


# Register property maps with the registry
def _register_maps() -> None:
    """Register RDS property maps with the registry."""
    try:
        from . import register_property_map

        register_property_map(
            "rds:instance",
            {
                "configurable": RDS_INSTANCE_CONFIGURABLE,
                "computed": RDS_INSTANCE_COMPUTED,
                "sensitive": SENSITIVE_FIELDS,
            },
        )
        register_property_map(
            "rds:cluster",
            {
                "configurable": RDS_CLUSTER_CONFIGURABLE,
                "computed": RDS_CLUSTER_COMPUTED,
                "sensitive": SENSITIVE_FIELDS,
            },
        )
        register_property_map(
            "AWS::RDS::DBInstance",
            {
                "configurable": RDS_INSTANCE_CONFIGURABLE,
                "computed": RDS_INSTANCE_COMPUTED,
                "sensitive": SENSITIVE_FIELDS,
            },
        )
        register_property_map(
            "AWS::RDS::DBCluster",
            {
                "configurable": RDS_CLUSTER_CONFIGURABLE,
                "computed": RDS_CLUSTER_COMPUTED,
                "sensitive": SENSITIVE_FIELDS,
            },
        )
    except ImportError:
        # Registry not available yet, will be registered on import
        pass


# Auto-register on module import
_register_maps()

__all__ = [
    "RDS_INSTANCE_CONFIGURABLE",
    "RDS_INSTANCE_COMPUTED",
    "RDS_CLUSTER_CONFIGURABLE",
    "RDS_CLUSTER_COMPUTED",
    "SENSITIVE_FIELDS",
    "get_rds_instance_properties",
    "get_rds_cluster_properties",
]
