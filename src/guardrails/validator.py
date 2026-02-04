"""Validation for guardrail and policy definitions."""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Valid operators for conditions
VALID_OPERATORS = [
    "equals",
    "not_equals",
    "exists",
    "not_exists",
    "contains",
    "not_contains",
    "matches",
    "in",
    "not_in",
    "greater_than",
    "less_than",
]

# Valid severity levels
VALID_SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

# Valid actions
VALID_ACTIONS = ["BLOCK", "AUTO-FIX", "WARN"]

# Guardrail ID pattern: PREFIX-CATEGORY-NUMBER (e.g., GR-ENC-001, ACME-SEC-001)
ID_PATTERN = re.compile(r"^[A-Z]+-[A-Z]+-\d{3}$")


def validate_guardrail(guardrail_dict: Dict[str, Any]) -> List[str]:
    """Validate a guardrail definition dictionary.

    Args:
        guardrail_dict: Raw dictionary from YAML.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors: List[str] = []

    # Required field: id
    if "id" not in guardrail_dict:
        errors.append("id is required")
    else:
        guardrail_id = guardrail_dict["id"]
        if not ID_PATTERN.match(guardrail_id):
            errors.append(
                f"id '{guardrail_id}' must match pattern PREFIX-CATEGORY-NUMBER (e.g., GR-ENC-001)"
            )

    # Required field: short_description
    if "short_description" not in guardrail_dict:
        errors.append("short_description is required")
    else:
        desc = guardrail_dict["short_description"]
        if len(desc) > 100:
            errors.append(f"short_description length ({len(desc)}) exceeds maximum 100 characters")

    # Required field: severity
    if "severity" not in guardrail_dict:
        errors.append("severity is required")
    else:
        severity = guardrail_dict["severity"]
        if severity not in VALID_SEVERITIES:
            errors.append(
                f"severity '{severity}' is invalid. Must be one of: {', '.join(VALID_SEVERITIES)}"
            )

    # Required field: action
    if "action" not in guardrail_dict:
        errors.append("action is required")
    else:
        action = guardrail_dict["action"]
        if action not in VALID_ACTIONS:
            errors.append(
                f"action '{action}' is invalid. Must be one of: {', '.join(VALID_ACTIONS)}"
            )

    # Required field: applies_to
    if "applies_to" not in guardrail_dict:
        errors.append("applies_to is required")
    else:
        applies_to = guardrail_dict["applies_to"]
        if not applies_to or not isinstance(applies_to, list) or len(applies_to) == 0:
            errors.append("applies_to must be a non-empty list of resource type patterns")

    # Required field: condition
    if "condition" not in guardrail_dict:
        errors.append("condition is required")
    else:
        condition_errors = _validate_condition(guardrail_dict["condition"])
        errors.extend(condition_errors)

    # Warning: AUTO-FIX without ai_context
    if guardrail_dict.get("action") == "AUTO-FIX" and not guardrail_dict.get("ai_context"):
        errors.append("ai_context is recommended for AUTO-FIX guardrails to enable AI remediation")

    return errors


def _validate_condition(condition_dict: Dict[str, Any]) -> List[str]:
    """Validate a condition definition.

    Args:
        condition_dict: Condition dictionary from YAML.

    Returns:
        List of validation error messages.
    """
    errors: List[str] = []

    if not isinstance(condition_dict, dict):
        return ["condition must be a dictionary"]

    # Required: attribute
    if "attribute" not in condition_dict:
        errors.append("condition.attribute is required")

    # Required: operator
    if "operator" not in condition_dict:
        errors.append("condition.operator is required")
    else:
        operator = condition_dict["operator"]
        if operator not in VALID_OPERATORS:
            errors.append(
                f"condition.operator '{operator}' is invalid. "
                f"Must be one of: {', '.join(VALID_OPERATORS)}"
            )

    return errors


def validate_policy(policy_dict: Dict[str, Any]) -> List[str]:
    """Validate a complete policy definition.

    Args:
        policy_dict: Raw dictionary from YAML.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors: List[str] = []

    # Required field: name
    if "name" not in policy_dict:
        errors.append("name is required")

    # Required field: version
    if "version" not in policy_dict:
        errors.append("version is required")

    # Validate guardrails
    guardrails = policy_dict.get("guardrails", [])
    if guardrails:
        seen_ids: set[str] = set()
        for i, guardrail in enumerate(guardrails):
            guardrail_errors = validate_guardrail(guardrail)
            for error in guardrail_errors:
                errors.append(f"guardrails[{i}]: {error}")

            # Check for duplicates
            guardrail_id = guardrail.get("id")
            if guardrail_id:
                if guardrail_id in seen_ids:
                    errors.append(f"guardrails[{i}]: duplicate guardrail id '{guardrail_id}'")
                seen_ids.add(guardrail_id)

        # Validate overrides reference valid guardrail IDs
        overrides = policy_dict.get("overrides", {})
        for env, env_overrides in overrides.items():
            if not isinstance(env_overrides, list):
                continue
            for override in env_overrides:
                if not isinstance(override, dict):
                    continue
                override_id = override.get("guardrail_id")
                if override_id and override_id not in seen_ids:
                    errors.append(
                        f"overrides.{env}: guardrail_id '{override_id}' not found in guardrails"
                    )

    return errors
