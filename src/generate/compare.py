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
            progress_callback(
                "activity", {"message": f"Loaded {len(resources)} resources"}
            )

        # Step 2: Read IaC files from directory
        if progress_callback:
            progress_callback(
                "activity", {"message": f"Reading IaC files from {iac_dir}"}
            )

        generated_code = _read_iac_files(iac_dir)

        if not generated_code:
            return ComparisonResult(
                coverage_percentage=0.0,
                total_resources=len(resources),
                represented_count=0,
                missing_count=len(resources),
                missing_resources=[
                    {
                        "type": _get_resource_type(r),
                        "name": _get_resource_name(r),
                        "reason": "No IaC files found",
                    }
                    for r in resources
                ],
                errors=[f"No IaC files found in {iac_dir}"],
            )

        if progress_callback:
            progress_callback(
                "activity", {"message": f"Found {len(generated_code)} IaC files"}
            )

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
            errors=(
                [
                    e.get("message", str(e)) if isinstance(e, dict) else str(e)
                    for e in errors
                ]
                if errors
                else []
            ),
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
    - CDK TypeScript: .ts files (prioritizes lib/ and bin/ directories)
    - CDK Python: .py files (prioritizes stacks/ directory)

    Detects CDK projects by presence of cdk.json and filters appropriately.

    Args:
        iac_dir: Directory to scan

    Returns:
        Dict mapping filename to content
    """
    iac_files: Dict[str, str] = {}
    path = Path(iac_dir)

    # Detect project type
    is_cdk_project = (path / "cdk.json").exists()
    is_typescript_cdk = is_cdk_project and (
        (path / "package.json").exists()
        or (path / "tsconfig.json").exists()
        or (path / "lib").is_dir()
    )
    is_python_cdk = is_cdk_project and (
        (path / "requirements.txt").exists()
        or (path / "setup.py").exists()
        or (path / "stacks").is_dir()
        or (path / "app.py").exists()
    )

    # Determine which extensions to scan based on project type
    if is_typescript_cdk:
        # TypeScript CDK project - scan .ts files only
        iac_extensions = {".ts"}
        # Skip test files and certain directories
        skip_dirs = {"node_modules", "__pycache__", "cdk.out", "test", "tests", ".git"}
        skip_patterns = {"test", "spec", ".d.ts"}
    elif is_python_cdk:
        # Python CDK project - scan .py files only
        iac_extensions = {".py"}
        skip_dirs = {
            "node_modules",
            "__pycache__",
            "cdk.out",
            ".git",
            "test",
            "tests",
            ".venv",
            "venv",
        }
        skip_patterns = {"test_", "_test.py", "conftest.py"}
    else:
        # Terraform or mixed project - scan all IaC file types
        iac_extensions = {".tf", ".ts", ".py"}
        skip_dirs = {"node_modules", "__pycache__", "cdk.out", ".git"}
        skip_patterns = set()

    for file_path in path.rglob("*"):
        if not file_path.is_file() or file_path.suffix not in iac_extensions:
            continue

        # Skip hidden directories and excluded directories
        if any(part.startswith(".") or part in skip_dirs for part in file_path.parts):
            continue

        # Skip test files for CDK projects
        filename = file_path.name.lower()
        if any(pattern in filename for pattern in skip_patterns):
            continue

        # For TypeScript CDK, prioritize lib/ and bin/ directories
        if is_typescript_cdk:
            rel_parts = file_path.relative_to(path).parts
            # Include files in lib/, bin/, or root (e.g., app.ts)
            if len(rel_parts) > 1 and rel_parts[0] not in ("lib", "bin"):
                continue

        # For Python CDK, prioritize stacks/ directory and root files
        if is_python_cdk:
            rel_parts = file_path.relative_to(path).parts
            # Include files in stacks/, or root (e.g., app.py)
            if len(rel_parts) > 1 and rel_parts[0] != "stacks":
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
