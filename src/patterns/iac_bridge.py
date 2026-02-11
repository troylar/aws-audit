"""Bridge between Pattern definitions and IaC generators."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Pattern


def pattern_to_inventory(pattern: Pattern) -> List[Dict[str, Any]]:
    """Convert a Pattern to a list of inventory resource dicts.

    Each PatternResource generates ``count`` inventory entries.
    The expect fields are used as raw_config values.
    """
    resources: List[Dict[str, Any]] = []
    for pat_resource in pattern.resources:
        for i in range(pat_resource.count):
            resource: Dict[str, Any] = {
                "arn": f"arn:aws:pattern:{pattern.name}:{pat_resource.type}:{i}",
                "resource_type": pat_resource.type,
                "name": f"{pat_resource.type.replace(':', '-')}-{i}",
                "region": "us-east-1",
                "tags": {},
                "raw_config": dict(pat_resource.expect) if pat_resource.expect else {},
            }
            resources.append(resource)
    return resources


def pattern_to_input_file(pattern: Pattern, output_dir: Optional[str] = None) -> str:
    """Write Pattern as a JSON inventory file for generator consumption.

    Args:
        pattern: The pattern to convert.
        output_dir: Directory to write the file to. If None, uses a temp directory.

    Returns:
        Path to the generated JSON file.
    """
    resources = pattern_to_inventory(pattern)

    if output_dir:
        path = Path(output_dir) / f"{pattern.name}-inventory.json"
    else:
        tmpdir = tempfile.mkdtemp()
        path = Path(tmpdir) / f"{pattern.name}-inventory.json"

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(resources, f, indent=2)

    return str(path)


def generate_iac_from_pattern(
    pattern: Pattern,
    output_format: str = "terraform",
    output_dir: str = "./output",
    guardrails_enabled: bool = False,
    guardrails_policy_path: Optional[str] = None,
    best_practices_enabled: bool = True,
) -> Any:
    """Generate IaC code from a Pattern definition.

    Args:
        pattern: The pattern to generate IaC from.
        output_format: One of "terraform", "cdk-typescript", "cdk-python".
        output_dir: Directory for generated code.
        guardrails_enabled: Whether to enable guardrails evaluation.
        guardrails_policy_path: Path to custom guardrails policy.
        best_practices_enabled: Whether to enable best practices checks.

    Returns:
        GenerationResult from the underlying generator.

    Raises:
        ValueError: If output_format is not supported.
    """
    valid_formats = ("terraform", "cdk-typescript", "cdk-python")
    if output_format not in valid_formats:
        raise ValueError(f"Unsupported format '{output_format}'. Use one of: {', '.join(valid_formats)}")

    input_file = pattern_to_input_file(pattern)

    try:
        if output_format == "terraform":
            from src.generate.terraform_generator import generate_terraform

            return generate_terraform(
                input_file=input_file,
                output_dir=output_dir,
                guardrails_enabled=guardrails_enabled,
                guardrails_policy_path=guardrails_policy_path,
                best_practices_enabled=best_practices_enabled,
            )
        else:
            from src.generate.cdk_generator import generate_cdk

            return generate_cdk(
                input_file=input_file,
                output_dir=output_dir,
                output_format=output_format,
                guardrails_enabled=guardrails_enabled,
                guardrails_policy_path=guardrails_policy_path,
                best_practices_enabled=best_practices_enabled,
            )
    finally:
        try:
            Path(input_file).unlink(missing_ok=True)
        except Exception:
            pass
