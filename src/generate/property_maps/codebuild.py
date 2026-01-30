"""AWS CodeBuild to Terraform property mappings."""

from typing import Any, Dict, Optional

from . import register_property_map

# CodeBuild Project configurable properties
CODEBUILD_PROJECT_CONFIGURABLE = {
    "Name": "name",
    "Description": "description",
    "Source": "source",
    "Artifacts": "artifacts",
    "Environment": "environment",
    "ServiceRole": "service_role",
    "TimeoutInMinutes": "build_timeout",
    "VpcConfig": "vpc_config",
    "Tags": "tags",
}

# CodeBuild Project computed/read-only properties
CODEBUILD_PROJECT_COMPUTED = {
    "Arn": "arn",
    "Created": "created",
    "LastModified": "last_modified",
}


def _transform_source(source: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform Source configuration to Terraform format.

    Args:
        source: AWS Source config dict with Type, Location, etc.

    Returns:
        Terraform-formatted source config or None if empty
    """
    if not source:
        return None

    result = {}

    if "Type" in source:
        result["type"] = source["Type"]

    if "Location" in source:
        result["location"] = source["Location"]

    if "GitCloneDepth" in source:
        result["git_clone_depth"] = source["GitCloneDepth"]

    if "GitSubmodulesConfig" in source:
        submodules = source["GitSubmodulesConfig"]
        result["git_submodules_config"] = {
            "fetch_submodules": submodules.get("FetchSubmodules", False),
        }

    if "BuildBatchConfig" in source:
        result["build_batch_config"] = source["BuildBatchConfig"]

    if "SourceIdentifier" in source:
        result["source_identifier"] = source["SourceIdentifier"]

    return result if result else None


def _transform_artifacts(artifacts: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform Artifacts configuration to Terraform format.

    Args:
        artifacts: AWS Artifacts config dict with Type, Location, etc.

    Returns:
        Terraform-formatted artifacts config or None if empty
    """
    if not artifacts:
        return None

    result = {}

    if "Type" in artifacts:
        result["type"] = artifacts["Type"]

    if "Location" in artifacts:
        result["location"] = artifacts["Location"]

    if "Name" in artifacts:
        result["name"] = artifacts["Name"]

    if "NamespaceType" in artifacts:
        result["namespace_type"] = artifacts["NamespaceType"]

    if "Packaging" in artifacts:
        result["packaging"] = artifacts["Packaging"]

    if "Path" in artifacts:
        result["path"] = artifacts["Path"]

    if "ArtifactIdentifier" in artifacts:
        result["artifact_identifier"] = artifacts["ArtifactIdentifier"]

    if "EncryptionDisabled" in artifacts:
        result["encryption_disabled"] = artifacts["EncryptionDisabled"]

    if "BucketOwnerAccess" in artifacts:
        result["bucket_owner_access"] = artifacts["BucketOwnerAccess"]

    return result if result else None


def _transform_environment(environment: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform Environment configuration to Terraform format.

    Args:
        environment: AWS Environment config dict with ComputeType, Image, etc.

    Returns:
        Terraform-formatted environment config or None if empty
    """
    if not environment:
        return None

    result = {}

    if "ComputeType" in environment:
        result["compute_type"] = environment["ComputeType"]

    if "Image" in environment:
        result["image"] = environment["Image"]

    if "Type" in environment:
        result["type"] = environment["Type"]

    if "EnvironmentVariables" in environment:
        env_vars = environment["EnvironmentVariables"]
        result["environment_variables"] = [
            {
                "name": var.get("name"),
                "value": var.get("value"),
                "type": var.get("type", "PARAMETER_STORE"),
            }
            for var in env_vars
        ]

    if "ImagePullCredentialsType" in environment:
        result["image_pull_credentials_type"] = environment["ImagePullCredentialsType"]

    if "RegistryCredential" in environment:
        registry = environment["RegistryCredential"]
        result["registry_credential"] = {
            "credential": registry.get("Credential"),
            "credential_provider": registry.get("CredentialProvider"),
        }

    if "PrivilegedMode" in environment:
        result["privileged_mode"] = environment["PrivilegedMode"]

    if "Certificate" in environment:
        result["certificate"] = environment["Certificate"]

    return result if result else None


def _transform_vpc_config(vpc_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Transform VPC configuration to Terraform format.

    Args:
        vpc_config: AWS VPC config dict with VpcId, Subnets, SecurityGroupIds, etc.

    Returns:
        Terraform-formatted VPC config or None if empty
    """
    if not vpc_config:
        return None

    result = {}

    if "VpcId" in vpc_config:
        result["vpc_id"] = vpc_config["VpcId"]

    if "Subnets" in vpc_config:
        result["subnets"] = vpc_config["Subnets"]

    if "SecurityGroupIds" in vpc_config:
        result["security_group_ids"] = vpc_config["SecurityGroupIds"]

    return result if result else None


def get_codebuild_project_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform CodeBuild project properties for Terraform.

    Args:
        raw_config: Raw CodeBuild project configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_codebuild_project resource
    """
    properties = {}

    for aws_field, tf_field in CODEBUILD_PROJECT_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "Source":
            transformed = _transform_source(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "Artifacts":
            transformed = _transform_artifacts(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "Environment":
            transformed = _transform_environment(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "VpcConfig":
            transformed = _transform_vpc_config(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in CODEBUILD_PROJECT_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for CodeBuild projects
register_property_map("codebuild:project", __name__)
register_property_map("codebuild", __name__)

__all__ = [
    "CODEBUILD_PROJECT_CONFIGURABLE",
    "CODEBUILD_PROJECT_COMPUTED",
    "get_codebuild_project_properties",
]
