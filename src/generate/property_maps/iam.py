"""AWS IAM to Terraform property mappings.

Maps AWS IAM API response properties to Terraform resource properties
for IAM Roles, Policies, and Instance Profiles.
"""

from typing import Any, Dict

# IAM Role configurable properties
# Maps AWS API field names to Terraform aws_iam_role argument names
IAM_ROLE_CONFIGURABLE: Dict[str, str] = {
    "AssumeRolePolicyDocument": "assume_role_policy",
    "RoleName": "name",
    "Path": "path",
    "Description": "description",
    "MaxSessionDuration": "max_session_duration",
    "PermissionsBoundary": "permissions_boundary",
    "Tags": "tags",
}

# IAM Role computed/read-only properties
# These are populated by AWS and typically not set by Terraform
IAM_ROLE_COMPUTED: Dict[str, str] = {
    "RoleId": "id",
    "Arn": "arn",
    "CreateDate": "create_date",
    "AssumeRolePolicyDocument": "assume_role_policy_document",
    "RolePolicyList": "inline_policy",
    "AttachedManagedPolicies": "managed_policy_arns",
    "InstanceProfileList": "instance_profile_list",
    "MaxSessionDuration": "max_session_duration",
}

# IAM Policy configurable properties
# Maps AWS API field names to Terraform aws_iam_policy argument names
IAM_POLICY_CONFIGURABLE: Dict[str, str] = {
    "PolicyName": "name",
    "PolicyDocument": "policy",
    "Path": "path",
    "Description": "description",
    "Tags": "tags",
}

# IAM Policy computed/read-only properties
IAM_POLICY_COMPUTED: Dict[str, str] = {
    "PolicyId": "id",
    "Arn": "arn",
    "CreateDate": "create_date",
    "UpdateDate": "update_date",
    "AttachmentCount": "attachment_count",
    "IsAttachable": "is_attachable",
    "DefaultVersionId": "default_version_id",
    "PolicyVersionList": "policy_version_list",
}

# IAM Instance Profile configurable properties
# Maps AWS API field names to Terraform aws_iam_instance_profile argument names
IAM_INSTANCE_PROFILE_CONFIGURABLE: Dict[str, str] = {
    "InstanceProfileName": "name",
    "Path": "path",
    "Roles": "role",
}

# IAM Instance Profile computed/read-only properties
IAM_INSTANCE_PROFILE_COMPUTED: Dict[str, str] = {
    "InstanceProfileId": "id",
    "Arn": "arn",
    "CreateDate": "create_date",
    "RoleList": "roles",
}


def get_iam_role_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and transform IAM Role properties for Terraform.

    Converts AWS API properties to Terraform argument names (snake_case)
    and omits computed/read-only properties.

    Args:
        raw_config: Raw IAM Role configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in IAM_ROLE_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in IAM_ROLE_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                # Handle AssumeRolePolicyDocument - ensure it's a string
                if aws_key == "AssumeRolePolicyDocument":
                    if isinstance(value, dict):
                        import json

                        value = json.dumps(value)
                # Handle PermissionsBoundary - extract ARN if present
                elif aws_key == "PermissionsBoundary":
                    if isinstance(value, dict):
                        value = value.get("PermissionsBoundaryArn")

                if value is not None:
                    terraform_config[tf_key] = value

    return terraform_config


def get_iam_policy_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and transform IAM Policy properties for Terraform.

    Converts AWS API properties to Terraform argument names (snake_case)
    and omits computed/read-only properties.

    Args:
        raw_config: Raw IAM Policy configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in IAM_POLICY_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in IAM_POLICY_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                # Handle PolicyDocument - ensure it's a string
                if aws_key == "PolicyDocument":
                    if isinstance(value, dict):
                        import json

                        value = json.dumps(value)

                if value is not None:
                    terraform_config[tf_key] = value

    return terraform_config


def get_iam_instance_profile_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and transform IAM Instance Profile properties for Terraform.

    Converts AWS API properties to Terraform argument names (snake_case)
    and omits computed/read-only properties.

    Args:
        raw_config: Raw IAM Instance Profile configuration from AWS API

    Returns:
        Dictionary with transformed properties suitable for Terraform
    """
    terraform_config: Dict[str, Any] = {}

    for aws_key, tf_key in IAM_INSTANCE_PROFILE_CONFIGURABLE.items():
        if aws_key in raw_config and aws_key not in IAM_INSTANCE_PROFILE_COMPUTED:
            value = raw_config[aws_key]
            if value is not None:
                # Handle Roles - extract role name from role objects if present
                if aws_key == "Roles":
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            # Extract role name from role object
                            role_name = value[0].get("RoleName")
                            if role_name:
                                terraform_config[tf_key] = role_name
                        else:
                            # Assume it's already a role name string
                            terraform_config[tf_key] = value[0]
                else:
                    terraform_config[tf_key] = value

    return terraform_config


def filter_properties(raw_config: Dict[str, Any], resource_type: str = "") -> Dict[str, Any]:
    """Filter IAM properties for Terraform generation.

    Uses the appropriate CONFIGURABLE dict as whitelist based on resource type.

    Args:
        raw_config: Raw IAM configuration from AWS API
        resource_type: Resource type (e.g., "AWS::IAM::Role", "AWS::IAM::Policy")

    Returns:
        Filtered dictionary with only Terraform-relevant properties
    """
    # Determine which configurable map to use based on resource type
    resource_type_lower = resource_type.lower()

    if "policy" in resource_type_lower and "role" not in resource_type_lower:
        configurable = IAM_POLICY_CONFIGURABLE
    elif "instanceprofile" in resource_type_lower or "instance_profile" in resource_type_lower:
        configurable = IAM_INSTANCE_PROFILE_CONFIGURABLE
    else:
        # Default to role
        configurable = IAM_ROLE_CONFIGURABLE

    filtered = {}

    # Include all configurable properties
    for aws_field in configurable.keys():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                # Handle special cases
                if aws_field == "AssumeRolePolicyDocument":
                    # Keep as dict for JSON serialization in prompt
                    filtered[aws_field] = value
                elif aws_field == "PolicyDocument":
                    # Keep as dict for JSON serialization in prompt
                    filtered[aws_field] = value
                elif aws_field == "PermissionsBoundary":
                    # Extract ARN if it's a dict
                    if isinstance(value, dict):
                        filtered[aws_field] = value.get("PermissionsBoundaryArn", value)
                    else:
                        filtered[aws_field] = value
                elif aws_field == "Roles":
                    # For instance profiles - extract role names
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            filtered[aws_field] = [r.get("RoleName", r) for r in value]
                        else:
                            filtered[aws_field] = value
                else:
                    # Skip empty collections
                    if not (isinstance(value, (list, dict)) and not value):
                        filtered[aws_field] = value

    return filtered


# Note: Registration is handled by __init__.py which registers the module.
# The filter_properties function handles different IAM resource types internally.

__all__ = [
    "IAM_ROLE_CONFIGURABLE",
    "IAM_ROLE_COMPUTED",
    "IAM_POLICY_CONFIGURABLE",
    "IAM_POLICY_COMPUTED",
    "IAM_INSTANCE_PROFILE_CONFIGURABLE",
    "IAM_INSTANCE_PROFILE_COMPUTED",
    "get_iam_role_properties",
    "get_iam_policy_properties",
    "get_iam_instance_profile_properties",
]
