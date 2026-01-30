"""AWS Secrets Manager to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
SECRETSMANAGER_SECRET_CONFIGURABLE = {
    "Name": "name",
    "Description": "description",
    "KmsKeyId": "kms_key_id",
    "Policy": "policy",
    "Tags": "tags",
}

# Properties that contain sensitive data and should be marked as such
SECRETSMANAGER_SECRET_SENSITIVE = {
    "SecretString": "secret_string",
    "SecretBinary": "secret_binary",
}

# Properties computed by AWS that are read-only
SECRETSMANAGER_SECRET_COMPUTED = {
    "ARN": "arn",
    "VersionId": "version_id",
    "CreatedDate": "created_date",
}


def _transform_tags(tags: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Transform Secrets Manager tags to Terraform format.

    Args:
        tags: AWS tags dict or list with key-value pairs

    Returns:
        Terraform-formatted tags dict or None if empty
    """
    if not tags:
        return None

    # Tags may be a list of dicts with Key/Value or direct key-value pairs
    if isinstance(tags, list):
        result = {}
        for tag in tags:
            if isinstance(tag, dict) and "Key" in tag and "Value" in tag:
                result[tag["Key"]] = tag["Value"]
        return result if result else None

    # Direct key-value pairs
    return tags if tags else None


def _is_sensitive_field(field_name: str) -> bool:
    """Check if a field contains sensitive data.

    Args:
        field_name: The field name in Terraform format

    Returns:
        True if the field contains sensitive data that should be marked as such
    """
    return field_name in SECRETSMANAGER_SECRET_SENSITIVE.values()


def get_secretsmanager_secret_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform Secrets Manager secret properties for Terraform.

    This helper transforms AWS Secrets Manager configuration into Terraform-compatible format,
    handling special cases for nested structures, field name conversions, and sensitive data marking.

    Note: SecretString and SecretBinary are marked as sensitive and should not be exposed in logs or plans.

    Args:
        raw_config: Raw Secrets Manager secret configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_secretsmanager_secret resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in SECRETSMANAGER_SECRET_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special transformations
        if aws_field == "Tags":
            transformed = _transform_tags(value)
            if transformed:
                properties[tf_field] = transformed
        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process sensitive properties (marked as sensitive in Terraform)
    for aws_field, tf_field in SECRETSMANAGER_SECRET_SENSITIVE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]
        if value is not None:
            # Mark as sensitive - in Terraform output, these will be marked with the sensitive() function
            properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in SECRETSMANAGER_SECRET_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for Secrets Manager secrets
register_property_map("secretsmanager:secret", __name__)
register_property_map("secretsmanager", __name__)
