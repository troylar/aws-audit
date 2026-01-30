"""AWS Backup to Terraform property mappings.

Maps AWS Backup API response properties to Terraform resource properties
for Backup Plans and Backup Vaults.
"""

from typing import Any, Dict

# Backup Plan configurable properties
# Maps AWS API field names to Terraform aws_backup_plan argument names
BACKUP_PLAN_CONFIGURABLE: Dict[str, Dict[str, Any]] = {
    "name": {
        "aws_key": "BackupPlanName",
        "tf_resource": "aws_backup_plan",
        "tf_attribute": "name",
        "type": "string",
        "required": True,
        "description": "Name of the backup plan",
    },
    "rules": {
        "aws_key": "Rules",
        "tf_resource": "aws_backup_plan",
        "tf_attribute": "rule",
        "type": "list(object)",
        "required": True,
        "description": "List of backup rules (RuleName, TargetBackupVaultName, ScheduleExpression, etc.)",
    },
    "tags": {
        "aws_key": "Tags",
        "tf_resource": "aws_backup_plan",
        "tf_attribute": "tags",
        "type": "map(string)",
        "required": False,
        "description": "Tags to apply to the backup plan",
    },
}

# Backup Plan computed/read-only properties
BACKUP_PLAN_COMPUTED: Dict[str, Dict[str, Any]] = {
    "arn": {
        "aws_key": "BackupPlanArn",
        "tf_resource": "aws_backup_plan",
        "tf_attribute": "arn",
        "type": "string",
        "computed": True,
        "description": "ARN of the backup plan",
    },
    "creation_date": {
        "aws_key": "CreationDate",
        "tf_resource": "aws_backup_plan",
        "tf_attribute": "creation_date",
        "type": "string",
        "computed": True,
        "description": "Date and time when the backup plan was created",
    },
    "version": {
        "aws_key": "VersionId",
        "tf_resource": "aws_backup_plan",
        "tf_attribute": "version",
        "type": "string",
        "computed": True,
        "description": "Version ID of the backup plan",
    },
}

# Backup Vault configurable properties
BACKUP_VAULT_CONFIGURABLE: Dict[str, Dict[str, Any]] = {
    "name": {
        "aws_key": "BackupVaultName",
        "tf_resource": "aws_backup_vault",
        "tf_attribute": "name",
        "type": "string",
        "required": True,
        "description": "Name of the backup vault",
    },
    "kms_key_arn": {
        "aws_key": "KmsKeyArn",
        "tf_resource": "aws_backup_vault",
        "tf_attribute": "kms_key_arn",
        "type": "string",
        "required": False,
        "description": "KMS key ARN used to encrypt the backup vault",
    },
    "tags": {
        "aws_key": "Tags",
        "tf_resource": "aws_backup_vault",
        "tf_attribute": "tags",
        "type": "map(string)",
        "required": False,
        "description": "Tags to apply to the backup vault",
    },
}

# Backup Vault computed/read-only properties
BACKUP_VAULT_COMPUTED: Dict[str, Dict[str, Any]] = {
    "arn": {
        "aws_key": "BackupVaultArn",
        "tf_resource": "aws_backup_vault",
        "tf_attribute": "arn",
        "type": "string",
        "computed": True,
        "description": "ARN of the backup vault",
    },
    "creation_date": {
        "aws_key": "CreationDate",
        "tf_resource": "aws_backup_vault",
        "tf_attribute": "creation_date",
        "type": "string",
        "computed": True,
        "description": "Date and time when the backup vault was created",
    },
}


def get_backup_plan_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Backup Plan properties from raw AWS config.

    Extracts backup plan properties including rules with schedule expressions,
    backup windows, and lifecycle configuration.

    Args:
        raw_config: Raw Backup Plan configuration from AWS API

    Returns:
        Dictionary of Terraform aws_backup_plan properties
    """
    properties = {}

    # Extract plan name
    if "BackupPlanName" in raw_config:
        properties["name"] = raw_config["BackupPlanName"]

    # Extract and process rules
    if "Rules" in raw_config:
        rules = raw_config["Rules"]
        tf_rules = []

        for rule in rules:
            tf_rule = {}

            # Extract rule name
            if "RuleName" in rule:
                tf_rule["rule_name"] = rule["RuleName"]

            # Extract target backup vault
            if "TargetBackupVaultName" in rule:
                tf_rule["target_backup_vault_name"] = rule["TargetBackupVaultName"]

            # Extract schedule expression
            if "ScheduleExpression" in rule:
                tf_rule["schedule_expression"] = rule["ScheduleExpression"]

            # Extract start window
            if "StartWindowMinutes" in rule:
                tf_rule["start_window_minutes"] = rule["StartWindowMinutes"]

            # Extract completion window
            if "CompletionWindowMinutes" in rule:
                tf_rule["completion_window_minutes"] = rule["CompletionWindowMinutes"]

            # Extract lifecycle configuration
            if "Lifecycle" in rule:
                lifecycle = rule["Lifecycle"]
                tf_lifecycle = {}

                if "MoveToColdStorageAfterDays" in lifecycle:
                    tf_lifecycle["move_to_cold_storage_after_days"] = lifecycle["MoveToColdStorageAfterDays"]

                if "DeleteAfterDays" in lifecycle:
                    tf_lifecycle["delete_after_days"] = lifecycle["DeleteAfterDays"]

                if tf_lifecycle:
                    tf_rule["lifecycle"] = tf_lifecycle

            # Extract recovery point tags
            if "RecoveryPointTags" in rule:
                tf_rule["recovery_point_tags"] = rule["RecoveryPointTags"]

            # Extract enable_continuous_backup flag
            if "EnableContinuousBackup" in rule:
                tf_rule["enable_continuous_backup"] = rule["EnableContinuousBackup"]

            if tf_rule:
                tf_rules.append(tf_rule)

        if tf_rules:
            properties["rules"] = tf_rules

    # Extract tags if present
    if "Tags" in raw_config:
        properties["tags"] = raw_config["Tags"]

    return properties


def get_backup_plan_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed properties from Backup Plan config.

    Args:
        raw_config: Raw Backup Plan configuration from AWS API

    Returns:
        Dictionary of computed properties
    """
    computed = {}

    if "BackupPlanArn" in raw_config:
        computed["arn"] = raw_config["BackupPlanArn"]

    if "CreationDate" in raw_config:
        computed["creation_date"] = str(raw_config["CreationDate"])

    if "VersionId" in raw_config:
        computed["version"] = raw_config["VersionId"]

    return computed


def get_backup_vault_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Backup Vault properties from raw AWS config.

    Extracts vault properties including name and KMS key ARN for encryption.

    Args:
        raw_config: Raw Backup Vault configuration from AWS API

    Returns:
        Dictionary of Terraform aws_backup_vault properties
    """
    properties = {}

    # Extract vault name
    if "BackupVaultName" in raw_config:
        properties["name"] = raw_config["BackupVaultName"]

    # Extract KMS key ARN if present
    if "KmsKeyArn" in raw_config:
        properties["kms_key_arn"] = raw_config["KmsKeyArn"]

    # Extract tags if present
    if "Tags" in raw_config:
        properties["tags"] = raw_config["Tags"]

    return properties


def get_backup_vault_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed properties from Backup Vault config.

    Args:
        raw_config: Raw Backup Vault configuration from AWS API

    Returns:
        Dictionary of computed properties
    """
    computed = {}

    if "BackupVaultArn" in raw_config:
        computed["arn"] = raw_config["BackupVaultArn"]

    if "CreationDate" in raw_config:
        computed["creation_date"] = str(raw_config["CreationDate"])

    return computed
