"""CDK validation nodes for the generation workflow.

Runs `npm install`, `npm run build` (for TypeScript), and `cdk synth` on generated code.
Split into separate nodes for real-time progress updates.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any, Dict

from ..state import GenerationState

logger = logging.getLogger(__name__)


def npm_build(state: GenerationState) -> Dict[str, Any]:
    """Run npm install and npm run build for TypeScript CDK projects.

    Args:
        state: Current generation state

    Returns:
        State updates with npm_build_success flag and any errors
    """
    output_dir = state.get("output_dir", "./cdk")
    generated_files = state.get("generated_files", [])
    output_format = state.get("output_format", "cdk-typescript")

    # Skip if no files were generated
    if not generated_files:
        logger.warning("No generated files to validate")
        return {
            "npm_build_success": False,
            "validation_errors": [],
            "validation_skipped": True,
        }

    # Skip npm for Python projects
    if output_format == "cdk-python":
        logger.info("Skipping npm build for Python CDK project")
        return {"npm_build_success": True, "npm_build_skipped": True}

    # Check if npm CLI is available
    npm_path = shutil.which("npm")
    if not npm_path:
        error = "npm CLI not found in PATH - skipping TypeScript build"
        logger.warning(error)
        return {"npm_build_success": False, "validation_errors": [error]}

    # Ensure output directory exists
    if not os.path.isdir(output_dir):
        error = f"Output directory does not exist: {output_dir}"
        logger.error(error)
        return {"npm_build_success": False, "validation_errors": [error]}

    # Check if package.json exists
    package_json = os.path.join(output_dir, "package.json")
    if not os.path.isfile(package_json):
        error = f"package.json not found in {output_dir}"
        logger.error(error)
        return {"npm_build_success": False, "validation_errors": [error]}

    validation_errors: list[str] = []

    # Run npm install
    logger.info(f"Running npm install in {output_dir}")
    try:
        install_result = subprocess.run(
            ["npm", "install"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes for npm install
        )

        if install_result.returncode != 0:
            error_msg = f"npm install failed: {install_result.stderr.strip()}"
            logger.error(error_msg)
            return {"npm_build_success": False, "validation_errors": [error_msg]}

        logger.info("npm install successful")

    except subprocess.TimeoutExpired:
        error = "npm install timed out after 300 seconds"
        logger.error(error)
        return {"npm_build_success": False, "validation_errors": [error]}
    except Exception as e:
        error = f"npm install error: {e}"
        logger.error(error)
        return {"npm_build_success": False, "validation_errors": [error]}

    # Run npm run build (TypeScript compilation)
    logger.info(f"Running npm run build in {output_dir}")
    try:
        build_result = subprocess.run(
            ["npm", "run", "build"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if build_result.returncode != 0:
            error_msg = f"npm run build failed: {build_result.stderr.strip()}"
            logger.error(error_msg)

            # Parse TypeScript errors from output
            for line in build_result.stdout.split("\n") + build_result.stderr.split("\n"):
                if "error TS" in line or "Error:" in line:
                    validation_errors.append(line.strip())

            if not validation_errors:
                validation_errors.append(error_msg)

            return {"npm_build_success": False, "validation_errors": validation_errors}

        logger.info("npm run build successful")
        return {"npm_build_success": True}

    except subprocess.TimeoutExpired:
        error = "npm run build timed out after 120 seconds"
        logger.error(error)
        return {"npm_build_success": False, "validation_errors": [error]}
    except Exception as e:
        error = f"npm run build error: {e}"
        logger.error(error)
        return {"npm_build_success": False, "validation_errors": [error]}


def pip_install(state: GenerationState) -> Dict[str, Any]:
    """Run pip install for Python CDK projects.

    Args:
        state: Current generation state

    Returns:
        State updates with pip_install_success flag and any errors
    """
    output_dir = state.get("output_dir", "./cdk")
    generated_files = state.get("generated_files", [])
    output_format = state.get("output_format", "cdk-python")

    # Skip if no files were generated
    if not generated_files:
        logger.warning("No generated files to validate")
        return {
            "pip_install_success": False,
            "validation_errors": [],
            "validation_skipped": True,
        }

    # Skip pip for TypeScript projects
    if output_format == "cdk-typescript":
        logger.info("Skipping pip install for TypeScript CDK project")
        return {"pip_install_success": True, "pip_install_skipped": True}

    # Check if pip is available
    pip_path = shutil.which("pip") or shutil.which("pip3")
    if not pip_path:
        error = "pip CLI not found in PATH - skipping Python dependency install"
        logger.warning(error)
        return {"pip_install_success": False, "validation_errors": [error]}

    # Ensure output directory exists
    if not os.path.isdir(output_dir):
        error = f"Output directory does not exist: {output_dir}"
        logger.error(error)
        return {"pip_install_success": False, "validation_errors": [error]}

    # Check if requirements.txt exists
    requirements_txt = os.path.join(output_dir, "requirements.txt")
    if not os.path.isfile(requirements_txt):
        error = f"requirements.txt not found in {output_dir}"
        logger.error(error)
        return {"pip_install_success": False, "validation_errors": [error]}

    # Run pip install
    logger.info(f"Running pip install in {output_dir}")
    try:
        pip_cmd = pip_path.split("/")[-1]  # pip or pip3
        install_result = subprocess.run(
            [pip_cmd, "install", "-r", "requirements.txt"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if install_result.returncode != 0:
            error_msg = f"pip install failed: {install_result.stderr.strip()}"
            logger.error(error_msg)
            return {"pip_install_success": False, "validation_errors": [error_msg]}

        logger.info("pip install successful")
        return {"pip_install_success": True}

    except subprocess.TimeoutExpired:
        error = "pip install timed out after 300 seconds"
        logger.error(error)
        return {"pip_install_success": False, "validation_errors": [error]}
    except Exception as e:
        error = f"pip install error: {e}"
        logger.error(error)
        return {"pip_install_success": False, "validation_errors": [error]}


def cdk_synth(state: GenerationState) -> Dict[str, Any]:
    """Run cdk synth to validate CDK code.

    Args:
        state: Current generation state

    Returns:
        State updates with validation_errors list
    """
    output_dir = state.get("output_dir", "./cdk")
    output_format = state.get("output_format", "cdk-typescript")

    # For TypeScript, check npm_build_success
    if output_format == "cdk-typescript":
        npm_success = state.get("npm_build_success", False)
        if not npm_success:
            logger.warning("Skipping cdk synth - npm build failed or skipped")
            return {}

    # For Python, check pip_install_success (if it ran)
    if output_format == "cdk-python":
        pip_success = state.get("pip_install_success", True)  # Default True if not run
        if not pip_success:
            logger.warning("Skipping cdk synth - pip install failed")
            return {}

    # Check if cdk CLI is available
    cdk_path = shutil.which("cdk")
    if not cdk_path:
        error = "cdk CLI not found in PATH - skipping synthesis validation"
        logger.warning(error)
        return {"validation_errors": [error]}

    validation_errors: list[str] = []

    logger.info(f"Running cdk synth in {output_dir}")
    try:
        synth_result = subprocess.run(
            ["cdk", "synth", "--no-staging"],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120,
            env={
                **os.environ,
                "CDK_DEFAULT_ACCOUNT": "123456789012",
                "CDK_DEFAULT_REGION": "us-east-1",
            },
        )

        if synth_result.returncode != 0:
            error_output = synth_result.stderr.strip() or synth_result.stdout.strip()

            # Parse CDK synth errors
            for line in error_output.split("\n"):
                line = line.strip()
                if line and ("Error:" in line or "error:" in line.lower() or "failed" in line.lower()):
                    validation_errors.append(line)

            if not validation_errors:
                validation_errors.append(f"cdk synth failed: {error_output[:200]}")

            logger.warning(f"cdk synth found {len(validation_errors)} errors")
        else:
            logger.info("cdk synth successful - no errors")

    except subprocess.TimeoutExpired:
        error = "cdk synth timed out after 120 seconds"
        logger.error(error)
        validation_errors.append(error)
    except Exception as e:
        error = f"cdk synth error: {e}"
        logger.error(error)
        validation_errors.append(error)

    return {"validation_errors": validation_errors}


def validate_cdk(state: GenerationState) -> Dict[str, Any]:
    """Validate generated CDK code.

    Runs appropriate validation based on output_format:
    - cdk-typescript: npm install, npm run build, cdk synth
    - cdk-python: pip install, cdk synth

    This is a combined function for convenience.

    Args:
        state: Current generation state

    Returns:
        State updates with validation_errors list
    """
    output_format = state.get("output_format", "cdk-typescript")

    if output_format == "cdk-typescript":
        # TypeScript: npm install + build + synth
        npm_result = npm_build(state)

        if npm_result.get("validation_skipped", False):
            return {"validation_errors": []}

        if not npm_result.get("npm_build_success", False):
            return {"validation_errors": npm_result.get("validation_errors", [])}

        state_with_npm = dict(state)
        state_with_npm["npm_build_success"] = True
        synth_result = cdk_synth(state_with_npm)

        return {"validation_errors": synth_result.get("validation_errors", [])}

    else:
        # Python: pip install + synth
        pip_result = pip_install(state)

        if pip_result.get("validation_skipped", False):
            return {"validation_errors": []}

        if not pip_result.get("pip_install_success", False):
            return {"validation_errors": pip_result.get("validation_errors", [])}

        state_with_pip = dict(state)
        state_with_pip["pip_install_success"] = True
        synth_result = cdk_synth(state_with_pip)

        return {"validation_errors": synth_result.get("validation_errors", [])}


def is_cdk_available() -> bool:
    """Check if CDK CLI is available.

    Returns:
        True if cdk is found in PATH
    """
    return shutil.which("cdk") is not None


def is_npm_available() -> bool:
    """Check if npm CLI is available.

    Returns:
        True if npm is found in PATH
    """
    return shutil.which("npm") is not None
