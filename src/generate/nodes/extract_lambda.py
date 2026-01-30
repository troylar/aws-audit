"""Extract Lambda code node for LangGraph workflow."""

from pathlib import Path
from typing import Any, Dict, List

from ...models.generation import LambdaCode, TrackedResource
from ..state import GenerationState


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

    for resource_dict in inventory:
        resource_type = resource_dict.get("type", resource_dict.get("resource_type", ""))
        if not resource_type.startswith("lambda:function"):
            continue

        resource = TrackedResource.from_inventory(resource_dict)
        lambda_code = LambdaCode.from_resource(resource)

        if not lambda_code.code_stored or not lambda_code.code_base64:
            continue

        try:
            zip_path = lambda_code.extract_to(lambda_dir)
            if zip_path:
                lambda_code_paths[lambda_code.function_name] = zip_path
        except Exception as e:
            errors.append(
                {
                    "resource": resource.name,
                    "resource_type": resource_type,
                    "error": f"Failed to extract Lambda code: {e}",
                }
            )

    return {
        "lambda_code_paths": lambda_code_paths,
        "errors": errors,
    }
