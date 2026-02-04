"""CDK TypeScript generation prompts for AI."""

from typing import Any, Dict, List, Optional

from ...models.generation import Layer, ResourceMap, TrackedResource
from ..property_maps import get_property_map

CDK_TYPESCRIPT_SYSTEM_PROMPT = """You are an expert AWS CDK engineer specializing in TypeScript.
Generate CDK TypeScript Stack classes from AWS resource descriptions.

## Guidelines

1. **Use L2 Constructs**: Prefer high-level L2 constructs over L1 CfnResource when available
   - Example: Use `new ec2.Vpc()` instead of `new ec2.CfnVPC()`
   - L2 constructs provide sensible defaults and better abstractions
   - Only use L1 when L2 doesn't expose needed properties

2. **Stack Structure**: Create a single Stack class per layer
   - Extend `cdk.Stack`
   - Accept props interface for cross-stack references
   - Export important resources as public readonly properties

3. **Cross-Stack References**: Pass resources via props
   - Define a Props interface extending StackProps
   - Use props to receive resources from other stacks
   - Export resources that other stacks need
   - Example: `readonly vpc: ec2.IVpc;`

4. **Resource References**: Use CDK references instead of hardcoded IDs
   - Example: Instead of "vpc-abc123", use `props.vpc`
   - I'll provide a resource map showing available references

5. **CRITICAL - Naming Convention**: You MUST use the EXACT construct ID I provide for each resource.
   - Each resource description includes "CDK construct ID: `<id>`"
   - Use this EXACT ID as the construct identifier
   - Example: If I say "CDK construct ID: `webServer1`", use:
     `new ec2.Instance(this, 'webServer1', { ... })`
   - NEVER use generic names like "default", "main", or "resource"
   - The IDs I provide are already unique and validated

6. **Best Practices**:
   - Import from 'aws-cdk-lib' and submodules (e.g., `import * as ec2 from 'aws-cdk-lib/aws-ec2'`)
   - Use meaningful variable names
   - Add JSDoc comments for the Stack class
   - Group related resources together
   - Use Tags.of() for tagging

7. **Props Pattern**:
   ```typescript
   export interface NetworkStackProps extends cdk.StackProps {
     // Define props received from other stacks
   }

   export class NetworkStack extends cdk.Stack {
     public readonly vpc: ec2.IVpc;

     constructor(scope: Construct, id: string, props?: NetworkStackProps) {
       super(scope, id, props);
       // ...
     }
   }
   ```

## Output Format

Return ONLY valid TypeScript code. No markdown, no explanations, just the CDK Stack class.
"""


def get_cdk_typescript_system_prompt() -> str:
    """Get the system prompt for CDK TypeScript generation."""
    return CDK_TYPESCRIPT_SYSTEM_PROMPT


def format_layer_prompt_typescript(
    layer: Layer,
    resource_map: ResourceMap,
    previous_layers: Optional[List[str]] = None,
    lambda_code_paths: Optional[Dict[str, str]] = None,
) -> str:
    """Format prompt for generating a CDK TypeScript Stack for a single layer.

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
        context_text += "These stacks are already defined. Import resources via props:\n"
        for layer_file in previous_layers:
            context_text += f"- {layer_file}\n"

    lambda_code_text = ""
    if lambda_code_paths:
        lambda_code_text = "\n\n## Lambda Code Files\n\n"
        lambda_code_text += "Use `lambda.Code.fromAsset()` to reference these pre-extracted code archives:\n\n"
        for func_name, code_path in lambda_code_paths.items():
            lambda_code_text += f"- `{func_name}` -> `{code_path}`\n"

    prompt = f"""Generate a CDK TypeScript Stack class for the **{layer.name}** layer.

## Stack Class Name: `{stack_class_name}`

## Constructs to Generate ({len(layer.resources)} resource{"s" if len(layer.resources) != 1 else ""})

{resources_text}

{map_text}
{context_text}
{lambda_code_text}

Generate complete, valid TypeScript CDK Stack code for all resources above.
Include the Props interface, Stack class, and export statements.
"""

    return prompt


def format_resource_for_cdk_prompt(
    resource: TrackedResource,
    lambda_code_paths: Optional[Dict[str, str]] = None,
) -> str:
    """Format a single resource for inclusion in CDK TypeScript prompt.

    Args:
        resource: The resource to format
        lambda_code_paths: Mapping of Lambda function names to extracted code file paths

    Returns:
        Formatted resource description
    """
    property_map = get_property_map(resource.resource_type)
    props = _filter_properties(resource.raw_config, property_map, resource.resource_type)

    # Generate CDK-style construct ID (camelCase)
    construct_id = _to_camel_case(resource.name)

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
        lines.append(f"(Use `lambda.Code.fromAsset('{code_path}')` in the Function construct)")

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
    # Split on common separators
    parts = name.replace("-", "_").replace(" ", "_").split("_")
    return "".join(part.capitalize() for part in parts if part)


def _to_camel_case(name: str) -> str:
    """Convert a name to camelCase.

    Args:
        name: Name to convert (may contain underscores, hyphens, or spaces)

    Returns:
        camelCase version of the name
    """
    pascal = _to_pascal_case(name)
    if not pascal:
        return ""
    return pascal[0].lower() + pascal[1:]


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


def format_retry_prompt_typescript(
    original_code: str,
    validation_errors: List[str],
    layer: Layer,
    resource_map: ResourceMap,
) -> str:
    """Format prompt for retrying after validation failure.

    Args:
        original_code: The invalid TypeScript code
        validation_errors: List of tsc/cdk synth errors
        layer: The layer being generated
        resource_map: Available resource references

    Returns:
        Formatted retry prompt
    """
    errors_text = "\n".join(f"- {err}" for err in validation_errors)

    prompt = f"""The CDK TypeScript code you generated has validation errors. Please fix them.

## Validation Errors

{errors_text}

## Original Code

```typescript
{original_code}
```

## Available Resource References

{_format_resource_map_text(resource_map)}

Generate the corrected CDK TypeScript code. Return ONLY valid TypeScript, no markdown or explanations.
"""

    return prompt


def _format_resource_map_text(resource_map: ResourceMap) -> str:
    """Format resource map as text for prompts."""
    lines = []
    for aws_id, cdk_ref in resource_map.id_to_ref.items():
        lines.append(f"- `{aws_id}` -> `{cdk_ref}`")
    return "\n".join(lines) if lines else "(No resource references available yet)"
