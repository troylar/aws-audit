"""Extract Lambda code node for LangGraph workflow."""

from pathlib import Path
from typing import Any, Dict, List

from ...models.generation import LambdaCode, TrackedResource
from ..state import GenerationState, emit_progress


def extract_lambda_code(state: GenerationState) -> Dict[str, Any]:
    """Extract Lambda function code to external files.

    For Lambda functions with inline code (base64 in raw_config.Code.ZipFile),
    extracts the code to zip files in the output directory.

    Args:
        state: Current state with inventory and output_dir

    Returns:
        Dict with:
        - lambda_code_paths: Dict[str, str] - Function name to zip path mapping
        - errors: List[Dict[str, Any]] - Any extraction errors (appended)
    """
    inventory: List[Dict[str, Any]] = state.get("inventory", [])
    output_dir = state.get("output_dir", "")

    lambda_code_paths: Dict[str, str] = state.get("lambda_code_paths", {}).copy()
    errors: List[Dict[str, Any]] = []

    if not output_dir:
        errors.append(
            {
                "resource": "extract_lambda_code",
                "error": "No output_dir specified in state",
            }
        )
        return {
            "lambda_code_paths": lambda_code_paths,
            "errors": errors,
        }

    lambda_dir = Path(output_dir) / "lambda"

    # Count Lambda functions first
    lambda_functions = [r for r in inventory if r.get("type", r.get("resource_type", "")).startswith("lambda:function")]

    if lambda_functions:
        emit_progress(
            "activity",
            {
                "message": f"Found {len(lambda_functions)} Lambda functions",
                "step": "extract_lambda",
                "count": len(lambda_functions),
            },
        )

    extracted_count = 0
    for i, resource_dict in enumerate(lambda_functions):
        resource_type = resource_dict.get("type", resource_dict.get("resource_type", ""))

        resource = TrackedResource.from_inventory(resource_dict)
        lambda_code = LambdaCode.from_resource(resource)

        if not lambda_code.code_stored or not lambda_code.code_base64:
            continue

        emit_progress(
            "activity",
            {
                "message": f"Extracting {lambda_code.function_name}",
                "step": "extract_lambda",
                "function": lambda_code.function_name,
                "index": i + 1,
                "total": len(lambda_functions),
            },
        )

        try:
            zip_path = lambda_code.extract_to(lambda_dir)
            if zip_path:
                lambda_code_paths[lambda_code.function_name] = zip_path
                extracted_count += 1
        except Exception as e:
            errors.append(
                {
                    "resource": resource.name,
                    "resource_type": resource_type,
                    "error": f"Failed to extract Lambda code: {e}",
                }
            )

    if extracted_count > 0:
        emit_progress(
            "activity",
            {
                "message": f"Extracted {extracted_count} Lambda packages",
                "step": "extract_lambda",
                "extracted": extracted_count,
            },
        )

    return {
        "lambda_code_paths": lambda_code_paths,
        "errors": errors,
    }
