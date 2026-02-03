"""Standalone IaC coverage comparison.

Compares inventory resources against existing IaC code without regenerating.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..models.generation import TrackedResource
from .nodes.compare_inventory import compare_inventory
from .nodes.parse_inventory import parse_inventory
from .state import GenerationState, set_progress_callback

# Progress callback type
ProgressCallback = Callable[[str, Dict[str, Any]], None]


@dataclass
class ComparisonResult:
    """Result of IaC coverage comparison."""

    coverage_percentage: float
    total_resources: int
    represented_count: int
    missing_count: int
    represented_resources: List[Dict[str, Any]] = field(default_factory=list)
    missing_resources: List[Dict[str, Any]] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if comparison completed without errors."""
        return len(self.errors) == 0


def compare_coverage(
    snapshot_name: Optional[str] = None,
    inventory_file: Optional[str] = None,
    iac_dir: str = "./terraform",
    progress_callback: Optional[ProgressCallback] = None,
) -> ComparisonResult:
    """Compare inventory against existing IaC code.

    Args:
        snapshot_name: Name of snapshot to compare (use this OR inventory_file)
        inventory_file: Path to inventory JSON/YAML file (use this OR snapshot_name)
        iac_dir: Directory containing IaC files (.tf, .ts, .py)
        progress_callback: Optional callback for progress updates

    Returns:
        ComparisonResult with coverage analysis
    """
    if not snapshot_name and not inventory_file:
        return ComparisonResult(
            coverage_percentage=0.0,
            total_resources=0,
            represented_count=0,
            missing_count=0,
            errors=["Either snapshot_name or inventory_file must be provided"],
        )

    if not os.path.isdir(iac_dir):
        return ComparisonResult(
            coverage_percentage=0.0,
            total_resources=0,
            represented_count=0,
            missing_count=0,
            errors=[f"IaC directory does not exist: {iac_dir}"],
        )

    # Set progress callback if provided
    if progress_callback:
        set_progress_callback(progress_callback)

    try:
        # Step 1: Load inventory
        if progress_callback:
            progress_callback("activity", {"message": "Loading inventory..."})

        parse_state: GenerationState = {
            "snapshot_name": snapshot_name or "",
            "input_file": inventory_file or "",
        }
        parse_result = parse_inventory(parse_state)

        if parse_result.get("errors"):
            return ComparisonResult(
                coverage_percentage=0.0,
                total_resources=0,
                represented_count=0,
                missing_count=0,
                errors=parse_result["errors"],
            )

        resources = parse_result.get("resources", [])
        if not resources:
            return ComparisonResult(
                coverage_percentage=0.0,
                total_resources=0,
                represented_count=0,
                missing_count=0,
                errors=["No resources found in inventory"],
            )

        if progress_callback:
            progress_callback("activity", {"message": f"Loaded {len(resources)} resources"})

        # Step 2: Read IaC files from directory
        if progress_callback:
            progress_callback("activity", {"message": f"Reading IaC files from {iac_dir}"})

        generated_code = _read_iac_files(iac_dir)

        if not generated_code:
            return ComparisonResult(
                coverage_percentage=0.0,
                total_resources=len(resources),
                represented_count=0,
                missing_count=len(resources),
                missing_resources=[
                    {"type": _get_resource_type(r), "name": _get_resource_name(r), "reason": "No IaC files found"}
                    for r in resources
                ],
                errors=[f"No IaC files found in {iac_dir}"],
            )

        if progress_callback:
            progress_callback("activity", {"message": f"Found {len(generated_code)} IaC files"})

        # Step 3: Run comparison
        if progress_callback:
            progress_callback("activity", {"message": "Running coverage comparison..."})

        compare_state: GenerationState = {
            "resources": resources,
            "generated_code": generated_code,
        }
        compare_result = compare_inventory(compare_state)

        comparison = compare_result.get("comparison_result", {})
        errors = compare_result.get("errors", [])

        return ComparisonResult(
            coverage_percentage=comparison.get("coverage_percentage", 0.0),
            total_resources=comparison.get("total_resources", len(resources)),
            represented_count=comparison.get("represented_count", 0),
            missing_count=comparison.get("missing_count", 0),
            represented_resources=comparison.get("represented_resources", []),
            missing_resources=comparison.get("missing_resources", []),
            issues=comparison.get("issues", []),
            summary=comparison.get("summary", ""),
            errors=[e.get("message", str(e)) if isinstance(e, dict) else str(e) for e in errors] if errors else [],
        )

    except Exception as e:
        return ComparisonResult(
            coverage_percentage=0.0,
            total_resources=0,
            represented_count=0,
            missing_count=0,
            errors=[f"Comparison failed: {e}"],
        )

    finally:
        # Clear progress callback
        if progress_callback:
            set_progress_callback(None)


def _read_iac_files(iac_dir: str) -> Dict[str, str]:
    """Read all IaC files from a directory.

    Supports:
    - Terraform: .tf files
    - CDK TypeScript: .ts files
    - CDK Python: .py files

    Args:
        iac_dir: Directory to scan

    Returns:
        Dict mapping filename to content
    """
    iac_files: Dict[str, str] = {}
    iac_extensions = {".tf", ".ts", ".py"}

    path = Path(iac_dir)
    for file_path in path.rglob("*"):
        if file_path.is_file() and file_path.suffix in iac_extensions:
            # Skip node_modules, __pycache__, etc.
            if any(part.startswith(".") or part in ("node_modules", "__pycache__", "cdk.out")
                   for part in file_path.parts):
                continue

            try:
                content = file_path.read_text()
                # Use relative path as key
                rel_path = str(file_path.relative_to(path))
                iac_files[rel_path] = content
            except Exception:
                continue

    return iac_files


def _get_resource_type(resource: Any) -> str:
    """Extract resource type from TrackedResource or dict."""
    if isinstance(resource, TrackedResource):
        return resource.resource_type
    if isinstance(resource, dict):
        return resource.get("resource_type", resource.get("type", "unknown"))
    return "unknown"


def _get_resource_name(resource: Any) -> str:
    """Extract resource name from TrackedResource or dict."""
    if isinstance(resource, TrackedResource):
        return resource.name
    if isinstance(resource, dict):
        return resource.get("name", "unnamed")
    return "unnamed"
