"""AWS Systems Manager (SSM) Parameter to Terraform property mappings."""

from typing import Any, Dict

# SSM Parameter configurable properties
# Maps AWS API field names to Terraform aws_ssm_parameter argument names
SSM_PARAMETER_CONFIGURABLE: Dict[str, Dict[str, Any]] = {
    "name": {
        "aws_key": "Name",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "name",
        "type": "string",
        "required": True,
        "description": "Name of the SSM parameter",
    },
    "type": {
        "aws_key": "Type",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "type",
        "type": "string",
        "required": True,
        "description": "Type of the parameter (String, StringList, SecureString)",
    },
    "value": {
        "aws_key": "Value",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "value",
        "type": "string",
        "required": True,
        "sensitive": True,
        "description": "Value of the parameter (marked sensitive for SecureString types)",
    },
    "description": {
        "aws_key": "Description",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "description",
        "type": "string",
        "required": False,
        "description": "Description of the parameter",
    },
    "key_id": {
        "aws_key": "KeyId",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "key_id",
        "type": "string",
        "required": False,
        "description": "KMS key ID used for SecureString encryption",
    },
    "tier": {
        "aws_key": "Tier",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "tier",
        "type": "string",
        "required": False,
        "description": "Parameter tier (Standard, Advanced, Intelligent-Tiering)",
    },
    "data_type": {
        "aws_key": "DataType",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "data_type",
        "type": "string",
        "required": False,
        "description": "Data type of the parameter (text, aws:ec2:image, aws:ssm:integration)",
    },
    "tags": {
        "aws_key": "Tags",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "tags",
        "type": "map(string)",
        "required": False,
        "description": "Tags to apply to the parameter",
    },
}

# SSM Parameter computed/read-only properties
SSM_PARAMETER_COMPUTED: Dict[str, Dict[str, Any]] = {
    "arn": {
        "aws_key": "ARN",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "arn",
        "type": "string",
        "computed": True,
        "description": "ARN of the SSM parameter",
    },
    "version": {
        "aws_key": "Version",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "version",
        "type": "number",
        "computed": True,
        "description": "Version number of the parameter",
    },
    "last_modified_date": {
        "aws_key": "LastModifiedDate",
        "tf_resource": "aws_ssm_parameter",
        "tf_attribute": "last_modified_date",
        "type": "string",
        "computed": True,
        "description": "Date and time when the parameter was last modified",
    },
}


def get_ssm_parameter_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract SSM Parameter properties from raw AWS config.

    Extracts parameter properties that map to the aws_ssm_parameter Terraform resource.
    Sensitive values (SecureString type) are marked for special handling.

    Args:
        raw_config: Raw SSM parameter configuration from AWS API

    Returns:
        Dictionary of Terraform aws_ssm_parameter properties
    """
    properties = {}

    # Extract name
    if "Name" in raw_config:
        properties["name"] = raw_config["Name"]

    # Extract type
    if "Type" in raw_config:
        properties["type"] = raw_config["Type"]

    # Extract value - mark as sensitive if SecureString type
    if "Value" in raw_config:
        properties["value"] = raw_config["Value"]
        if raw_config.get("Type") == "SecureString":
            properties["_sensitive"] = True

    # Extract description if present
    if "Description" in raw_config:
        properties["description"] = raw_config["Description"]

    # Extract key_id for SecureString parameters
    if "KeyId" in raw_config:
        properties["key_id"] = raw_config["KeyId"]

    # Extract tier if present
    if "Tier" in raw_config:
        properties["tier"] = raw_config["Tier"]

    # Extract data_type if present
    if "DataType" in raw_config:
        properties["data_type"] = raw_config["DataType"]

    # Extract tags if present
    if "Tags" in raw_config:
        properties["tags"] = raw_config["Tags"]

    return properties


def get_ssm_parameter_computed_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract computed properties from SSM Parameter config.

    Args:
        raw_config: Raw SSM parameter configuration from AWS API

    Returns:
        Dictionary of computed properties
    """
    computed = {}

    if "ARN" in raw_config:
        computed["arn"] = raw_config["ARN"]

    if "Version" in raw_config:
        computed["version"] = raw_config["Version"]

    if "LastModifiedDate" in raw_config:
        computed["last_modified_date"] = str(raw_config["LastModifiedDate"])

    return computed
