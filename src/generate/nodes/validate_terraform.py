"""Terraform validation node for the generation workflow.

Runs `terraform init` and `terraform validate` on generated code to catch errors.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict

from ..state import GenerationState

logger = logging.getLogger(__name__)


def validate_terraform(state: GenerationState) -> Dict[str, Any]:
    """Validate generated Terraform code using terraform CLI.

    Runs `terraform init` followed by `terraform validate` in the output directory.
    Captures validation errors and adds them to state.

    Args:
        state: Current generation state

    Returns:
        State updates with validation_errors list
    """
    output_dir = state.get("output_dir", "./terraform")
    generated_files = state.get("generated_files", [])

    # Skip validation if no files were generated
    if not generated_files:
        logger.warning("No generated files to validate")
        return {"validation_errors": []}

    # Check if terraform CLI is available
    terraform_path = shutil.which("terraform")
    if not terraform_path:
        error = "terraform CLI not found in PATH - skipping validation"
        logger.warning(error)
        return {"validation_errors": [error]}

    # Ensure output directory exists
    if not os.path.isdir(output_dir):
        error = f"Output directory does not exist: {output_dir}"
        logger.error(error)
        return {"validation_errors": [error]}

    validation_errors: list[str] = []

    # Run terraform init
    logger.info(f"Running terraform init in {output_dir}")
    try:
        init_result = subprocess.run(
            ["terraform", "init", "-backend=false", "-input=false"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        if init_result.returncode != 0:
            error_msg = f"terraform init failed: {init_result.stderr.strip()}"
            logger.error(error_msg)
            validation_errors.append(error_msg)
            # Don't proceed to validate if init failed
            return {"validation_errors": validation_errors}

        logger.info("terraform init successful")

    except subprocess.TimeoutExpired:
        error = "terraform init timed out after 120 seconds"
        logger.error(error)
        return {"validation_errors": [error]}
    except Exception as e:
        error = f"terraform init error: {e}"
        logger.error(error)
        return {"validation_errors": [error]}

    # Run terraform validate
    logger.info(f"Running terraform validate in {output_dir}")
    try:
        validate_result = subprocess.run(
            ["terraform", "validate", "-json"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout
        )

        if validate_result.returncode != 0:
            # Parse JSON output for detailed errors
            import json

            try:
                validate_json = json.loads(validate_result.stdout)
                if not validate_json.get("valid", True):
                    for diagnostic in validate_json.get("diagnostics", []):
                        severity = diagnostic.get("severity", "error")
                        summary = diagnostic.get("summary", "Unknown error")
                        detail = diagnostic.get("detail", "")

                        # Get location info if available
                        location = ""
                        if "range" in diagnostic:
                            range_info = diagnostic["range"]
                            filename = range_info.get("filename", "")
                            start_line = range_info.get("start", {}).get("line", 0)
                            if filename:
                                location = f" ({filename}:{start_line})"

                        error_msg = f"{severity}: {summary}{location}"
                        if detail:
                            error_msg += f" - {detail}"
                        validation_errors.append(error_msg)
            except json.JSONDecodeError:
                # Fallback to stderr if JSON parsing fails
                validation_errors.append(f"terraform validate failed: {validate_result.stderr.strip()}")

            logger.warning(f"terraform validate found {len(validation_errors)} errors")
        else:
            logger.info("terraform validate successful - no errors")

    except subprocess.TimeoutExpired:
        error = "terraform validate timed out after 60 seconds"
        logger.error(error)
        validation_errors.append(error)
    except Exception as e:
        error = f"terraform validate error: {e}"
        logger.error(error)
        validation_errors.append(error)

    return {"validation_errors": validation_errors}


def is_terraform_available() -> bool:
    """Check if terraform CLI is available.

    Returns:
        True if terraform is found in PATH
    """
    return shutil.which("terraform") is not None


def run_terraform_fmt(output_dir: str) -> tuple[bool, str]:
    """Run terraform fmt to format generated code.

    Args:
        output_dir: Directory containing terraform files

    Returns:
        Tuple of (success, error_message)
    """
    terraform_path = shutil.which("terraform")
    if not terraform_path:
        return False, "terraform CLI not found in PATH"

    try:
        result = subprocess.run(
            ["terraform", "fmt", "-recursive"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return False, f"terraform fmt failed: {result.stderr.strip()}"

        return True, ""

    except subprocess.TimeoutExpired:
        return False, "terraform fmt timed out"
    except Exception as e:
        return False, f"terraform fmt error: {e}"
