"""Generate layer node for LangGraph workflow."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import boto3

from ...models.generation import Layer, ResourceMap
from ..layers import LayerStatus
from ..prompts.terraform import (
    format_layer_prompt,
    get_terraform_system_prompt,
)
from ..state import GenerationConfig, GenerationState, emit_progress


def generate_layer(state: GenerationState) -> Dict[str, Any]:
    """Generate Terraform for the current layer using AI.

    Calls AWS Bedrock to generate Terraform HCL for resources in the current layer.

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

    config = GenerationConfig.from_env()

    if current_layer_index >= len(layer_order):
        return {"errors": [{"message": "No more layers to generate"}]}

    layer_name = layer_order[current_layer_index]
    layer_resources = layers.get(layer_name, [])

    if not layer_resources:
        return {
            "current_layer_index": current_layer_index + 1,
            "current_layer_status": LayerStatus.COMPLETED.value,
        }

    # Emit progress: starting layer generation
    emit_progress("activity", {
        "message": f"Preparing {layer_name} layer ({len(layer_resources)} resources)",
        "layer": layer_name,
        "resource_count": len(layer_resources),
    })

    layer = Layer(
        name=layer_name,
        order=current_layer_index,
        resources=layer_resources,
        status=LayerStatus.GENERATING.value,
    )

    try:
        # Emit progress: creating Bedrock client
        emit_progress("activity", {
            "message": f"Connecting to Bedrock ({config.bedrock_region})",
            "layer": layer_name,
        })

        client = boto3.client("bedrock-runtime", region_name=config.bedrock_region)

        # Emit progress: building prompt
        emit_progress("activity", {
            "message": f"Building prompt for {len(layer_resources)} resources",
            "layer": layer_name,
        })

        system_prompt = get_terraform_system_prompt()
        user_prompt = format_layer_prompt(
            layer=layer,
            resource_map=resource_map,
            previous_layers=generated_files,
            lambda_code_paths=lambda_code_paths,
        )

        # Emit progress: calling AI
        emit_progress("activity", {
            "message": f"Calling AI to generate Terraform ({config.bedrock_model_id.split('/')[-1]})",
            "layer": layer_name,
            "model": config.bedrock_model_id,
        })

        # Use streaming API for real-time progress
        terraform_code = ""
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
                            terraform_code += delta["text"]
                            token_count += 1
                            # Emit progress every 50 tokens
                            if token_count % 50 == 0:
                                emit_progress("activity", {
                                    "message": f"Generating code... ({token_count} tokens)",
                                    "layer": layer_name,
                                    "tokens": token_count,
                                })

            # If streaming didn't produce any code, fall back to non-streaming
            if not terraform_code:
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
            terraform_code = response["output"]["message"]["content"][0]["text"] or ""

        # Emit progress: processing response
        emit_progress("activity", {
            "message": f"Processing AI response ({len(terraform_code)} chars)",
            "layer": layer_name,
            "code_length": len(terraform_code),
        })

        terraform_code = _clean_terraform_code(terraform_code)

        # Emit progress: replacing IDs
        emit_progress("activity", {
            "message": "Replacing AWS IDs with Terraform references",
            "layer": layer_name,
        })

        terraform_code = resource_map.replace_ids_in_code(terraform_code)

        # Emit progress: saving file
        emit_progress("activity", {
            "message": f"Saving {layer_name} Terraform file",
            "layer": layer_name,
        })

        output_file = _save_layer_file(
            layer=layer,
            code=terraform_code,
            output_dir=output_dir,
        )

        layer.status = LayerStatus.COMPLETED.value
        layer.generated_code = terraform_code

        layers[layer_name] = layer_resources

        # Emit progress: layer complete
        emit_progress("activity", {
            "message": f"Completed {layer_name} layer",
            "layer": layer_name,
            "file": output_file,
        })

        return {
            "layers": layers,
            "generated_files": [output_file],
            "generated_code": {layer_name: terraform_code},
            "current_layer_index": current_layer_index + 1,
            "current_layer_status": LayerStatus.COMPLETED.value,
        }

    except Exception as e:
        layer.status = LayerStatus.FAILED.value
        emit_progress("activity", {
            "message": f"Failed: {str(e)[:50]}",
            "layer": layer_name,
            "error": str(e),
        })
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


def _save_layer_file(layer: Layer, code: str, output_dir: str) -> str:
    """Save generated Terraform to a file.

    File naming: layer_{order}_{name}.tf
    Example: layer_01_network.tf
    """
    os.makedirs(output_dir, exist_ok=True)

    safe_name = layer.name.lower().replace(" ", "_").replace("-", "_")
    filename = f"layer_{layer.order:02d}_{safe_name}.tf"
    filepath = os.path.join(output_dir, filename)

    header = f"""# {layer.name}
# Generated by aws-inventory-manager
# Resources: {len(layer.resources)}

"""

    with open(filepath, "w") as f:
        f.write(header + code)

    return filepath
