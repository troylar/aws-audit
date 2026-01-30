"""AWS S3 to Terraform property mappings."""

from typing import Any, Dict, Optional

# S3 Bucket configurable properties that map directly to Terraform aws_s3_bucket resource
S3_BUCKET_CONFIGURABLE = {
    "bucket": {
        "aws_key": "Name",
        "tf_resource": "aws_s3_bucket",
        "tf_attribute": "bucket",
        "type": "string",
        "required": True,
        "description": "Name of the S3 bucket",
    },
    "tags": {
        "aws_key": "Tags",
        "tf_resource": "aws_s3_bucket",
        "tf_attribute": "tags",
        "type": "map(string)",
        "required": False,
        "description": "Tags to apply to the bucket",
    },
}

# S3 Bucket computed/read-only properties
S3_BUCKET_COMPUTED = {
    "arn": {
        "aws_key": "Arn",
        "tf_resource": "aws_s3_bucket",
        "tf_attribute": "arn",
        "type": "string",
        "computed": True,
        "description": "ARN of the bucket",
    },
    "id": {
        "aws_key": "Name",
        "tf_resource": "aws_s3_bucket",
        "tf_attribute": "id",
        "type": "string",
        "computed": True,
        "description": "Name of the bucket",
    },
    "region": {
        "aws_key": "Region",
        "tf_resource": "aws_s3_bucket",
        "tf_attribute": "region",
        "type": "string",
        "computed": True,
        "description": "Region where bucket was created",
    },
    "created_date": {
        "aws_key": "CreationDate",
        "tf_resource": "aws_s3_bucket",
        "tf_attribute": "creation_date",
        "type": "string",
        "computed": True,
        "description": "UTC date and time when the bucket was created",
    },
}

# Note: S3 bucket configuration is split across multiple Terraform resources
# This is because AWS S3 API represents configuration via separate API calls
# In Terraform, you must use separate resource blocks:
# - aws_s3_bucket: Basic bucket creation (name, tags)
# - aws_s3_bucket_versioning: Versioning configuration
# - aws_s3_bucket_server_side_encryption_configuration: Encryption settings
# - aws_s3_bucket_public_access_block: Public access blocking rules
# - aws_s3_bucket_acl: Access control list
# - aws_s3_bucket_logging: Access logging configuration
# - aws_s3_bucket_lifecycle_configuration: Lifecycle rules
# - aws_s3_bucket_cors_configuration: CORS rules
# - aws_s3_bucket_website_configuration: Website hosting settings
# - aws_s3_bucket_object_lock_configuration: Object lock settings


def get_s3_bucket_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract S3 bucket properties from raw AWS config.

    Extracts the basic bucket properties that map to the aws_s3_bucket Terraform resource.
    Other configuration (versioning, encryption, etc.) must be handled by separate
    resource mappings.

    Args:
        raw_config: Raw S3 bucket configuration from AWS API

    Returns:
        Dictionary of Terraform aws_s3_bucket properties
    """
    properties = {}

    # Extract bucket name
    if "Name" in raw_config:
        properties["bucket"] = raw_config["Name"]

    # Extract tags if present
    if "Tags" in raw_config:
        properties["tags"] = raw_config["Tags"]

    return properties


def get_s3_versioning_config(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract S3 versioning configuration for aws_s3_bucket_versioning resource.

    The versioning status from get_bucket_versioning API call can be:
    - "Enabled": Versioning is enabled
    - "Suspended": Versioning was enabled but is now suspended
    - Not present: Versioning has never been enabled (treated as disabled)

    Args:
        raw_config: Raw S3 bucket configuration from AWS API

    Returns:
        Dictionary of Terraform aws_s3_bucket_versioning properties, or None if no versioning config
    """
    versioning_status = raw_config.get("Versioning")

    if not versioning_status or versioning_status == "Disabled":
        # No versioning configuration needed
        return None

    versioning_config = {
        "status": versioning_status,
    }

    # Include MFADelete if configured
    if raw_config.get("MFADelete"):
        versioning_config["mfa_delete"] = raw_config.get("MFADelete")

    return versioning_config


def get_s3_encryption_config(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract S3 server-side encryption configuration for aws_s3_bucket_server_side_encryption_configuration resource.

    Extracts encryption settings that must be configured via a separate Terraform resource.
    The Encryption config is returned from get_bucket_encryption API call.

    Args:
        raw_config: Raw S3 bucket configuration from AWS API

    Returns:
        Dictionary of Terraform aws_s3_bucket_server_side_encryption_configuration properties,
        or None if no encryption is configured
    """
    encryption_config = raw_config.get("Encryption")

    if not encryption_config:
        # No encryption configured
        return None

    # encryption_config should be the ServerSideEncryptionConfiguration structure
    # from AWS API, containing Rules array with encryption rule details
    rules = encryption_config.get("Rules", [])

    if not rules:
        return None

    # Build Terraform rules from AWS rules
    tf_rules = []
    for rule in rules:
        tf_rule = {}

        # Extract apply_server_side_encryption_by_default
        sse_by_default = rule.get("ApplyServerSideEncryptionByDefault", {})
        if sse_by_default:
            tf_rule["apply_server_side_encryption_by_default"] = {
                "sse_algorithm": sse_by_default.get("SSEAlgorithm"),
                "kms_master_key_id": sse_by_default.get("KMSMasterKeyID"),
            }

        # Extract bucket_key_enabled if present
        if rule.get("BucketKeyEnabled") is not None:
            tf_rule["bucket_key_enabled"] = rule.get("BucketKeyEnabled")

        if tf_rule:
            tf_rules.append(tf_rule)

    if not tf_rules:
        return None

    return {
        "rules": tf_rules,
    }


def get_s3_public_access_block_config(raw_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract S3 public access block configuration for aws_s3_bucket_public_access_block resource.

    Public access block settings control whether S3 blocks public access at multiple levels.
    These settings are returned from get_public_access_block API call.

    Args:
        raw_config: Raw S3 bucket configuration from AWS API

    Returns:
        Dictionary of Terraform aws_s3_bucket_public_access_block properties,
        or None if public access block is not configured
    """
    public_access_block = raw_config.get("PublicAccessBlock")

    if not public_access_block:
        return None

    return {
        "block_public_acls": public_access_block.get("BlockPublicAcls", False),
        "block_public_policy": public_access_block.get("BlockPublicPolicy", False),
        "ignore_public_acls": public_access_block.get("IgnorePublicAcls", False),
        "restrict_public_buckets": public_access_block.get("RestrictPublicBuckets", False),
    }
