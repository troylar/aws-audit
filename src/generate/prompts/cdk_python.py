"""CDK Python generation prompts for AI."""

from typing import Any, Dict, List, Optional

from ...models.generation import Layer, ResourceMap, TrackedResource
from ..property_maps import get_property_map

CDK_PYTHON_SYSTEM_PROMPT = """You are an expert AWS CDK engineer specializing in Python.
Generate CDK Python Stack classes from AWS resource descriptions.

## Guidelines

1. **Use L2 Constructs**: Prefer high-level L2 constructs over L1 CfnResource when available
   - Example: Use `ec2.Vpc()` instead of `ec2.CfnVPC()`
   - L2 constructs provide sensible defaults and better abstractions
   - Only use L1 when L2 doesn't expose needed properties

2. **Stack Structure**: Create a single Stack class per layer
   - Inherit from `Stack`
   - Accept keyword arguments for cross-stack references
   - Expose important resources as instance attributes

3. **Cross-Stack References**: Pass resources via constructor kwargs
   - Define type-hinted parameters for resources from other stacks
   - Store as instance attributes for other stacks to reference
   - Example: `self.vpc: ec2.IVpc = ...`

4. **Resource References**: Use CDK references instead of hardcoded IDs
   - Example: Instead of "vpc-abc123", use `vpc` parameter
   - I'll provide a resource map showing available references

5. **CRITICAL - Naming Convention**: You MUST use the EXACT construct ID I provide for each resource.
   - Each resource description includes "CDK construct ID: `<id>`"
   - Use this EXACT ID as the construct identifier
   - Example: If I say "CDK construct ID: `web_server_1`", use:
     `ec2.Instance(self, "web_server_1", ...)`
   - NEVER use generic names like "default", "main", or "resource"
   - The IDs I provide are already unique and validated

6. **Python Style - snake_case**: Use snake_case for all Python identifiers
   - Variable names: `my_vpc`, `public_subnet`
   - Method names: `get_availability_zones()`
   - Only use PascalCase for class names

7. **Best Practices**:
   - Import from `aws_cdk` and submodules (e.g., `from aws_cdk import aws_ec2 as ec2`)
   - Use type hints for all parameters and attributes
   - Add docstrings for the Stack class
   - Group related resources together
   - Use `Tags.of()` for tagging

8. **Stack Pattern**:
   ```python
   from aws_cdk import Stack, Tags
   from aws_cdk import aws_ec2 as ec2
   from constructs import Construct
   from typing import Optional

   class NetworkStack(Stack):
       \"\"\"Network layer infrastructure stack.\"\"\"

       def __init__(
           self,
           scope: Construct,
           construct_id: str,
           **kwargs,
       ) -> None:
           super().__init__(scope, construct_id, **kwargs)

           self.vpc = ec2.Vpc(self, "vpc", ...)
   ```

## Output Format

Return ONLY valid Python code. No markdown, no explanations, just the CDK Stack class.
"""


def get_cdk_python_system_prompt() -> str:
    """Get the system prompt for CDK Python generation."""
    return CDK_PYTHON_SYSTEM_PROMPT


def format_layer_prompt_python(
    layer: Layer,
    resource_map: ResourceMap,
    previous_layers: Optional[List[str]] = None,
    lambda_code_paths: Optional[Dict[str, str]] = None,
) -> str:
    """Format prompt for generating a CDK Python Stack for a single layer.

    Args:
        layer: The layer to generate
        resource_map: Available resource references from other stacks
        previous_layers: List of already generated stack file paths
        lambda_code_paths: Mapping of Lambda function names to extracted code file paths

    Returns:
        Formatted prompt string
    """
    resource_descriptions = []
    for resource in layer.resources:
        if isinstance(resource, TrackedResource):
            tracked = resource
        else:
            tracked = TrackedResource.from_inventory(resource)
        desc = format_resource_for_cdk_prompt(tracked, lambda_code_paths)
        resource_descriptions.append(desc)

    resources_text = "\n\n".join(resource_descriptions)

    # Convert layer name to PascalCase for Stack class name
    stack_class_name = _to_pascal_case(layer.name) + "Stack"

    map_text = "## Available Resource References\n\n"
    map_text += "Use these CDK references instead of hardcoded AWS IDs:\n\n"
    for aws_id, cdk_ref in resource_map.id_to_ref.items():
        map_text += f"- `{aws_id}` -> `{cdk_ref}`\n"

    context_text = ""
    if previous_layers:
        context_text = "\n\n## Previously Generated Stacks\n\n"
        context_text += "These stacks are already defined. Import resources via constructor parameters:\n"
        for layer_file in previous_layers:
            context_text += f"- {layer_file}\n"

    lambda_code_text = ""
    if lambda_code_paths:
        lambda_code_text = "\n\n## Lambda Code Files\n\n"
        lambda_code_text += "Use `_lambda.Code.from_asset()` to reference these pre-extracted code archives:\n\n"
        for func_name, code_path in lambda_code_paths.items():
            lambda_code_text += f"- `{func_name}` -> `{code_path}`\n"

    prompt = f"""Generate a CDK Python Stack class for the **{layer.name}** layer.

## Stack Class Name: `{stack_class_name}`

## Constructs to Generate ({len(layer.resources)} resource{"s" if len(layer.resources) != 1 else ""})

{resources_text}

{map_text}
{context_text}
{lambda_code_text}

Generate complete, valid Python CDK Stack code for all resources above.
Include imports, the Stack class with type hints, and docstrings.
Use snake_case for all Python identifiers (variables, methods, parameters).
"""

    return prompt


def format_resource_for_cdk_prompt(
    resource: TrackedResource,
    lambda_code_paths: Optional[Dict[str, str]] = None,
) -> str:
    """Format a single resource for inclusion in CDK Python prompt.

    Args:
        resource: The resource to format
        lambda_code_paths: Mapping of Lambda function names to extracted code file paths

    Returns:
        Formatted resource description
    """
    property_map = get_property_map(resource.resource_type)
    props = _filter_properties(
        resource.raw_config, property_map, resource.resource_type
    )

    # Generate CDK-style construct ID (snake_case for Python)
    construct_id = _to_snake_case(resource.name)

    lines = [
        f"### {resource.resource_type}: {resource.resource_id if hasattr(resource, 'resource_id') else resource.name}",
        f"CDK construct ID: `{construct_id}`",
        f"Region: {resource.region}",
    ]

    if resource.arn:
        lines.append(f"ARN: {resource.arn}")

    if resource.tags:
        lines.append(f"Tags: {resource.tags}")

    if lambda_code_paths and resource.name in lambda_code_paths:
        code_path = lambda_code_paths[resource.name]
        lines.append(f"\n**Lambda Code File:** `{code_path}`")
        lines.append(
            f"(Use `_lambda.Code.from_asset('{code_path}')` in the Function construct)"
        )

    lines.append("\n**Properties:**")
    lines.append("```json")

    import json

    lines.append(json.dumps(props, indent=2, default=str))

    lines.append("```")

    return "\n".join(lines)


def _to_pascal_case(name: str) -> str:
    """Convert a name to PascalCase.

    Args:
        name: Name to convert (may contain underscores, hyphens, or spaces)

    Returns:
        PascalCase version of the name
    """
    parts = name.replace("-", "_").replace(" ", "_").split("_")
    return "".join(part.capitalize() for part in parts if part)


def _to_snake_case(name: str) -> str:
    """Convert a name to snake_case.

    Args:
        name: Name to convert (may contain hyphens or spaces)

    Returns:
        snake_case version of the name
    """
    # Replace hyphens and spaces with underscores
    result = name.replace("-", "_").replace(" ", "_")
    # Handle camelCase by inserting underscores before uppercase letters
    import re

    result = re.sub(r"([a-z])([A-Z])", r"\1_\2", result)
    return result.lower()


def _filter_properties(
    raw_config: Dict[str, Any],
    property_map: Optional[Any],
    resource_type: str = "",
) -> Dict[str, Any]:
    """Filter properties for prompt inclusion.

    Uses property map's filter_properties if available, otherwise falls back
    to generic computed property filtering.

    Args:
        raw_config: Raw resource configuration from AWS API
        property_map: Property map module or dict (may have filter_properties function)
        resource_type: Resource type string for context

    Returns:
        Filtered dictionary suitable for CDK generation prompt
    """
    if property_map and hasattr(property_map, "filter_properties"):
        import inspect

        sig = inspect.signature(property_map.filter_properties)
        if len(sig.parameters) > 1:
            return property_map.filter_properties(raw_config, resource_type)
        else:
            return property_map.filter_properties(raw_config)

    # Fallback to generic filtering if no property map
    computed_props = {
        "CreateTime",
        "CreationDate",
        "LastModified",
        "LastUpdated",
        "State",
        "Status",
        "Arn",
        "FunctionArn",
        "OwnerId",
        "RequesterId",
        "Attachments",
        "Association",
        "NetworkInterfaces",
        "BlockDeviceMappings",
        "StateReason",
        "StateTransitionReason",
        "Platform",
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
        "RoleId",
        "PolicyId",
        "CreateDate",
        "UpdateDate",
        "AttachmentCount",
        "IsAttachable",
        "DefaultVersionId",
        "PolicyVersionList",
        "CodeSize",
        "Version",
        "Revision",
        "PackageType",
        "StateReasonCode",
        "LastUpdateStatus",
        "LastUpdateStatusReason",
        "LastUpdateStatusReasonCode",
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
            if key in ("_code",):
                filtered[key] = value
            continue

        filtered[key] = value

    return filtered


def format_retry_prompt_python(
    original_code: str,
    validation_errors: List[str],
    layer: Layer,
    resource_map: ResourceMap,
) -> str:
    """Format prompt for retrying after validation failure.

    Args:
        original_code: The invalid Python code
        validation_errors: List of Python/cdk synth errors
        layer: The layer being generated
        resource_map: Available resource references

    Returns:
        Formatted retry prompt
    """
    errors_text = "\n".join(f"- {err}" for err in validation_errors)

    prompt = f"""The CDK Python code you generated has validation errors. Please fix them.

## Validation Errors

{errors_text}

## Original Code

```python
{original_code}
```

## Available Resource References

{_format_resource_map_text(resource_map)}

Generate the corrected CDK Python code. Return ONLY valid Python, no markdown or explanations.
"""

    return prompt


def _format_resource_map_text(resource_map: ResourceMap) -> str:
    """Format resource map as text for prompts."""
    lines = []
    for aws_id, cdk_ref in resource_map.id_to_ref.items():
        lines.append(f"- `{aws_id}` -> `{cdk_ref}`")
    return "\n".join(lines) if lines else "(No resource references available yet)"
