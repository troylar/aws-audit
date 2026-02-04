"""Loading guardrail policies and definitions from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import (
    Action,
    Condition,
    Guardrail,
    GuardrailLoadError,
    GuardrailPolicy,
    GuardrailValidationError,
    PolicyOverride,
    Severity,
)
from .validator import validate_policy

# Directory containing built-in guardrail YAML files
BUILTIN_DIR = Path(__file__).parent / "builtin"

# Mapping of builtin categories to files
BUILTIN_CATEGORIES = {
    "encryption": "encryption.yaml",
    "network": "network.yaml",
    "tagging": "tagging.yaml",
    "logging": "logging.yaml",
    "all": None,  # Special case: load all
}


def load_policy(
    policy_path: str,
    environment: str = "default",
) -> GuardrailPolicy:
    """Load a guardrail policy from a YAML file.

    Args:
        policy_path: Path to the policy YAML file.
        environment: Environment name for applying overrides.

    Returns:
        GuardrailPolicy with guardrails and environment overrides applied.

    Raises:
        GuardrailLoadError: If policy file doesn't exist or is invalid YAML.
        GuardrailValidationError: If policy is malformed.
    """
    path = Path(policy_path)
    if not path.exists():
        raise GuardrailLoadError(f"Policy file not found: {policy_path}")

    try:
        with open(path, "r") as f:
            policy_dict = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise GuardrailLoadError(f"Invalid YAML in policy file: {e}")

    if not policy_dict:
        raise GuardrailLoadError(f"Empty policy file: {policy_path}")

    # Process include directives
    if "include" in policy_dict:
        included_guardrails = _process_includes(policy_dict.get("include", []))
        existing_guardrails = policy_dict.get("guardrails", [])
        policy_dict["guardrails"] = included_guardrails + existing_guardrails

    # Validate the policy
    errors = validate_policy(policy_dict)
    if errors:
        raise GuardrailValidationError(errors)

    # Parse the policy
    return _parse_policy(policy_dict)


def _process_includes(includes: List[str]) -> List[Dict[str, Any]]:
    """Process include directives and return guardrail definitions.

    Args:
        includes: List of include directives (e.g., "builtin:encryption").

    Returns:
        List of guardrail dictionaries from included sources.
    """
    guardrails: List[Dict[str, Any]] = []

    for include in includes:
        if include.startswith("builtin:"):
            category = include.split(":", 1)[1]
            if category == "all":
                # Load all built-in guardrails
                builtin_guardrails = load_builtin_guardrails()
                for g in builtin_guardrails:
                    guardrails.append(_guardrail_to_dict(g))
            elif category in BUILTIN_CATEGORIES:
                filename = BUILTIN_CATEGORIES[category]
                if filename:
                    file_path = BUILTIN_DIR / filename
                    if file_path.exists():
                        with open(file_path, "r") as f:
                            data = yaml.safe_load(f)
                            if data and "guardrails" in data:
                                guardrails.extend(data["guardrails"])

    return guardrails


def _guardrail_to_dict(guardrail: Guardrail) -> Dict[str, Any]:
    """Convert a Guardrail object back to a dictionary."""
    return {
        "id": guardrail.id,
        "short_description": guardrail.short_description,
        "severity": guardrail.severity.value,
        "action": guardrail.action.value,
        "applies_to": guardrail.applies_to,
        "condition": {
            "attribute": guardrail.condition.attribute,
            "operator": guardrail.condition.operator,
            "value": guardrail.condition.value,
            "type": guardrail.condition.type,
        },
        "ai_context": guardrail.ai_context,
        "enabled": guardrail.enabled,
        "tags": guardrail.tags,
    }


def load_builtin_guardrails() -> List[Guardrail]:
    """Load all built-in guardrail definitions.

    Returns:
        List of Guardrail objects from builtin/*.yaml files.
    """
    guardrails: List[Guardrail] = []

    for category, filename in BUILTIN_CATEGORIES.items():
        if category == "all" or filename is None:
            continue

        file_path = BUILTIN_DIR / filename
        if file_path.exists():
            with open(file_path, "r") as f:
                data = yaml.safe_load(f)
                if data and "guardrails" in data:
                    for g_dict in data["guardrails"]:
                        guardrails.append(_parse_guardrail(g_dict))

    return guardrails


def _parse_policy(policy_dict: Dict[str, Any]) -> GuardrailPolicy:
    """Parse a policy dictionary into a GuardrailPolicy object.

    Args:
        policy_dict: Validated policy dictionary.

    Returns:
        GuardrailPolicy object.
    """
    # Parse guardrails
    guardrails = [
        _parse_guardrail(g_dict)
        for g_dict in policy_dict.get("guardrails", [])
    ]

    # Parse overrides
    overrides: Dict[str, List[PolicyOverride]] = {}
    for env, env_overrides in policy_dict.get("overrides", {}).items():
        if isinstance(env_overrides, list):
            overrides[env] = [
                _parse_override(o_dict)
                for o_dict in env_overrides
                if isinstance(o_dict, dict)
            ]

    return GuardrailPolicy(
        name=policy_dict["name"],
        version=str(policy_dict["version"]),
        description=policy_dict.get("description", ""),
        guardrails=guardrails,
        overrides=overrides,
    )


def _parse_guardrail(g_dict: Dict[str, Any]) -> Guardrail:
    """Parse a guardrail dictionary into a Guardrail object.

    Args:
        g_dict: Guardrail dictionary from YAML.

    Returns:
        Guardrail object.
    """
    condition_dict = g_dict.get("condition", {})
    condition = Condition(
        attribute=condition_dict.get("attribute", ""),
        operator=condition_dict.get("operator", "exists"),
        value=condition_dict.get("value"),
        type=condition_dict.get("type", "attribute_check"),
    )

    return Guardrail(
        id=g_dict["id"],
        short_description=g_dict["short_description"],
        severity=Severity(g_dict["severity"]),
        action=Action(g_dict["action"]),
        applies_to=g_dict.get("applies_to", []),
        condition=condition,
        ai_context=g_dict.get("ai_context", ""),
        enabled=g_dict.get("enabled", True),
        tags=g_dict.get("tags", []),
    )


def _parse_override(o_dict: Dict[str, Any]) -> PolicyOverride:
    """Parse an override dictionary into a PolicyOverride object.

    Args:
        o_dict: Override dictionary from YAML.

    Returns:
        PolicyOverride object.
    """
    severity = None
    if "severity" in o_dict:
        severity = Severity(o_dict["severity"])

    action = None
    if "action" in o_dict:
        action = Action(o_dict["action"])

    return PolicyOverride(
        guardrail_id=o_dict["guardrail_id"],
        severity=severity,
        action=action,
        enabled=o_dict.get("enabled"),
    )
