"""Generate layer node for LangGraph workflow."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Tuple

import boto3

from ...models.generation import Layer, ResourceMap
from ..layers import LayerStatus
from ..prompts.cdk_python import (
    format_layer_prompt_python,
    get_cdk_python_system_prompt,
)
from ..prompts.cdk_typescript import (
    format_layer_prompt_typescript,
    get_cdk_typescript_system_prompt,
)
from ..prompts.terraform import (
    format_layer_prompt,
    get_terraform_system_prompt,
)
from ..state import GenerationConfig, GenerationState, emit_progress


def get_prompts_for_format(
    output_format: str,
) -> Tuple[Callable[[], str], Callable[..., str]]:
    """Get the appropriate prompt functions for the output format.

    Args:
        output_format: One of 'terraform', 'cdk-typescript', 'cdk-python'

    Returns:
        Tuple of (system_prompt_fn, layer_prompt_fn)
    """
    if output_format == "cdk-typescript":
        return (get_cdk_typescript_system_prompt, format_layer_prompt_typescript)
    elif output_format == "cdk-python":
        return (get_cdk_python_system_prompt, format_layer_prompt_python)
    else:
        # Default to terraform
        return (get_terraform_system_prompt, format_layer_prompt)


def _get_file_extension(output_format: str) -> str:
    """Get the file extension for the output format.

    Args:
        output_format: One of 'terraform', 'cdk-typescript', 'cdk-python'

    Returns:
        File extension including the dot (e.g., '.tf', '.ts', '.py')
    """
    if output_format == "cdk-typescript":
        return ".ts"
    elif output_format == "cdk-python":
        return ".py"
    else:
        return ".tf"


def _get_format_label(output_format: str) -> str:
    """Get a human-readable label for the output format.

    Args:
        output_format: One of 'terraform', 'cdk-typescript', 'cdk-python'

    Returns:
        Human-readable label (e.g., 'Terraform', 'CDK TypeScript')
    """
    if output_format == "cdk-typescript":
        return "CDK TypeScript"
    elif output_format == "cdk-python":
        return "CDK Python"
    else:
        return "Terraform"


def _clean_code(code: str, output_format: str) -> str:
    """Remove markdown code blocks based on output format.

    Args:
        code: Raw code potentially wrapped in markdown
        output_format: One of 'terraform', 'cdk-typescript', 'cdk-python'

    Returns:
        Cleaned code without markdown formatting
    """
    code = code.strip()

    # Define possible markdown prefixes for each format
    prefixes = {
        "terraform": ["```hcl", "```terraform", "```tf"],
        "cdk-typescript": ["```typescript", "```ts", "```tsx"],
        "cdk-python": ["```python", "```py"],
    }

    format_prefixes = prefixes.get(output_format, prefixes["terraform"])

    for prefix in format_prefixes:
        if code.startswith(prefix):
            code = code[len(prefix) :]
            break
    else:
        # Generic markdown block
        if code.startswith("```"):
            code = code[3:]

    if code.endswith("```"):
        code = code[:-3]

    return code.strip()


def _apply_auto_fixes(
    resources: List[Dict[str, Any]],
    auto_fixes: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Apply guardrail auto-fixes to resource configurations.

    Args:
        resources: List of resource dictionaries
        auto_fixes: Dict mapping resource_id -> {guardrail_id -> fix_config}

    Returns:
        Resources with auto-fixes merged into their configs
    """
    import copy

    if not auto_fixes:
        return resources

    fixed_resources = []
    for resource in resources:
        resource = copy.deepcopy(resource)

        # Build resource_id (same logic as in evaluator)
        resource_arn = resource.get("arn", "")
        resource_type = resource.get("resource_type", "")
        resource_name = resource.get("name", "")
        resource_id = resource_arn or f"{resource_type}/{resource_name}"

        # Check if there are fixes for this resource
        if resource_id in auto_fixes:
            fixes = auto_fixes[resource_id]
            config = resource.get("config", {})

            # Merge all fixes into the config
            for guardrail_id, fix_config in fixes.items():
                config = _deep_merge(config, fix_config)

            resource["config"] = config

        fixed_resources.append(resource)

    return fixed_resources


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge overlay dict into base dict."""
    import copy

    result = copy.deepcopy(base)

    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)

    return result


def generate_layer(state: GenerationState) -> Dict[str, Any]:
    """Generate IaC code for the current layer using AI.

    Calls AWS Bedrock to generate Terraform/CDK code for resources in the current layer.
    Applies any guardrail auto-fixes to resource configs before generating.

    Args:
        state: Current state with layers, resource_map, and config

    Returns:
        Dict with:
        - layers: Updated layers with generated code
        - generated_files: List of generated file paths (appended)
        - errors: List of errors (appended)
    """
    layers: Dict[str, List[Dict[str, Any]]] = state.get("layers", {})
    layer_order: List[str] = state.get("layer_order", [])
    raw_resource_map = state.get("resource_map")
    resource_map = raw_resource_map if isinstance(raw_resource_map, ResourceMap) else ResourceMap()
    current_layer_index: int = state.get("current_layer_index", 0)
    generated_files: List[str] = list(state.get("generated_files", []))
    output_dir: str = state.get("output_dir", "./terraform")
    lambda_code_paths: Dict[str, str] = state.get("lambda_code_paths", {})
    output_format: str = state.get("output_format", "terraform")
    guardrails_auto_fixes: Dict[str, Dict[str, Any]] = state.get("guardrails_auto_fixes", {})

    config = GenerationConfig.from_env()

    if current_layer_index >= len(layer_order):
        return {"errors": [{"message": "No more layers to generate"}]}

    layer_name = layer_order[current_layer_index]
    layer_resources = layers.get(layer_name, [])

    # Apply guardrail auto-fixes to resources before generating
    if guardrails_auto_fixes:
        layer_resources = _apply_auto_fixes(layer_resources, guardrails_auto_fixes)

    if not layer_resources:
        return {
            "current_layer_index": current_layer_index + 1,
            "current_layer_status": LayerStatus.COMPLETED.value,
        }

    # Emit progress: starting layer generation
    emit_progress(
        "activity",
        {
            "message": f"Preparing {layer_name} layer ({len(layer_resources)} resources)",
            "layer": layer_name,
            "resource_count": len(layer_resources),
        },
    )

    layer = Layer(
        name=layer_name,
        order=current_layer_index,
        resources=layer_resources,
        status=LayerStatus.GENERATING.value,
    )

    try:
        # Emit progress: creating Bedrock client
        emit_progress(
            "activity",
            {
                "message": f"Connecting to Bedrock ({config.bedrock_region})",
                "layer": layer_name,
            },
        )

        client = boto3.client("bedrock-runtime", region_name=config.bedrock_region)

        # Emit progress: building prompt
        format_label = _get_format_label(output_format)
        emit_progress(
            "activity",
            {
                "message": f"Building {format_label} prompt for {len(layer_resources)} resources",
                "layer": layer_name,
            },
        )

        # Get appropriate prompts for the output format
        get_system_prompt, format_layer = get_prompts_for_format(output_format)
        system_prompt = get_system_prompt()
        user_prompt = format_layer(
            layer=layer,
            resource_map=resource_map,
            previous_layers=generated_files,
            lambda_code_paths=lambda_code_paths,
        )

        # Emit progress: calling AI
        emit_progress(
            "activity",
            {
                "message": f"Calling AI to generate {format_label} ({config.bedrock_model_id.split('/')[-1]})",
                "layer": layer_name,
                "model": config.bedrock_model_id,
            },
        )

        # Use streaming API for real-time progress
        generated_code = ""
        token_count = 0

        try:
            stream_response = client.converse_stream(
                modelId=config.bedrock_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ],
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "temperature": config.temperature,
                    "maxTokens": config.max_tokens,
                },
            )

            # Stream is an EventStream object
            event_stream = stream_response.get("stream")
            if event_stream:
                for event in event_stream:
                    if "contentBlockDelta" in event:
                        delta = event["contentBlockDelta"].get("delta", {})
                        if "text" in delta:
                            generated_code += delta["text"]
                            token_count += 1
                            # Emit progress every 50 tokens
                            if token_count % 50 == 0:
                                emit_progress(
                                    "activity",
                                    {
                                        "message": f"Generating code... ({token_count} tokens)",
                                        "layer": layer_name,
                                        "tokens": token_count,
                                    },
                                )

            # If streaming didn't produce any code, fall back to non-streaming
            if not generated_code:
                raise ValueError("Streaming produced no output")

        except Exception:
            # Fall back to non-streaming if streaming fails
            response = client.converse(
                modelId=config.bedrock_model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}],
                    }
                ],
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "temperature": config.temperature,
                    "maxTokens": config.max_tokens,
                },
            )
            generated_code = response["output"]["message"]["content"][0]["text"] or ""

        # Emit progress: processing response
        emit_progress(
            "activity",
            {
                "message": f"Processing AI response ({len(generated_code)} chars)",
                "layer": layer_name,
                "code_length": len(generated_code),
            },
        )

        generated_code = _clean_code(generated_code, output_format)

        # Emit progress: replacing IDs
        emit_progress(
            "activity",
            {
                "message": f"Replacing AWS IDs with {format_label} references",
                "layer": layer_name,
            },
        )

        generated_code = resource_map.replace_ids_in_code(generated_code)

        # Emit progress: saving file
        emit_progress(
            "activity",
            {
                "message": f"Saving {layer_name} {format_label} file",
                "layer": layer_name,
            },
        )

        output_file = _save_layer_file(
            layer=layer,
            code=generated_code,
            output_dir=output_dir,
            output_format=output_format,
        )

        layer.status = LayerStatus.COMPLETED.value
        layer.generated_code = generated_code

        layers[layer_name] = layer_resources

        # Emit progress: layer complete
        emit_progress(
            "activity",
            {
                "message": f"Completed {layer_name} layer",
                "layer": layer_name,
                "file": output_file,
            },
        )

        return {
            "layers": layers,
            "generated_files": [output_file],
            "generated_code": {layer_name: generated_code},
            "current_layer_index": current_layer_index + 1,
            "current_layer_status": LayerStatus.COMPLETED.value,
        }

    except Exception as e:
        layer.status = LayerStatus.FAILED.value
        emit_progress(
            "activity",
            {
                "message": f"Failed: {str(e)[:50]}",
                "layer": layer_name,
                "error": str(e),
            },
        )
        return {
            "layers": layers,
            "errors": [{"message": f"Failed to generate {layer_name}: {e}"}],
            "current_layer_index": current_layer_index + 1,  # Skip failed layer
            "current_layer_status": LayerStatus.FAILED.value,
        }


def _clean_terraform_code(code: str) -> str:
    """Remove markdown code blocks if present."""
    code = code.strip()

    if code.startswith("```hcl"):
        code = code[6:]
    elif code.startswith("```terraform"):
        code = code[12:]
    elif code.startswith("```"):
        code = code[3:]

    if code.endswith("```"):
        code = code[:-3]

    return code.strip()


def _save_layer_file(layer: Layer, code: str, output_dir: str, output_format: str = "terraform") -> str:
    """Save generated IaC code to a file.

    File naming varies by format:
    - Terraform: layer_{order}_{name}.tf (e.g., layer_01_network.tf)
    - CDK TypeScript: {name}_stack.ts (e.g., network_stack.ts)
    - CDK Python: {name}_stack.py (e.g., network_stack.py)

    Args:
        layer: The layer being saved
        code: Generated code to save
        output_dir: Directory to save the file in
        output_format: Output format (terraform, cdk-typescript, cdk-python)

    Returns:
        Path to the saved file
    """
    os.makedirs(output_dir, exist_ok=True)

    safe_name = layer.name.lower().replace(" ", "_").replace("-", "_")
    extension = _get_file_extension(output_format)

    if output_format == "terraform":
        filename = f"layer_{layer.order:02d}_{safe_name}{extension}"
    else:
        # CDK uses stack naming convention
        # Put stacks in a stacks/ subdirectory for CDK projects
        stacks_dir = os.path.join(output_dir, "stacks" if output_format == "cdk-python" else "lib")
        os.makedirs(stacks_dir, exist_ok=True)
        filename = f"{safe_name}_stack{extension}"
        output_dir = stacks_dir

    filepath = os.path.join(output_dir, filename)

    # Generate appropriate header based on format
    if output_format == "terraform":
        header = f"""# {layer.name}
# Generated by aws-inventory-manager
# Resources: {len(layer.resources)}

"""
    elif output_format == "cdk-typescript":
        header = f"""// {layer.name} Stack
// Generated by aws-inventory-manager
// Resources: {len(layer.resources)}

"""
    else:  # cdk-python
        header = f'''"""
{layer.name} Stack
Generated by aws-inventory-manager
Resources: {len(layer.resources)}
"""

'''

    with open(filepath, "w") as f:
        f.write(header + code)

    return filepath
