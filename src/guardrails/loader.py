"""Loading guardrail policies and definitions from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

import io

from .models import (
    Action,
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
    result: Dict[str, Any] = {
        "id": guardrail.id,
        "short_description": guardrail.short_description,
        "severity": guardrail.severity.value,
        "action": guardrail.action.value,
        "applies_to": guardrail.applies_to,
        "ai_context": guardrail.ai_context,
        "enabled": guardrail.enabled,
        "tags": guardrail.tags,
        "best_practice": guardrail.best_practice,
    }

    # Add condition or AI rule (mutually exclusive)
    if guardrail.condition:
        result["condition"] = guardrail.condition
    elif guardrail.ai_fail_if:
        result["ai_fail_if"] = guardrail.ai_fail_if
    elif guardrail.ai_warn_if:
        result["ai_warn_if"] = guardrail.ai_warn_if
    elif guardrail.ai_notify_if:
        result["ai_notify_if"] = guardrail.ai_notify_if

    return result


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
    guardrails = [_parse_guardrail(g_dict) for g_dict in policy_dict.get("guardrails", [])]

    # Parse overrides
    overrides: Dict[str, List[PolicyOverride]] = {}
    for env, env_overrides in policy_dict.get("overrides", {}).items():
        if isinstance(env_overrides, list):
            overrides[env] = [_parse_override(o_dict) for o_dict in env_overrides if isinstance(o_dict, dict)]

    # Parse context and context_overrides
    context: Dict[str, Any] = policy_dict.get("context", {})
    context_overrides: Dict[str, Dict[str, Any]] = policy_dict.get("context_overrides", {})

    return GuardrailPolicy(
        name=policy_dict["name"],
        version=str(policy_dict["version"]),
        description=policy_dict.get("description", ""),
        guardrails=guardrails,
        overrides=overrides,
        context=context,
        context_overrides=context_overrides,
    )


def _parse_guardrail(g_dict: Dict[str, Any]) -> Guardrail:
    """Parse a guardrail dictionary into a Guardrail object.

    Args:
        g_dict: Guardrail dictionary from YAML.

    Returns:
        Guardrail object.

    Condition can be:
        - A string formula: "Encryption exists and Tags.Environment == 'prod'"
        - A dict (legacy format): {"attribute": "Encryption", "operator": "exists"}
    """
    # Handle condition - can be string formula or legacy dict
    condition = g_dict.get("condition")
    if isinstance(condition, dict):
        # Convert legacy dict format to formula string
        attr = condition.get("attribute", "")
        op = condition.get("operator", "exists")
        val = condition.get("value")

        if op == "exists":
            condition = f"{attr} exists"
        elif op == "not_exists":
            condition = f"{attr} not exists"
        elif op == "equals":
            condition = f"get('{attr}') == {repr(val)}"
        elif op == "not_equals":
            condition = f"get('{attr}') != {repr(val)}"
        elif op == "contains":
            condition = f"contains(get('{attr}'), {repr(val)})"
        elif op == "matches":
            condition = f"matches(get('{attr}'), {repr(val)})"
        elif op == "in":
            condition = f"get('{attr}') in {repr(val)}"
        elif op == "greater_than":
            condition = f"get('{attr}') > {repr(val)}"
        elif op == "less_than":
            condition = f"get('{attr}') < {repr(val)}"
        else:
            # Default: just use exists
            condition = f"{attr} exists"

    return Guardrail(
        id=g_dict["id"],
        short_description=g_dict["short_description"],
        severity=Severity(g_dict["severity"]),
        action=Action(g_dict["action"]),
        applies_to=g_dict.get("applies_to", []),
        condition=condition if isinstance(condition, str) else None,
        ai_fail_if=g_dict.get("ai_fail_if"),
        ai_warn_if=g_dict.get("ai_warn_if"),
        ai_notify_if=g_dict.get("ai_notify_if"),
        ai_context=g_dict.get("ai_context", ""),
        enabled=g_dict.get("enabled", True),
        tags=g_dict.get("tags", []),
        best_practice=g_dict.get("best_practice", False),
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


def load_best_practice_guardrails() -> List[Guardrail]:
    """Load only built-in guardrails marked as best_practice.

    Returns:
        List of Guardrail objects where best_practice=True.
    """
    return [g for g in load_builtin_guardrails() if g.best_practice]


def export_builtin_policy_yaml(category: Optional[str] = None) -> str:
    """Export built-in guardrails as a standard policy YAML string.

    Args:
        category: Optional category filter (e.g., "encryption", "network").

    Returns:
        YAML string in standard policy format.
    """
    guardrails = load_builtin_guardrails()

    if category:
        cat_upper = category.upper()
        # Match category abbreviation in ID (e.g., GR-ENC-001 -> ENC matches "encryption")
        category_map: Dict[str, str] = {
            "encryption": "ENC",
            "network": "NET",
            "tagging": "TAG",
            "logging": "LOG",
        }
        abbrev = category_map.get(category.lower(), cat_upper)
        guardrails = [g for g in guardrails if f"-{abbrev}-" in g.id]

    policy_dict: Dict[str, Any] = {
        "name": "builtin-best-practices",
        "version": "1.0",
        "description": "Built-in best-practice guardrails exported for customization",
        "guardrails": [_guardrail_to_dict(g) for g in guardrails],
    }

    stream = io.StringIO()
    yaml.dump(policy_dict, stream, default_flow_style=False, sort_keys=False)
    return stream.getvalue()
