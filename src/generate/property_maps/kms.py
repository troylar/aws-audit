"""AWS KMS to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# Properties that can be set by the user in Terraform
KMS_KEY_CONFIGURABLE = {
    "Description": "description",
    "KeyUsage": "key_usage",
    "CustomerMasterKeySpec": "customer_master_key_spec",
    "Policy": "policy",
    "EnableKeyRotation": "enable_key_rotation",
    "Tags": "tags",
    "MultiRegion": "multi_region",
}

# Properties computed by AWS that are read-only
KMS_KEY_COMPUTED = {
    "KeyId": "key_id",
    "Arn": "arn",
    "KeyState": "key_state",
    "CreationDate": "creation_date",
}


def _transform_tags(tags: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Transform KMS tags to Terraform format.

    Args:
        tags: AWS tags dict with key-value pairs

    Returns:
        Terraform-formatted tags dict or None if empty
    """
    if not tags:
        return None

    # Tags may be a list of dicts with TagKey/TagValue or direct key-value pairs
    if isinstance(tags, list):
        result = {}
        for tag in tags:
            if isinstance(tag, dict) and "TagKey" in tag and "TagValue" in tag:
                result[tag["TagKey"]] = tag["TagValue"]
        return result if result else None

    # Direct key-value pairs
    return tags if tags else None


def get_kms_key_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform KMS key properties for Terraform.

    This helper transforms AWS KMS configuration into Terraform-compatible format,
    handling special cases for nested structures and field name conversions.

    Args:
        raw_config: Raw KMS key configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_kms_key resource
    """
    properties = {}

    # Process configurable properties
    for aws_field, tf_field in KMS_KEY_CONFIGURABLE.items():
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

    # Process computed properties (read-only)
    for aws_field, tf_field in KMS_KEY_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for KMS keys
register_property_map("kms:key", __name__)
register_property_map("kms", __name__)
