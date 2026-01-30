"""Terraform generation prompts for AI."""

from typing import Any, Dict, List, Optional

from ...models.generation import Layer, ResourceMap, TrackedResource
from ..property_maps import get_property_map

TERRAFORM_SYSTEM_PROMPT = """You are an expert Terraform engineer.
Generate Terraform configuration files from AWS resource descriptions.

## Guidelines

1. **Resource References**: Use Terraform references instead of hardcoded IDs
   - Example: Instead of "vpc-abc123", use `aws_vpc.main.id`
   - I'll provide a resource map showing available references

2. **Variable Usage**: Create variables for configurable values
   - Instance types, AMIs, counts, etc.
   - Use sensible defaults based on the inventory values

3. **Output Generation**: Create outputs for important resource attributes
   - IDs, ARNs, DNS names, endpoints

4. **Provider Configuration**: Do NOT include provider blocks - I'll handle that separately

5. **Naming Convention**: Use terraform names I provide for each resource

6. **Dependencies**: Use implicit dependencies via references
   - Explicit depends_on only when necessary

7. **Best Practices**:
   - Use count/for_each for similar resources
   - Add meaningful descriptions to variables
   - Group related resources together
   - Add comments for complex logic

## Output Format

Return ONLY valid HCL code. No markdown, no explanations, just the Terraform configuration.
"""


def get_terraform_system_prompt() -> str:
    """Get the system prompt for Terraform generation."""
    return TERRAFORM_SYSTEM_PROMPT


def format_layer_prompt(
    layer: Layer,
    resource_map: ResourceMap,
    previous_layers: Optional[List[str]] = None,
) -> str:
    """Format prompt for generating a single layer.

    Args:
        layer: The layer to generate
        resource_map: Available resource references
        previous_layers: List of already generated layer file paths

    Returns:
        Formatted prompt string
    """
    resource_descriptions = []
    for resource in layer.resources:
        tracked = TrackedResource.from_inventory(resource)
        desc = format_resource_for_prompt(tracked)
        resource_descriptions.append(desc)

    resources_text = "\n\n".join(resource_descriptions)

    map_text = "## Available Resource References\n\n"
    map_text += "Use these Terraform references instead of hardcoded AWS IDs:\n\n"
    for aws_id, tf_ref in resource_map.id_to_ref.items():
        map_text += f"- `{aws_id}` -> `{tf_ref}`\n"

    context_text = ""
    if previous_layers:
        context_text = "\n\n## Previously Generated Layers\n\n"
        context_text += "These resources are already defined and available for reference:\n"
        for layer_file in previous_layers:
            context_text += f"- {layer_file}\n"

    prompt = f"""Generate Terraform configuration for the **{layer.name}** layer.

## Resources to Generate ({len(layer.resources)} resources)

{resources_text}

{map_text}
{context_text}

Generate complete, valid Terraform HCL for all resources above.
"""

    return prompt


def format_resource_for_prompt(resource: TrackedResource) -> str:
    """Format a single resource for inclusion in prompt.

    Applies property filtering and formatting:
    - Removes computed/read-only properties
    - Converts CamelCase to snake_case
    - Applies resource-specific property maps

    Args:
        resource: The resource to format

    Returns:
        Formatted resource description
    """
    property_map = get_property_map(resource.resource_type)

    props = _filter_properties(resource.raw_config, property_map)

    lines = [
        f"### {resource.resource_type}: {resource.resource_id if hasattr(resource, 'resource_id') else resource.name}",
        f"Terraform name: `{resource.get_terraform_name()}`",
        f"Region: {resource.region}",
    ]

    if resource.arn:
        lines.append(f"ARN: {resource.arn}")

    if resource.tags:
        lines.append(f"Tags: {resource.tags}")

    lines.append("\n**Properties:**")
    lines.append("```json")

    import json

    lines.append(json.dumps(props, indent=2, default=str))

    lines.append("```")

    return "\n".join(lines)


def _filter_properties(
    raw_config: Dict[str, Any],
    property_map: Optional[Any],
) -> Dict[str, Any]:
    """Filter properties for prompt inclusion.

    Removes computed properties and applies property map transformations.
    """
    computed_props = {
        "CreateTime",
        "CreationDate",
        "LastModified",
        "LastUpdated",
        "State",
        "Status",
        "Arn",
        "OwnerId",
        "RequesterId",
        "Attachments",
        "Association",
        "NetworkInterfaces",
        "BlockDeviceMappings",
        "StateReason",
        "StateTransitionReason",
        "Platform",
        "Architecture",
        "RootDeviceType",
        "VirtualizationType",
        "Monitoring",
        "Placement",
        "LaunchTime",
        "UsageOperation",
        "UsageOperationUpdateTime",
        "CapacityReservationSpecification",
        "HibernationOptions",
        "MetadataOptions",
        "EnclaveOptions",
        "BootMode",
        "CurrentInstanceBootMode",
        "PrivateDnsNameOptions",
    }

    filtered = {}

    for key, value in raw_config.items():
        if key in computed_props:
            continue

        if value is None:
            continue

        if isinstance(value, (list, dict)) and not value:
            continue

        if key.startswith("_"):
            continue

        filtered[key] = value

    if property_map and hasattr(property_map, "filter_properties"):
        filtered = property_map.filter_properties(filtered)

    return filtered


def format_retry_prompt(
    original_code: str,
    validation_errors: List[str],
    layer: Layer,
    resource_map: ResourceMap,
) -> str:
    """Format prompt for retrying after validation failure.

    Args:
        original_code: The invalid Terraform code
        validation_errors: List of terraform validate errors
        layer: The layer being generated
        resource_map: Available resource references

    Returns:
        Formatted retry prompt
    """
    errors_text = "\n".join(f"- {err}" for err in validation_errors)

    prompt = f"""The Terraform code you generated has validation errors. Please fix them.

## Validation Errors

{errors_text}

## Original Code

```hcl
{original_code}
```

## Available Resource References

{_format_resource_map_text(resource_map)}

Generate the corrected Terraform code. Return ONLY valid HCL, no markdown or explanations.
"""

    return prompt


def _format_resource_map_text(resource_map: ResourceMap) -> str:
    """Format resource map as text for prompts."""
    lines = []
    for aws_id, tf_ref in resource_map.id_to_ref.items():
        lines.append(f"- `{aws_id}` -> `{tf_ref}`")
    return "\n".join(lines) if lines else "(No resource references available yet)"
