"""AWS CodePipeline to Terraform property mappings."""

from typing import Any, Dict, List, Optional

from . import register_property_map

# CodePipeline configurable properties
CODEPIPELINE_CONFIGURABLE = {
    "Name": "name",
    "RoleArn": "role_arn",
    "Stages": "stages",
    "ArtifactStore": "artifact_store",
    "Tags": "tags",
}

# CodePipeline computed/read-only properties
CODEPIPELINE_COMPUTED = {
    "PipelineArn": "arn",
    "Created": "created",
    "Updated": "updated",
}


def _transform_stage_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a single stage action to Terraform format.

    Args:
        action: AWS stage action dict

    Returns:
        Terraform-formatted action dict
    """
    result = {}

    if "Name" in action:
        result["name"] = action["Name"]

    if "ActionTypeId" in action:
        action_type = action["ActionTypeId"]
        result["action_type_id"] = {
            "category": action_type.get("Category"),
            "owner": action_type.get("Owner"),
            "provider": action_type.get("Provider"),
            "version": action_type.get("Version"),
        }

    if "Configuration" in action:
        result["configuration"] = action["Configuration"]

    if "InputArtifacts" in action:
        result["input_artifacts"] = [{"name": artifact.get("Name")} for artifact in action["InputArtifacts"]]

    if "OutputArtifacts" in action:
        result["output_artifacts"] = [{"name": artifact.get("Name")} for artifact in action["OutputArtifacts"]]

    if "RoleArn" in action:
        result["role_arn"] = action["RoleArn"]

    if "RunOrder" in action:
        result["run_order"] = action["RunOrder"]

    if "Namespace" in action:
        result["namespace"] = action["Namespace"]

    return result


def _transform_stage(stage: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a pipeline stage to Terraform format.

    Args:
        stage: AWS stage dict with Name and Actions

    Returns:
        Terraform-formatted stage dict
    """
    result = {}

    if "Name" in stage:
        result["name"] = stage["Name"]

    if "Actions" in stage:
        result["actions"] = [_transform_stage_action(action) for action in stage["Actions"]]

    return result


def _transform_stages(stages: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Transform pipeline stages to Terraform format.

    Args:
        stages: List of AWS stage dicts

    Returns:
        List of Terraform-formatted stage dicts or None if empty
    """
    if not stages:
        return None

    return [_transform_stage(stage) for stage in stages]


def _transform_artifact_store(
    artifact_store: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Transform artifact store configuration to Terraform format.

    Args:
        artifact_store: AWS artifact store dict with Type, Location, etc.

    Returns:
        Terraform-formatted artifact store or None if empty
    """
    if not artifact_store:
        return None

    result = {}

    if "Type" in artifact_store:
        result["type"] = artifact_store["Type"]

    if "Location" in artifact_store:
        result["location"] = artifact_store["Location"]

    if "EncryptionKey" in artifact_store:
        encryption_key = artifact_store["EncryptionKey"]
        result["encryption_key"] = {
            "id": encryption_key.get("Id"),
            "type": encryption_key.get("Type"),
        }

    return result if result else None


def get_codepipeline_properties(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and transform CodePipeline properties for Terraform.

    Args:
        raw_config: Raw CodePipeline configuration from AWS API

    Returns:
        Dictionary of properties suitable for Terraform aws_codepipeline resource
    """
    properties = {}

    for aws_field, tf_field in CODEPIPELINE_CONFIGURABLE.items():
        if aws_field not in raw_config:
            continue

        value = raw_config[aws_field]

        # Handle special nested transformations
        if aws_field == "Stages":
            transformed = _transform_stages(value)
            if transformed:
                properties[tf_field] = transformed

        elif aws_field == "ArtifactStore":
            transformed = _transform_artifact_store(value)
            if transformed:
                properties[tf_field] = transformed

        else:
            # Simple pass-through for non-nested properties
            if value is not None:
                properties[tf_field] = value

    # Process computed properties (read-only)
    for aws_field, tf_field in CODEPIPELINE_COMPUTED.items():
        if aws_field in raw_config:
            value = raw_config[aws_field]
            if value is not None:
                properties[tf_field] = value

    return properties


# Register the property map for CodePipeline
register_property_map("codepipeline", __name__)

__all__ = [
    "CODEPIPELINE_CONFIGURABLE",
    "CODEPIPELINE_COMPUTED",
    "get_codepipeline_properties",
]
