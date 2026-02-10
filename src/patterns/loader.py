"""Pattern YAML loading, validation, and persistence."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Optional, Union

import yaml

from .models import Pattern

logger = logging.getLogger(__name__)

VALID_OPERATORS = (">=", "<=", "!=", ">", "<")
_EXPECT_KEY_RE = re.compile(r"^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)*$")

# Guardrail-related keywords in expect keys that suggest overlap
_GUARDRAIL_OVERLAP_KEYWORDS = (
    "encrypt",
    "sse",
    "kms",
    "trac",
    "log",
    "public",
    "acl",
)


def load_pattern(path: Union[str, Path]) -> Pattern:
    """Load a single pattern YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        Parsed Pattern object.

    Raises:
        ValueError: If the YAML is malformed or missing required fields.
    """
    filepath = Path(path)
    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {filepath}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {filepath}, got {type(data).__name__}")

    if "name" not in data:
        raise ValueError(f"Missing required field 'name' in {filepath}")
    if "description" not in data:
        raise ValueError(f"Missing required field 'description' in {filepath}")

    return Pattern.from_dict(data)


def load_library(library_path: Union[str, Path]) -> List[Pattern]:
    """Load all patterns from the library directory.

    Args:
        library_path: Directory containing pattern YAML files.

    Returns:
        List of Pattern objects. Empty list if directory is empty.
    """
    lib_dir = Path(library_path)
    if not lib_dir.is_dir():
        return []

    patterns: List[Pattern] = []
    for filepath in sorted(lib_dir.iterdir()):
        if filepath.suffix not in (".yaml", ".yml"):
            continue
        try:
            patterns.append(load_pattern(filepath))
        except ValueError:
            logger.warning("Skipping invalid pattern file: %s", filepath)
    return patterns


def validate_pattern(pattern: Pattern) -> List[str]:
    """Validate pattern structure.

    Returns:
        List of error/warning strings. Empty list means valid.
        Warning strings contain the word 'warning' or 'guardrail' for overlap warnings.
    """
    issues: List[str] = []

    if not pattern.resources:
        issues.append("Pattern must have at least one resource.")

    for i, resource in enumerate(pattern.resources):
        if ":" not in resource.type:
            issues.append(
                f"Resource {i}: type '{resource.type}' must contain a ':' separator (e.g., 'lambda:function')."
            )

        if resource.count < 1:
            issues.append(f"Resource {i}: count must be >= 1, got {resource.count}.")

        for key, value in resource.expect.items():
            if not _EXPECT_KEY_RE.match(key):
                issues.append(
                    f"Resource {i}: expect key '{key}' is not a valid dotted-path "
                    f"(alphanumeric segments separated by dots)."
                )

            value_str = str(value)
            _validate_expect_value(value_str, i, key, issues)

            if pattern.guardrails and any(kw in key.lower() for kw in _GUARDRAIL_OVERLAP_KEYWORDS):
                issues.append(
                    f"Warning: Resource {i} expect key '{key}' may overlap with a "
                    f"referenced guardrail. Consider using guardrail references instead."
                )

    return issues


def _validate_expect_value(value: str, resource_idx: int, key: str, issues: List[str]) -> None:
    """Validate an expect field value for valid operator syntax."""
    if " " not in value:
        return

    parts = value.split(" ", 1)
    operator = parts[0]

    if operator in VALID_OPERATORS:
        return

    if operator and operator[0] in (">", "<", "!", "="):
        issues.append(
            f"Resource {resource_idx}: expect value '{value}' for key '{key}' "
            f"has invalid operator '{operator}'. Valid operators: {', '.join(VALID_OPERATORS)}."
        )


def save_pattern(pattern: Pattern, library_path: Union[str, Path]) -> str:
    """Save pattern YAML to library.

    Args:
        pattern: The Pattern object to save.
        library_path: Directory to save the file in.

    Returns:
        Path to the saved file.
    """
    lib_dir = Path(library_path)
    lib_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{pattern.name}-v{pattern.version}.yaml"
    filepath = lib_dir / filename

    data = pattern.to_dict()
    with open(filepath, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    return str(filepath)


def list_pattern_versions(name: str, library_path: Union[str, Path]) -> List[int]:
    """List all version numbers of a named pattern.

    Args:
        name: Pattern name to search for.
        library_path: Library directory path.

    Returns:
        Sorted list of version integers.
    """
    lib_dir = Path(library_path)
    if not lib_dir.is_dir():
        return []

    versions: List[int] = []
    pattern = re.compile(rf"^{re.escape(name)}-v(\d+)\.ya?ml$")
    for filepath in lib_dir.iterdir():
        match = pattern.match(filepath.name)
        if match:
            versions.append(int(match.group(1)))

    return sorted(versions)


def delete_pattern(
    name: str,
    library_path: Union[str, Path],
    version: Optional[int] = None,
) -> bool:
    """Delete pattern or specific version.

    Args:
        name: Pattern name.
        library_path: Library directory path.
        version: Specific version to delete. If None, deletes all versions.

    Returns:
        True if at least one file was deleted.
    """
    lib_dir = Path(library_path)
    if not lib_dir.is_dir():
        return False

    if version is not None:
        filepath = lib_dir / f"{name}-v{version}.yaml"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    versions = list_pattern_versions(name, library_path)
    if not versions:
        return False

    for v in versions:
        filepath = lib_dir / f"{name}-v{v}.yaml"
        if filepath.exists():
            filepath.unlink()

    return True


def get_library_path(custom_path: Optional[str] = None) -> str:
    """Resolve library path.

    Precedence: custom_path > AWS_PATTERN_LIBRARY_PATH env var > default .patterns/

    Args:
        custom_path: Optional explicit path override.

    Returns:
        Resolved path string.
    """
    if custom_path:
        return str(Path(custom_path).expanduser().resolve())

    env_path = os.getenv("AWS_PATTERN_LIBRARY_PATH")
    if env_path:
        return env_path

    from ..utils.paths import get_snapshot_storage_path

    storage_root = get_snapshot_storage_path().parent
    return str(storage_root / ".patterns")
